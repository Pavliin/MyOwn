"""Posts a family-facing announcement to the shared #etat-du-systeme
Matrix room, using the same alertbot account as Uptime Kuma's alerting
(deliberately reused — same "what's going on with our system?" channel
from the family's point of view, cf. architecture.md §6).

Intended for the sensitive-service update workflow: notify before a
manual ArgoCD sync goes out for a family-facing service, so people get
a heads-up instead of an unannounced change (cf. architecture.md §6,
"Canal d'annonce familial").

Usage:
    TUWUNEL_ALERTBOT_TOKEN=... TUWUNEL_ALERT_ROOM_ID=... \
      python3 tuwunel-announce.py "Nextcloud : mise a jour ce soir a 22h, ~10 min d'interruption prevue."

Credentials: gitops/secrets/uptime-kuma/uptime-kuma.sops.yaml
"""

import os
import sys
import time

import requests

TUWUNEL_URL = "https://myown-tuwunel.local:8453"
ROOM_ID = os.environ.get("TUWUNEL_ALERT_ROOM_ID")
TOKEN = os.environ.get("TUWUNEL_ALERTBOT_TOKEN")


def main():
    if not ROOM_ID or not TOKEN:
        print("Set TUWUNEL_ALERTBOT_TOKEN and TUWUNEL_ALERT_ROOM_ID (see gitops/secrets/uptime-kuma/).", file=sys.stderr)
        sys.exit(1)
    if len(sys.argv) < 2:
        print("Usage: tuwunel-announce.py \"message\"", file=sys.stderr)
        sys.exit(1)

    message = f"📢 {sys.argv[1]}"
    txn_id = str(int(time.time() * 1000))
    room_id_encoded = ROOM_ID.replace("!", "%21").replace(":", "%3A")

    r = requests.put(
        f"{TUWUNEL_URL}/_matrix/client/v3/rooms/{room_id_encoded}/send/m.room.message/{txn_id}",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={"msgtype": "m.text", "body": message},
    )
    r.raise_for_status()
    print(f"Annonce envoyee (event {r.json()['event_id']})")


if __name__ == "__main__":
    main()
