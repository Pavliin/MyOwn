#!/usr/bin/env bash
# Installs and configures Postfix on the VPS façade as a dumb relay for
# offsystem.fr: accepts mail on the public :25, forwards it straight to
# Mailu through the WireGuard mail-relay tunnel (wireguard-mail-relay/)
# via the transport map in mail-relay-vps/postfix/transport. No DKIM
# signing here — Rspamd already signs on the Mailu side, this VPS only
# relays bytes.
#
# Meant to run from the machine holding this git repo (dev today) — like
# scripts/wireguard-mail-relay-setup.sh, it applies everything on the VPS
# remotely over SSH (passwordless sudo on the `ubuntu` account, see
# notes-techniques.md's "VPS façade OVH" section). Idempotent: safe to
# re-run after editing mail-relay-vps/postfix/transport or this script.
#
# Env vars (all optional):
#   MYOWN_PFVPS_VPS_HOST     ssh user@host, default "ubuntu@51.178.46.161"
#   MYOWN_PFVPS_VPS_SSH_KEY  default "$HOME/.ssh/id_ed25519_ovh_vps"
#   MYOWN_PFVPS_MAILNAME     the relay's own hostname (myhostname), default
#                             "mail.offsystem.fr" — matches the future MX
#                             record, deliberately distinct from
#                             mailu.offsystem.fr (webmail/admin at home)
#   MYOWN_PFVPS_RELAY_DOMAIN default "offsystem.fr"
#   MYOWN_PFVPS_TUNNEL_SUBNET default "10.100.1.0/24" — added to
#                             mynetworks so Mailu's outbound mail relays
#                             through here without SMTP AUTH (the tunnel
#                             itself is the authentication)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VPS_HOST="${MYOWN_PFVPS_VPS_HOST:-ubuntu@51.178.46.161}"
VPS_SSH_KEY="${MYOWN_PFVPS_VPS_SSH_KEY:-$HOME/.ssh/id_ed25519_ovh_vps}"
MAILNAME="${MYOWN_PFVPS_MAILNAME:-mail.offsystem.fr}"
RELAY_DOMAIN="${MYOWN_PFVPS_RELAY_DOMAIN:-offsystem.fr}"
TUNNEL_SUBNET="${MYOWN_PFVPS_TUNNEL_SUBNET:-10.100.1.0/24}"
TRANSPORT_FILE="$REPO_ROOT/mail-relay-vps/postfix/transport"

step() { echo -e "\n\033[1;34m==> $1\033[0m"; }

[ -f "$TRANSPORT_FILE" ] || { echo "Introuvable : $TRANSPORT_FILE"; exit 1; }

step "Copie de la table de transport sur le VPS"
scp -i "$VPS_SSH_KEY" "$TRANSPORT_FILE" "$VPS_HOST:/tmp/postfix-transport"

step "Installation + configuration Postfix (via SSH, sudo sans mot de passe)"
ssh -i "$VPS_SSH_KEY" "$VPS_HOST" "
  set -e

  if ! dpkg -l postfix >/dev/null 2>&1; then
    echo 'postfix postfix/main_mailer_type select Internet Site' | sudo debconf-set-selections
    echo 'postfix postfix/mailname string ${MAILNAME}' | sudo debconf-set-selections
    sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postfix
  else
    echo 'postfix déjà installé, on ne touche que la config.'
  fi

  sudo postconf -e \"myhostname = ${MAILNAME}\"
  sudo postconf -e \"mydestination = \\\$myhostname, localhost.\\\$mydomain, localhost\"
  sudo postconf -e \"relay_domains = ${RELAY_DOMAIN}\"
  sudo postconf -e \"transport_maps = hash:/etc/postfix/transport\"
  sudo postconf -e \"mynetworks = 127.0.0.0/8 [::1]/128 ${TUNNEL_SUBNET}\"
  sudo postconf -e \"inet_interfaces = all\"
  sudo postconf -e \"smtp_tls_security_level = may\"
  sudo postconf -e \"smtpd_tls_security_level = may\"
  # Real bug found via a live outbound test: this VPS has native IPv6
  # (OVH default), and Postfix's default address_preference let it pick
  # IPv6 to reach Gmail — but SPF/PTR here are deliberately IPv4-only
  # (matches this project's existing stance of deferring IPv6 as a
  # separate chantier, see notes-techniques.md). Gmail bounced with
  # \"SPF ... did not pass\" because it checked the IPv6 source against
  # an SPF record that only lists ip4:. Forcing IPv4 preference keeps
  # outbound consistent with what's actually authenticated, without
  # taking on a full IPv6 SPF/reverse-DNS setup now.
  sudo postconf -e \"smtp_address_preference = ipv4\"

  sudo cp /tmp/postfix-transport /etc/postfix/transport
  sudo postmap /etc/postfix/transport
  shred -u /tmp/postfix-transport

  sudo postfix check
  sudo systemctl reload postfix 2>/dev/null || sudo systemctl restart postfix
  sudo systemctl enable postfix >/dev/null

  sudo ufw allow 25/tcp >/dev/null
  sudo systemctl is-active postfix
  sudo postconf relay_domains transport_maps mynetworks myhostname mydestination
"

step "Terminé"
echo "Postfix actif sur le VPS, relay_domains=${RELAY_DOMAIN} -> transport vers ${TUNNEL_SUBNET%.*}.2:25 via le tunnel."
echo "Prochaine étape : test interne (mail envoyé depuis le VPS vers une adresse @${RELAY_DOMAIN}, confirmé reçu côté Mailu), avant tout DNS public."
