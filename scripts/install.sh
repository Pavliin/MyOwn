#!/usr/bin/env bash
# Installeur MyOwn — automatise docs/manuel-installation.md. À lancer depuis
# un dépôt déjà cloné (section 1 du manuel = juste `git clone`).
#
# Deux cibles :
#   - k3s (défaut) : vraie installation, k3s bare-metal mono-nœud sur la
#     machine qui lance le script (section 14 du manuel). Ubuntu installé
#     au préalable avec son propre installeur — pas d'ISO maison
#     (docs/installation-utilisateur.md).
#   - k3d : cluster de dev conteneurisé dans Docker (sections 2-11).
#
# Choix des services : seul le socle (Authentik, Vaultwarden) est imposé ;
# le reste se coche dans une liste. RELANCER le script permet à tout moment
# d'ajouter un service ou d'en arrêter un (ses données sont conservées) —
# toutes les étapes sont rejouables sans effet de bord. Catalogue, dépendances
# et mécanique : scripts/lib/services.sh.
#
# Variables d'environnement :
#   MYOWN_TARGET            k3s (défaut) | k3d
#   MYOWN_DOMAIN            domaine de l'installation (obligatoire sur une
#                           installation neuve ; une relance reprend celui
#                           déjà configuré)
#   MYOWN_ADMIN_SOURCE_RANGES  plages autorisées à joindre les outils d'admin,
#                           séparées par des virgules (défaut : réseau local +
#                           VPN d'admin + pods ; une relance garde la valeur)
#   MYOWN_SERVICES          sélection sans question : « nextcloud,immich » ou
#                           « all », ou « none » pour le socle seul (le socle
#                           est toujours ajouté)
#   MYOWN_ASSUME_YES        1 pour confirmer sans question l'arrêt de services
#   MYOWN_REVISION          révision suivie par root (branche ou tag de release).
#                           Défaut : master sur une installation neuve ; sur une
#                           relance, la révision déjà suivie est conservée.
#   MYOWN_DOMAIN_SETUP      1 pour activer le vrai domaine : Let's Encrypt en
#                           DNS-01 + DynDNS (manuel, section 16). JAMAIS sur une
#                           machine de test : le DynDNS repointerait le domaine réel.
#   MYOWN_DNS_PROVIDER      code lego du fournisseur DNS (une relance garde
#                           celui déjà configuré)
#   MYOWN_ACME_EMAIL        e-mail du compte Let's Encrypt (idem)
#   MYOWN_DNS_CREDENTIALS_FILE  fichier KEY=VALUE des variables qu'attend lego
#                           pour ce fournisseur (si kube-system/dns-provider-credentials
#                           n'existe pas encore)
#   MYOWN_DDNS_CREDENTIALS_FILE  fichier JSON des réglages ddns-updater propres
#                           au fournisseur, sans le domaine (si dyndns/dyndns-config
#                           n'existe pas encore)
#   MYOWN_DDNS_IPV6         1/0 : tenir aussi les enregistrements AAAA à jour
#                           (défaut : oui si la machine a une route IPv6 par défaut)
#   MYOWN_K3S_VERSION       version k3s d'une installation neuve (défaut : celle
#                           validée en production, ci-dessous)
#   MYOWN_ARGOCD_VERSION    version ArgoCD. Défaut : celle validée en production
#                           sur une installation neuve ; sur une relance, la
#                           version en place n'est JAMAIS changée sans cette
#                           variable (une mise à jour d'ArgoCD est un choix).
#   MYOWN_GENERATE_AGE_KEY  1 pour générer la clé age d'une toute première install
#   (k3s : l'installeur règle aussi les limites inotify du noyau et les
#   résolveurs DNS du cluster — voir les étapes correspondantes)
#   k3d seulement : MYOWN_CLUSTER_NAME, MYOWN_PORT_443, MYOWN_PORT_LIVEKIT_WS, MYOWN_PORT_LIVEKIT_TCP,
#   MYOWN_PORT_LIVEKIT_UDP

set -euo pipefail

TARGET="${MYOWN_TARGET:-k3s}"
case "$TARGET" in k3s|k3d) ;; *) echo "MYOWN_TARGET doit valoir k3s ou k3d" >&2; exit 1 ;; esac
DOMAIN_SETUP="${MYOWN_DOMAIN_SETUP:-0}"
# Versions qui tournent réellement sur le mini PC (relevé du 2026-10-10) —
# une réinstallation reproduit la production plutôt que « la dernière ».
K3S_VERSION="${MYOWN_K3S_VERSION:-v1.36.3+k3s1}"
ARGOCD_DEFAULT_VERSION="v3.5.1"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
# shellcheck source=lib/services.sh
source "$REPO_ROOT/scripts/lib/services.sh"

step() { echo -e "\n\033[1;34m==> $1\033[0m"; }
die() { echo -e "\033[1;31mERREUR : $1\033[0m" >&2; exit 1; }

svc_check_catalog gitops/apps/templates || exit 1

# Domaine de l'installation (valeur `domain` du chart gitops/apps, rendue
# obligatoire par le chart). Relance : celui déjà configuré dans root, jamais
# changé en silence. Installation neuve : MYOWN_DOMAIN. Appelée dès l'étape
# DNS (CoreDNS en a besoin), puis avant le bootstrap GitOps.
resolve_domain() {
  MYOWN_DOMAIN_VALUE="$(kubectl get application root -n argocd -o jsonpath='{.spec.source.helm.valuesObject.domain}' 2>/dev/null || true)"
  if [ -n "${MYOWN_DOMAIN:-}" ] && [ -n "$MYOWN_DOMAIN_VALUE" ] && [ "$MYOWN_DOMAIN" != "$MYOWN_DOMAIN_VALUE" ]; then
    die "domaine déjà configuré : $MYOWN_DOMAIN_VALUE (MYOWN_DOMAIN=$MYOWN_DOMAIN). Changer de domaine n'est pas pris en charge par une simple relance."
  fi
  MYOWN_DOMAIN_VALUE="${MYOWN_DOMAIN_VALUE:-${MYOWN_DOMAIN:-}}"
  [ -n "$MYOWN_DOMAIN_VALUE" ] || die "aucun domaine configuré : relancez avec MYOWN_DOMAIN=<votre-domaine>."
  export MYOWN_DOMAIN_VALUE
  echo "Domaine : $MYOWN_DOMAIN_VALUE"
}


step "Vérification des outils requis ($TARGET)"
if [ "$TARGET" = "k3d" ]; then
  for tool in docker git kubectl k3d; do
    command -v "$tool" >/dev/null || die "manquant : $tool — installez-le puis relancez."
  done
else
  for tool in git curl sudo systemctl; do
    command -v "$tool" >/dev/null || die "manquant : $tool — installez-le puis relancez."
  done
  [ "$(uname -m)" = "x86_64" ] || die "seule l'architecture x86_64 est prise en charge pour l'instant."
fi
if ! command -v sops >/dev/null; then
  echo "sops absent, installation dans ~/.local/bin..."
  mkdir -p ~/.local/bin
  curl -fsSL -o ~/.local/bin/sops \
    https://github.com/getsops/sops/releases/download/v3.10.2/sops-v3.10.2.linux.amd64
  chmod +x ~/.local/bin/sops
  export PATH="$HOME/.local/bin:$PATH"
fi
command -v age-keygen >/dev/null || die "manquant : age-keygen — installez le paquet 'age' puis relancez."
step "Clé de chiffrement des secrets (age)"
AGE_KEY="$HOME/.config/sops/age/keys.txt"
if [ ! -f "$AGE_KEY" ]; then
  echo "Aucune clé age trouvée à $AGE_KEY"
  echo "  - Première installation du projet : relancez avec MYOWN_GENERATE_AGE_KEY=1"
  echo "  - Sinon : restaurez votre clé depuis votre sauvegarde à cet emplacement, puis relancez."
  if [ "${MYOWN_GENERATE_AGE_KEY:-0}" = "1" ]; then
    mkdir -p ~/.config/sops/age
    age-keygen -o "$AGE_KEY"
    echo "Nouvelle clé générée — mettez à jour .sops.yaml avec la clé publique ci-dessus et committez, avant de continuer."
  fi
  exit 1
fi
echo "Clé présente."

if [ "$TARGET" = "k3d" ]; then
  CLUSTER_NAME="${MYOWN_CLUSTER_NAME:-myown-dev}"
  step "Création du cluster k3d ($CLUSTER_NAME)"
  if k3d cluster list 2>/dev/null | grep -q "^${CLUSTER_NAME} "; then
    echo "Cluster $CLUSTER_NAME déjà présent, réutilisation."
  else
    k3d cluster create "$CLUSTER_NAME" \
      -p "${MYOWN_PORT_443:-443}:443@loadbalancer" \
      -p "${MYOWN_PORT_LIVEKIT_WS:-7880}:7880@loadbalancer" -p "${MYOWN_PORT_LIVEKIT_TCP:-7881}:7881@loadbalancer" \
      -p "${MYOWN_PORT_LIVEKIT_UDP:-7882}:7882/udp@loadbalancer" \
      --wait
  fi
  kubectl config use-context "k3d-${CLUSTER_NAME}"
else
  step "Limites inotify du noyau"
  # Ubuntu limite à 128 les instances inotify par utilisateur : trop peu pour
  # un nœud Kubernetes (kubelet, containerd et beaucoup d'applications
  # surveillent des fichiers). Vu sur le mini PC avec ~40 pods : systemctl
  # lui-même échoue en « Failed to allocate directory watch: Too many open
  # files » (2026-10-15). Valeurs couramment recommandées pour un nœud k8s.
  INOTIFY_CONF=/etc/sysctl.d/90-myown-inotify.conf
  WANT_INOTIFY="$(printf 'fs.inotify.max_user_instances = 8192\nfs.inotify.max_user_watches = 524288\n')"
  if [ "$(cat "$INOTIFY_CONF" 2>/dev/null)" != "$WANT_INOTIFY" ]; then
    echo "$WANT_INOTIFY" | sudo tee "$INOTIFY_CONF" >/dev/null
    sudo sysctl -q -p "$INOTIFY_CONF"
    echo "Limites relevées (instances 8192, watches 524288)."
  else
    echo "Déjà configurées."
  fi

  step "Résolveurs DNS du cluster"
  # CoreDNS relaie les noms externes vers les résolveurs de l'hôte, un au
  # hasard par requête. Mailu refuse de démarrer si le résolveur ne valide
  # pas DNSSEC — sur le mini PC, Pi-hole ne valide pas (1 requête sur 3),
  # dans une VM aucun ne valide : démarrage au hasard, ou jamais (vu en VM,
  # 2026-10-10). k3s reçoit donc ses propres résolveurs, qui valident tous
  # les deux. N'affecte que les pods : l'hôte et le réseau local gardent
  # leur DNS (Pi-hole compris). Noms internes et *.offsystem.fr : toujours
  # résolus par CoreDNS (coredns-custom.yaml).
  DNS_RESOLV=/etc/rancher/k3s/myown-resolv.conf
  DNS_CFG=/etc/rancher/k3s/config.yaml.d/myown-dns.yaml
  DNS_CHANGED=0
  WANT_RESOLV="$(printf 'nameserver 9.9.9.9\nnameserver 1.1.1.1\n')"
  WANT_CFG="resolv-conf: $DNS_RESOLV"
  if [ "$(sudo cat "$DNS_RESOLV" 2>/dev/null)" != "$WANT_RESOLV" ] || [ "$(sudo cat "$DNS_CFG" 2>/dev/null)" != "$WANT_CFG" ]; then
    sudo mkdir -p /etc/rancher/k3s/config.yaml.d
    echo "$WANT_RESOLV" | sudo tee "$DNS_RESOLV" >/dev/null
    echo "$WANT_CFG" | sudo tee "$DNS_CFG" >/dev/null
    DNS_CHANGED=1
    echo "Résolveurs du cluster : Quad9 (9.9.9.9) et Cloudflare (1.1.1.1), validation DNSSEC."
  else
    echo "Déjà configurés."
  fi

  step "Installation de k3s"
  if systemctl is-active --quiet k3s && [ "$DNS_CHANGED" = 1 ]; then
    echo "Redémarrage de k3s pour appliquer les résolveurs (les conteneurs continuent de tourner)..."
    sudo systemctl restart k3s
  fi
  if systemctl is-active --quiet k3s; then
    echo "k3s déjà actif ($(k3s --version | head -1)), réutilisation."
  else
    echo "Installation via get.k3s.io (sudo requis)..."
    curl -sfL https://get.k3s.io | sudo env INSTALL_K3S_VERSION="$K3S_VERSION" sh -
  fi
  # Kubeconfig dédié plutôt que d'écraser ~/.kube/config (qui peut contenir
  # d'autres clusters). Le kubectl de k3s ne lit pas ~/.kube/config de toute
  # façon — toujours passer par KUBECONFIG (manuel, section 14.1).
  mkdir -p ~/.kube
  KCFG="$HOME/.kube/myown-k3s.yaml"
  sudo cat /etc/rancher/k3s/k3s.yaml > "$KCFG"
  chmod 600 "$KCFG"
  export KUBECONFIG="$KCFG"
  echo "Kubeconfig : $KCFG (à exporter dans KUBECONFIG pour vos sessions)"
  echo "Attente du nœud..."
  for _ in $(seq 1 60); do
    kubectl get nodes --no-headers 2>/dev/null | grep -q " Ready" && break
    sleep 3
  done
  kubectl wait --for=condition=Ready node --all --timeout=60s

  step "Traefik et DNS interne (bootstrap hors GitOps)"
  # k3s fournit déjà Traefik sur 80/443. Le Service interne et CoreDNS font
  # résoudre <service>.<domaine> vers Traefik depuis les pods (manuel, §14.2) ;
  # coredns-custom.yaml est un gabarit, __DOMAIN__ remplacé par le domaine.
  resolve_domain
  kubectl apply -f gitops/bootstrap/traefik-internal-svc.yaml
  sed "s/__DOMAIN__/$MYOWN_DOMAIN_VALUE/g" gitops/bootstrap/coredns-custom.yaml | kubectl apply -f -
  kubectl rollout restart deployment coredns -n kube-system
  kubectl rollout status deployment coredns -n kube-system --timeout=120s

  if [ "$DOMAIN_SETUP" = "1" ]; then
    step "Domaine réel : certificats Let's Encrypt (DNS-01)"
    # Fournisseur et e-mail : relance → ceux déjà posés dans la configuration
    # de Traefik, sauf variable explicite.
    TRAEFIK_VALUES="$(kubectl get helmchartconfig traefik -n kube-system -o jsonpath='{.spec.valuesContent}' 2>/dev/null || true)"
    DNS_PROVIDER="${MYOWN_DNS_PROVIDER:-$(awk '$1 == "provider:" {print $2; exit}' <<<"$TRAEFIK_VALUES")}"
    ACME_EMAIL="${MYOWN_ACME_EMAIL:-$(awk '$1 == "email:" {print $2; exit}' <<<"$TRAEFIK_VALUES")}"
    [[ "$DNS_PROVIDER" =~ ^[a-z0-9.-]+$ ]] || die "fournisseur DNS inconnu : relancez avec MYOWN_DNS_PROVIDER=<code lego du fournisseur> (manuel, section 16)."
    [[ "$ACME_EMAIL" =~ ^[^[:space:]/@]+@[^[:space:]/@]+$ ]] || die "e-mail Let's Encrypt manquant ou invalide : relancez avec MYOWN_ACME_EMAIL=<adresse>."
    if ! kubectl get secret dns-provider-credentials -n kube-system >/dev/null 2>&1; then
      [ -n "${MYOWN_DNS_CREDENTIALS_FILE:-}" ] && [ -f "$MYOWN_DNS_CREDENTIALS_FILE" ] || \
        die "secret dns-provider-credentials absent : relancez avec MYOWN_DNS_CREDENTIALS_FILE=<fichier KEY=VALUE des identifiants du fournisseur> (manuel, section 16)."
      kubectl create secret generic dns-provider-credentials -n kube-system --from-env-file="$MYOWN_DNS_CREDENTIALS_FILE"
    fi
    sed -e "s/__DNS_PROVIDER__/$DNS_PROVIDER/" -e "s/__ACME_EMAIL__/$ACME_EMAIL/" \
      gitops/bootstrap/traefik-acme-helmchartconfig.yaml | kubectl apply -f -
    echo "Fournisseur DNS : $DNS_PROVIDER — compte Let's Encrypt : $ACME_EMAIL"

    step "DynDNS (ddns-updater)"
    # Réglages complets (identifiants compris) dans un Secret, jamais commité :
    # le domaine et son wildcard, en IPv4 et, si la machine en a, en IPv6.
    if ! kubectl get secret dyndns-config -n dyndns >/dev/null 2>&1; then
      [ -n "${MYOWN_DDNS_CREDENTIALS_FILE:-}" ] && [ -f "$MYOWN_DDNS_CREDENTIALS_FILE" ] || \
        die "secret dyndns-config absent : relancez avec MYOWN_DDNS_CREDENTIALS_FILE=<fichier JSON des réglages ddns-updater du fournisseur> (manuel, section 16)."
      DDNS_IPV6="${MYOWN_DDNS_IPV6:-}"
      if [ -z "$DDNS_IPV6" ]; then
        DDNS_IPV6=0
        [ -n "$(ip -6 route show default 2>/dev/null)" ] && DDNS_IPV6=1
      fi
      kubectl create namespace dyndns --dry-run=client -o yaml | kubectl apply -f - >/dev/null
      # Calculé avant toute création : un échec ne doit pas laisser un Secret
      # vide, qu'une relance prendrait pour déjà en place.
      DDNS_CONFIG="$(python3 - "$MYOWN_DDNS_CREDENTIALS_FILE" "$MYOWN_DOMAIN_VALUE" "$DDNS_IPV6" <<'PY'
import json, sys
path, domain, ipv6 = sys.argv[1:]
provider = json.load(open(path))
if not isinstance(provider, dict) or "provider" not in provider:
    sys.exit("MYOWN_DDNS_CREDENTIALS_FILE : un objet JSON avec au moins « provider » est attendu")
versions = ["ipv4", "ipv6"] if ipv6 == "1" else ["ipv4"]
settings = [dict(provider, domain=host, ip_version=v)
            for host in (domain, "*." + domain) for v in versions]
print(json.dumps({"settings": settings}))
PY
)"
      kubectl create secret generic dyndns-config -n dyndns --from-file=config.json=<(printf '%s' "$DDNS_CONFIG")
      echo "Enregistrements tenus à jour : $MYOWN_DOMAIN_VALUE et *.$MYOWN_DOMAIN_VALUE (IPv6 : $([ "$DDNS_IPV6" = 1 ] && echo oui || echo non))"
    fi
  fi
fi

step "Installation d'ArgoCD"
ARGOCD_CURRENT="$(kubectl get deploy argocd-server -n argocd -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null | sed 's/.*://' || true)"
if [ -n "$ARGOCD_CURRENT" ] && [ -z "${MYOWN_ARGOCD_VERSION:-}" ]; then
  echo "ArgoCD $ARGOCD_CURRENT déjà en place, conservé (MYOWN_ARGOCD_VERSION pour changer de version)."
else
  ARGOCD_VERSION="${MYOWN_ARGOCD_VERSION:-$ARGOCD_DEFAULT_VERSION}"
  echo "ArgoCD $ARGOCD_VERSION"
  kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
  kubectl apply -n argocd --server-side --force-conflicts \
    -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"
fi
kubectl wait --for=condition=available --timeout=300s deployment --all -n argocd
kubectl patch configmap argocd-cmd-params-cm -n argocd --type merge \
  -p '{"data":{"server.insecure":"true"}}'
kubectl rollout restart deployment argocd-server -n argocd
kubectl rollout status deployment argocd-server -n argocd --timeout=120s

step "Activation de KSOPS"
kubectl create secret generic sops-age -n argocd \
  --from-file=keys.txt="$AGE_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl patch configmap argocd-cm -n argocd --type merge \
  -p '{"data":{"kustomize.buildOptions":"--enable-alpha-plugins --enable-exec"}}'
kubectl patch deployment argocd-repo-server -n argocd --type strategic \
  --patch-file gitops/bootstrap/argocd-repo-server-ksops-patch.yaml
# Attendre le nouveau pod avant toute synchro : sinon le contrôleur compare
# contre l'ancien repo-server sans KSOPS et met en cache une ComparisonError
# (vu en vrai, notes-techniques.md).
kubectl rollout status deployment argocd-repo-server -n argocd --timeout=120s

step "Health check ArgoCD pour Prometheus Operator"
kubectl patch configmap argocd-cm -n argocd --type merge \
  --patch-file gitops/bootstrap/argocd-cm-health-checks-patch.yaml

step "Choix des services"
FRESH=0
kubectl get application root -n argocd >/dev/null 2>&1 || FRESH=1
if [ "$FRESH" = 1 ]; then
  CURRENT="$(printf '%s\n' "${MYOWN_DEFAULT_SERVICES[@]}")"
else
  CURRENT="$(svc_installed)"
  echo "Installation existante — services actuellement en place :"
  for s in $CURRENT; do echo "  * ${SVC_LABEL[$s]}"; done
fi
DOMAIN_APPS="$(svc_domain_apps_installed)"
if [ "$DOMAIN_SETUP" = "1" ]; then DOMAIN_APPS="$(printf '%s\n' "${MYOWN_DOMAIN_APPS[@]}")"; fi
HAS_DOMAIN=0
[ -n "$DOMAIN_APPS" ] && HAS_DOMAIN=1
SELECTED="$(svc_prompt "$CURRENT")"
WANTED="$(svc_filter_domain "$HAS_DOMAIN" <<<"$SELECTED" | svc_resolve)"

if [ "$TARGET" = "k3s" ] && grep -qx nextcloud <<<"$WANTED"; then
  step "Stockage Nextcloud (hostPath)"
  # Doit exister, groupe www-data (gid 33) inscriptible, AVANT le tout premier
  # démarrage — sinon l'auto-installation échoue et ne se relance jamais
  # (manuel, section 14.4).
  NC_DIR=/var/lib/rancher/k3s/storage/myown/nextcloud-data
  sudo mkdir -p "$NC_DIR"
  sudo chown root:33 "$NC_DIR"
  sudo chmod g+rwx "$NC_DIR"
  # config/ aussi, en www-data : le chart y monte ses fichiers de config un
  # par un (subPath), donc sans ça c'est kubelet qui crée config/ en root
  # avant le conteneur — Nextcloud ne peut plus écrire config.php, et
  # l'image ne retente jamais l'installation après ce premier échec (vu en
  # VM, 2026-10-10 ; manuel §14.4).
  [ -d "$NC_DIR/config" ] || sudo install -d -o 33 -g 33 -m 775 "$NC_DIR/config"
  echo "$NC_DIR prêt."
fi

# Domaine (voir resolve_domain ; la question interactive et les niveaux A/B/C
# viennent avec l'étape 4 de docs/installation-utilisateur.md).
resolve_domain

# Plages autorisées à joindre les outils d'admin (ArgoCD, Grafana, Ollama,
# admin Uptime Kuma : <outil>.<domaine>). Relance : la valeur déjà configurée.
# Sinon MYOWN_ADMIN_SOURCE_RANGES (liste séparée par des virgules), ou à défaut :
# réseau local de cette machine + VPN d'admin (wg0, s'il existe) + réseau des
# pods. Jamais le tunnel du relais mail : un VPS compromis ne doit atteindre
# aucun outil d'admin.
MYOWN_ADMIN_RANGES_JSON="$(kubectl get application root -n argocd -o jsonpath='{.spec.source.helm.valuesObject.adminSourceRanges}' 2>/dev/null || true)"
if [ -z "$MYOWN_ADMIN_RANGES_JSON" ] || [ "$MYOWN_ADMIN_RANGES_JSON" = "[]" ]; then
  if [ -n "${MYOWN_ADMIN_SOURCE_RANGES:-}" ]; then
    RANGES="$(tr ',' ' ' <<<"$MYOWN_ADMIN_SOURCE_RANGES")"
  else
    LAN_IF="$(ip -4 route show default | awk '{print $5; exit}')"
    LAN_CIDR="$(ip -4 route show dev "$LAN_IF" scope link 2>/dev/null | awk '$1 ~ /\// {print $1; exit}')"
    WG_CIDR="$(ip -4 route show dev wg0 scope link 2>/dev/null | awk '$1 ~ /\// {print $1; exit}')"
    RANGES="$LAN_CIDR $WG_CIDR 10.42.0.0/16"
  fi
  MYOWN_ADMIN_RANGES_JSON="[$(for r in $RANGES; do printf '"%s",' "$r"; done | sed 's/,$//')]"
fi
export MYOWN_ADMIN_RANGES_JSON
echo "Outils d'admin réservés à : $MYOWN_ADMIN_RANGES_JSON"

step "Bootstrap GitOps"
if [ "$FRESH" = 1 ]; then
  kubectl apply -f gitops/bootstrap/root-app.yaml
fi
# Jamais de `kubectl apply` de root-app.yaml sur une relance : il remettrait
# targetRevision à master sur une installation qui suit un tag de release.
# (La forme Helm de root — paramètre `revision`, liste `apps` — est posée par
# svc_apply plus bas, y compris sur une installation qui ne l'a pas encore.)
if [ -n "${MYOWN_REVISION:-}" ]; then
  kubectl patch application root -n argocd --type merge \
    -p "{\"spec\":{\"source\":{\"targetRevision\":\"$MYOWN_REVISION\"}}}" >/dev/null
fi
echo "root suit : $(kubectl get application root -n argocd -o jsonpath='{.spec.source.targetRevision}')"
# Ancien DynDNS propre à un fournisseur (avant le 2026-10-27), remplacé par
# dyndns : arrêté avec ses ressources (sans le finaliseur, retirer
# l'Application laisserait son CronJob tourner).
if [ "$HAS_DOMAIN" = 1 ] && kubectl get application gandi-dyndns -n argocd >/dev/null 2>&1; then
  kubectl get secret dyndns-config -n dyndns >/dev/null 2>&1 || \
    die "remplacement de l'ancien DynDNS : relancez avec MYOWN_DOMAIN_SETUP=1 et MYOWN_DDNS_CREDENTIALS_FILE (manuel, section 16)."
  svc_remove_app gandi-dyndns
fi
MYOWN_DOMAIN_SETUP="$HAS_DOMAIN" svc_apply "$WANTED" "$DOMAIN_APPS"
[ "$HAS_DOMAIN" = 1 ] && svc_kick_cert_sync "$WANTED"

step "Secrets générés dans le cluster"
# Ceux qui manquent seulement, jamais affichés (scripts/lib/secrets.py). Le
# secret OIDC côté Authentik est dérivé de celui du service : on attend
# qu'ArgoCD ait créé ce dernier (code 3), un autre échec arrête tout.
for i in $(seq 1 30); do
  rc=0
  python3 scripts/lib/secrets.py ensure || rc=$?
  [ "$rc" = 0 ] && break
  [ "$rc" = 3 ] && [ "$i" -lt 30 ] || die "secrets générés : échec (voir ci-dessus)."
  sleep 10
done

if grep -qx jellyfin <<<"$WANTED"; then
  step "Médiathèque partagée Nextcloud (lue par Jellyfin)"
  # Jellyfin lit le dossier de groupe Nextcloud n°1 (gitops/apps/templates/jellyfin.yaml)
  # et reste bloqué au démarrage tant qu'il n'existe pas. Rejoue le §15 du
  # manuel : groupe « famille », dossier « Mediatheque ». occ toujours en
  # www-data — lancé en root il crée des fichiers illisibles pour Apache.
  echo "Attente de la fin de l'installation de Nextcloud (jusqu'à 15 min au premier lancement)..."
  NC_OK=0
  for _ in $(seq 1 90); do
    if kubectl exec -n nextcloud deploy/nextcloud -c nextcloud -- \
      su -s /bin/sh www-data -c "php occ status --output=json" 2>/dev/null | grep -q '"installed":true'; then
      NC_OK=1; break
    fi
    sleep 10
  done
  if [ "$NC_OK" = 1 ]; then
    occ() { kubectl exec -n nextcloud deploy/nextcloud -c nextcloud -- su -s /bin/sh www-data -c "php occ $*"; }
    # occ renvoie 1 quand l'app ou le groupe existe déjà : normal sur une
    # relance, ne doit pas arrêter le script.
    occ app:install groupfolders >/dev/null 2>&1 || occ app:enable groupfolders >/dev/null 2>&1 || true
    occ group:add famille >/dev/null 2>&1 || true
    GF_LIST="$(occ groupfolders:list --output=json)"
    if grep -q '"mountPoint":"Mediatheque"' <<<"$GF_LIST"; then
      echo "Dossier Mediatheque déjà présent."
    else
      GF_ID="$(occ groupfolders:create Mediatheque | tr -dc '0-9')"
      occ groupfolders:group "$GF_ID" famille read write share delete >/dev/null
      echo "Dossier Mediatheque créé (id $GF_ID), partagé avec le groupe famille."
      [ "$GF_ID" = 1 ] || echo "  ATTENTION : id $GF_ID ≠ 1 — gitops/apps/templates/jellyfin.yaml lit __groupfolders/1, à ajuster."
    fi
    echo "  Ajouter chaque membre au groupe : manuel-admin.md (occ group:adduser famille <compte>)."
  else
    echo "Nextcloud pas encore installé après 15 min — relancer ce script plus tard pour créer la médiathèque (Jellyfin attendra)."
  fi
fi

step "Vérification"
echo "Les Applications convergent en arrière-plan (plusieurs minutes au premier lancement) :"
kubectl get applications -n argocd
echo
svc_print_box "$WANTED" "$HAS_DOMAIN"
cat <<EOF

Installation terminée.
  - Suivi : kubectl get applications -n argocd${KUBECONFIG:+   (KUBECONFIG=$KUBECONFIG)}
  - Ajouter ou arrêter un service plus tard : relancer ce script.
  - Usage de chaque service : docs/manuel-utilisateur.md
EOF
