"""Interpreting a human reply to a Phase 5 proposal.

Shared by opt_in.py (blocking, manual CLI) and orchestrator.py (the
asynchronous state machine the CronJob runs) so the "what counts as yes"
rule exists once.

A reply is only ever accepted on a clear match. Silence or ambiguity is
not consent: parse_yes_no() returns None for anything unclear, and the
caller asks once more (or gives up) rather than guessing — same
principle as step 4, kept deliberately narrow.
"""

import re

YES_PATTERN = re.compile(r"\b(oui|ok|d'accord|daccord|yes|go)\b", re.IGNORECASE)
NO_PATTERN = re.compile(r"\b(non|no|pas maintenant|jamais)\b", re.IGNORECASE)


def parse_yes_no(text: str) -> bool | None:
    """True / False on a clear answer, None if unclear (neither, or both)."""
    is_yes, is_no = bool(YES_PATTERN.search(text)), bool(NO_PATTERN.search(text))
    if is_yes and not is_no:
        return True
    if is_no and not is_yes:
        return False
    return None


def reply_target(event: dict) -> str | None:
    """The event_id a message explicitly replies to (Element's "Reply"),
    or None for a plain message.

    Several proposals can be open at once, so a plain "oui" typed into the
    room is *not* an answer to any of them — it would become attributable
    to the wrong one as soon as the others resolved. An answer is either a
    vote on the proposal's poll, or a text reply whose target is one of that
    proposal's own messages; anything else is ignored."""
    return (
        event.get("content", {})
        .get("m.relates_to", {})
        .get("m.in_reply_to", {})
        .get("event_id")
    )
