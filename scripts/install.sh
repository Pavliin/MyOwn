#!/usr/bin/env bash
# Automates manuel-installation.md end to end (sections 2-11 — run this
# from inside an already-cloned checkout, section 1 is just `git clone`).
#
# Prototype for Phase 6's "installeur pour utilisateurs non-techos"
# (installation-utilisateur.md): a single script rather than an ISO,
# relying on the OS's own installer for everything below the app layer.
# Palier 2 today ("un script à lancer") — sane defaults, minimal
# prompts, not yet the guided palier-3 experience.
#
# Overridable via env vars for testing against a throwaway cluster
# without touching a real myown-dev instance (used to validate this
# script itself — see notes-techniques.md):
#   MYOWN_CLUSTER_NAME, MYOWN_PORT_HTTP, MYOWN_PORT_HTTPS, MYOWN_PORT_443,
#   MYOWN_PORT_LIVEKIT_WS, MYOWN_PORT_LIVEKIT_TCP, MYOWN_PORT_LIVEKIT_UDP,
#   MYOWN_SKIP_HOSTS (1 to skip the /etc/hosts step, e.g. in a sandbox
#   without interactive sudo), MYOWN_SKIP_MKCERT (1 to skip TLS certs).

set -euo pipefail

CLUSTER_NAME="${MYOWN_CLUSTER_NAME:-myown-dev}"
PORT_HTTP="${MYOWN_PORT_HTTP:-8090}"
PORT_HTTPS="${MYOWN_PORT_HTTPS:-8453}"
PORT_443="${MYOWN_PORT_443:-443}"
PORT_LK_WS="${MYOWN_PORT_LIVEKIT_WS:-7880}"
PORT_LK_TCP="${MYOWN_PORT_LIVEKIT_TCP:-7881}"
PORT_LK_UDP="${MYOWN_PORT_LIVEKIT_UDP:-7882}"
SKIP_HOSTS="${MYOWN_SKIP_HOSTS:-0}"
SKIP_MKCERT="${MYOWN_SKIP_MKCERT:-0}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

step() { echo -e "\n\033[1;34m==> $1\033[0m"; }

step "Vérification des outils requis"
for tool in docker git kubectl helm k3d; do
  command -v "$tool" >/dev/null || { echo "Manquant : $tool — installez-le puis relancez."; exit 1; }
done
if ! command -v sops >/dev/null; then
  echo "sops absent, installation..."
  mkdir -p ~/.local/bin
  curl -fsSL -o ~/.local/bin/sops \
    https://github.com/getsops/sops/releases/download/v3.10.2/sops-v3.10.2.linux.amd64
  chmod +x ~/.local/bin/sops
  export PATH="$HOME/.local/bin:$PATH"
fi
command -v age-keygen >/dev/null || { echo "Manquant : age-keygen — installez le paquet 'age' puis relancez."; exit 1; }
if [ "$SKIP_MKCERT" != "1" ]; then
  command -v mkcert >/dev/null || { echo "Manquant : mkcert — installez-le puis relancez (ou MYOWN_SKIP_MKCERT=1)."; exit 1; }
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

step "Création du cluster k3d ($CLUSTER_NAME)"
if k3d cluster list 2>/dev/null | grep -q "^${CLUSTER_NAME} "; then
  echo "Cluster $CLUSTER_NAME déjà présent, réutilisation."
else
  k3d cluster create "$CLUSTER_NAME" \
    -p "${PORT_HTTP}:80@loadbalancer" -p "${PORT_HTTPS}:443@loadbalancer" -p "${PORT_443}:443@loadbalancer" \
    -p "${PORT_LK_WS}:7880@loadbalancer" -p "${PORT_LK_TCP}:7881@loadbalancer" -p "${PORT_LK_UDP}:7882/udp@loadbalancer" \
    --wait
fi
kubectl config use-context "k3d-${CLUSTER_NAME}"

step "Installation d'ArgoCD"
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd --server-side --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=available --timeout=180s deployment --all -n argocd
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

step "Health check ArgoCD pour Prometheus Operator"
kubectl patch configmap argocd-cm -n argocd --type merge \
  --patch-file gitops/bootstrap/argocd-cm-health-checks-patch.yaml

step "Bootstrap GitOps"
kubectl apply -f gitops/bootstrap/root-app.yaml
kubectl apply -f gitops/bootstrap/argocd-ingress.yaml

if [ "$SKIP_MKCERT" != "1" ]; then
  step "Certificats TLS locaux (mkcert)"
  mkcert -install
  TMPDIR_CERTS="$(mktemp -d)"
  for host in myown-vaultwarden.local myown-nextcloud.local myown-tuwunel.local myown-livekit.local myown-livekit-jwt.local; do
    ns="${host#myown-}"; ns="${ns%.local}"
    secret="${ns}-tls"
    mkcert -cert-file "$TMPDIR_CERTS/$host.pem" -key-file "$TMPDIR_CERTS/$host-key.pem" "$host"
    kubectl create namespace "$ns" --dry-run=client -o yaml | kubectl apply -f - >/dev/null 2>&1 || true
    kubectl create secret tls "$secret" -n "$ns" \
      --cert="$TMPDIR_CERTS/$host.pem" --key="$TMPDIR_CERTS/$host-key.pem" \
      --dry-run=client -o yaml | kubectl apply -f - 2>/dev/null || \
      echo "  (namespace $ns pas encore créé par ArgoCD — le secret sera à recréer une fois le service déployé)"
  done
  for ns in livekit monitoring; do
    kubectl create configmap mkcert-ca -n "$ns" --from-file=ca.pem="$(mkcert -CAROOT)/rootCA.pem" \
      --dry-run=client -o yaml | kubectl apply -f - 2>/dev/null || \
      echo "  (namespace $ns pas encore créé — ConfigMap mkcert-ca à recréer une fois le service déployé)"
  done
  rm -rf "$TMPDIR_CERTS"
fi

if [ "$SKIP_HOSTS" != "1" ]; then
  step "Entrées /etc/hosts"
  HOSTS_LINES="127.0.0.1 myown-argocd.local
127.0.0.1 myown-grafana.local
127.0.0.1 myown-uptime.local
127.0.0.1 myown-authentik.local
127.0.0.1 myown-vaultwarden.local
127.0.0.1 myown-nextcloud.local
127.0.0.1 myown-immich.local
127.0.0.1 myown-tuwunel.local
127.0.0.1 myown-livekit.local
127.0.0.1 myown-livekit-jwt.local
127.0.0.1 myown-ollama.local"
  MISSING=""
  while IFS= read -r line; do
    grep -qF "$line" /etc/hosts || MISSING="${MISSING}${line}
"
  done <<< "$HOSTS_LINES"
  if [ -n "$MISSING" ]; then
    echo "Ajout à /etc/hosts (sudo requis) :"
    echo "$MISSING"
    echo "$MISSING" | sudo tee -a /etc/hosts >/dev/null
  else
    echo "Déjà à jour."
  fi
fi

step "Vérification"
echo "Attente de la convergence des Applications ArgoCD (peut prendre plusieurs minutes)..."
kubectl get application -n argocd
echo -e "\nInstallation terminée. Détail de chaque service : manuel-utilisateur.md"
