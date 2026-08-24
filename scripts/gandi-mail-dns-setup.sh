#!/usr/bin/env bash
# One-shot: creates the DNS records offsystem.fr needs for the VPS mail
# relay (mail-relay-vps/) — A for the MX hostname, MX itself, SPF, DKIM,
# DMARC. Reuses the same Gandi LiveDNS PUT pattern and PAT as the
# gitops/apps/gandi-dyndns.yaml CronJob (that one only ever touches the
# wildcard/apex records; this script is the one-time complement for the
# mail-specific ones it doesn't manage).
#
# Run this yourself, in your own terminal — it decrypts the Gandi PAT via
# sops, which the auto-mode classifier correctly won't let Claude Code do
# on your behalf (same boundary already hit for the WireGuard private
# key). Confirmed with the user before writing this script: no active
# Gandi mailbox exists on this domain, so overwriting its MX/SPF records
# is safe.
#
# Idempotent: Gandi's LiveDNS PUT replaces a record's value set, safe to
# re-run.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN="offsystem.fr"
VPS_IP="51.178.46.161"
DKIM_PUBKEY="MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA4b8snminDdyMHBfVqpXVU8SSeEsr7jGKuc4OUxANkZ1t1PLe7DDkSbl7SDaJHlZPwJHB+Nx8fiTkgLdbiQ7syZiUuNo2APYfV90RruXLL2a/oxyY+SG6mnkPbdC9/0X+B2iHYFPWsSkGVFgfZId4FF/8Ohj7asJwCLNIaNg0h208i4BChb7j8NvF7uJnkYAGHQz8M7l9MY4K/uWsB9hCkfwmi3HC8UiXTBBlY4ZhOjdnlyKUJTfo2ErWmis9QtLtgwuwRe4M4YKpxeKgjAUGRlrcxdjMXwZVnI1ac875610z2zbQNFyAEXhRIvW6il8l6SJ9QpHxn6UPwnEaoWj0nwIDAQAB"
DMARC_RUA="admin@${DOMAIN}"

step() { echo -e "\n\033[1;34m==> $1\033[0m"; }

command -v sops >/dev/null || { echo "Manquant : sops."; exit 1; }

step "Déchiffrement du token Gandi (SOPS, local, jamais transmis)"
TOKEN="$(sops -d --extract '["stringData"]["GANDIV5_PERSONAL_ACCESS_TOKEN"]' "$REPO_ROOT/gitops/secrets/gandi-dyndns/gandi-dyndns.sops.yaml")"

put_record() {
  local name="$1" type="$2" value="$3" ttl="${4:-3600}"
  curl -sf -X PUT \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"rrset_values\":[\"${value}\"],\"rrset_ttl\":${ttl}}" \
    "https://api.gandi.net/v5/livedns/domains/${DOMAIN}/records/${name}/${type}"
  echo "OK: ${type} ${name}.${DOMAIN} -> ${value}"
}

step "A mail.${DOMAIN} -> ${VPS_IP}"
put_record "mail" "A" "${VPS_IP}" 300

step "MX ${DOMAIN} -> 10 mail.${DOMAIN}."
put_record "@" "MX" "10 mail.${DOMAIN}." 3600

step "TXT SPF ${DOMAIN}"
put_record "@" "TXT" "v=spf1 ip4:${VPS_IP} ~all" 3600

step "TXT DKIM dkim._domainkey.${DOMAIN}"
put_record "dkim._domainkey" "TXT" "v=DKIM1; k=rsa; p=${DKIM_PUBKEY}" 3600

step "TXT DMARC _dmarc.${DOMAIN}"
put_record "_dmarc" "TXT" "v=DMARC1; p=none; rua=mailto:${DMARC_RUA}; fo=1" 3600

step "Terminé"
echo "Vérifie la propagation avec : dig +short MX ${DOMAIN} ; dig +short TXT ${DOMAIN} ; dig +short TXT dkim._domainkey.${DOMAIN} ; dig +short TXT _dmarc.${DOMAIN}"
