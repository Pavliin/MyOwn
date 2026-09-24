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
app for the first time (nothing forces that before this pipeline exists);
`find_or_create_task_list()` looks for an existing VTODO-capable
collection under the user's calendar home and creates one via MKCALENDAR
if none exists, rather than assuming `personal` (or any fixed name) works
for tasks.

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
from datetime import datetime, timezone

import requests

from user_directory import nextcloud_port_forward

CALENDAR = "personal"
TASK_LIST_FALLBACK_NAME = "phase5-taches"

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


def write_event(base: str, nc_auth: tuple[str, str], nc_uid: str, summary: str, start_utc: str, end_utc: str) -> str:
    """Returns the new event's iCalendar UID."""
    event_uid = str(uuid.uuid4())
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


def find_or_create_task_list(base: str, nc_auth: tuple[str, str], nc_uid: str) -> str:
    """Returns the path segment of a VTODO-capable calendar collection
    under nc_uid's calendar home, creating one (MKCALENDAR) if none
    exists yet — see this module's docstring for why `personal` alone
    can't be assumed."""
    body = (
        '<?xml version="1.0"?>'
        '<d:propfind xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">'
        '<d:prop><d:resourcetype/><cal:supported-calendar-component-set/></d:prop>'
        '</d:propfind>'
    )
    home = f"{base}/remote.php/dav/calendars/{nc_uid}/"
    r = requests.request("PROPFIND", home, auth=nc_auth, data=body,
                          headers={"Depth": "1", "Content-Type": "application/xml"}, timeout=10)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    for response in root.findall(f"{{{DAV_NS}}}response"):
        href = response.findtext(f"{{{DAV_NS}}}href")
        comps = response.findall(f".//{{{CAL_NS}}}supported-calendar-component-set/{{{CAL_NS}}}comp")
        comp_names = {c.get("name") for c in comps}
        if "VTODO" in comp_names:
            # href looks like /remote.php/dav/calendars/<uid>/<segment>/
            segment = href.rstrip("/").rsplit("/", 1)[-1]
            info(f"Found existing VTODO-capable list: {segment!r}")
            return segment

    info(f"No VTODO-capable list found, creating {TASK_LIST_FALLBACK_NAME!r}...")
    mkcalendar_body = (
        '<?xml version="1.0"?>'
        '<c:mkcalendar xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
        '<d:set><d:prop>'
        '<d:displayname>Tâches (Phase 5)</d:displayname>'
        '<c:supported-calendar-component-set><c:comp name="VTODO"/></c:supported-calendar-component-set>'
        '</d:prop></d:set>'
        '</c:mkcalendar>'
    )
    r = requests.request(
        "MKCALENDAR", f"{home}{TASK_LIST_FALLBACK_NAME}/", auth=nc_auth, data=mkcalendar_body,
        headers={"Content-Type": "application/xml"}, timeout=10,
    )
    r.raise_for_status()
    return TASK_LIST_FALLBACK_NAME


def write_task(base: str, nc_auth: tuple[str, str], nc_uid: str, summary: str, due_utc: str | None = None, task_list: str | None = None) -> str:
    """Returns the new task's iCalendar UID. Resolves a VTODO-capable list
    via find_or_create_task_list() if task_list isn't given explicitly."""
    if task_list is None:
        task_list = find_or_create_task_list(base, nc_auth, nc_uid)

    task_uid = str(uuid.uuid4())
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
