"""Reads/writes one Phase 5 IA memory file per user, inside their own
Nextcloud — the isolation mechanism decided in the Phase 5 planning doc:
rather than build a new per-user access-control system for the AI's
memory, it lives as an ordinary file in the same Nextcloud account the
person already has exclusive access to.

Phase 5 step 2 (see the planning doc's "Plan d'implémentation") — depends
on step 1 (`user_directory.py`) for the Nextcloud `user_oidc` uid, and
feeds every later step: the extraction pipeline reads/updates this file,
the traceability requirement (a "sujet manquant" in the same doc) is the
`history` list inside it.

File: `/Phase5-IA/memoire.json` in the user's own files, written via
WebDAV over an **app-password token**, never a local password — the same
constraint already documented for CalDAV writes (`occ user:auth-tokens:add`,
notes-techniques.md): a `user_oidc`-provisioned account has no local
password to authenticate with at all.

Real scope decision made here: minting that app-password itself
(`occ user:auth-tokens:add`) is blocked for Claude Code by the same
auto-mode classifier as the email fix in user_directory.py — creating a
new credential is exactly the kind of action that boundary exists for.
This module therefore takes the app-password as an input (env var for
now) rather than generating it. Storing one durably per user (a
Kubernetes Secret, most likely) is real follow-up work, deliberately not
guessed at here — out of scope for what step 2 actually needs, which is
the read/write mechanism itself.

Usage:
    # One-off, run by hand (Claude Code is blocked from minting tokens):
    kubectl exec -n nextcloud deploy/nextcloud -- php occ user:auth-tokens:add \\
        --name "phase5-ia-memoire" <nextcloud_uid>
    # Prints the app-password once — save it, Nextcloud never shows it again.

    export NEXTCLOUD_APP_PASSWORD=<the token above>
    python3 phase5/user_memory.py <nextcloud_uid>   # round-trip self-test

Concurrency: simple read-modify-write, no locking. Fine at this project's
scale (one background job at a time per user, never two Phase 5 processes
racing on the same file) — not a general-purpose datastore.
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

from user_directory import nextcloud_port_forward

MEMORY_DIR = "Phase5-IA"
MEMORY_FILENAME = "memoire.json"

DEFAULT_MEMORY = {"memory": {}, "history": []}


def info(msg: str) -> None:
    print(f"[user-memory] {msg}", file=sys.stderr)


def _webdav_path(nc_uid: str) -> str:
    return f"/remote.php/dav/files/{nc_uid}/{MEMORY_DIR}/{MEMORY_FILENAME}"


def _ensure_folder(base: str, auth: tuple[str, str], nc_uid: str) -> None:
    url = f"{base}/remote.php/dav/files/{nc_uid}/{MEMORY_DIR}"
    r = requests.request("MKCOL", url, auth=auth, timeout=10)
    if r.status_code not in (201, 405):  # 405 = already exists
        r.raise_for_status()


def read_memory(base: str, auth: tuple[str, str], nc_uid: str) -> dict:
    r = requests.get(f"{base}{_webdav_path(nc_uid)}", auth=auth, timeout=10)
    if r.status_code == 404:
        return dict(DEFAULT_MEMORY)
    r.raise_for_status()
    return r.json()


def write_memory(base: str, auth: tuple[str, str], nc_uid: str, data: dict) -> None:
    _ensure_folder(base, auth, nc_uid)
    r = requests.put(
        f"{base}{_webdav_path(nc_uid)}",
        auth=auth,
        data=json.dumps(data, indent=2, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    r.raise_for_status()


def append_history(base: str, auth: tuple[str, str], nc_uid: str, entry: dict) -> dict:
    """Read-modify-write: appends one entry (proposé/accepté/rejeté) with a timestamp."""
    data = read_memory(base, auth, nc_uid)
    entry = {"at": datetime.now(timezone.utc).isoformat(), **entry}
    data.setdefault("history", []).append(entry)
    write_memory(base, auth, nc_uid, data)
    return data


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: user_memory.py <nextcloud_uid>")
    nc_uid = sys.argv[1]

    app_password = os.environ.get("NEXTCLOUD_APP_PASSWORD")
    if not app_password:
        raise SystemExit(
            "Set NEXTCLOUD_APP_PASSWORD (see this script's usage notes for how to "
            "mint one via occ user:auth-tokens:add — Claude Code can't do it itself)."
        )
    auth = (nc_uid, app_password)

    with nextcloud_port_forward() as base:
        info("Reading current memory...")
        before = read_memory(base, auth, nc_uid)
        info(f"Current: {json.dumps(before, ensure_ascii=False)}")

        info("Appending a test history entry...")
        after = append_history(
            base, auth, nc_uid,
            {"kind": "self-test", "detail": "phase5/user_memory.py round-trip check"},
        )

        info("Re-reading to confirm the write actually persisted (not just accepted)...")
        reread = read_memory(base, auth, nc_uid)
        if reread != after:
            raise SystemExit(f"Round-trip mismatch: wrote {after!r}, read back {reread!r}")

        print(json.dumps(reread, indent=2, ensure_ascii=False))
        info("Round-trip confirmed: write persisted and reads back identical.")


if __name__ == "__main__":
    main()
