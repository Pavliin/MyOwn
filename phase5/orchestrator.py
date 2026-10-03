"""End-to-end orchestrator — Phase 5 step 8. Ties every connector into one
run and handles the cases the planning doc names (mail already processed,
no answer, unclear answer).

**Asynchronous by design, because the CronJob runs it unattended.** The
manual version blocked on a reply for up to 5 minutes per proposal — fine
with a human at the keyboard, wrong in a bounded scheduled job, and it hid
two defects that only appear when nobody is watching: an unanswered
proposal was re-sent every run, and a late "oui" meant for one mail could
be consumed by the wait for the next and write the wrong event.

How it works now. A *proposal* is two Matrix messages: a detail message
(sender, date, what was detected) and, right under it, a one-tap poll
("Oui" / "Non"). Several proposals can be open at once — at most
MAX_PENDING, or MAX_PENDING_URGENT for mails the model flags as important
— and each is answered independently: a vote on *its own* poll, or an
explicit Reply to *its own* messages. A plain "oui" typed into the room is
deliberately **not** an answer (replies.py): with several proposals open
it would become attributable to the wrong one as soon as the others
resolved.

All state lives in the user's own memory file, so nothing is lost or
repeated between runs:
- `pending_proposals`: proposals sent and awaiting an answer;
- `deferred`: mails already analysed whose proposal is waiting for a free
  slot. The extraction is cached because Ollama here runs CPU-only
  (~3 tokens/s) — re-analysing the same mail every 15 minutes would burn
  the whole job;
- `processed_mail_uids`: mails dealt with for good.
Each tick: resolve answered/expired proposals, analyse new mail (silently
handling anything with nothing to confirm), then propose from the queue —
urgent first — while slots remain. Nothing in a tick waits on a person.

Crash-safety: pending state is persisted *before* anything is sent, every
Matrix send uses a deterministic transaction id (the endpoint is
idempotent per id), and CalDAV writes use a deterministic UID — a job
killed at any point either repeats a harmless no-op or resumes.

"Already processed" lives in the memory file, not IMAP's \\Seen flag: the
IMAP connector is read-only on purpose, and "the AI already asked" is
unrelated to "the human already read it".

Usage (one tick; run it again to see the next step — this no longer waits):
    export TUWUNEL_ALERTBOT_TOKEN=...
    export NEXTCLOUD_APP_PASSWORD=...   # for the target user's own nc_uid
    export MAILU_IMAP_PASSWORD=...
    export PHASE5_SSH_HOST=192.168.1.143   # mini PC; unset = dev cluster
    python3 phase5/orchestrator.py <matrix_id> <nextcloud_uid> <mailbox-email>
"""

import hashlib
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

from caldav_writer import CALENDAR_DISPLAY_NAME, find_or_create_task_list, write_event, write_task
from extraction import extract_from_email
from imap_connector import fetch_message_text, list_recent_messages
from matrix_dm import end_poll, get_or_create_dm, get_poll_vote, get_replies_after, send_poll, send_proposal
from opt_in import build_question, has_opted_in
from replies import parse_yes_no, reply_target
from user_directory import nextcloud_port_forward
from user_memory import read_memory, write_memory

# Open proposals per user. Normal mails stop at MAX_PENDING; a mail the
# model flags as important may go beyond that, up to a hard ceiling so a
# burst can never flood the room. Both are tunable, not sacred.
MAX_PENDING = 5
MAX_PENDING_URGENT = 10

# How long a proposal waits for an answer before it is dropped (the DM
# stays readable). Mail proposals are time-sensitive; the opt-in question
# is a one-off the person may reasonably get to later. A mail analysed but
# still waiting for a slot is dropped after DEFERRED_TTL.
PENDING_TTL = {"mail_proposal": timedelta(hours=48), "opt_in": timedelta(days=7)}
DEFERRED_TTL = timedelta(days=7)

ANSWERS = {"yes": "Oui", "no": "Non"}


def info(msg: str) -> None:
    print(f"[orchestrator] {msg}", file=sys.stderr)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _txn_id(*parts: str) -> str:
    """Deterministic Matrix transaction id (alphanumeric, URL-safe): the
    same inputs always give the same id, which is what makes a retried
    send a no-op instead of a second message."""
    return "phase5-" + hashlib.sha1(":".join(parts).encode()).hexdigest()[:24]


def _caldav_uid(mailbox: str, mail_uid: str, kind: str) -> str:
    """Deterministic iCalendar UID per (mailbox, mail, event|task): a retry
    after a crash overwrites the same calendar entry."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"phase5:{mailbox}:{mail_uid}:{kind}"))


def _human_local(local_iso: str | None) -> str | None:
    """'2026-09-18T12:15:00' -> '18/09/2026 à 12h15' — for display only,
    never for the actual CalDAV write (that uses the UTC conversion in
    extraction.py's to_utc_z())."""
    if not local_iso:
        return None
    return datetime.strptime(local_iso, "%Y-%m-%dT%H:%M:%S").strftime("%d/%m/%Y à %Hh%M")


def _format_proposal(message: dict, extracted: dict, task_list_display_name: str | None = None) -> tuple[str, str]:
    """(details, poll_question) for the has_event/has_reminder case.

    The details go in a normal message (multi-line, readable); the question
    goes on the poll, short but self-sufficient — it names the mail, since
    several polls may be on screen at once — and says exactly what would be
    written and where ("un événement dans l'agenda « Personnel »"), never a
    bare "j'ajoute ça ?" (a real bug found live: it named neither what nor
    where). Times are shown in local, human form, not raw UTC."""
    lines = [f"🤖 Mail du {message.get('date', '?')}\nDe : {message['from']}\nSujet : « {message['subject']} »"]
    asks_for = []
    if extracted.get("has_event") and extracted.get("event"):
        ev = extracted["event"]
        lines.append(f"📅 Événement détecté : {ev.get('title')} le {_human_local(ev.get('start_local'))}")
        asks_for.append(f"un événement dans l'agenda « {CALENDAR_DISPLAY_NAME} »")
    if extracted.get("has_reminder") and extracted.get("reminder"):
        rem = extracted["reminder"]
        due = _human_local(rem.get("due_local"))
        due_str = f" (échéance {due})" if due else ""
        lines.append(f"✅ Tâche suggérée : {rem.get('title')}{due_str}")
        target = f" dans la liste « {task_list_display_name} »" if task_list_display_name else ""
        asks_for.append(f"une tâche{target}")
    if extracted.get("important"):
        lines.append(f"⚠️ Par ailleurs, ce mail a été jugé important : {extracted.get('important_reason')}")

    subject = message["subject"]
    short = subject if len(subject) <= 50 else subject[:47] + "…"
    question = f"Dois-je ajouter {' et '.join(asks_for)} ? (mail « {short} »)"
    return "\n".join(lines), question


def _format_notification(message: dict, extracted: dict) -> str:
    """important=true with no event/reminder: purely informational, never
    written anywhere — no question, no poll, since there's nothing to
    consent to ("notifier la réception d'un mail important" is its own
    thing, separate from "proposition d'ajout")."""
    return (
        f"🤖 Mail important reçu du {message.get('date', '?')}\n"
        f"De : {message['from']}\nSujet : « {message['subject']} »\n"
        f"⚠️ {extracted.get('important_reason')}"
    )


def _drop_past_event(result: dict) -> dict:
    """A mail can wait in the queue for days; an event that has started in
    the meantime is no longer worth proposing (same reasoning as
    extraction._reject_past_events, applied at proposal time)."""
    ev = result.get("event")
    if ev and ev.get("start_utc"):
        start = datetime.strptime(ev["start_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if start < _now():
            result = dict(result, has_event=False, event=None)
    return result


class _Session:
    """Everything one tick needs to know about one user."""

    def __init__(self, nc_base: str, nc_auth: tuple[str, str], nc_uid: str,
                 matrix_id: str, mailbox: str, imap_password: str):
        self.nc_base, self.nc_auth, self.nc_uid = nc_base, nc_auth, nc_uid
        self.matrix_id, self.mailbox, self.imap_password = matrix_id, mailbox, imap_password

    # --- memory ---------------------------------------------------------

    def _update(self, fn) -> dict:
        """One read-modify-write. Related changes (add pending + drop from
        the queue, finish a mail + clear its proposal + history) go through a
        single call so a crash can't leave them half-applied."""
        data = read_memory(self.nc_base, self.nc_auth, self.nc_uid)
        data.setdefault("memory", {})
        data.setdefault("history", [])
        fn(data)
        write_memory(self.nc_base, self.nc_auth, self.nc_uid, data)
        return data

    def _memory(self) -> dict:
        return read_memory(self.nc_base, self.nc_auth, self.nc_uid).get("memory", {})

    @staticmethod
    def _history(data: dict, entry: dict) -> None:
        data["history"].append({"at": _now().isoformat(), **entry})

    def _pendings(self) -> list[dict]:
        return list(self._memory().get("pending_proposals", []))

    def _save_pending(self, p: dict, drop_deferred_uid: str | None = None) -> None:
        def fn(data):
            lst = data["memory"].setdefault("pending_proposals", [])
            for i, q in enumerate(lst):
                if q["id"] == p["id"]:
                    lst[i] = p
                    break
            else:
                lst.append(p)
            if drop_deferred_uid is not None:
                data["memory"].get("deferred", {}).pop(drop_deferred_uid, None)
        self._update(fn)

    def _finish_mail(self, uid: str, entry: dict | None, pending_id: str | None = None) -> None:
        """Mail dealt with for good: processed, its proposal and queue entry
        cleared, history recorded (when there is something worth recording —
        a newsletter with nothing to do deliberately leaves none) — atomically."""
        def fn(data):
            processed = data["memory"].setdefault("processed_mail_uids", [])
            if uid not in processed:
                processed.append(uid)
            if pending_id is not None:
                data["memory"]["pending_proposals"] = [
                    q for q in data["memory"].get("pending_proposals", []) if q["id"] != pending_id]
            data["memory"].get("deferred", {}).pop(uid, None)
            if entry:
                self._history(data, entry)
        self._update(fn)

    def _close_pending(self, pending_id: str, entry: dict, extra=None) -> None:
        def fn(data):
            data["memory"]["pending_proposals"] = [
                q for q in data["memory"].get("pending_proposals", []) if q["id"] != pending_id]
            if extra:
                extra(data)
            self._history(data, entry)
        self._update(fn)

    # --- proposals ------------------------------------------------------

    def _send_pending(self, p: dict) -> None:
        """Send (or re-send) a proposal's two messages under deterministic
        transaction ids, then record their event ids."""
        room = get_or_create_dm(self.matrix_id)
        message_id = send_proposal(room, p["text"], txn_id=p["id"] + "-m")
        poll_id = send_poll(room, p["question"], ANSWERS, txn_id=p["id"] + "-p")
        p.update(message_event_id=message_id, poll_event_id=poll_id, own_event_ids=[message_id, poll_id])
        self._save_pending(p)

    def _start_pending(self, kind: str, key: str, text: str, question: str, payload: dict,
                       drop_deferred_uid: str | None = None) -> None:
        """Persist first, send second: if the job dies in between, the next
        tick finds a proposal with no event ids and re-sends it under the
        same transaction ids."""
        p = {"id": _txn_id(kind, key), "kind": kind, "created_at": _now().isoformat(),
             "message_event_id": None, "poll_event_id": None, "own_event_ids": [],
             "text": text, "question": question, "payload": payload}
        self._save_pending(p, drop_deferred_uid)
        self._send_pending(p)
        info(f"Proposal sent ({kind}); waiting for an answer.")

    def _end_poll(self, p: dict) -> None:
        if not p.get("poll_event_id"):
            return
        try:
            end_poll(get_or_create_dm(self.matrix_id), p["poll_event_id"], txn_id=p["id"] + "-e")
        except Exception as e:  # cosmetic: the decision is already recorded
            info(f"Could not close the poll ({e!r}); not critical.")

    def _expired(self, p: dict) -> bool:
        return _now() - datetime.fromisoformat(p["created_at"]) > PENDING_TTL[p["kind"]]

    def _answer(self, p: dict, room: str) -> tuple[bool, str] | None:
        """(decision, raw) if this proposal has been clearly answered, else
        None. A poll vote counts first (latest wins); otherwise a text reply
        aimed at one of this proposal's own messages."""
        try:
            vote = get_poll_vote(room, p["poll_event_id"])
        except LookupError as e:
            info(f"{e}; leaving it for the next tick.")
            return None
        if vote in ANSWERS:
            return vote == "yes", f"poll:{vote}"

        replies = get_replies_after(room, p["message_event_id"])
        if replies is None:
            return None
        own = set(p["own_event_ids"])
        for event in reversed(replies):  # latest clear text answer wins
            if reply_target(event) in own:
                body = event.get("content", {}).get("body", "")
                decision = parse_yes_no(body)
                if decision is not None:
                    return decision, body
        return None

    def resolve_pending(self, p: dict) -> None:
        """Advance one proposal, independently of the others."""
        if not p.get("poll_event_id"):
            self._send_pending(p)
            info("Re-sent a proposal interrupted before it was recorded (same transaction ids).")
            return
        room = get_or_create_dm(self.matrix_id)
        answer = self._answer(p, room)
        if answer is None:
            if self._expired(p):
                self._expire(p)
            return
        self._apply(p, *answer)

    def _apply(self, p: dict, decision: bool, raw: str) -> None:
        if p["kind"] == "opt_in":
            service = p["payload"]["service"]

            def set_opt_in(data):
                data["memory"].setdefault("opt_in", {})[service] = decision
            self._close_pending(p["id"], {"kind": "opt_in_decision", "service": service,
                                          "decision": decision, "raw_reply": raw}, set_opt_in)
            self._end_poll(p)
            info(f"{self.matrix_id} {'opted in to' if decision else 'declined'} {service!r}.")
            return

        mail, result = p["payload"]["mail"], p["payload"]["result"]
        if decision:
            # Idempotent writes first, bookkeeping after: a crash in between
            # replays the same writes onto the same UIDs next tick.
            if result.get("has_event") and result.get("event"):
                ev = result["event"]
                write_event(self.nc_base, self.nc_auth, self.nc_uid, ev["title"], ev["start_utc"],
                            ev.get("end_utc"), ev.get("duration_kind", "rdv"),
                            uid=_caldav_uid(self.mailbox, mail["uid"], "event"))
            if result.get("has_reminder") and result.get("reminder"):
                rem = result["reminder"]
                write_task(self.nc_base, self.nc_auth, self.nc_uid, rem["title"], rem.get("due_utc"),
                           task_list=p["payload"].get("task_list"),
                           uid=_caldav_uid(self.mailbox, mail["uid"], "task"))
        self._finish_mail(mail["uid"], {
            "kind": "mail_proposal_accepted" if decision else "mail_proposal_declined",
            "subject": mail["subject"], "uid": mail["uid"],
        }, pending_id=p["id"])
        self._end_poll(p)

    def _expire(self, p: dict) -> None:
        if p["kind"] == "opt_in":
            self._close_pending(p["id"], {"kind": "opt_in_expired", "service": p["payload"]["service"]})
            self._end_poll(p)
            info("Opt-in question expired unanswered; it will be asked again.")
            return
        mail = p["payload"]["mail"]
        self._finish_mail(mail["uid"], {"kind": "mail_proposal_expired", "subject": mail["subject"],
                                        "uid": mail["uid"]}, pending_id=p["id"])
        self._end_poll(p)
        info(f"Proposal for {mail['subject']!r} expired unanswered — dropped, not re-sent.")

    # --- the queue ------------------------------------------------------

    def ask_opt_in(self, service: str = "mail") -> None:
        self._start_pending("opt_in", f"{self.matrix_id}:{service}:{_now().isoformat()}",
                            build_question(service, include_question=False),
                            "Activer l'aide sur tes mails ?", {"service": service})

    def _analyse_new_mail(self) -> None:
        """Read recent mail; anything not seen before is analysed once. What
        needs no confirmation is finished on the spot; what needs one goes
        into the `deferred` queue (persisted immediately, so a job killed
        mid-scan never re-pays for an extraction)."""
        mem = self._memory()
        known = set(mem.get("processed_mail_uids", [])) | set(mem.get("deferred", {}))
        known |= {p["payload"]["mail"]["uid"] for p in mem.get("pending_proposals", []) if p["kind"] == "mail_proposal"}

        messages = list_recent_messages(self.mailbox, self.imap_password, limit=10)
        info(f"{len(messages)} recent message(s) to check for {self.matrix_id}.")

        for m in messages:
            if m["uid"] in known:
                continue
            body = fetch_message_text(self.mailbox, self.imap_password, m["uid"])
            result = extract_from_email(m["from"], m["subject"], body)
            needs_write = bool(result.get("has_event") or result.get("has_reminder"))

            if not (needs_write or result.get("important")):
                info(f"Nothing actionable in {m['subject']!r}, marking processed without a proposal.")
                self._finish_mail(m["uid"], None)
                continue

            if not needs_write:
                # important-only: a plain notification, nothing to write and
                # nothing to consent to. Deterministic transaction id so a
                # retry after a crash can't post it twice.
                send_proposal(get_or_create_dm(self.matrix_id), _format_notification(m, result),
                              txn_id=_txn_id("notif", self.mailbox, m["uid"]))
                self._finish_mail(m["uid"], {"kind": "mail_notification", "subject": m["subject"], "uid": m["uid"]})
                continue

            task_list = task_list_name = None
            if result.get("has_reminder") and result.get("reminder"):
                task_list, task_list_name = find_or_create_task_list(self.nc_base, self.nc_auth, self.nc_uid)

            def enqueue(data, m=m, result=result, task_list=task_list, task_list_name=task_list_name):
                data["memory"].setdefault("deferred", {})[m["uid"]] = {
                    "mail": {k: m.get(k) for k in ("uid", "from", "subject", "date")},
                    "result": result, "task_list": task_list, "task_list_name": task_list_name,
                    "urgent": bool(result.get("important")), "queued_at": _now().isoformat(),
                }
            self._update(enqueue)

    def _propose_from_queue(self) -> None:
        mem = self._memory()
        open_count = sum(1 for p in mem.get("pending_proposals", []) if p["kind"] == "mail_proposal")
        queue = list(mem.get("deferred", {}).values())
        # Urgent first, then newest first (IMAP uids grow with arrival).
        queue.sort(key=lambda d: (not d["urgent"], -int(d["mail"]["uid"]) if str(d["mail"]["uid"]).isdigit() else 0))

        for item in queue:
            mail, urgent = item["mail"], item["urgent"]

            if _now() - datetime.fromisoformat(item["queued_at"]) > DEFERRED_TTL:
                self._finish_mail(mail["uid"], {"kind": "mail_proposal_stale", "subject": mail["subject"], "uid": mail["uid"]})
                continue

            result = _drop_past_event(item["result"])
            if not (result.get("has_event") or result.get("has_reminder")):
                info(f"{mail['subject']!r} no longer has anything to propose (event already past).")
                self._finish_mail(mail["uid"], {"kind": "mail_proposal_stale", "subject": mail["subject"], "uid": mail["uid"]})
                continue

            ceiling = MAX_PENDING_URGENT if urgent else MAX_PENDING
            if open_count >= ceiling:
                continue  # stays queued, already analysed

            details, question = _format_proposal(mail, result, item.get("task_list_name"))
            self._start_pending("mail_proposal", f"{self.mailbox}:{mail['uid']}", details, question,
                                {"mail": mail, "result": result, "task_list": item.get("task_list")},
                                drop_deferred_uid=mail["uid"])
            open_count += 1


def process_user(matrix_id: str, nc_uid: str, mailbox: str, imap_password: str, nc_app_password: str) -> None:
    """One tick for one user. Never blocks waiting for a person."""
    with nextcloud_port_forward() as nc_base:
        s = _Session(nc_base, (nc_uid, nc_app_password), nc_uid, matrix_id, mailbox, imap_password)

        for p in s._pendings():
            s.resolve_pending(p)

        opted_in = has_opted_in(nc_base, s.nc_auth, nc_uid, "mail")
        if opted_in is None:
            if not any(p["kind"] == "opt_in" for p in s._pendings()):
                s.ask_opt_in("mail")
            return
        if not opted_in:
            info(f"{matrix_id} has not opted in to mail, skipping.")
            return

        s._analyse_new_mail()
        s._propose_from_queue()


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
