"""Writes a calendar event (VEVENT) or task (VTODO) to a user's own
Nextcloud via CalDAV — Phase 5 step 7 (calendar/task half; the Sieve
half is sieve_writer.py). Only ever called after a real human
confirmation (opt_in.py/matrix_dm.py) — this module itself has no
concept of consent, it just writes what it's told.

Calendar name confirmed live via PROPFIND against @robin's real account
(`personal`, displayed as "Personnel") rather than assumed — same
verification discipline as the original mail-pipeline prototype
(notes-techniques.md: "confirmé PROPFIND, pas deviné").

Real assumption proven wrong live, caught by an actual write attempt, not
a docs read: a calendar collection isn't a generic bucket for any
component type. `personal`'s own `supported-calendar-component-set`
(checked via PROPFIND) is VEVENT-only — writing a VTODO there 403s.
Nextcloud only creates a VTODO-capable list once someone opens the Tasks
app for the first time, so a list has to be found or created anyway.

Tasks go in a **dedicated list, "Myo's help"**, never in whichever
VTODO-capable list happens to exist. The first version took the first one
it found, which on the real account was the user's own personal packing
list ("to take to bretagne") — a "pick up your parcel" task has no business
there, and a decision made by the user on seeing it in a real proposal.
`find_or_create_task_list()` therefore only ever returns that one list,
creating it (MKCALENDAR, VTODO-only) if absent. The proposal names it
up front from the constant below, without touching Nextcloud: *creating*
the list is a write, and nothing is written before the person says yes.

Real gotcha already documented, applied here rather than rediscovered:
floating time (no timezone) saves and reads back fine via the API but
never renders in Nextcloud's Calendar UI. Every DTSTART/DTEND/DUE this
module writes is UTC with an explicit "Z" — the extraction pipeline
(step 6) already asks the model for exactly that format, this is the
other half of actually getting it right.

Usage:
    export NEXTCLOUD_APP_PASSWORD=...   # for the TARGET user's own uid
    export PHASE5_SSH_HOST=192.168.1.143
    python3 phase5/caldav_writer.py <nextcloud_uid> event "Titre" 2026-09-18T12:15:00Z 2026-09-18T13:15:00Z
    python3 phase5/caldav_writer.py <nextcloud_uid> task "Titre" [2026-10-05T00:00:00Z]
"""

import sys
import uuid
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape
from datetime import datetime, timedelta, timezone

import requests

from user_directory import nextcloud_port_forward

CALENDAR = "personal"
CALENDAR_DISPLAY_NAME = "Personnel"  # confirmed via PROPFIND displayname, not guessed
TASK_LIST_SEGMENT = "myo-help"
TASK_LIST_DISPLAY_NAME = "Myo's help"

DAV_NS = "DAV:"
CAL_NS = "urn:ietf:params:xml:ns:caldav"


def info(msg: str) -> None:
    print(f"[caldav] {msg}", file=sys.stderr)


def _now_utc_ics() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _to_ics_utc(iso_z: str) -> str:
    """'2026-09-18T12:15:00Z' -> '20260918T121500Z' (iCalendar's own UTC
    form) — refuses anything not explicitly UTC, on purpose: a floating
    or offset timestamp reaching here means the extraction step (6)
    didn't follow its own prompt, better to fail loudly than silently
    write an invisible event again."""
    if not iso_z.endswith("Z"):
        raise ValueError(f"Not an explicit UTC timestamp (missing 'Z'): {iso_z!r}")
    dt = datetime.strptime(iso_z, "%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y%m%dT%H%M%SZ")


DEFAULT_DURATION_MINUTES = {"rdv": 60, "action": 20}


def _default_end(start_utc: str, duration_kind: str) -> str:
    """Real gap found live: events with no end_local ended up with
    DTEND == DTSTART (a zero-duration calendar entry) — silently correct
    per the ICS spec but useless to look at. duration_kind ("rdv" vs
    "action", extraction.py) picks a sensible default instead of assuming
    one size fits all: an hour for an appointment-style event, ~20 min
    for a quick errand."""
    minutes = DEFAULT_DURATION_MINUTES.get(duration_kind, DEFAULT_DURATION_MINUTES["rdv"])
    dt = datetime.strptime(start_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (dt + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_event(base: str, nc_auth: tuple[str, str], nc_uid: str, summary: str, start_utc: str, end_utc: str | None = None, duration_kind: str = "rdv", uid: str | None = None) -> str:
    """Returns the event's iCalendar UID. end_utc defaults via
    _default_end() when not given, instead of collapsing to a
    zero-duration event.

    `uid`: pass a deterministic one when the caller may retry (the CronJob
    does, after a crash between "write" and "remember I wrote"). The
    resource URL is derived from it, so a retry overwrites the same event
    instead of creating a second one."""
    if not end_utc:
        end_utc = _default_end(start_utc, duration_kind)
    event_uid = uid or str(uuid.uuid4())
    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//MyOwn//Phase5//FR\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{event_uid}\r\n"
        f"DTSTAMP:{_now_utc_ics()}\r\n"
        f"DTSTART:{_to_ics_utc(start_utc)}\r\n"
        f"DTEND:{_to_ics_utc(end_utc)}\r\n"
        f"SUMMARY:{summary}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    url = f"{base}/remote.php/dav/calendars/{nc_uid}/{CALENDAR}/{event_uid}.ics"
    r = requests.put(url, auth=nc_auth, data=ics.encode(), headers={"Content-Type": "text/calendar; charset=utf-8"}, timeout=10)
    r.raise_for_status()
    info(f"Event written: {summary!r} ({start_utc} -> {end_utc}), uid={event_uid}")
    return event_uid


def find_or_create_task_list(base: str, nc_auth: tuple[str, str], nc_uid: str) -> tuple[str, str]:
    """Returns (path_segment, display_name) of the dedicated task list,
    creating it if it doesn't exist yet. Only ever that list — see the
    module docstring for why not "any VTODO-capable list"."""
    body = (
        '<?xml version="1.0"?>'
        '<d:propfind xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">'
        '<d:prop><d:resourcetype/><d:displayname/><cal:supported-calendar-component-set/></d:prop>'
        '</d:propfind>'
    )
    home = f"{base}/remote.php/dav/calendars/{nc_uid}/"
    r = requests.request("PROPFIND", home, auth=nc_auth, data=body,
                          headers={"Depth": "1", "Content-Type": "application/xml"}, timeout=10)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    for response in root.findall(f"{{{DAV_NS}}}response"):
        href = response.findtext(f"{{{DAV_NS}}}href")
        segment = href.rstrip("/").rsplit("/", 1)[-1]
        display_name = response.findtext(f".//{{{DAV_NS}}}displayname")
        if segment != TASK_LIST_SEGMENT and display_name != TASK_LIST_DISPLAY_NAME:
            continue
        comps = response.findall(f".//{{{CAL_NS}}}supported-calendar-component-set/{{{CAL_NS}}}comp")
        if "VTODO" not in {c.get("name") for c in comps}:
            raise RuntimeError(
                f"{segment!r} exists but doesn't accept tasks (VTODO) — won't write into it, "
                "and can't create the dedicated list over it."
            )
        return segment, display_name or TASK_LIST_DISPLAY_NAME

    info(f"Dedicated task list not found, creating {TASK_LIST_DISPLAY_NAME!r}...")
    mkcalendar_body = (
        '<?xml version="1.0"?>'
        '<c:mkcalendar xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
        '<d:set><d:prop>'
        f'<d:displayname>{xml_escape(TASK_LIST_DISPLAY_NAME)}</d:displayname>'
        '<c:supported-calendar-component-set><c:comp name="VTODO"/></c:supported-calendar-component-set>'
        '</d:prop></d:set>'
        '</c:mkcalendar>'
    )
    r = requests.request(
        "MKCALENDAR", f"{home}{TASK_LIST_SEGMENT}/", auth=nc_auth, data=mkcalendar_body,
        headers={"Content-Type": "application/xml"}, timeout=10,
    )
    r.raise_for_status()
    return TASK_LIST_SEGMENT, TASK_LIST_DISPLAY_NAME


def write_task(base: str, nc_auth: tuple[str, str], nc_uid: str, summary: str, due_utc: str | None = None, task_list: str | None = None, uid: str | None = None) -> str:
    """Returns the task's iCalendar UID. Resolves a VTODO-capable list
    via find_or_create_task_list() if task_list isn't given explicitly.
    `uid`: deterministic when the caller may retry — see write_event()."""
    if task_list is None:
        task_list, _ = find_or_create_task_list(base, nc_auth, nc_uid)

    task_uid = uid or str(uuid.uuid4())
    due_line = f"DUE:{_to_ics_utc(due_utc)}\r\n" if due_utc else ""
    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//MyOwn//Phase5//FR\r\n"
        "BEGIN:VTODO\r\n"
        f"UID:{task_uid}\r\n"
        f"DTSTAMP:{_now_utc_ics()}\r\n"
        f"SUMMARY:{summary}\r\n"
        f"{due_line}"
        "STATUS:NEEDS-ACTION\r\n"
        "END:VTODO\r\n"
        "END:VCALENDAR\r\n"
    )
    url = f"{base}/remote.php/dav/calendars/{nc_uid}/{task_list}/{task_uid}.ics"
    r = requests.put(url, auth=nc_auth, data=ics.encode(), headers={"Content-Type": "text/calendar; charset=utf-8"}, timeout=10)
    r.raise_for_status()
    info(f"Task written: {summary!r} (due {due_utc or 'none'}), uid={task_uid}")
    return task_uid


def main() -> None:
    import os
    if len(sys.argv) < 4:
        raise SystemExit(
            "Usage:\n"
            "  caldav_writer.py <nextcloud_uid> event <summary> <start_utc> <end_utc>\n"
            "  caldav_writer.py <nextcloud_uid> task <summary> [due_utc]"
        )
    nc_uid, kind, summary = sys.argv[1:4]
    app_password = os.environ.get("NEXTCLOUD_APP_PASSWORD")
    if not app_password:
        raise SystemExit("Set NEXTCLOUD_APP_PASSWORD (see this script's usage notes).")
    nc_auth = (nc_uid, app_password)

    with nextcloud_port_forward() as base:
        if kind == "event":
            start_utc, end_utc = sys.argv[4], sys.argv[5]
            write_event(base, nc_auth, nc_uid, summary, start_utc, end_utc)
        elif kind == "task":
            due_utc = sys.argv[4] if len(sys.argv) > 4 else None
            write_task(base, nc_auth, nc_uid, summary, due_utc)
        else:
            raise SystemExit(f"Unknown kind {kind!r}, expected 'event' or 'task'")


if __name__ == "__main__":
    main()
