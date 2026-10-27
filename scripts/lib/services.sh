# shellcheck shell=bash
# Catalogue des services MyOwn et logique de sélection — sourcé par
# scripts/install.sh, pas exécutable seul.
#
# Un « service » (ce que choisit la personne qui installe) regroupe une ou
# plusieurs Applications ArgoCD (un template gitops/apps/templates/<app>.yaml
# chacune) :
# les synchros de certificats suivent leur service, jamais choisies à part.
#
# Où vit l'état installé : nulle part ailleurs que dans le cluster lui-même.
# gitops/apps est un chart Helm ; l'Application `root` ne rend que les
# Applications listées dans sa valeur `apps` (spec.source.helm.valuesObject)
# — l'installeur écrit cette liste. Pour savoir ce qui est déjà en place, il
# relit les Applications présentes. Pas de fichier d'état à part qui pourrait
# diverger du cluster.
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
  [livekit]="LiveKit — appels audio/vidéo (requiert Tuwunel + vrai domaine)"
  [mailu]="Mailu — mail (requiert un vrai domaine + relais VPS)"
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

# Réglages à faire sur la box internet (redirections de ports vers la machine
# MyOwn), affichés à l'installation. Uniquement ce qui a été réellement
# nécessaire sur le mini PC (Freebox) — manuel-installation.md §16-17,
# notes-techniques.md. Hors box mais signalé aussi quand c'est bloquant.
declare -A SVC_BOX=(
  [livekit]="7881/tcp et 7882/udp (média des appels) + 5349/tcp (TURN, indispensable pour les mobiles)"
  [mailu]="993/tcp (IMAPS) et 465/tcp (SMTPS) pour les clients mail mobiles. Le port 25 n'est PAS à ouvrir : la réception et l'envoi passent par le relais VPS (Free bloque le 25 sortant) — VPS + enregistrements DNS MX/SPF/DKIM/DMARC à préparer à part (docs/notes-techniques.md, relais mail)"
)

# À l'inverse : ports qu'un service ouvre sur le réseau local mais qui ne
# doivent JAMAIS être redirigés depuis internet.
declare -A SVC_BOX_NEVER=(
  [jellyfin]="8096/tcp (téléviseurs Android, réservé au réseau local)"
)

# Réglage commun dès qu'un vrai domaine est utilisé (MYOWN_DOMAIN_SETUP=1).
MYOWN_BOX_DOMAIN="443/tcp (tous les services web) + réservation DHCP pour que la machine MyOwn garde toujours la même adresse"

# Services inutilisables sans vrai domaine : leur certificat (TURN pour
# LiveKit, IMAPS/SMTPS pour Mailu) est extrait du certificat Let's Encrypt de
# Traefik par un CronJob (*-cert-sync). Sans domaine, ce certificat n'existe
# jamais et leurs pods restent bloqués en ContainerCreating (vu en VM,
# 2026-10-10). Valeur : le CronJob (kube-system) et le secret qu'il produit.
declare -A SVC_CERT_SYNC=(
  [livekit]="livekit-turn-cert-sync livekit/livekit-turn-tls"
  [mailu]="mailu-cert-sync mailu/mailu-certificates"
)

MYOWN_CORE_SERVICES=(authentik vaultwarden)

# Proposés cochés sur une installation neuve (relance : l'état réel prime).
MYOWN_DEFAULT_SERVICES=(tuwunel uptime-kuma)

# Applications d'infrastructure, jamais proposées dans la liste : liées au
# domaine réel, pas un service que la famille utilise. dyndns réécrit
# les enregistrements DNS publics vers l'IP de la machine — ne doit JAMAIS
# tourner sur une machine de test (détournerait le vrai domaine).
MYOWN_DOMAIN_APPS=(dyndns)

# Applications d'infrastructure toujours déployées, quel que soit le choix
# des services (jamais proposées dans la liste).
MYOWN_INFRA_APPS=(argocd-access)

svc_is_core() {
  local s
  for s in "${MYOWN_CORE_SERVICES[@]}"; do [ "$s" = "$1" ] && return 0; done
  return 1
}

# Échoue bruyamment si un template de gitops/apps/templates/ n'est rattaché à aucun
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
    for a in "${MYOWN_DOMAIN_APPS[@]}" "${MYOWN_INFRA_APPS[@]}"; do [ "$a" = "$app" ] && known=1; done
    if [ "$known" = 0 ]; then
      echo "ERREUR : gitops/apps/templates/$app.yaml n'est rattaché à aucun service dans scripts/lib/services.sh" >&2
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
  # Nom d'avant le DynDNS générique (2026-10-27) : une installation qui l'a
  # encore a bien un vrai domaine, et passe à dyndns à la relance.
  grep -qx gandi-dyndns <<<"$apps" && ! grep -qx dyndns <<<"$apps" && echo dyndns
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

# Retire d'une sélection les services qui exigent un vrai domaine quand il
# n'y en a pas, en l'expliquant. $1 : 1 si domaine. Entrée/sortie : services.
svc_filter_domain() {
  local domain="$1" s
  while read -r s; do
    [ -z "$s" ] && continue
    if [ "$domain" != "1" ] && [ -n "${SVC_CERT_SYNC[$s]:-}" ]; then
      echo "  -> ${SVC_LABEL[$s]%% —*} retiré : il ne peut pas démarrer sans vrai domaine (relancer avec MYOWN_DOMAIN_SETUP=1)" >&2
      continue
    fi
    echo "$s"
  done
  return 0
}

# Lance tout de suite la première synchro de certificat des services qui en
# ont besoin, au lieu d'attendre le passage quotidien du CronJob (05h05) —
# sinon une installation neuve laisse LiveKit/Mailu bloqués jusqu'au
# lendemain. Le Job réessaie seul tant que Traefik n'a pas encore obtenu le
# certificat Let's Encrypt.
svc_kick_cert_sync() {
  local wanted="$1" s cj target ns secret i
  for s in $wanted; do
    [ -n "${SVC_CERT_SYNC[$s]:-}" ] || continue
    read -r cj target <<<"${SVC_CERT_SYNC[$s]}"
    ns="${target%%/*}"; secret="${target#*/}"
    kubectl get secret "$secret" -n "$ns" >/dev/null 2>&1 && continue
    for i in $(seq 1 30); do
      kubectl get cronjob "$cj" -n kube-system >/dev/null 2>&1 && break
      sleep 4
    done
    if kubectl create job "$cj-install-$(date +%s)" --from="cronjob/$cj" -n kube-system >/dev/null 2>&1; then
      echo "  première synchro du certificat lancée ($cj)"
    else
      echo "  $cj introuvable — le certificat sera synchronisé au passage quotidien (05h05)"
    fi
  done
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

# Liste les réglages de box pour une sélection. $1 : services (un par ligne),
# $2 : 1 si le vrai domaine est configuré. N'affiche rien s'il n'y a rien.
svc_print_box() {
  local wanted="$1" domain="$2" ip s lines="" never=""
  ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") print $(i + 1)}')"
  [ "$domain" = "1" ] && lines="  - Accès depuis internet : $MYOWN_BOX_DOMAIN\n"
  for s in $wanted; do
    [ -n "${SVC_BOX[$s]:-}" ] && lines="$lines  - ${SVC_LABEL[$s]%% —*} : ${SVC_BOX[$s]}\n"
    [ -n "${SVC_BOX_NEVER[$s]:-}" ] && never="$never  - ${SVC_LABEL[$s]%% —*} : ${SVC_BOX_NEVER[$s]}\n"
  done
  if [ -n "$lines" ]; then
    echo -e "\033[1;33mÀ FAIRE SUR VOTRE BOX INTERNET\033[0m (redirection de ports vers cette machine${ip:+, $ip}) :"
    echo -ne "$lines"
    [ "$domain" = "1" ] || echo "  (Sans vrai domaine — MYOWN_DOMAIN_SETUP=1 — ces redirections ne servent pas encore.)"
  fi
  if [ -n "$never" ]; then
    echo -e "\033[1;33mÀ NE PAS rediriger sur la box\033[0m (réseau local uniquement) :"
    echo -ne "$never"
  fi
  return 0
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
  local wanted="$1" domain_apps="$2" installed removed="" s a apps="" apps_json
  installed="$(svc_installed)"
  for s in $installed; do grep -qx "$s" <<<"$wanted" || removed="$removed $s"; done
  for s in $wanted; do apps="$apps ${SVC_APPS[$s]}"; done
  for a in $domain_apps; do apps="$apps $a"; done
  for a in "${MYOWN_INFRA_APPS[@]}"; do apps="$apps $a"; done

  echo "Services installés après cette étape :"
  for s in $wanted; do echo "  + ${SVC_LABEL[$s]}"; done
  local added=""
  for s in $wanted; do grep -qx "$s" <<<"$installed" || added="$added $s"; done
  [ -n "$added" ] && svc_print_box "$(tr ' ' '\n' <<<"$added")" "${MYOWN_DOMAIN_SETUP:-0}"
  if [ -n "$removed" ]; then
    echo "Services qui seront ARRÊTÉS (données conservées, réactivables plus tard) :"
    for s in $removed; do echo "  - ${SVC_LABEL[$s]}"; done
    if [ "${MYOWN_ASSUME_YES:-0}" != "1" ]; then
      [ -t 0 ] || { echo "Arrêt de services en mode non interactif : relancer avec MYOWN_ASSUME_YES=1" >&2; return 1; }
      read -r -p "Confirmer ? [o/N] " ans
      [[ "$ans" =~ ^[oOyY]$ ]] || { echo "Annulé, rien n'a été modifié."; return 1; }
    fi
  fi

  # Valeurs `domain` (MYOWN_DOMAIN_VALUE, résolu par install.sh) et `apps`
  # du chart gitops/apps. Le même patch pose aussi le paramètre
  # `revision` (la révision suivie par root, substituée par ArgoCD) et retire
  # l'ancien filtre `directory` — ce qui migre au passage une installation
  # antérieure au chart (root en simple lecture de dossier).
  apps_json="[$(for a in $apps; do printf '"%s",' "$a"; done | sed 's/,$//')]"
  kubectl patch application root -n argocd --type merge -p "{\"spec\":{\"source\":{\"directory\":null,\"helm\":{\"parameters\":[{\"name\":\"revision\",\"value\":\"\$ARGOCD_APP_SOURCE_TARGET_REVISION\"}],\"valuesObject\":{\"domain\":\"$MYOWN_DOMAIN_VALUE\",\"adminSourceRanges\":${MYOWN_ADMIN_RANGES_JSON:-[]},\"apps\":$apps_json}}}}}" >/dev/null

  for s in $removed; do
    for a in ${SVC_APPS[$s]}; do svc_remove_app "$a"; done
  done
  svc_sync_root
}
