#!/usr/bin/env bash
# Restaure des Secrets depuis la sauvegarde chiffrée (gitops/manifests/secrets-backup).
#
#   scripts/secrets-restore.sh <namespace>/<nom> [...]   un ou plusieurs Secrets
#   scripts/secrets-restore.sh --list                    contenu du dernier snapshot
#   (SNAPSHOT=<id> pour un autre snapshot que le dernier ; KUBECTL="sudo k3s kubectl"
#   sur le serveur lui-même)
#
# Un pod jetable restaure le snapshot en mémoire, n'en garde que les Secrets
# demandés (sans les champs propres à leur ancienne existence : uid, version,
# annotations de suivi…) et les écrit sur sa sortie, envoyée directement à
# `kubectl apply`. Les valeurs ne sont jamais affichées ni écrites sur disque.
# Un Secret existant est remplacé par sa version sauvegardée.
#
# Suppose le dépôt de sauvegarde et son mot de passe encore dans le cluster
# (Secret erroné ou supprimé par erreur). Après la perte du disque, voir
# manuel-admin.md, « Sauvegarde des secrets ».
set -euo pipefail
read -r -a K <<<"${KUBECTL:-kubectl}"
NS=myown-backup
POD="secrets-restore-$$"
SNAPSHOT="${SNAPSHOT:-latest}"

[ $# -ge 1 ] || { sed -n '2,8p' "$0"; exit 1; }
if [ "$1" = "--list" ]; then WANT=""; else WANT="$*"; fi
for w in $WANT; do
  [[ "$w" =~ ^[a-z0-9-]+/[a-z0-9-]+$ ]] || { echo "nom invalide : $w (attendu : namespace/nom)" >&2; exit 1; }
done

cleanup() { "${K[@]}" delete pod "$POD" -n "$NS" --wait=false >/dev/null 2>&1 || true; }
trap cleanup EXIT

"${K[@]}" apply -f - >/dev/null <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: $POD
  namespace: $NS
spec:
  restartPolicy: Never
  initContainers:
    - name: restore
      image: restic/restic:0.19.1
      env:
        - {name: RESTIC_REPOSITORY, value: /repo}
        - name: RESTIC_PASSWORD
          valueFrom: {secretKeyRef: {name: secrets-backup, key: RESTIC_PASSWORD}}
      command: ["restic", "restore", "$SNAPSHOT", "--target", "/restored"]
      volumeMounts:
        - {name: repo, mountPath: /repo}
        - {name: restored, mountPath: /restored}
  containers:
    - name: emit
      image: python:3.13-alpine
      env:
        - {name: WANT, value: "$WANT"}
      command:
        - python3
        - -c
        - |
          import glob, json, os, sys
          want = set(os.environ["WANT"].split())
          found = {}
          for p in sorted(glob.glob("/restored/export/*.json")):
              s = json.load(open(p)); md = s["metadata"]; key = md["namespace"] + "/" + md["name"]
              if not want:
                  print(key, len(s.get("data") or {}), "clé(s)", file=sys.stderr); continue
              if key not in want: continue
              keep = {k: md[k] for k in ("name", "namespace") if k in md}
              if md.get("labels"): keep["labels"] = md["labels"]
              found[key] = {"apiVersion": "v1", "kind": "Secret", "type": s.get("type", "Opaque"),
                            "metadata": keep, "data": s.get("data") or {}}
          missing = want - set(found)
          if missing:
              print("absent(s) du snapshot : " + ", ".join(sorted(missing)), file=sys.stderr); sys.exit(1)
          if found:
              print(json.dumps({"apiVersion": "v1", "kind": "List", "items": list(found.values())}))
      volumeMounts:
        - {name: restored, mountPath: /restored}
  volumes:
    - name: repo
      persistentVolumeClaim: {claimName: secrets-restic-repo}
    - name: restored
      emptyDir: {medium: Memory, sizeLimit: 16Mi}
EOF

for _ in $(seq 1 60); do
  phase="$("${K[@]}" get pod "$POD" -n "$NS" -o jsonpath='{.status.phase}')"
  [ "$phase" = Succeeded ] || [ "$phase" = Failed ] && break
  sleep 2
done
if [ "$phase" != Succeeded ]; then
  echo "échec de la restauration (pod : ${phase:-inconnu})" >&2
  "${K[@]}" logs "$POD" -n "$NS" -c restore 2>&1 | tail -5 >&2 || true
  "${K[@]}" logs "$POD" -n "$NS" -c emit 2>&1 | grep -v '^{' >&2 || true
  exit 1
fi

if [ -z "$WANT" ]; then
  # --list : les noms sont sur la sortie d'erreur du pod, rien d'autre n'est émis.
  "${K[@]}" logs "$POD" -n "$NS" -c emit
else
  "${K[@]}" logs "$POD" -n "$NS" -c emit | "${K[@]}" apply -f -
fi
