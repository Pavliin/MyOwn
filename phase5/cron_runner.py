"""CronJob entrypoint — Phase 5 step 8's scheduling half, deliberately left
out of the PR that built the pipeline itself: a container image, a GitOps
Application, secrets wiring is materially different work from the
connector logic in orchestrator.py, which this only drives.

Runs inside the cluster (the CronJob manifest sets PHASE5_IN_CLUSTER=true)
— reaches Nextcloud/Ollama via in-cluster Service DNS
(cluster_target.py's third mode), Tuwunel/Mailu via their own
env-overridable hosts (TUWUNEL_URL, MAILU_IMAP_HOST) pointed at their
in-cluster Services too. No kubectl, no SSH, unlike every phase5/*.py
script run interactively so far in this project.

User list: PHASE5_USERS_JSON, a JSON array, one object per user this
CronJob processes — each one carries its own already-minted credentials
(nc_app_password, imap_password). Claude Code is blocked from minting
these (see user_memory.py/imap_connector.py's own usage notes) — this
list only grows as a human runs those one-off commands for each real
family member. Deliberately not derived automatically from
user_directory.py on every tick: that would call the Authentik/Nextcloud
APIs every 15 minutes for no benefit (the set of opted-in, credentialed
users changes rarely, a human already has to act — mint credentials —
every time it does).

One user's failure doesn't stop the others — logged and the run still
exits non-zero so a stuck user is visible in kubectl/CronJob history,
without blocking everyone else's mail from being checked that tick.

Usage (only meaningful inside the cluster; see gitops/manifests/phase5-mail/):
    export PHASE5_IN_CLUSTER=true
    export TUWUNEL_ALERTBOT_TOKEN=...
    export PHASE5_USERS_JSON='[{"matrix_id": "@robin:offsystem.fr", "nextcloud_uid": "...", "mailbox": "robin.chartier@offsystem.fr", "nc_app_password": "...", "imap_password": "..."}]'
    python3 cron_runner.py
"""

import json
import os
import sys

from orchestrator import process_user


def info(msg: str) -> None:
    print(f"[cron-runner] {msg}", file=sys.stderr)


def main() -> None:
    users_json = os.environ.get("PHASE5_USERS_JSON")
    if not users_json:
        raise SystemExit("Set PHASE5_USERS_JSON (see this script's usage notes).")
    users = json.loads(users_json)
    info(f"{len(users)} user(s) configured.")

    had_error = False
    for user in users:
        matrix_id = user.get("matrix_id", "?")
        try:
            process_user(
                matrix_id, user["nextcloud_uid"], user["mailbox"],
                user["imap_password"], user["nc_app_password"],
            )
        except Exception as e:
            info(f"Error processing {matrix_id}: {e!r}")
            had_error = True

    if had_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
