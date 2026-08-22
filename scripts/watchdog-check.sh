#!/usr/bin/env bash
# Checks k3s API health and, after MYOWN_WD_THRESHOLD consecutive
# failures, restarts the k3s service automatically — no human
# intervention needed for the common case. See architecture.md §6 and
# wireguard/README.md for why this runs on the host, outside the
# cluster it watches: if it lived inside, a total cluster outage would
# take the thing meant to fix it down too.
#
# Installed to /usr/local/bin/myown-watchdog-check.sh and triggered
# every 60s by the myown-watchdog.timer unit — see watchdog-setup.sh.
# Not meant to be run manually except for testing.
#
# State persisted across runs in STATE_DIR (each run is a fresh
# short-lived process, triggered by the timer, nothing survives in
# memory between runs):
#   failcount               consecutive failed health checks
#   remediation-timestamps  one unix timestamp per restart attempt,
#                           used to rate-limit remediation attempts
#   gave-up                 marker: already sent the "giving up" alert
#                           for the *current* incident, cleared once
#                           healthy again
#   pending-notifications   queued Tuwunel messages, tab-separated
#                           (timestamp, text) — see the honest
#                           limitation below
#
# Alerting limitation, stated plainly rather than glossed over: Tuwunel
# itself runs inside the cluster this watchdog watches, so a message
# can only be delivered once the cluster is actually reachable again.
# During a total outage nothing can be sent in real time — this is the
# same blind spot already consciously accepted for Uptime Kuma
# (roadmap.md). Queuing notifications and flushing them on the first
# healthy tick afterwards covers the common case (transient failure,
# self-healed) close to real time, and still gives after-the-fact
# visibility for the worst case (gave up after the remediation cap).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${MYOWN_WD_STATE_DIR:-/var/lib/myown-watchdog}"
SECRETS_FILE="$REPO_ROOT/gitops/secrets/uptime-kuma/uptime-kuma.sops.yaml"

THRESHOLD="${MYOWN_WD_THRESHOLD:-3}"
MAX_REMEDIATIONS_PER_HOUR="${MYOWN_WD_MAX_REMEDIATIONS_PER_HOUR:-3}"
WINDOW_SECONDS=3600
TUWUNEL_URL="${MYOWN_WD_TUWUNEL_URL:-https://tuwunel.offsystem.fr}"

FAILCOUNT_FILE="$STATE_DIR/failcount"
REMEDIATIONS_FILE="$STATE_DIR/remediation-timestamps"
GAVE_UP_FILE="$STATE_DIR/gave-up"
PENDING_FILE="$STATE_DIR/pending-notifications"

mkdir -p "$STATE_DIR"
touch "$REMEDIATIONS_FILE" "$PENDING_FILE"
[ -s "$FAILCOUNT_FILE" ] || echo 0 > "$FAILCOUNT_FILE"

log() {
    logger -t myown-watchdog -- "$1"
}

queue_notification() {
    printf '%s\t%s\n' "$(date +%s)" "$1" >> "$PENDING_FILE"
}

k3s_healthy() {
    k3s kubectl get --raw /healthz --request-timeout=5s >/dev/null 2>&1
}

send_tuwunel_message() {
    local token="$1" room="$2" msg="$3"
    local room_enc="${room//!/%21}"
    room_enc="${room_enc//:/%3A}"
    local txn
    txn="$(date +%s%N)"
    curl -sf --max-time 10 -X PUT \
        "${TUWUNEL_URL}/_matrix/client/v3/rooms/${room_enc}/send/m.room.message/${txn}" \
        -H "Authorization: Bearer ${token}" \
        -H "Content-Type: application/json" \
        -d "{\"msgtype\":\"m.text\",\"body\":\"[MyOwn Watchdog] ${msg}\"}" \
        >/dev/null 2>&1
}

flush_pending_notifications() {
    [ -s "$PENDING_FILE" ] || return 0
    k3s_healthy || return 0

    if ! command -v sops >/dev/null 2>&1; then
        log "sops introuvable — notifications en attente non envoyées"
        return 0
    fi

    local creds
    if ! creds="$(sops -d "$SECRETS_FILE" 2>/dev/null)"; then
        log "échec du déchiffrement de $SECRETS_FILE — notifications en attente non envoyées"
        return 0
    fi

    local token room
    token="$(printf '%s\n' "$creds" | grep '^TUWUNEL_ALERTBOT_TOKEN:' | sed "s/^[^:]*: *//;s/^'//;s/'\$//")"
    room="$(printf '%s\n' "$creds" | grep '^TUWUNEL_ALERT_ROOM_ID:' | sed "s/^[^:]*: *//;s/^'//;s/'\$//")"
    if [ -z "$token" ] || [ -z "$room" ]; then
        log "jeton/salon alertbot introuvable dans $SECRETS_FILE — notifications en attente non envoyées"
        return 0
    fi

    local tmp_remaining
    tmp_remaining="$(mktemp)"
    while IFS=$'\t' read -r ts msg; do
        [ -n "${msg:-}" ] || continue
        if send_tuwunel_message "$token" "$room" "$msg"; then
            log "notification envoyée: $msg"
        else
            printf '%s\t%s\n' "$ts" "$msg" >> "$tmp_remaining"
        fi
    done < "$PENDING_FILE"
    mv "$tmp_remaining" "$PENDING_FILE"
}

if k3s_healthy; then
    echo 0 > "$FAILCOUNT_FILE"
    rm -f "$GAVE_UP_FILE"
    flush_pending_notifications
    exit 0
fi

FAILCOUNT=$(($(cat "$FAILCOUNT_FILE") + 1))
echo "$FAILCOUNT" > "$FAILCOUNT_FILE"
log "échec du contrôle de santé k3s ($FAILCOUNT/$THRESHOLD consécutifs)"

if [ "$FAILCOUNT" -lt "$THRESHOLD" ]; then
    exit 0
fi

NOW=$(date +%s)
CUTOFF=$((NOW - WINDOW_SECONDS))
RECENT=$(awk -v cutoff="$CUTOFF" '$1 > cutoff' "$REMEDIATIONS_FILE" | wc -l)

if [ "$RECENT" -ge "$MAX_REMEDIATIONS_PER_HOUR" ]; then
    if [ ! -f "$GAVE_UP_FILE" ]; then
        log "seuil atteint mais $MAX_REMEDIATIONS_PER_HOUR remédiations déjà tentées dans la dernière heure — abandon, intervention humaine nécessaire"
        queue_notification "Watchdog : le cluster reste indisponible malgré $MAX_REMEDIATIONS_PER_HOUR redémarrages tentés dans la dernière heure. Le watchdog abandonne — intervention manuelle nécessaire (VPN admin)."
        touch "$GAVE_UP_FILE"
    fi
    exit 0
fi

log "seuil atteint, redémarrage de k3s"
echo "$NOW" >> "$REMEDIATIONS_FILE"
queue_notification "Watchdog : le cluster ne répondait plus depuis $((THRESHOLD * 60))s, redémarrage automatique de k3s tenté."
systemctl restart k3s
echo 0 > "$FAILCOUNT_FILE"
