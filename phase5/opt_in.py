"""Explicit per-service opt-in gate — Phase 5 step 4.

Before any automation touches a real service on someone's behalf (their
mailbox first, others later), the bot must explicitly propose it in DM
and explain that processing stays local — a decision made directly from
a review comment on the Phase 5 planning doc, not an afterthought. Every
later connector (step 5 onward) must check `has_opted_in()` before doing
anything with a user's actual data — there's no other gate.

Persists the answer in the user's own memory file (user_memory.py,
step 2) under memory["opt_in"][<service>] — so the question is only asked
once per service, and stays answerable again later if the answer is ever
cleared (the "droit à l'oubli" gap the planning doc already flags as
open, not solved here).

Reads the DM reply in natural language (cadrage 1 from the planning doc:
"réponse scopée à une proposition", never a bare yes/no button) — but for
a consent gate specifically, an ambiguous or unrecognized reply must
never resolve to "yes" by default. request_opt_in() only records a
decision on a clear match and asks again otherwise: silence or ambiguity
is not consent, matching "l'IA propose, l'utilisateur valide" literally
rather than assuming intent.

Usage:
    export TUWUNEL_ALERTBOT_TOKEN=...
    export NEXTCLOUD_APP_PASSWORD=...   # for the TARGET user's own uid, not the bot's
    export PHASE5_SSH_HOST=192.168.1.143   # mini PC; unset = dev cluster
    python3 phase5/opt_in.py @robin:offsystem.fr ee9952eac6e5fc9bf11721e8376b405aeb60ec2a843f88691e16bca411a06ecc mail
"""

import os
import re
import sys

from matrix_dm import get_or_create_dm, send_proposal, wait_for_reply
from user_directory import nextcloud_port_forward
from user_memory import append_history, read_memory, write_memory

SERVICE_DESCRIPTIONS = {
    "mail": (
        "la lecture de tes mails, pour te proposer des rappels, des "
        "événements à ajouter au calendrier, ou un classement — jamais "
        "d'action automatique, toujours une proposition que tu valides "
        "toi-même."
    ),
}

# Real natural-language answers only, no button — deliberately narrow: an
# unmatched reply must fall through to "ask again", never guess.
YES_PATTERN = re.compile(r"\b(oui|ok|d'accord|daccord|yes|go)\b", re.IGNORECASE)
NO_PATTERN = re.compile(r"\b(non|no|pas maintenant|jamais)\b", re.IGNORECASE)


def info(msg: str) -> None:
    print(f"[opt-in] {msg}", file=sys.stderr)


def has_opted_in(base: str, nc_auth: tuple[str, str], nc_uid: str, service: str) -> bool | None:
    """None = never asked, True/False = the user's recorded answer."""
    data = read_memory(base, nc_auth, nc_uid)
    return data.get("memory", {}).get("opt_in", {}).get(service)


def _record_decision(base: str, nc_auth: tuple[str, str], nc_uid: str, service: str, decision: bool, raw_reply: str) -> None:
    data = read_memory(base, nc_auth, nc_uid)
    data.setdefault("memory", {}).setdefault("opt_in", {})[service] = decision
    write_memory(base, nc_auth, nc_uid, data)
    append_history(base, nc_auth, nc_uid, {
        "kind": "opt_in_decision", "service": service, "decision": decision, "raw_reply": raw_reply,
    })


def request_opt_in(
    base: str, nc_auth: tuple[str, str], nc_uid: str, matrix_id: str, service: str, max_attempts: int = 3,
) -> bool:
    """Asks in DM if not already answered; re-asks on an ambiguous reply
    rather than guessing. Raises if still unclear after max_attempts."""
    existing = has_opted_in(base, nc_auth, nc_uid, service)
    if existing is not None:
        info(f"{matrix_id} already answered for {service!r}: {existing}")
        return existing

    description = SERVICE_DESCRIPTIONS.get(service, service)
    room_id = get_or_create_dm(matrix_id)

    question = (
        f"🤖 Avant de commencer : je peux t'aider avec {description}\n\n"
        "Ce traitement tourne en local, sur le serveur — rien n'en sort jamais.\n\n"
        "Tu es d'accord pour que j'active ça (oui/non) ?"
    )
    for attempt in range(max_attempts):
        send_proposal(room_id, question if attempt == 0 else
                       "Je n'ai pas compris — réponds simplement oui ou non.")
        reply = wait_for_reply(room_id)
        body = reply["content"].get("body", "")
        is_yes = bool(YES_PATTERN.search(body))
        is_no = bool(NO_PATTERN.search(body))
        if is_yes and not is_no:
            _record_decision(base, nc_auth, nc_uid, service, True, body)
            info(f"{matrix_id} opted in to {service!r}")
            return True
        if is_no and not is_yes:
            _record_decision(base, nc_auth, nc_uid, service, False, body)
            info(f"{matrix_id} declined {service!r}")
            return False
        info(f"Ambiguous reply {body!r}, asking again ({attempt + 1}/{max_attempts})")

    raise RuntimeError(f"No clear answer from {matrix_id} for {service!r} after {max_attempts} attempts")


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("Usage: opt_in.py <matrix_id> <nextcloud_uid> <service>")
    matrix_id, nc_uid, service = sys.argv[1:4]

    app_password = os.environ.get("NEXTCLOUD_APP_PASSWORD")
    if not app_password:
        raise SystemExit("Set NEXTCLOUD_APP_PASSWORD (see this script's usage notes).")

    with nextcloud_port_forward() as base:
        nc_auth = (nc_uid, app_password)
        decision = request_opt_in(base, nc_auth, nc_uid, matrix_id, service)
        print(decision)


if __name__ == "__main__":
    main()
