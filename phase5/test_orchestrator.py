"""Offline tests for the orchestrator's asynchronous state machine.

Justified here because the failures this guards against only appear when
*nobody is watching* (the same DM re-sent every tick, a late answer
confirming the wrong mail, a crash duplicating a message or a calendar
entry, a burst flooding the room), so an attended live run can't surface
them. Everything external is faked: the Matrix room (with the real send
endpoint's idempotence per transaction id and the real shape of a poll
vote), the Nextcloud memory file, IMAP, the extraction model, CalDAV.

Run:  cd phase5 && python3 -m unittest -v test_orchestrator
"""

import copy
import unittest
from contextlib import contextmanager
from datetime import timedelta
from unittest import mock

import orchestrator as orch

ROOM = "!room:offsystem.fr"
BOT = "@alertbot:offsystem.fr"
HUMAN = "@robin:offsystem.fr"
MAILBOX = "robin@offsystem.fr"


class FakeRoom:
    """A Matrix room: ordered events, idempotent sends per transaction id."""

    def __init__(self):
        self.events: list[dict] = []
        self._txn: dict[str, str] = {}
        self.ended: list[str] = []

    def _add(self, etype: str, sender: str, content: dict) -> str:
        event_id = f"$e{len(self.events) + 1}"
        self.events.append({"event_id": event_id, "type": etype, "sender": sender, "content": content})
        return event_id

    def _idempotent(self, txn_id, make):
        if txn_id and txn_id in self._txn:        # Matrix: same txn id -> same event, no new one
            return self._txn[txn_id]
        event_id = make()
        if txn_id:
            self._txn[txn_id] = event_id
        return event_id

    # --- what the orchestrator calls (patched over matrix_dm's functions) ---
    def send_proposal(self, room_id, text, txn_id=None, reply_to=None):
        content = {"msgtype": "m.text", "body": text}
        if reply_to:
            content["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to}}
        return self._idempotent(txn_id, lambda: self._add("m.room.message", BOT, content))

    def send_poll(self, room_id, question, answers, txn_id=None):
        content = {"org.matrix.msc3381.poll.start": {"question": {"org.matrix.msc1767.text": question},
                                                      "answers": list(answers)}}
        return self._idempotent(txn_id, lambda: self._add("org.matrix.msc3381.poll.start", BOT, content))

    def end_poll(self, room_id, poll_id, txn_id=None):
        def make():
            self.ended.append(poll_id)
            return self._add("org.matrix.msc3381.poll.end", BOT, {"m.relates_to": {"event_id": poll_id}})
        return self._idempotent(txn_id, make)

    def get_poll_vote(self, room_id, poll_id):
        ids = [e["event_id"] for e in self.events]
        if poll_id not in ids:
            raise LookupError(poll_id)
        for e in reversed(self.events):          # newest first: the latest vote wins
            if (e["type"] == "org.matrix.msc3381.poll.response" and e["sender"] == HUMAN
                    and e["content"]["m.relates_to"]["event_id"] == poll_id):
                answers = e["content"]["org.matrix.msc3381.poll.response"]["answers"]
                return answers[0] if answers else None
        return None

    def get_replies_after(self, room_id, event_id, max_pages=5):
        ids = [e["event_id"] for e in self.events]
        if event_id not in ids:
            return None
        return [e for e in self.events[ids.index(event_id) + 1:]
                if e["type"] == "m.room.message" and e["sender"] != BOT]

    # --- what the test drives ---
    def human_says(self, body, reply_to=None):
        content = {"msgtype": "m.text", "body": body}
        if reply_to:
            content["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to}}
        return self._add("m.room.message", HUMAN, content)

    def human_votes(self, poll_id, answer):
        return self._add("org.matrix.msc3381.poll.response", HUMAN, {
            "m.relates_to": {"rel_type": "m.reference", "event_id": poll_id},
            "org.matrix.msc3381.poll.response": {"answers": [answer] if answer else []},
        })

    def messages(self):
        return [e for e in self.events if e["type"] == "m.room.message" and e["sender"] == BOT]

    def polls(self):
        return [e for e in self.events if e["type"] == "org.matrix.msc3381.poll.start"]

    def poll_for(self, text):
        found = [p for p in self.polls()
                 if text in p["content"]["org.matrix.msc3381.poll.start"]["question"]["org.matrix.msc1767.text"]]
        assert len(found) == 1, f"expected exactly one poll mentioning {text!r}, got {len(found)}"
        return found[0]["event_id"]


class FakeMemory:
    def __init__(self, opted_in=True):
        self.data = {"memory": {"opt_in": {"mail": opted_in} if opted_in is not None else {}}, "history": []}

    def read(self, base, auth, uid):
        return copy.deepcopy(self.data)

    def write(self, base, auth, uid, data):
        self.data = copy.deepcopy(data)

    @property
    def memory(self):
        return self.data["memory"]

    def history_kinds(self):
        return [h["kind"] for h in self.data["history"]]


def event_result(important=False, start="2099-01-10T19:00:00Z"):
    return {
        "has_event": True, "has_reminder": False, "important": important,
        "important_reason": "urgent" if important else None,
        "event": {"title": "Dîner", "start_local": "2099-01-10T20:00:00", "start_utc": start, "duration_kind": "rdv"},
        "reminder": None,
    }


REMINDER_RESULT = {"has_event": False, "has_reminder": True, "important": False, "event": None,
                   "reminder": {"title": "Colis", "due_local": None}}
IMPORTANT_ONLY = {"has_event": False, "has_reminder": False, "important": True,
                  "important_reason": "Paiement", "event": None, "reminder": None}
NOTHING = {"has_event": False, "has_reminder": False, "important": False, "event": None, "reminder": None}


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.room = FakeRoom()
        self.mem = FakeMemory()
        self.mailbox_messages: list[dict] = []     # newest first, like IMAP listing
        self.extractions: dict[str, dict] = {}
        self.extract_calls: list[str] = []
        self.event_writes: list[dict] = []
        self.task_writes: list[dict] = []
        self._patchers: list = []
        self._install_patches()

    def _install_patches(self):
        @contextmanager
        def fake_nc():
            yield "http://nc"

        def fake_extract(frm, subj, body):
            self.extract_calls.append(subj)
            return copy.deepcopy(self.extractions[subj])

        patches = {
            "nextcloud_port_forward": fake_nc,
            "read_memory": lambda *a: self.mem.read(*a),
            "write_memory": lambda *a: self.mem.write(*a),
            "has_opted_in": lambda b, a, u, s: self.mem.memory.get("opt_in", {}).get(s),
            "get_or_create_dm": lambda matrix_id: ROOM,
            "send_proposal": lambda *a, **k: self.room.send_proposal(*a, **k),
            "send_poll": lambda *a, **k: self.room.send_poll(*a, **k),
            "end_poll": lambda *a, **k: self.room.end_poll(*a, **k),
            "get_poll_vote": lambda *a, **k: self.room.get_poll_vote(*a, **k),
            "get_replies_after": lambda *a, **k: self.room.get_replies_after(*a, **k),
            "list_recent_messages": lambda mb, pw, limit=10: list(self.mailbox_messages),
            "fetch_message_text": lambda mb, pw, uid: "corps",
            "extract_from_email": fake_extract,
            "find_or_create_task_list": lambda b, a, u: ("liste", "Ma liste"),
            "write_event": lambda *a, **k: self.event_writes.append({"args": a, "kwargs": k}),
            "write_task": lambda *a, **k: self.task_writes.append({"args": a, "kwargs": k}),
        }
        for name, fn in patches.items():
            p = mock.patch.object(orch, name, fn)
            p.start()
            self.addCleanup(p.stop)

    def add_mail(self, uid, subject, result):
        self.mailbox_messages.insert(0, {"uid": str(uid), "from": "resa@example.com", "subject": subject,
                                         "date": "Thu, 24 Sep 2026 10:00:00 +0000"})
        self.extractions[subject] = result

    def tick(self):
        orch.process_user(HUMAN, "ncuid", MAILBOX, "imap-pw", "nc-pw")

    def pendings(self):
        return self.mem.memory.get("pending_proposals", [])

    def deferred(self):
        return self.mem.memory.get("deferred", {})

    # --- defect 1: re-sending every tick -----------------------------------

    def test_unanswered_proposal_is_never_resent(self):
        self.add_mail(5, "Résa", event_result())
        for _ in range(3):
            self.tick()
        self.assertEqual(len(self.room.messages()), 1, "detail message re-sent on a later tick")
        self.assertEqual(len(self.room.polls()), 1, "poll re-sent on a later tick")
        self.assertEqual(self.event_writes, [])

    # --- defect 2: answers attributed to the wrong proposal -----------------

    def test_votes_are_per_proposal(self):
        self.add_mail(5, "Mail-A", event_result())
        self.add_mail(6, "Mail-B", event_result())
        self.tick()
        self.assertEqual(len(self.room.polls()), 2)
        self.room.human_votes(self.room.poll_for("Mail-A"), "yes")
        self.tick()
        self.assertEqual(len(self.event_writes), 1)
        self.assertEqual(self.event_writes[0]["kwargs"]["uid"], orch._caldav_uid(MAILBOX, "5", "event"))
        self.assertEqual([p["payload"]["mail"]["subject"] for p in self.pendings()], ["Mail-B"])
        self.assertIn(self.room.poll_for("Mail-A"), self.room.ended)
        self.assertNotIn(self.room.poll_for("Mail-B"), self.room.ended)

    def test_plain_text_is_not_an_answer_even_with_a_single_proposal(self):
        self.add_mail(5, "Résa", event_result())
        self.tick()
        self.room.human_says("oui")
        self.tick()
        self.assertEqual(self.event_writes, [])
        self.assertEqual(len(self.pendings()), 1)

    def test_text_reply_to_the_proposal_message_or_poll_is_accepted(self):
        for target in ("message", "poll"):
            with self.subTest(target=target):
                self.setUp()
                self.add_mail(5, "Résa", event_result())
                self.tick()
                reply_to = self.room.messages()[0]["event_id"] if target == "message" else self.room.poll_for("Résa")
                self.room.human_says("oui merci", reply_to=reply_to)
                self.tick()
                self.assertEqual(len(self.event_writes), 1)

    def test_text_reply_aimed_at_another_message_is_ignored(self):
        self.add_mail(5, "Mail-A", event_result())
        self.add_mail(6, "Mail-B", event_result())
        self.tick()
        # "oui" typed as a reply to B's message must not confirm A
        b_message = [m for m in self.room.messages() if "Mail-B" in m["content"]["body"]][0]["event_id"]
        self.room.human_says("oui", reply_to=b_message)
        self.tick()
        self.assertEqual(len(self.event_writes), 1)
        self.assertEqual(self.event_writes[0]["kwargs"]["uid"], orch._caldav_uid(MAILBOX, "6", "event"))
        self.assertEqual([p["payload"]["mail"]["subject"] for p in self.pendings()], ["Mail-A"])

    def test_unclear_text_reply_is_ignored(self):
        self.add_mail(5, "Résa", event_result())
        self.tick()
        self.room.human_says("hmm je sais pas", reply_to=self.room.messages()[0]["event_id"])
        self.tick()
        self.assertEqual(self.event_writes, [])
        self.assertEqual(len(self.pendings()), 1)

    # --- normal answers -------------------------------------------------------

    def test_vote_yes_writes_once_and_closes_the_poll(self):
        self.add_mail(5, "Résa", event_result())
        self.tick()
        poll = self.room.poll_for("Résa")
        self.room.human_votes(poll, "yes")
        self.tick()
        self.tick()                                       # must not write again
        self.assertEqual(len(self.event_writes), 1)
        self.assertIn("5", self.mem.memory["processed_mail_uids"])
        self.assertEqual(self.pendings(), [])
        self.assertEqual(self.room.ended, [poll])
        self.assertEqual(self.mem.history_kinds()[-1], "mail_proposal_accepted")

    def test_vote_no_writes_nothing_and_is_not_proposed_again(self):
        self.add_mail(5, "Résa", event_result())
        self.tick()
        self.room.human_votes(self.room.poll_for("Résa"), "no")
        self.tick()
        self.tick()
        self.assertEqual(self.event_writes, [])
        self.assertEqual(len(self.room.polls()), 1)
        self.assertEqual(self.mem.history_kinds()[-1], "mail_proposal_declined")

    def test_a_changed_vote_counts_latest_wins(self):
        self.add_mail(5, "Résa", event_result())
        self.tick()
        poll = self.room.poll_for("Résa")
        self.room.human_votes(poll, "yes")
        self.room.human_votes(poll, "no")
        self.tick()
        self.assertEqual(self.event_writes, [])
        self.assertEqual(self.mem.history_kinds()[-1], "mail_proposal_declined")

    def test_a_cleared_vote_is_not_an_answer(self):
        self.add_mail(5, "Résa", event_result())
        self.tick()
        poll = self.room.poll_for("Résa")
        self.room.human_votes(poll, "yes")
        self.room.human_votes(poll, None)
        self.tick()
        self.assertEqual(self.event_writes, [])
        self.assertEqual(len(self.pendings()), 1)

    def test_reminder_goes_to_the_resolved_list_and_the_poll_names_it(self):
        self.add_mail(5, "Colis", REMINDER_RESULT)
        self.tick()
        question = self.room.polls()[0]["content"]["org.matrix.msc3381.poll.start"]["question"]["org.matrix.msc1767.text"]
        self.assertIn("Ma liste", question)
        self.room.human_votes(self.room.poll_for("Colis"), "yes")
        self.tick()
        self.assertEqual(self.task_writes[0]["kwargs"]["task_list"], "liste")

    def test_poll_question_names_the_mail_and_the_target(self):
        self.add_mail(5, "Réservation du 18", event_result())
        self.tick()
        q = self.room.polls()[0]["content"]["org.matrix.msc3381.poll.start"]["question"]["org.matrix.msc1767.text"]
        self.assertIn("Réservation du 18", q)
        self.assertIn("« Personnel »", q)

    # --- limits and the queue -------------------------------------------------

    def test_at_most_five_open_proposals_and_analysis_is_cached(self):
        for uid in range(1, 8):
            self.add_mail(uid, f"Mail-{uid}", event_result())
        self.tick()
        self.tick()
        self.assertEqual(len(self.room.polls()), orch.MAX_PENDING)
        self.assertEqual(len(self.deferred()), 2)
        self.assertEqual(len(self.extract_calls), 7, "a queued mail was analysed again")

    def test_the_queue_drains_as_answers_free_slots_without_reanalysis(self):
        for uid in range(1, 8):
            self.add_mail(uid, f"Mail-{uid}", event_result())
        self.tick()
        for p in self.room.polls()[:2]:
            self.room.human_votes(p["event_id"], "no")
        self.tick()
        self.assertEqual(len(self.room.polls()), 7)
        self.assertEqual(self.deferred(), {})
        self.assertEqual(len(self.extract_calls), 7)

    def test_urgent_mail_may_exceed_the_normal_cap_up_to_the_hard_ceiling(self):
        for uid in range(1, 6):
            self.add_mail(uid, f"Normal-{uid}", event_result())
        self.tick()
        self.assertEqual(len(self.room.polls()), orch.MAX_PENDING)
        for uid in range(10, 16):                              # six urgent mails arrive
            self.add_mail(uid, f"Urgent-{uid}", event_result(important=True))
        self.tick()
        self.assertEqual(len(self.room.polls()), orch.MAX_PENDING_URGENT)
        self.assertEqual(len(self.deferred()), 1, "hard ceiling not enforced")

    def test_a_normal_mail_does_not_use_the_urgent_headroom(self):
        for uid in range(1, 6):
            self.add_mail(uid, f"Normal-{uid}", event_result())
        self.tick()
        self.add_mail(20, "Un-de-plus", event_result())
        self.tick()
        self.assertEqual(len(self.room.polls()), orch.MAX_PENDING)
        self.assertIn("20", self.deferred())

    def test_urgent_mail_is_proposed_before_older_normal_ones(self):
        for uid in (1, 2, 4, 5, 6, 7):
            self.add_mail(uid, f"Normal-{uid}", event_result())
        self.add_mail(3, "Urgent-3", event_result(important=True))   # older than most, still first
        self.tick()
        self.assertEqual(len(self.room.polls()), orch.MAX_PENDING)
        self.room.poll_for("Urgent-3")                                # raises if it was left in the queue

    def test_an_event_that_has_started_while_queued_is_dropped_not_proposed(self):
        self.add_mail(5, "Périmé", event_result(start="2000-01-10T19:00:00Z"))
        self.tick()
        self.assertEqual(self.room.polls(), [])
        self.assertIn("5", self.mem.memory["processed_mail_uids"])
        self.assertEqual(self.deferred(), {})

    def test_a_mail_stuck_in_the_queue_too_long_is_dropped(self):
        self.mem.data["memory"]["deferred"] = {"5": {
            "mail": {"uid": "5", "from": "x", "subject": "Vieux", "date": ""}, "result": event_result(),
            "task_list": None, "task_list_name": None, "urgent": False,
            "queued_at": (orch._now() - orch.DEFERRED_TTL - timedelta(hours=1)).isoformat(),
        }}
        self.tick()
        self.assertEqual(self.room.polls(), [])
        self.assertIn("5", self.mem.memory["processed_mail_uids"])

    # --- expiry ---------------------------------------------------------------

    def test_expired_proposal_is_dropped_and_its_poll_closed(self):
        self.add_mail(5, "Résa", event_result())
        self.tick()
        self.mem.data["memory"]["pending_proposals"][0]["created_at"] = (orch._now() - timedelta(hours=49)).isoformat()
        self.tick()
        self.tick()
        self.assertEqual(self.event_writes, [])
        self.assertEqual(len(self.room.polls()), 1)
        self.assertEqual(self.pendings(), [])
        self.assertEqual(len(self.room.ended), 1)
        self.assertEqual(self.mem.history_kinds()[-1], "mail_proposal_expired")

    def test_one_expiring_does_not_touch_the_others(self):
        self.add_mail(5, "Mail-A", event_result())
        self.add_mail(6, "Mail-B", event_result())
        self.tick()
        for p in self.mem.data["memory"]["pending_proposals"]:
            if p["payload"]["mail"]["subject"] == "Mail-A":
                p["created_at"] = (orch._now() - timedelta(hours=49)).isoformat()
        self.tick()
        self.assertEqual([p["payload"]["mail"]["subject"] for p in self.pendings()], ["Mail-B"])

    # --- crash safety ---------------------------------------------------------

    def test_crash_before_anything_is_sent_resumes_with_the_same_transaction_ids(self):
        self.add_mail(5, "Résa", event_result())
        with mock.patch.object(orch, "send_proposal", side_effect=RuntimeError("killed")):
            with self.assertRaises(RuntimeError):
                self.tick()
        self.assertIsNone(self.pendings()[0]["poll_event_id"])        # persisted before sending
        self.assertEqual(self.room.events, [])
        self.tick()
        self.assertEqual((len(self.room.messages()), len(self.room.polls())), (1, 1))
        self.assertIsNotNone(self.pendings()[0]["poll_event_id"])

    def test_crash_between_the_message_and_the_poll_does_not_duplicate_the_message(self):
        self.add_mail(5, "Résa", event_result())
        with mock.patch.object(orch, "send_poll", side_effect=RuntimeError("killed")):
            with self.assertRaises(RuntimeError):
                self.tick()
        self.assertEqual((len(self.room.messages()), len(self.room.polls())), (1, 0))
        self.tick()
        self.assertEqual((len(self.room.messages()), len(self.room.polls())), (1, 1), "message or poll duplicated")

    def test_crash_after_sending_but_before_recording_does_not_duplicate_anything(self):
        self.add_mail(5, "Résa", event_result())
        self.tick()
        self.mem.data["memory"]["pending_proposals"][0].update(message_event_id=None, poll_event_id=None, own_event_ids=[])
        self.tick()
        self.assertEqual((len(self.room.messages()), len(self.room.polls())), (1, 1), "duplicate after a crash")

    def test_replaying_an_accepted_proposal_targets_the_same_calendar_entry(self):
        a = orch._caldav_uid(MAILBOX, "5", "event")
        self.assertEqual(a, orch._caldav_uid(MAILBOX, "5", "event"))
        self.assertNotEqual(a, orch._caldav_uid(MAILBOX, "6", "event"))
        self.assertNotEqual(a, orch._caldav_uid(MAILBOX, "5", "task"))

    def test_a_poll_that_cannot_be_located_is_left_for_the_next_tick(self):
        self.add_mail(5, "Résa", event_result())
        self.tick()
        with mock.patch.object(orch, "get_poll_vote", side_effect=LookupError("not in the scanned history")):
            self.tick()
        self.assertEqual(self.event_writes, [])
        self.assertEqual(len(self.pendings()), 1)

    def test_transaction_ids_are_deterministic_and_distinct(self):
        self.assertEqual(orch._txn_id("notif", "a", "1"), orch._txn_id("notif", "a", "1"))
        self.assertNotEqual(orch._txn_id("notif", "a", "1"), orch._txn_id("notif", "a", "2"))
        self.assertNotEqual(orch._txn_id("notif", "a", "1"), orch._txn_id("proposal", "a", "1"))

    # --- other paths ----------------------------------------------------------

    def test_important_only_is_a_single_notification_with_no_question_and_no_poll(self):
        self.add_mail(5, "Impôts", IMPORTANT_ONLY)
        self.tick()
        self.tick()
        self.assertEqual(len(self.room.messages()), 1)
        self.assertEqual(self.room.polls(), [])
        self.assertIn("5", self.mem.memory["processed_mail_uids"])

    def test_crash_after_a_notification_is_sent_does_not_post_it_twice(self):
        """The notification's transaction id is recomputed on the retry (it
        isn't stored anywhere), so it must be deterministic — this is the
        path that depends on it."""
        self.add_mail(5, "Impôts", IMPORTANT_ONLY)
        with mock.patch.object(orch._Session, "_finish_mail", side_effect=RuntimeError("killed after send")):
            with self.assertRaises(RuntimeError):
                self.tick()
        self.assertEqual(len(self.room.messages()), 1)
        self.assertNotIn("5", self.mem.memory.get("processed_mail_uids", []))
        self.tick()
        self.assertEqual(len(self.room.messages()), 1, "notification posted twice after a crash")
        self.assertIn("5", self.mem.memory["processed_mail_uids"])

    # --- found on the first real tick -----------------------------------------

    def test_important_without_a_reason_never_prints_none(self):
        """Real: the model flagged a mail important with important_reason
        null and the proposal said "jugé important : None"."""
        result = event_result(important=True)
        result["important_reason"] = None
        self.add_mail(5, "Commande", result)
        self.add_mail(6, "Alerte", dict(IMPORTANT_ONLY, important_reason=None))
        self.tick()
        for message in self.room.messages():
            self.assertNotIn("None", message["content"]["body"])
            if "jugé important" in message["content"]["body"]:
                self.assertTrue(message["content"]["body"].rstrip().endswith("important.")
                                or "important." in message["content"]["body"])

    def test_the_analysis_budget_stops_scanning_but_still_proposes_from_the_queue(self):
        """Real: ten new mails took longer than the job's deadline. Once the
        budget is spent no further mail is analysed, but what is already
        queued is still proposed, and the rest is picked up next tick."""
        self.mem.data["memory"]["deferred"] = {"9": {
            "mail": {"uid": "9", "from": "x", "subject": "Déjà analysé", "date": ""}, "result": event_result(),
            "task_list_name": None, "urgent": False, "queued_at": orch._now().isoformat(),
        }}
        self.add_mail(10, "Pas encore analysé", event_result())
        with mock.patch.object(orch, "SCAN_BUDGET_S", 0):
            self.tick()
        self.assertEqual(self.extract_calls, [], "analysed a mail with no budget left")
        self.assertEqual(len(self.room.polls()), 1)
        self.room.poll_for("Déjà analysé")
        self.tick()                                       # next tick has budget again
        self.assertEqual(self.extract_calls, ["Pas encore analysé"])
        self.assertEqual(len(self.room.polls()), 2)

    def test_non_actionable_mail_is_marked_processed_silently_with_no_history(self):
        self.add_mail(5, "Newsletter", NOTHING)
        self.tick()
        self.assertEqual(self.room.events, [])
        self.assertIn("5", self.mem.memory["processed_mail_uids"])
        self.assertEqual(self.mem.data["history"], [])

    def test_nothing_actionable_does_not_block_a_later_actionable_mail(self):
        self.add_mail(5, "Résa", event_result())
        self.add_mail(6, "Newsletter", NOTHING)
        self.tick()
        self.assertEqual(len(self.room.polls()), 1)

    def test_opt_in_is_one_poll_asked_once_without_blocking(self):
        self.mem.data["memory"]["opt_in"] = {}
        self.add_mail(5, "Résa", event_result())
        self.tick()
        self.tick()
        self.assertEqual(len(self.room.polls()), 1, "opt-in question re-sent")
        self.assertEqual(self.pendings()[0]["kind"], "opt_in")
        self.assertEqual(self.extract_calls, [], "mail was read before consent")
        self.room.human_votes(self.room.polls()[0]["event_id"], "yes")
        self.tick()
        self.assertTrue(self.mem.memory["opt_in"]["mail"])
        self.assertEqual([p["kind"] for p in self.pendings()], ["mail_proposal"])   # same tick carries on

    def test_declined_opt_in_stops_everything(self):
        self.mem.data["memory"]["opt_in"] = {"mail": False}
        self.add_mail(5, "Résa", event_result())
        self.tick()
        self.assertEqual(self.room.events, [])
        self.assertEqual(self.extract_calls, [])


if __name__ == "__main__":
    unittest.main()
