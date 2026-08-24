#!/usr/bin/env bash
# Bootstraps (first run) or extends (subsequent runs) the WireGuard tunnel
# between the VPS façade and the "home" machine that hosts Mailu — see
# wireguard-mail-relay/README.md for why this is a separate tunnel from the
# admin VPN (wireguard/), and why the server role is inverted (VPS = server,
# home = client) compared to it.
#
# Unlike scripts/wireguard-setup.sh (meant to run ON the server machine
# itself), this one is meant to run on the machine that has this git repo +
# the sops age key (the dev machine today) — it applies the server side on
# the VPS *remotely* over SSH (the `ubuntu` account there has passwordless
# sudo, see notes-techniques.md), then writes the resulting client config
# locally for the "home" side. Installing that client config still needs
# interactive sudo (package install if missing, /etc/wireguard/, systemd) —
# not available to Claude Code in this environment — so that last step is
# printed for the user to run themselves, same spirit as wireguard-setup.sh.
#
# Env vars (all optional, sane defaults for the current VPS/dev setup):
#   MYOWN_WGMAIL_VPS_HOST     ssh user@host for the VPS, default
#                             "ubuntu@51.178.46.161"
#   MYOWN_WGMAIL_VPS_SSH_KEY  path to the VPS SSH private key, default
#                             "$HOME/.ssh/id_ed25519_ovh_vps"
#   MYOWN_WGMAIL_SUBNET_PREFIX  first three octets of the tunnel subnet,
#                             default "10.100.1" (server = .1, peers = .2+)
#                             — deliberately different from the admin VPN's
#                             10.100.0.0/24
#   MYOWN_WGMAIL_PORT         UDP listen port, default 51821 (admin VPN
#                             uses 51820 — kept distinct)
#   MYOWN_WGMAIL_IFACE        interface name, default "wg-mail0"
#   MYOWN_WGMAIL_PEER_NAME    name for the peer this run creates; default
#                             "dev-machine" on first bootstrap, REQUIRED
#                             (no default) on later runs to avoid clobbering
#
# First run: generates the server identity + one peer, applies it on the
# VPS over SSH. Later runs (config already exists): add a new peer (e.g.
# the mini PC once Mailu migrates there) without touching the server's
# identity or already-issued peers.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONF_ENC="$REPO_ROOT/wireguard-mail-relay/wg-mail0.conf.sops.yaml"

VPS_HOST="${MYOWN_WGMAIL_VPS_HOST:-ubuntu@51.178.46.161}"
VPS_SSH_KEY="${MYOWN_WGMAIL_VPS_SSH_KEY:-$HOME/.ssh/id_ed25519_ovh_vps}"
SUBNET="${MYOWN_WGMAIL_SUBNET_PREFIX:-10.100.1}"
PORT="${MYOWN_WGMAIL_PORT:-51821}"
IFACE="${MYOWN_WGMAIL_IFACE:-wg-mail0}"

step() { echo -e "\n\033[1;34m==> $1\033[0m"; }

step "Vérification des outils requis"
command -v sops >/dev/null || { echo "Manquant : sops (voir manuel-installation.md)."; exit 1; }
command -v wg >/dev/null || { echo "Manquant : wireguard-tools (pour générer les clés localement)."; exit 1; }

VPS_ENDPOINT="${VPS_HOST#*@}:${PORT}"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT
umask 077

if [ ! -f "$CONF_ENC" ]; then
  step "Amorçage : première configuration du serveur (sur le VPS)"
  PEER_NAME="${MYOWN_WGMAIL_PEER_NAME:-dev-machine}"
  SERVER_PRIV="$(wg genkey)"
  SERVER_PUB="$(echo "$SERVER_PRIV" | wg pubkey)"
  PEER_PRIV="$(wg genkey)"
  PEER_PUB="$(echo "$PEER_PRIV" | wg pubkey)"
  SERVER_IP="${SUBNET}.1"
  PEER_IP="${SUBNET}.2"

  cat > "$WORKDIR/$IFACE.conf" <<EOF
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
  PEER_NAME="${MYOWN_WGMAIL_PEER_NAME:?Définissez MYOWN_WGMAIL_PEER_NAME pour identifier ce nouveau pair.}"
  DECRYPTED="$(sops -d --extract "[\"$IFACE.conf\"]" "$CONF_ENC")"
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
  } > "$WORKDIR/$IFACE.conf"
fi

step "Chiffrement de la configuration serveur (SOPS)"
{
  echo "$IFACE.conf: |"
  sed 's/^/  /' "$WORKDIR/$IFACE.conf"
} > "$WORKDIR/$IFACE.conf.sops.yaml"
mkdir -p "$REPO_ROOT/wireguard-mail-relay"
cp "$WORKDIR/$IFACE.conf.sops.yaml" "$CONF_ENC"
sops --encrypt --in-place "$CONF_ENC"
echo "Écrit et chiffré : ${CONF_ENC#"$REPO_ROOT"/}"

step "Application sur le VPS (via SSH, sudo sans mot de passe)"
scp -i "$VPS_SSH_KEY" "$WORKDIR/$IFACE.conf" "$VPS_HOST:/tmp/$IFACE.conf"
ssh -i "$VPS_SSH_KEY" "$VPS_HOST" "
  set -e
  which wg >/dev/null || (sudo apt-get update -qq && sudo apt-get install -y -qq wireguard-tools)
  sudo install -d -m 700 /etc/wireguard
  sudo cp /tmp/$IFACE.conf /etc/wireguard/$IFACE.conf
  sudo chmod 600 /etc/wireguard/$IFACE.conf
  shred -u /tmp/$IFACE.conf
  sudo systemctl enable --now wg-quick@$IFACE
  sudo ufw allow $PORT/udp
  sudo wg show $IFACE
"

CLIENT_CONF="$HOME/myown-wireguard-mail-${PEER_NAME}.conf"
cat > "$CLIENT_CONF" <<EOF
[Interface]
PrivateKey = $PEER_PRIV
Address = ${PEER_IP}/32

[Peer]
PublicKey = $SERVER_PUB
Endpoint = $VPS_ENDPOINT
AllowedIPs = ${SUBNET}.0/24
PersistentKeepalive = 25
EOF
chmod 600 "$CLIENT_CONF"

step "Terminé côté serveur"
echo "Config cliente pour '$PEER_NAME' écrite hors dépôt : $CLIENT_CONF"
echo "  - Jamais commitée, même chiffrée (cf. wireguard-mail-relay/README.md)."
echo ""
echo "Reste à appliquer toi-même (sudo interactif requis) sur la machine '$PEER_NAME' :"
echo "  sudo install -d -m 700 /etc/wireguard"
echo "  sudo cp $CLIENT_CONF /etc/wireguard/$IFACE.conf"
echo "  sudo chmod 600 /etc/wireguard/$IFACE.conf"
echo "  sudo systemctl enable --now wg-quick@$IFACE"
echo "  sudo wg show $IFACE"
