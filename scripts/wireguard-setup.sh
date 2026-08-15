#!/usr/bin/env bash
# Bootstraps (first run) or extends (subsequent runs) the host-level
# WireGuard admin-access VPN — see wireguard/README.md for why this is
# deliberately NOT a Kubernetes manifest (circular dependency: the VPN
# gates access to the cluster, so it can't live inside the cluster it
# gates).
#
# Needs interactive sudo (package install, /etc/wireguard/, systemd) —
# run this yourself in your own terminal, never via an automated tool.
#
# Env vars (all optional, sane defaults for the current dev/LAN setup):
#   MYOWN_WG_SUBNET_PREFIX  first three octets of the tunnel subnet,
#                           default "10.100.0" (server = .1, peers = .2+)
#   MYOWN_WG_PORT           UDP listen port, default 51820 (WireGuard's
#                           IANA-assigned default)
#   MYOWN_WG_IFACE          interface name, default "wg0"
#   MYOWN_WG_ENDPOINT       host:port peers dial to reach the server;
#                           default auto-detected LAN IP (fine for a
#                           same-LAN test today — replace with the real
#                           domain once port-forwarding exists, Phase 4)
#   MYOWN_WG_PEER_NAME      name for the peer this run creates; default
#                           "admin" on first bootstrap, REQUIRED (no
#                           default) on later runs to avoid clobbering
#
# First run: generates the server identity + one peer, installs and
# starts the service. Later runs (config already exists): add a new
# peer to the existing server without touching its identity or
# already-issued peers.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONF_ENC="$REPO_ROOT/wireguard/wg0.conf.sops.yaml"

SUBNET="${MYOWN_WG_SUBNET_PREFIX:-10.100.0}"
PORT="${MYOWN_WG_PORT:-51820}"
IFACE="${MYOWN_WG_IFACE:-wg0}"
ENDPOINT="${MYOWN_WG_ENDPOINT:-}"

step() { echo -e "\n\033[1;34m==> $1\033[0m"; }

step "Vérification des outils requis"
command -v sops >/dev/null || { echo "Manquant : sops (voir manuel-installation.md)."; exit 1; }
if ! command -v wg >/dev/null; then
  echo "wireguard-tools absent, installation (sudo requis)..."
  sudo apt-get update && sudo apt-get install -y wireguard-tools
fi

if [ -z "$ENDPOINT" ]; then
  LAN_IP="$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i=="src") print $(i+1)}')"
  if [ -z "$LAN_IP" ]; then
    echo "Impossible de détecter une IP locale automatiquement — définissez MYOWN_WG_ENDPOINT." >&2
    exit 1
  fi
  ENDPOINT="${LAN_IP}:${PORT}"
  echo "MYOWN_WG_ENDPOINT non défini, utilisation de l'IP LAN détectée : $ENDPOINT (à remplacer par le vrai domaine en Phase 4)."
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT
umask 077

if [ ! -f "$CONF_ENC" ]; then
  step "Amorçage : première configuration du serveur WireGuard"
  PEER_NAME="${MYOWN_WG_PEER_NAME:-admin}"
  SERVER_PRIV="$(wg genkey)"
  SERVER_PUB="$(echo "$SERVER_PRIV" | wg pubkey)"
  PEER_PRIV="$(wg genkey)"
  PEER_PUB="$(echo "$PEER_PRIV" | wg pubkey)"
  SERVER_IP="${SUBNET}.1"
  PEER_IP="${SUBNET}.2"

  cat > "$WORKDIR/wg0.conf" <<EOF
[Interface]
PrivateKey = $SERVER_PRIV
Address = ${SERVER_IP}/24
ListenPort = $PORT

[Peer]
# $PEER_NAME
PublicKey = $PEER_PUB
AllowedIPs = ${PEER_IP}/32
EOF
else
  step "Ajout d'un pair à la configuration existante"
  PEER_NAME="${MYOWN_WG_PEER_NAME:?Définissez MYOWN_WG_PEER_NAME pour identifier ce nouveau pair.}"
  DECRYPTED="$(sops -d --extract '["wg0.conf"]' "$CONF_ENC")"
  SERVER_PRIV="$(echo "$DECRYPTED" | awk -F' = ' '/^PrivateKey/{print $2; exit}')"
  SERVER_PUB="$(echo "$SERVER_PRIV" | wg pubkey)"
  LAST_OCTET="$(echo "$DECRYPTED" | grep -oP "AllowedIPs = ${SUBNET//./\\.}\.\K[0-9]+" | sort -n | tail -1)"
  PEER_IP="${SUBNET}.$((LAST_OCTET + 1))"
  PEER_PRIV="$(wg genkey)"
  PEER_PUB="$(echo "$PEER_PRIV" | wg pubkey)"

  {
    echo "$DECRYPTED"
    echo ""
    echo "[Peer]"
    echo "# $PEER_NAME"
    echo "PublicKey = $PEER_PUB"
    echo "AllowedIPs = ${PEER_IP}/32"
  } > "$WORKDIR/wg0.conf"
fi

step "Chiffrement de la configuration serveur (SOPS)"
{
  echo 'wg0.conf: |'
  sed 's/^/  /' "$WORKDIR/wg0.conf"
} > "$WORKDIR/wg0.conf.sops.yaml"
mkdir -p "$REPO_ROOT/wireguard"
cp "$WORKDIR/wg0.conf.sops.yaml" "$CONF_ENC"
sops --encrypt --in-place "$CONF_ENC"
echo "Écrit et chiffré : ${CONF_ENC#"$REPO_ROOT"/}"

step "Installation sur l'hôte (/etc/wireguard/$IFACE.conf, sudo requis)"
sudo install -d -m 700 /etc/wireguard
sudo cp "$WORKDIR/wg0.conf" "/etc/wireguard/$IFACE.conf"
sudo chmod 600 "/etc/wireguard/$IFACE.conf"
sudo systemctl enable --now "wg-quick@$IFACE"
sudo systemctl status "wg-quick@$IFACE" --no-pager || true

CLIENT_CONF="$HOME/myown-wireguard-${PEER_NAME}.conf"
cat > "$CLIENT_CONF" <<EOF
[Interface]
PrivateKey = $PEER_PRIV
Address = ${PEER_IP}/32

[Peer]
PublicKey = $SERVER_PUB
Endpoint = $ENDPOINT
AllowedIPs = ${SUBNET}.0/24
PersistentKeepalive = 25
EOF
chmod 600 "$CLIENT_CONF"

step "Terminé"
echo "Config cliente pour '$PEER_NAME' écrite hors dépôt : $CLIENT_CONF"
echo "  - Jamais commitée, même chiffrée (cf. wireguard/README.md) — à transférer directement à l'appareil de l'admin."
echo "  - Import direct dans l'app WireGuard, ou générer un QR code : qrencode -t ansiutf8 < $CLIENT_CONF"
echo ""
echo "Vérification côté serveur : sudo wg show"
echo "AllowedIPs actuel du client est volontairement limité au sous-réseau du tunnel (${SUBNET}.0/24)"
echo "— pas de full-tunnel. Route vers les services internes du cluster (ArgoCD, API k8s) : à ajouter en Phase 4"
echo "une fois le vrai nœud (mini PC + pare-feu réel) en place, cf. roadmap.md."
