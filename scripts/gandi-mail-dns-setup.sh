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
# Regenerated 2026-09-07: the original key (extracted when this script was
# first written) had never actually been written to Mailu's persistent
# /dkim/ path — the admin pod's DKIM_PATH lookup returned nothing, so every
# outbound message sent through the client-facing submission ports (Android
# app validation) was going out completely unsigned despite this DNS record
# existing. Real domain-details-page crash traced to the same underlying
# gap (ValueError on an unrelated empty PORTS config, found while
# investigating) forced a pod restart, which is what surfaced the missing
# key in the first place. New key generated via the admin UI's own
# "Generate keys" button (Domains -> offsystem.fr) rather than by hand, so
# it's written to the correct on-disk path automatically.
DKIM_PUBKEY="MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtIhCVnD77B2f3/+8ppUJfhJN4kS3fmcnx0XnbqRahqIOOrOtD9OgFy1/3EVnvGl3fHNhPhnqcidrCcinb+Wzrqhujy//eDmGVR/LpReZL04cn7zrPvTfgEh/mmdfT9Iwcedn3mxxopZm7UccE85am6Gg/kitzdNRUzL2CS+AKKHPdl9IHmNKUM+tehJ9R92+H38BTOCL4n9wDqqkOew8oJJLwXZIXQyqoNKaTE4yuVxGD2UY3mk1GU0eMrcZLtzolI1/DCoyZO89nbM4+QQF3ziEDfhDEtUYHKvX4Nr9Xc9B1BRTs/wo9cPUScpu9hvrbherBRjreZMulf6fFp+54QIDAQAB"
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
