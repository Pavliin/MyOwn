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
#   MYOWN_SERVICES          sélection sans question : « nextcloud,immich » ou
#                           « all », ou « none » pour le socle seul (le socle
#                           est toujours ajouté)
#   MYOWN_ASSUME_YES        1 pour confirmer sans question l'arrêt de services
#   MYOWN_REVISION          révision suivie par root (branche ou tag de release).
#                           Défaut : master sur une installation neuve ; sur une
#                           relance, la révision déjà suivie est conservée.
#   MYOWN_DOMAIN_SETUP      1 pour activer le vrai domaine : Let's Encrypt via
#                           Gandi + DynDNS (section 16). JAMAIS sur une machine
#                           de test : le DynDNS repointerait le domaine réel.
#   MYOWN_GANDI_TOKEN_FILE  fichier contenant le PAT Gandi (si le secret
#                           kube-system/gandi-dns-credentials n'existe pas encore)
#   MYOWN_K3S_VERSION       version k3s d'une installation neuve (défaut : celle
#                           validée en production, ci-dessous)
#   MYOWN_ARGOCD_VERSION    version ArgoCD. Défaut : celle validée en production
#                           sur une installation neuve ; sur une relance, la
#                           version en place n'est JAMAIS changée sans cette
#                           variable (une mise à jour d'ArgoCD est un choix).
#   MYOWN_GENERATE_AGE_KEY  1 pour générer la clé age d'une toute première install
#   MYOWN_SKIP_MKCERT       1/0 — défaut 0 en k3d, 1 en k3s (domaine réel)
#   MYOWN_SKIP_HOSTS        1 pour ne pas toucher /etc/hosts (k3d uniquement)
#   k3d seulement : MYOWN_CLUSTER_NAME, MYOWN_PORT_HTTP, MYOWN_PORT_HTTPS,
#   MYOWN_PORT_443, MYOWN_PORT_LIVEKIT_WS, MYOWN_PORT_LIVEKIT_TCP,
#   MYOWN_PORT_LIVEKIT_UDP

set -euo pipefail

TARGET="${MYOWN_TARGET:-k3s}"
case "$TARGET" in k3s|k3d) ;; *) echo "MYOWN_TARGET doit valoir k3s ou k3d" >&2; exit 1 ;; esac
if [ "$TARGET" = "k3d" ]; then SKIP_MKCERT="${MYOWN_SKIP_MKCERT:-0}"; else SKIP_MKCERT="${MYOWN_SKIP_MKCERT:-1}"; fi
SKIP_HOSTS="${MYOWN_SKIP_HOSTS:-0}"
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

svc_check_catalog gitops/apps || exit 1

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
if [ "$SKIP_MKCERT" != "1" ]; then
  command -v mkcert >/dev/null || die "manquant : mkcert — installez-le puis relancez (ou MYOWN_SKIP_MKCERT=1)."
fi

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
      -p "${MYOWN_PORT_HTTP:-8090}:80@loadbalancer" -p "${MYOWN_PORT_HTTPS:-8453}:443@loadbalancer" \
      -p "${MYOWN_PORT_443:-443}:443@loadbalancer" \
      -p "${MYOWN_PORT_LIVEKIT_WS:-7880}:7880@loadbalancer" -p "${MYOWN_PORT_LIVEKIT_TCP:-7881}:7881@loadbalancer" \
      -p "${MYOWN_PORT_LIVEKIT_UDP:-7882}:7882/udp@loadbalancer" \
      --wait
  fi
  kubectl config use-context "k3d-${CLUSTER_NAME}"
else
  step "Installation de k3s"
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
  # k3s fournit déjà Traefik sur 80/443 ; ces Services ajoutent 8090/8453 et
  # l'alias interne, CoreDNS résout les noms des services vers Traefik
  # (manuel, section 14.2).
  kubectl apply -f gitops/bootstrap/traefik-external-svc.yaml
  kubectl apply -f gitops/bootstrap/traefik-internal-svc.yaml
  kubectl apply -f gitops/bootstrap/coredns-custom.yaml
  kubectl rollout restart deployment coredns -n kube-system
  kubectl rollout status deployment coredns -n kube-system --timeout=120s

  if [ "$DOMAIN_SETUP" = "1" ]; then
    step "Domaine réel : Let's Encrypt (Gandi DNS-01)"
    if ! kubectl get secret gandi-dns-credentials -n kube-system >/dev/null 2>&1; then
      [ -n "${MYOWN_GANDI_TOKEN_FILE:-}" ] && [ -f "$MYOWN_GANDI_TOKEN_FILE" ] || \
        die "secret gandi-dns-credentials absent : relancez avec MYOWN_GANDI_TOKEN_FILE=<fichier contenant le PAT Gandi> (manuel, section 16)."
      kubectl create secret generic gandi-dns-credentials -n kube-system --from-file=token="$MYOWN_GANDI_TOKEN_FILE"
    fi
    kubectl apply -f gitops/bootstrap/traefik-acme-helmchartconfig.yaml
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
SELECTED="$(svc_prompt "$CURRENT")"
WANTED="$(svc_resolve <<<"$SELECTED")"

DOMAIN_APPS="$(svc_domain_apps_installed)"
if [ "$DOMAIN_SETUP" = "1" ]; then DOMAIN_APPS="$(printf '%s\n' "${MYOWN_DOMAIN_APPS[@]}")"; fi
if grep -qx mailu <<<"$WANTED" && [ -z "$DOMAIN_APPS" ]; then
  echo "  (attention : Mailu ne fonctionne qu'avec un vrai domaine — MYOWN_DOMAIN_SETUP=1 — et le relais VPS)"
fi

if [ "$TARGET" = "k3s" ] && grep -qx nextcloud <<<"$WANTED"; then
  step "Stockage Nextcloud (hostPath)"
  # Doit exister, groupe www-data (gid 33) inscriptible, AVANT le tout premier
  # démarrage — sinon l'auto-installation échoue et ne se relance jamais
  # (manuel, section 14.4).
  NC_DIR=/var/lib/rancher/k3s/storage/myown/nextcloud-data
  sudo mkdir -p "$NC_DIR"
  sudo chown root:33 "$NC_DIR"
  sudo chmod g+rwx "$NC_DIR"
  echo "$NC_DIR prêt."
fi

step "Bootstrap GitOps"
if [ "$FRESH" = 1 ]; then
  kubectl apply -f gitops/bootstrap/root-app.yaml
fi
# Jamais de `kubectl apply` de root-app.yaml sur une relance : il remettrait
# targetRevision à master sur une installation qui suit un tag de release.
if [ -n "${MYOWN_REVISION:-}" ]; then
  kubectl patch application root -n argocd --type merge \
    -p "{\"spec\":{\"source\":{\"targetRevision\":\"$MYOWN_REVISION\"}}}" >/dev/null
fi
echo "root suit : $(kubectl get application root -n argocd -o jsonpath='{.spec.source.targetRevision}')"
kubectl apply -f gitops/bootstrap/argocd-ingress.yaml
svc_apply "$WANTED" "$DOMAIN_APPS"

if [ "$SKIP_MKCERT" != "1" ]; then
  step "Certificats TLS locaux (mkcert)"
  mkcert -install
  TMPDIR_CERTS="$(mktemp -d)"
  # service:host:namespace:secret — namespace explicite, pas dérivé du nom
  # d'hôte (myown-livekit-jwt.local vit dans « livekit », trouvé en vrai le
  # 2026-08-20, notes-techniques.md).
  for entry in \
    "vaultwarden:myown-vaultwarden.local:vaultwarden:vaultwarden-tls" \
    "nextcloud:myown-nextcloud.local:nextcloud:nextcloud-tls" \
    "tuwunel:myown-tuwunel.local:tuwunel:tuwunel-tls" \
    "livekit:myown-livekit.local:livekit:livekit-tls" \
    "livekit:myown-livekit-jwt.local:livekit:livekit-jwt-tls"; do
    IFS=: read -r svc host ns secret <<<"$entry"
    grep -qx "$svc" <<<"$WANTED" || continue
    mkcert -cert-file "$TMPDIR_CERTS/$host.pem" -key-file "$TMPDIR_CERTS/$host-key.pem" "$host"
    kubectl create namespace "$ns" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
    kubectl create secret tls "$secret" -n "$ns" \
      --cert="$TMPDIR_CERTS/$host.pem" --key="$TMPDIR_CERTS/$host-key.pem" \
      --dry-run=client -o yaml | kubectl apply -f -
  done
  for entry in "livekit:livekit" "uptime-kuma:monitoring"; do
    IFS=: read -r svc ns <<<"$entry"
    grep -qx "$svc" <<<"$WANTED" || continue
    kubectl create namespace "$ns" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
    kubectl create configmap mkcert-ca -n "$ns" --from-file=ca.pem="$(mkcert -CAROOT)/rootCA.pem" \
      --dry-run=client -o yaml | kubectl apply -f -
  done
  rm -rf "$TMPDIR_CERTS"
fi

if [ "$TARGET" = "k3d" ] && [ "$SKIP_HOSTS" != "1" ]; then
  step "Entrées /etc/hosts"
  MISSING=""
  for host in myown-argocd.local myown-grafana.local myown-uptime.local myown-authentik.local \
    myown-vaultwarden.local myown-nextcloud.local myown-immich.local myown-tuwunel.local \
    myown-livekit.local myown-livekit-jwt.local myown-ollama.local; do
    existing="$(awk -v h="$host" '$1 !~ /^#/ { for (i = 2; i <= NF; i++) if ($i == h) print $1 }' /etc/hosts | head -1)"
    if [ -z "$existing" ]; then
      MISSING="${MISSING}127.0.0.1 $host
"
    elif [ "$existing" != "127.0.0.1" ]; then
      # Ne jamais ajouter une 2e ligne contradictoire : c'est la 1re qui gagne,
      # le conflit resterait invisible (roadmap Phase 4, ambiguïté dev/minipc).
      echo "  $host pointe déjà vers $existing (pas 127.0.0.1) — laissé tel quel, à corriger à la main si ce n'est pas voulu."
    fi
  done
  if [ -n "$MISSING" ]; then
    echo "Ajout à /etc/hosts (sudo requis) :"
    echo -n "$MISSING"
    echo -n "$MISSING" | sudo tee -a /etc/hosts >/dev/null
  else
    echo "Rien à ajouter."
  fi
fi

step "Vérification"
echo "Les Applications convergent en arrière-plan (plusieurs minutes au premier lancement) :"
kubectl get applications -n argocd
cat <<EOF

Installation terminée.
  - Suivi : kubectl get applications -n argocd${KUBECONFIG:+   (KUBECONFIG=$KUBECONFIG)}
  - Ajouter ou arrêter un service plus tard : relancer ce script.
  - Usage de chaque service : docs/manuel-utilisateur.md
EOF
