"""Matrix DM channel for AI proposals — step 3 of the Phase 5 planning
doc's implementation plan.

Reuses the existing @alertbot account (already registered for admin
alerting, gitops/secrets/uptime-kuma/) but strictly in DM mode: personal
proposals go out as a private 1:1 room per person, never the shared
#etat-du-systeme room infra alerts use — a distinction already decided in
the planning doc and installation-utilisateur.md, not something this
module should be able to get wrong by accident (there's no code path here
that can post to a room other than the target's own DM).

Replaces the 2026-09-16 prototype's history-polling with a real `/sync`
long-poll, the exact reste-à-faire item the planning doc names.

DM room reuse: Matrix has no server-side concept of "the" DM with someone
— this reads/writes the bot's own `m.direct` account_data, the same
client-side convention Element itself uses, so a Phase 5 run doesn't
create a fresh room every time it has something to propose.

Usage:
    export TUWUNEL_ALERTBOT_TOKEN=$(sops -d gitops/secrets/uptime-kuma/uptime-kuma.sops.yaml | yq '.stringData.TUWUNEL_ALERTBOT_TOKEN')
    python3 phase5/matrix_dm.py @akadmin:offsystem.fr "Un test de proposition. Réponds oui ou non."
    # Sends, then blocks on a real /sync long-poll (up to 5 min) for a
    # reply, and prints it.

Requires the target user to already exist on the homeserver (logged in at
least once via SSO) — Matrix can't invite an account nobody has created
yet, confirmed live against the dev cluster: a profile lookup for
@akadmin:offsystem.fr 404s until that first login happens.
"""

import json
import os
import sys
import time

import requests

BASE = os.environ.get("TUWUNEL_URL", "https://myown-tuwunel.local:8453")
TOKEN = os.environ.get("TUWUNEL_ALERTBOT_TOKEN")
BOT_USER_ID = "@alertbot:offsystem.fr"


def info(msg: str) -> None:
    print(f"[matrix-dm] {msg}", file=sys.stderr)


def _headers() -> dict:
    return {"Authorization": f"Bearer {TOKEN}"}


def _room_id_path(room_id: str) -> str:
    return room_id.replace("!", "%21").replace(":", "%3A")


def _get_account_data_direct() -> dict:
    """m.direct account_data: {user_id: [room_id, ...]} — the client-side
    convention for "my DMs", not a server-side concept."""
    r = requests.get(
        f"{BASE}/_matrix/client/v3/user/{BOT_USER_ID}/account_data/m.direct",
        headers=_headers(), timeout=10,
    )
    if r.status_code == 404:
        return {}
    r.raise_for_status()
    return r.json()


def _set_account_data_direct(direct: dict) -> None:
    r = requests.put(
        f"{BASE}/_matrix/client/v3/user/{BOT_USER_ID}/account_data/m.direct",
        headers=_headers(), json=direct, timeout=10,
    )
    r.raise_for_status()


def get_or_create_dm(target_user_id: str) -> str:
    """Returns an existing DM room_id with target_user_id, creating one if needed."""
    direct = _get_account_data_direct()
    existing = direct.get(target_user_id, [])
    if existing:
        room_id = existing[0]
        info(f"Reusing existing DM {room_id} with {target_user_id}")
        return room_id

    info(f"No existing DM with {target_user_id}, creating one...")
    r = requests.post(
        f"{BASE}/_matrix/client/v3/createRoom",
        headers=_headers(),
        json={
            "is_direct": True,
            "preset": "trusted_private_chat",
            "invite": [target_user_id],
            "initial_state": [
                {"type": "m.room.history_visibility", "state_key": "", "content": {"history_visibility": "shared"}}
            ],
        },
        timeout=10,
    )
    r.raise_for_status()
    room_id = r.json()["room_id"]
    direct.setdefault(target_user_id, []).append(room_id)
    _set_account_data_direct(direct)
    info(f"Created DM {room_id} with {target_user_id}")
    return room_id


def send_proposal(room_id: str, text: str) -> str:
    txn_id = str(int(time.time() * 1000))
    r = requests.put(
        f"{BASE}/_matrix/client/v3/rooms/{_room_id_path(room_id)}/send/m.room.message/{txn_id}",
        headers=_headers(),
        json={"msgtype": "m.text", "body": text},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["event_id"]


def wait_for_reply(room_id: str, timeout_s: int = 300) -> dict:
    """Real /sync long-poll — blocks until a new m.room.message lands in
    room_id from someone other than the bot, or timeout_s elapses.
    Not the 2026-09-16 prototype's polling: one blocking GET per
    iteration, not a fixed interval re-checking history."""
    deadline = time.time() + timeout_s

    # Establish a starting point without replaying old history.
    r = requests.get(f"{BASE}/_matrix/client/v3/sync", headers=_headers(),
                      params={"timeout": 0}, timeout=10)
    r.raise_for_status()
    next_batch = r.json()["next_batch"]

    while time.time() < deadline:
        remaining_ms = max(1000, int((deadline - time.time()) * 1000))
        poll_ms = min(30000, remaining_ms)
        r = requests.get(
            f"{BASE}/_matrix/client/v3/sync",
            headers=_headers(),
            params={"since": next_batch, "timeout": poll_ms},
            timeout=(poll_ms / 1000) + 10,
        )
        r.raise_for_status()
        data = r.json()
        next_batch = data["next_batch"]

        room = data.get("rooms", {}).get("join", {}).get(room_id)
        if room:
            for event in room.get("timeline", {}).get("events", []):
                if event["type"] == "m.room.message" and event["sender"] != BOT_USER_ID:
                    return event
    raise TimeoutError(f"No reply in {room_id} after {timeout_s}s")


def main() -> None:
    if not TOKEN:
        raise SystemExit("Set TUWUNEL_ALERTBOT_TOKEN (see this script's usage notes).")
    if len(sys.argv) != 3:
        raise SystemExit('Usage: matrix_dm.py <@user:offsystem.fr> "message"')
    target, text = sys.argv[1], sys.argv[2]

    room_id = get_or_create_dm(target)
    event_id = send_proposal(room_id, text)
    info(f"Sent (event {event_id}). Waiting up to 5 min for a real reply via /sync...")
    reply = wait_for_reply(room_id)
    print(json.dumps({"sender": reply["sender"], "body": reply["content"].get("body")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
