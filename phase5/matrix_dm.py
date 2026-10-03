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


def send_proposal(room_id: str, text: str, txn_id: str | None = None, reply_to: str | None = None) -> str:
    """Sends a message, returns its event_id.

    `txn_id`: pass a deterministic one for anything an unattended job might
    retry. The Matrix send endpoint is idempotent per transaction id — a
    second PUT with the same id returns the *same* event instead of posting
    a second message — so a job killed between "send" and "remember I sent
    it" can't produce a duplicate DM on its next run. Defaults to a
    timestamp (fine for the interactive CLI, never repeated on purpose).

    `reply_to`: an event_id, sent as a proper Matrix reply so Element shows
    which message this answers (used for the "didn't understand" nudge)."""
    txn_id = txn_id or str(int(time.time() * 1000))
    content: dict = {"msgtype": "m.text", "body": text}
    if reply_to:
        content["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to}}
    r = requests.put(
        f"{BASE}/_matrix/client/v3/rooms/{_room_id_path(room_id)}/send/m.room.message/{txn_id}",
        headers=_headers(),
        json=content,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["event_id"]


# Polls (MSC3381). The unstable-prefixed names are what Element Web and
# Element X actually emit and render today — confirmed against a real vote
# from the user's own client (`org.matrix.msc3381.poll.response`, answers
# carried as ids under the same key, linked to the poll via an
# `m.reference` relation). The stable `m.poll.response` / `m.selections`
# shape is also read, in case a client sends that instead.
POLL_START = "org.matrix.msc3381.poll.start"
POLL_END = "org.matrix.msc3381.poll.end"
POLL_RESPONSE_TYPES = ("org.matrix.msc3381.poll.response", "m.poll.response")


def _send_event(room_id: str, event_type: str, content: dict, txn_id: str | None = None) -> str:
    """PUT any event type; idempotent per transaction id (see send_proposal)."""
    txn_id = txn_id or str(int(time.time() * 1000))
    r = requests.put(
        f"{BASE}/_matrix/client/v3/rooms/{_room_id_path(room_id)}/send/{event_type}/{txn_id}",
        headers=_headers(), json=content, timeout=10,
    )
    r.raise_for_status()
    return r.json()["event_id"]


def send_poll(room_id: str, question: str, answers: dict[str, str], txn_id: str | None = None) -> str:
    """A one-choice, disclosed poll; `answers` maps answer id -> label.
    Returns the poll's event_id. The plain-text fallback is what a client
    without poll support shows (and, with Reply, can still answer)."""
    fallback = question + "\n" + "\n".join(f"{i}. {label}" for i, label in enumerate(answers.values(), 1))
    return _send_event(room_id, POLL_START, {
        "org.matrix.msc1767.text": fallback,
        POLL_START: {
            "kind": "org.matrix.msc3381.poll.disclosed",
            "max_selections": 1,
            "question": {"org.matrix.msc1767.text": question},
            "answers": [{"id": aid, "org.matrix.msc1767.text": label} for aid, label in answers.items()],
        },
    }, txn_id)


def end_poll(room_id: str, poll_id: str, txn_id: str | None = None) -> str:
    """Closes a poll so a late or changed vote can't alter an answer that was
    already acted on."""
    return _send_event(room_id, POLL_END, {
        "m.relates_to": {"rel_type": "m.reference", "event_id": poll_id},
        "org.matrix.msc1767.text": "Sondage clos.",
        POLL_END: {},
    }, txn_id)


def get_poll_vote(room_id: str, poll_id: str, max_pages: int = 5) -> str | None:
    """The answer id currently selected on a poll by a human, or None if
    nobody voted (or they cleared their vote). The latest vote wins, so a
    changed mind counts. Raises LookupError if the poll itself isn't found
    in the history scanned — "can't tell", never "no vote"."""
    token = None
    for _ in range(max_pages):
        params: dict = {"dir": "b", "limit": 100}
        if token:
            params["from"] = token
        r = requests.get(
            f"{BASE}/_matrix/client/v3/rooms/{_room_id_path(room_id)}/messages",
            headers=_headers(), params=params, timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        chunk = data.get("chunk", [])
        for event in chunk:  # newest first, so the first matching vote is the latest
            if event.get("event_id") == poll_id:
                return None
            if event.get("type") in POLL_RESPONSE_TYPES and event.get("sender") != BOT_USER_ID:
                rel = event.get("content", {}).get("m.relates_to", {})
                if rel.get("event_id") == poll_id:
                    content = event.get("content", {})
                    answers = (content.get("org.matrix.msc3381.poll.response", {}).get("answers")
                               or content.get("m.selections") or [])
                    return answers[0] if answers else None
        token = data.get("end")
        if not token or not chunk:
            break
    raise LookupError(f"poll {poll_id} not found in the last {max_pages * 100} events of {room_id}")


def get_replies_after(room_id: str, event_id: str, max_pages: int = 5) -> list[dict] | None:
    """Human messages posted after `event_id` in the room, oldest first.

    Walks the room history backwards from the newest message until it
    reaches `event_id`, so "after" is decided by position in the room, not
    by comparing clocks (a local timestamp against the homeserver's would
    be one more thing to get subtly wrong). Messages from the bot itself
    are skipped. Returns None if `event_id` isn't found within `max_pages`
    pages (100 events each) — the caller must treat that as "can't tell",
    not as "no reply".

    This is what lets the CronJob stop blocking on a reply: each tick just
    asks "has anyone answered since my proposal?" and moves on."""
    collected: list[dict] = []
    token = None
    for _ in range(max_pages):
        params: dict = {"dir": "b", "limit": 100}
        if token:
            params["from"] = token
        r = requests.get(
            f"{BASE}/_matrix/client/v3/rooms/{_room_id_path(room_id)}/messages",
            headers=_headers(), params=params, timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        chunk = data.get("chunk", [])
        for event in chunk:  # newest first
            if event.get("event_id") == event_id:
                return list(reversed(collected))
            if event.get("type") == "m.room.message" and event.get("sender") != BOT_USER_ID:
                collected.append(event)
        token = data.get("end")
        if not token or not chunk:
            break
    return None


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
