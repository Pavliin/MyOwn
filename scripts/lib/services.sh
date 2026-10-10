# shellcheck shell=bash
# Catalogue des services MyOwn et logique de sélection — sourcé par
# scripts/install.sh, pas exécutable seul.
#
# Un « service » (ce que choisit la personne qui installe) regroupe une ou
# plusieurs Applications ArgoCD (un fichier gitops/apps/<app>.yaml chacune) :
# les synchros de certificats suivent leur service, jamais choisies à part.
#
# Où vit l'état installé : nulle part ailleurs que dans le cluster lui-même.
# L'Application `root` ne déploie que les fichiers listés dans
# `spec.source.directory.include` — l'installeur écrit cette liste, et la
# relit à chaque relance pour savoir ce qui est déjà en place. Pas de fichier
# d'état à part qui pourrait diverger du cluster.
#
# Socle (non désactivable) : Authentik (seule source d'identité) et
# Vaultwarden (reçoit les secrets générés à l'installation — modèle admin de
# docs/installation-utilisateur.md). Décidé avec l'utilisateur le 2026-10-10.

MYOWN_SERVICES_ORDER=(authentik vaultwarden tuwunel uptime-kuma nextcloud immich jellyfin livekit mailu ollama monitoring)

declare -A SVC_LABEL=(
  [authentik]="Authentik — identité et connexion unique (SSO)"
  [vaultwarden]="Vaultwarden — mots de passe"
  [tuwunel]="Tuwunel — messagerie Matrix (+ alertes et annonces)"
  [uptime-kuma]="Uptime Kuma — page d'état des services"
  [nextcloud]="Nextcloud — fichiers, agenda, contacts"
  [immich]="Immich — photos et vidéos"
  [jellyfin]="Jellyfin — films et séries (requiert Nextcloud)"
  [livekit]="LiveKit — appels audio/vidéo (requiert Tuwunel)"
  [mailu]="Mailu — mail (requiert un vrai domaine + relais)"
  [ollama]="Ollama — IA locale"
  [monitoring]="Prometheus/Grafana — supervision admin"
)

declare -A SVC_APPS=(
  [authentik]="authentik"
  [vaultwarden]="vaultwarden"
  [tuwunel]="tuwunel"
  [uptime-kuma]="uptime-kuma"
  [nextcloud]="nextcloud"
  [immich]="immich"
  [jellyfin]="jellyfin"
  [livekit]="livekit livekit-turn-cert-sync"
  [mailu]="mailu mailu-cert-sync"
  [ollama]="ollama"
  [monitoring]="monitoring"
)

declare -A SVC_DEPS=(
  [jellyfin]="nextcloud"
  [livekit]="tuwunel"
)

MYOWN_CORE_SERVICES=(authentik vaultwarden)

# Proposés cochés sur une installation neuve (relance : l'état réel prime).
MYOWN_DEFAULT_SERVICES=(tuwunel uptime-kuma)

# Applications d'infrastructure, jamais proposées dans la liste : liées au
# domaine réel, pas un service que la famille utilise. gandi-dyndns réécrit
# les enregistrements DNS publics vers l'IP de la machine — ne doit JAMAIS
# tourner sur une machine de test (détournerait le vrai domaine).
MYOWN_DOMAIN_APPS=(gandi-dyndns)

svc_is_core() {
  local s
  for s in "${MYOWN_CORE_SERVICES[@]}"; do [ "$s" = "$1" ] && return 0; done
  return 1
}

# Échoue bruyamment si un fichier de gitops/apps/ n'est rattaché à aucun
# service : sinon un nouveau service ajouté au dépôt serait silencieusement
# jamais déployé par l'installeur.
svc_check_catalog() {
  local apps_dir="$1" f app known s a
  for f in "$apps_dir"/*.yaml; do
    app="$(basename "$f" .yaml)"
    known=0
    for s in "${MYOWN_SERVICES_ORDER[@]}"; do
      for a in ${SVC_APPS[$s]}; do [ "$a" = "$app" ] && known=1; done
    done
    for a in "${MYOWN_DOMAIN_APPS[@]}"; do [ "$a" = "$app" ] && known=1; done
    if [ "$known" = 0 ]; then
      echo "ERREUR : gitops/apps/$app.yaml n'est rattaché à aucun service dans scripts/lib/services.sh" >&2
      return 1
    fi
  done
}

# Services actuellement installés, déduits des Applications présentes dans le
# cluster (pas du filtre de root : une installation antérieure à ce mécanisme
# n'a pas de filtre, tout y est déployé). Un service compte comme installé si
# son Application principale (la première de SVC_APPS) existe.
svc_installed() {
  local apps s main
  apps="$(kubectl get applications -n argocd -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null || true)"
  for s in "${MYOWN_SERVICES_ORDER[@]}"; do
    main="${SVC_APPS[$s]%% *}"
    grep -qx "$main" <<<"$apps" && echo "$s"
  done
  return 0
}

svc_domain_apps_installed() {
  local apps a
  apps="$(kubectl get applications -n argocd -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null || true)"
  for a in "${MYOWN_DOMAIN_APPS[@]}"; do
    grep -qx "$a" <<<"$apps" && echo "$a"
  done
  return 0
}

# Complète une sélection : ajoute le socle et les dépendances manquantes,
# en le signalant. Entrée/sortie : une liste de services, un par ligne.
svc_resolve() {
  local -A want=()
  local s d changed=1
  while read -r s; do [ -n "$s" ] && want[$s]=1; done
  for s in "${MYOWN_CORE_SERVICES[@]}"; do want[$s]=1; done
  while [ "$changed" = 1 ]; do
    changed=0
    for s in "${!want[@]}"; do
      for d in ${SVC_DEPS[$s]:-}; do
        if [ -z "${want[$d]:-}" ]; then
          echo "  -> $d ajouté : requis par $s" >&2
          want[$d]=1; changed=1
        fi
      done
    done
  done
  for s in "${MYOWN_SERVICES_ORDER[@]}"; do [ -n "${want[$s]:-}" ] && echo "$s"; done
  return 0
}

# Demande la sélection. $1 : services cochés au départ (un par ligne).
# MYOWN_SERVICES (liste séparée par des virgules, « all » ou « none » = socle
# seul) court-circuite
# la question — pour un usage non interactif ou un test.
svc_prompt() {
  local current="$1" s state args=() out
  if [ -n "${MYOWN_SERVICES:-}" ]; then
    if [ "$MYOWN_SERVICES" = "all" ]; then
      printf '%s\n' "${MYOWN_SERVICES_ORDER[@]}"
    elif [ "$MYOWN_SERVICES" = "none" ]; then
      return 0
    else
      while read -r s; do
        [ -z "$s" ] && continue
        [ -n "${SVC_APPS[$s]:-}" ] || { echo "Service inconnu : $s" >&2; return 1; }
        echo "$s"
      done < <(tr ',' '\n' <<<"$MYOWN_SERVICES")
    fi
    return
  fi
  if [ ! -t 0 ] || ! command -v whiptail >/dev/null; then
    echo "Pas de terminal interactif (ou whiptail absent) : sélection inchangée." >&2
    echo "$current"
    return
  fi
  for s in "${MYOWN_SERVICES_ORDER[@]}"; do
    svc_is_core "$s" && continue
    state=OFF
    grep -qx "$s" <<<"$current" && state=ON
    args+=("$s" "${SVC_LABEL[$s]}" "$state")
  done
  out="$(whiptail --title "MyOwn — services à installer" --separate-output --checklist \
    "Toujours installés (socle) : Authentik, Vaultwarden.\n\nEspace pour cocher/décocher, Entrée pour valider. Décocher un service déjà installé l'arrête mais conserve ses données." \
    22 78 11 "${args[@]}" 3>&1 1>&2 2>&3)" || { echo "Annulé." >&2; exit 1; }
  echo "$out"
}

# Déclenche une synchro de `root` (manuelle par conception, cf.
# gitops/bootstrap/root-app.yaml) sans dépendre de la CLI argocd : écrire le
# champ `operation` est exactement ce que fait `argocd app sync`.
svc_sync_root() {
  local phase op i
  kubectl patch application root -n argocd --type merge \
    -p '{"operation":{"initiatedBy":{"username":"myown-install"},"sync":{"prune":true}}}' >/dev/null
  for i in $(seq 1 120); do
    op="$(kubectl get application root -n argocd -o jsonpath='{.operation}')"
    phase="$(kubectl get application root -n argocd -o jsonpath='{.status.operationState.phase}')"
    if [ -z "$op" ] && [ "$phase" != "Running" ] && [ -n "$phase" ]; then
      echo "Synchro de root : $phase"
      [ "$phase" = "Succeeded" ] && return 0
      kubectl get application root -n argocd -o jsonpath='{.status.operationState.message}{"\n"}'
      return 1
    fi
    sleep 2
  done
  echo "Synchro de root toujours en cours après 4 min — vérifier avec : kubectl get application root -n argocd" >&2
  return 1
}

# Retire une Application en supprimant ses ressources MAIS en conservant ses
# données : les PVC/PV qu'elle gère reçoivent `Delete=false` (ArgoCD ne les
# supprime alors jamais), puis le finalizer de suppression en cascade est
# ajouté — sans lui (cas de toutes les Applications de ce dépôt), supprimer
# l'Application laisserait ses pods tourner, orphelins. Les dossiers hostPath
# (Nextcloud, médiathèque Immich) ne sont jamais touchés par Kubernetes.
svc_remove_app() {
  local app="$1" ns name cur
  kubectl get application "$app" -n argocd >/dev/null 2>&1 || return 0
  while read -r ns name; do
    [ -z "$name" ] && continue
    cur="$(kubectl get pvc "$name" -n "$ns" -o jsonpath='{.metadata.annotations.argocd\.argoproj\.io/sync-options}' 2>/dev/null || true)"
    [[ "$cur" == *Delete=false* ]] || kubectl annotate pvc "$name" -n "$ns" --overwrite \
      "argocd.argoproj.io/sync-options=${cur:+$cur,}Delete=false" >/dev/null
    echo "  données conservées : PVC $ns/$name"
  done < <(kubectl get application "$app" -n argocd \
    -o jsonpath='{range .status.resources[?(@.kind=="PersistentVolumeClaim")]}{.namespace}{" "}{.name}{"\n"}{end}')
  while read -r name; do
    [ -z "$name" ] && continue
    cur="$(kubectl get pv "$name" -o jsonpath='{.metadata.annotations.argocd\.argoproj\.io/sync-options}' 2>/dev/null || true)"
    [[ "$cur" == *Delete=false* ]] || kubectl annotate pv "$name" --overwrite \
      "argocd.argoproj.io/sync-options=${cur:+$cur,}Delete=false" >/dev/null
    echo "  données conservées : PV $name"
  done < <(kubectl get application "$app" -n argocd \
    -o jsonpath='{range .status.resources[?(@.kind=="PersistentVolume")]}{.name}{"\n"}{end}')
  kubectl patch application "$app" -n argocd --type merge \
    -p '{"metadata":{"finalizers":["resources-finalizer.argocd.argoproj.io"]}}' >/dev/null
  kubectl delete application "$app" -n argocd --wait --timeout=300s >/dev/null
  echo "  $app arrêté"
}

# Applique une sélection au cluster. $1 : services voulus (résolus, un par
# ligne). $2 : applications de domaine voulues (un par ligne, peut être vide).
svc_apply() {
  local wanted="$1" domain_apps="$2" installed removed="" s a apps="" include
  installed="$(svc_installed)"
  for s in $installed; do grep -qx "$s" <<<"$wanted" || removed="$removed $s"; done
  for s in $wanted; do apps="$apps ${SVC_APPS[$s]}"; done
  for a in $domain_apps; do apps="$apps $a"; done

  echo "Services installés après cette étape :"
  for s in $wanted; do echo "  + ${SVC_LABEL[$s]}"; done
  if [ -n "$removed" ]; then
    echo "Services qui seront ARRÊTÉS (données conservées, réactivables plus tard) :"
    for s in $removed; do echo "  - ${SVC_LABEL[$s]}"; done
    if [ "${MYOWN_ASSUME_YES:-0}" != "1" ]; then
      [ -t 0 ] || { echo "Arrêt de services en mode non interactif : relancer avec MYOWN_ASSUME_YES=1" >&2; return 1; }
      read -r -p "Confirmer ? [o/N] " ans
      [[ "$ans" =~ ^[oOyY]$ ]] || { echo "Annulé, rien n'a été modifié."; return 1; }
    fi
  fi

  # Glob ArgoCD : {a.yaml,b.yaml,...}
  include="{$(for a in $apps; do printf '%s.yaml,' "$a"; done | sed 's/,$//')}"
  kubectl patch application root -n argocd --type merge \
    -p "{\"spec\":{\"source\":{\"directory\":{\"include\":\"$include\"}}}}" >/dev/null

  for s in $removed; do
    for a in ${SVC_APPS[$s]}; do svc_remove_app "$a"; done
  done
  svc_sync_root
}
