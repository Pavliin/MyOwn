"""End-to-end orchestrator — Phase 5 step 8: ties every connector built so
far into one real run, plus the error-handling cases the planning doc
names explicitly: mail already processed, ambiguous reply, confirmation
timeout.

For each opted-in user: fetch recent INBOX mail, skip anything already
handled, extract structured info (step 6), skip anything with nothing
actionable, propose in DM (step 3) only for the rest, wait for a real
reply, write to Nextcloud (step 7) only on a clear "oui" — nothing here
ever writes without an explicit human yes, matching every earlier step's
own principle.

"Already processed" tracking deliberately lives in the user's own memory
file (step 2), not IMAP's \\Seen flag: the IMAP connector (step 5) is
read-only/non-marking on purpose, and conflating "the AI already asked
about this" with "the human already read this in their own mail client"
would tie two unrelated states together for no reason.

Confirmation timeout: `wait_for_reply` already raises after its timeout —
caught here and left unprocessed (not marked done), so a later run
retries it rather than silently dropping it.

Ambiguous reply: one re-ask (mirrors opt_in.py's own pattern), and if
still unclear, left unprocessed rather than guessed — same "silence or
ambiguity is not consent" principle as step 4, applied here too.

This script is a single real run for one user, driven by hand — the
CronJob/scheduling half of step 8 (turning this into something that runs
unattended) is a separate, larger piece of work (a container image, a
GitOps Application, secrets wiring) deliberately not bundled into this
same change.

Usage:
    export TUWUNEL_ALERTBOT_TOKEN=...
    export NEXTCLOUD_APP_PASSWORD=...   # for the target user's own nc_uid
    export MAILU_IMAP_PASSWORD=...
    export PHASE5_SSH_HOST=192.168.1.143   # mini PC; unset = dev cluster
    python3 phase5/orchestrator.py <matrix_id> <nextcloud_uid> <mailbox-email>
"""

import os
import re
import sys

from caldav_writer import write_event, write_task
from extraction import extract_from_email
from imap_connector import fetch_message_text, list_recent_messages
from matrix_dm import get_or_create_dm, send_proposal, wait_for_reply
from opt_in import request_opt_in
from user_directory import nextcloud_port_forward
from user_memory import append_history, read_memory, write_memory

CONFIRM_TIMEOUT_S = 300
YES_PATTERN = re.compile(r"\b(oui|ok|d'accord|daccord|yes|go)\b", re.IGNORECASE)
NO_PATTERN = re.compile(r"\b(non|no|pas maintenant|jamais)\b", re.IGNORECASE)


def info(msg: str) -> None:
    print(f"[orchestrator] {msg}", file=sys.stderr)


def _already_processed(memory_data: dict, uid: str) -> bool:
    return uid in memory_data.get("memory", {}).get("processed_mail_uids", [])


def _mark_processed(nc_base: str, nc_auth: tuple[str, str], nc_uid: str, uid: str) -> None:
    data = read_memory(nc_base, nc_auth, nc_uid)
    data.setdefault("memory", {}).setdefault("processed_mail_uids", []).append(uid)
    write_memory(nc_base, nc_auth, nc_uid, data)


def _format_proposal(message: dict, extracted: dict) -> str:
    """Only for the has_event/has_reminder case — there's something to
    write, so the closing question asks for consent to write it.
    _format_notification (below) handles the important-only case, where
    nothing gets written and there's nothing to "add" — a real bug found
    live: asking "j'ajoute ça ?" for a plain importance flag confused the
    person it was sent to, correctly, since nothing was actually being
    proposed for addition."""
    lines = [f"🤖 Mail de {message['from']} — « {message['subject']} »"]
    if extracted.get("has_event") and extracted.get("event"):
        ev = extracted["event"]
        lines.append(f"📅 Événement détecté : {ev.get('title')} — {ev.get('start_utc')}")
    if extracted.get("has_reminder") and extracted.get("reminder"):
        rem = extracted["reminder"]
        due = f" (échéance {rem['due_utc']})" if rem.get("due_utc") else ""
        lines.append(f"✅ Tâche suggérée : {rem.get('title')}{due}")
    if extracted.get("important"):
        lines.append(f"⚠️ Par ailleurs, ce mail a été jugé important : {extracted.get('important_reason')}")
    lines.append("\nJ'ajoute ça (oui/non) ?")
    return "\n".join(lines)


def _format_notification(message: dict, extracted: dict) -> str:
    """important=true with no event/reminder: purely informational, never
    written anywhere — no question, no confirmation needed, since there's
    nothing to consent to (matches the very first mail use-case: "notifier
    la réception d'un mail important" is its own thing, separate from
    "proposition d'ajout")."""
    return (
        f"🤖 Mail important reçu, {message['from']} — « {message['subject']} »\n"
        f"⚠️ {extracted.get('important_reason')}"
    )


def _confirm(room_id: str, question: str | None = None, max_attempts: int = 2) -> bool | None:
    """True/False on a clear reply, None on timeout or persistent ambiguity
    (never guessed — matches step 4's "silence/ambiguity isn't consent")."""
    for attempt in range(max_attempts):
        if attempt > 0:
            send_proposal(room_id, "Je n'ai pas compris — réponds juste oui ou non pour ce mail.")
        elif question:
            send_proposal(room_id, question)
        try:
            reply = wait_for_reply(room_id, timeout_s=CONFIRM_TIMEOUT_S)
        except TimeoutError:
            info("Confirmation timeout — leaving this mail unprocessed for a later run.")
            return None
        body = reply["content"].get("body", "")
        is_yes, is_no = bool(YES_PATTERN.search(body)), bool(NO_PATTERN.search(body))
        if is_yes and not is_no:
            return True
        if is_no and not is_yes:
            return False
        info(f"Ambiguous reply {body!r} ({attempt + 1}/{max_attempts})")
    info("Still ambiguous after retries — leaving this mail unprocessed for a later run.")
    return None


def process_user(matrix_id: str, nc_uid: str, mailbox: str, imap_password: str, nc_app_password: str) -> None:
    with nextcloud_port_forward() as nc_base:
        nc_auth = (nc_uid, nc_app_password)

        if not request_opt_in(nc_base, nc_auth, nc_uid, matrix_id, "mail"):
            info(f"{matrix_id} has not opted in to mail, skipping.")
            return

        messages = list_recent_messages(mailbox, imap_password, limit=10)
        info(f"{len(messages)} recent message(s) to check for {matrix_id}.")

        for m in messages:
            memory_data = read_memory(nc_base, nc_auth, nc_uid)
            if _already_processed(memory_data, m["uid"]):
                continue

            body = fetch_message_text(mailbox, imap_password, m["uid"])
            result = extract_from_email(m["from"], m["subject"], body)

            needs_write = bool(result.get("has_event") or result.get("has_reminder"))

            if not (needs_write or result.get("important")):
                info(f"Nothing actionable in {m['subject']!r}, marking processed without a proposal.")
                _mark_processed(nc_base, nc_auth, nc_uid, m["uid"])
                continue

            room_id = get_or_create_dm(matrix_id)

            if not needs_write:
                # important-only: a plain notification, nothing to write,
                # nothing to consent to — no question, no wait for a reply.
                send_proposal(room_id, _format_notification(m, result))
                append_history(nc_base, nc_auth, nc_uid, {"kind": "mail_notification", "subject": m["subject"], "uid": m["uid"]})
                _mark_processed(nc_base, nc_auth, nc_uid, m["uid"])
                continue

            send_proposal(room_id, _format_proposal(m, result))
            decision = _confirm(room_id)

            if decision is None:
                continue  # timeout or unresolved ambiguity — retried next run, not marked processed

            if decision:
                if result.get("has_event") and result.get("event"):
                    ev = result["event"]
                    write_event(nc_base, nc_auth, nc_uid, ev["title"], ev["start_utc"], ev.get("end_utc") or ev["start_utc"])
                if result.get("has_reminder") and result.get("reminder"):
                    rem = result["reminder"]
                    write_task(nc_base, nc_auth, nc_uid, rem["title"], rem.get("due_utc"))
                append_history(nc_base, nc_auth, nc_uid, {"kind": "mail_proposal_accepted", "subject": m["subject"], "uid": m["uid"]})
            else:
                append_history(nc_base, nc_auth, nc_uid, {"kind": "mail_proposal_declined", "subject": m["subject"], "uid": m["uid"]})

            _mark_processed(nc_base, nc_auth, nc_uid, m["uid"])


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("Usage: orchestrator.py <matrix_id> <nextcloud_uid> <mailbox-email>")
    matrix_id, nc_uid, mailbox = sys.argv[1:4]

    imap_password = os.environ.get("MAILU_IMAP_PASSWORD")
    nc_app_password = os.environ.get("NEXTCLOUD_APP_PASSWORD")
    if not imap_password or not nc_app_password:
        raise SystemExit("Set MAILU_IMAP_PASSWORD and NEXTCLOUD_APP_PASSWORD (see this script's usage notes).")

    process_user(matrix_id, nc_uid, mailbox, imap_password, nc_app_password)


if __name__ == "__main__":
    main()
