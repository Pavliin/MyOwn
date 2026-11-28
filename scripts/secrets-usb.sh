#!/usr/bin/env bash
# Copie hors machine de la sauvegarde des secrets (gitops/manifests/secrets-backup)
# sur une clé USB, et vérification de cette copie. À lancer sur le serveur, en root,
# la clé branchée et montée :
#
#   sudo scripts/secrets-usb.sh copier   <point de montage de la clé>
#   sudo scripts/secrets-usb.sh verifier <point de montage de la clé>
#
# copier   : sauvegarde immédiate, copie du dépôt Restic chiffré tel quel sur la clé
#            (dossier myown-secrets-backup/), puis `verifier`.
# verifier : restic check de la copie, restauration du dernier snapshot de la CLÉ en
#            mémoire (tmpfs), comparaison Secret par Secret avec le cluster, effacement.
#            Rien n'est affiché que des noms et des comptes.
#
# Le mot de passe du dépôt n'est jamais lu dans le cluster ni écrit sur la clé : restic
# le demande, à taper depuis le coffre ou le papier — la vérification prouve donc aussi
# que la copie hors serveur du mot de passe est la bonne. Refaire `copier` après chaque
# changement de secrets (nouveau service, rotation, remise des clés).
set -euo pipefail

RESTIC_VERSION=0.20.0
RESTIC_SHA256=0ccd9fa7885074a24603b051e01bf9bd8b5e45d6a1791e9d9887e9e9372107f7
RESTIC_URL="https://github.com/restic/restic/releases/download/v${RESTIC_VERSION}/restic_${RESTIC_VERSION}_linux_amd64.bz2"
NS=myown-backup
PVC=secrets-restic-repo
CRONJOB=secrets-restic-backup
DIRNAME=myown-secrets-backup

if [ -n "${KUBECTL:-}" ]; then read -r -a K <<<"$KUBECTL"
elif command -v k3s >/dev/null; then K=(k3s kubectl)
else K=(kubectl); fi

die() { echo "ARRÊT : $*" >&2; exit 1; }
say() { echo "$*"; }

[ $# -eq 2 ] || { sed -n '2,17p' "$0"; exit 1; }
MODE="$1"; MNT="${2%/}"; MNT="${MNT:-/}"
[ "$MODE" = copier ] || [ "$MODE" = verifier ] || die "mode inconnu : $MODE (copier ou verifier)"
[ "$(id -u)" -eq 0 ] || die "à lancer en root (sudo) : le dépôt est lisible par root seulement"
command -v python3 >/dev/null || die "python3 introuvable"

# --- La clé : un vrai point de montage, sur un autre périphérique que le cluster ---
findmnt -n --mountpoint "$MNT" >/dev/null || die "$MNT n'est pas un point de montage (clé non montée ?)"
REPO_PV="$("${K[@]}" get pvc "$PVC" -n "$NS" -o jsonpath='{.spec.volumeName}')"
[ -n "$REPO_PV" ] || die "PVC $NS/$PVC introuvable"
SRC="$("${K[@]}" get pv "$REPO_PV" -o jsonpath='{.spec.hostPath.path}{.spec.local.path}')"
[ -f "$SRC/config" ] || die "dépôt Restic introuvable sur le serveur ($SRC)"
SRC_DEV="$(findmnt -n -o SOURCE --target "$SRC")"
MNT_DEV="$(findmnt -n -o SOURCE --mountpoint "$MNT")"
[ "$SRC_DEV" != "$MNT_DEV" ] || die "$MNT est sur le même disque que le cluster ($SRC_DEV) : ce ne serait pas une copie hors machine"
DEST="$MNT/$DIRNAME"

# --- restic épinglé, empreinte vérifiée (le serveur n'en a pas besoin autrement) ---
restic_bin() {
  local dir=/root/.local/share/myown/restic-$RESTIC_VERSION bin
  bin="$dir/restic"
  if [ ! -x "$bin" ]; then
    say "Téléchargement de restic $RESTIC_VERSION (binaire officiel)..." >&2
    mkdir -p "$dir"
    curl -fsSL "$RESTIC_URL" -o "$dir/restic.bz2"
    echo "$RESTIC_SHA256  $dir/restic.bz2" | sha256sum -c --quiet - || { rm -f "$dir/restic.bz2"; die "empreinte de restic inattendue : téléchargement refusé"; }
    python3 -c 'import bz2,sys; open(sys.argv[2],"wb").write(bz2.open(sys.argv[1]).read())' "$dir/restic.bz2" "$bin"
    rm -f "$dir/restic.bz2"; chmod 755 "$bin"
  fi
  echo "$bin"
}

backup_now() {
  local job="${CRONJOB:0:40}-usb-$(date +%s)"
  say "Sauvegarde immédiate des secrets..."
  "${K[@]}" create job "$job" -n "$NS" --from="cronjob/$CRONJOB" >/dev/null
  "${K[@]}" wait -n "$NS" "job/$job" --for=condition=complete --timeout=600s >/dev/null \
    || die "sauvegarde non terminée : ${K[*]} logs -n $NS job/$job"
  say "  sauvegarde faite"
}

copier() {
  backup_now
  say "Copie du dépôt chiffré vers $DEST ..."
  mkdir -p "$DEST"
  # -rt seulement : une clé en FAT/exFAT ne garde ni propriétaire ni droits. --delete :
  # la copie reflète le dépôt (restic forget/prune y retire des fichiers).
  rsync -rt --delete --modify-window=2 "$SRC/" "$DEST/repo/"
  cat >"$DEST/LISEZMOI.txt" <<EOF
Copie hors machine de la sauvegarde des secrets MyOwn (dépôt Restic chiffré).
Copiée le $(date '+%Y-%m-%d %H:%M') depuis le serveur $(hostname).

Le mot de passe N'EST PAS sur cette clé : il est dans le coffre de l'admin et sur papier.
Sans lui, cette copie est illisible ; sans cette copie (ou le serveur), les secrets des
services sont perdus, et avec eux toutes les autres sauvegardes.

Lister :    restic -r <cette clé>/$DIRNAME/repo snapshots
Restaurer : restic -r <cette clé>/$DIRNAME/repo restore latest --target <dossier en mémoire>
            (les Secrets sont dans export/*.json, au format Kubernetes)
Procédure complète : docs/manuel-admin.md, « Sauvegarde des secrets ».
EOF
  sync
  say "  copie faite ($(du -sh "$DEST/repo" | cut -f1))"
}

verifier() {
  local restic
  [ -f "$DEST/repo/config" ] || die "pas de copie sur la clé ($DEST/repo) : lancer d'abord « copier »"
  restic="$(restic_bin)"
  TMP="$(mktemp -d /dev/shm/myown-usb-XXXXXX)"
  trap 'rm -rf "$TMP"' EXIT
  say "Vérification de la copie sur la clé."
  say "Mot de passe de la sauvegarde des secrets, à recopier depuis le coffre ou le papier :"
  # Un seul mot de passe tapé pour les deux commandes : lu une fois, passé par une
  # variable d'environnement de ce processus seulement, jamais affiché.
  local pw
  IFS= read -r -s -p "  mot de passe (rien ne s'affiche) : " pw; echo
  export RESTIC_PASSWORD="$pw"; unset pw
  local rc=0
  "$restic" -r "$DEST/repo" --no-cache --quiet check || rc=$?
  # restic sort en 12 sur un mot de passe refusé (≥ 0.17), autre chose sinon.
  [ "$rc" -ne 12 ] || die "mot de passe refusé par le dépôt de la clé (faute de frappe, ou copie du mot de passe périmée ?)"
  [ "$rc" -eq 0 ] || die "restic check a échoué sur la copie (code $rc) : copie abîmée ?"
  say "  dépôt sur la clé : intègre, mot de passe accepté"
  "$restic" -r "$DEST/repo" --no-cache --quiet restore latest --target "$TMP" \
    || die "restauration depuis la clé impossible"
  unset RESTIC_PASSWORD
  say "  dernier snapshot de la clé restauré en mémoire"
  # Comparaison Secret par Secret avec le cluster, sans jamais afficher une valeur.
  "${K[@]}" get secrets -A -o json | python3 -c '
import glob, json, sys
live = {s["metadata"]["namespace"] + "/" + s["metadata"]["name"]: s.get("data") or {}
        for s in json.load(sys.stdin)["items"]}
same, diff, gone = [], [], []
# Le CronJob sauvegarde /export : restauré sous <cible>/export.
for p in sorted(glob.glob(sys.argv[1] + "/export/*.json")):
    s = json.load(open(p)); md = s["metadata"]; key = md["namespace"] + "/" + md["name"]
    if key not in live: gone.append(key)
    elif (s.get("data") or {}) == live[key]: same.append(key)
    else: diff.append(key)
total = len(same) + len(diff) + len(gone)
if total == 0:
    sys.exit("  aucun Secret dans le snapshot restauré")
print(f"  {len(same)}/{total} Secrets identiques au cluster")
for k in diff: print(f"  DIFFÉRENT du cluster : {k}")
for k in gone: print(f"  absent du cluster : {k}")
sys.exit(1 if diff or gone else 0)
' "$TMP" || die "la copie sur la clé ne correspond pas au cluster : relancer « copier »"
  say "  copie sur la clé vérifiée"
}

"$MODE"
[ "$MODE" = copier ] && verifier
say "Terminé. Démonter la clé avant de la retirer : umount $MNT"
