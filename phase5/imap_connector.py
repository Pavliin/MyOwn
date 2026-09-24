"""Real IMAP connector to Mailu — Phase 5 step 5, replaces the
2026-09-16 prototype's GreenMail (disposable test SMTP/IMAP server) with
the actual mail service.

Read-only at this stage, deliberately: lists/fetches recent messages,
never marks them read, never moves/deletes/labels anything. Step 5's own
scope in the planning doc is explicitly "aucune écriture, aucun
classement" — that's steps 6-7 (extraction, CalDAV/Sieve writes), not
this one.

Reaches Mailu directly on the mini PC's LAN IMAPS endpoint
(`front.externalService`, `gitops/apps/mailu.yaml`) — no port-forward or
SSH tunnel needed, confirmed live (`openssl s_client` to
192.168.1.143:993 presents Mailu's real Let's Encrypt chain).

Credentials: a mailbox auto-provisioned by Mailu's SSO ForwardAuth
(`proxyAuth.create`) gets a random internal password nobody — including
its own owner — ever sees, since login always goes through SSO. Same
class of problem step 2 solved for Nextcloud with an app-password token;
Mailu has no equivalent "app password" feature, so the substitute here is
setting a dedicated password via Mailu's own admin API (`PATCH
/api/v1/user/<email>` with `raw_password`) instead of a webmail one —
never learning or touching whatever a person would actually type into
their own mail client. Minting it is blocked for Claude Code by the same
auto-mode classifier as every other credential-creation step so far
(email fix, Nextcloud token) — see this script's usage notes for the
one-off command.

Usage:
    # One-off, run by hand (Claude Code is blocked from setting it):
    MAILU_API_TOKEN=$(sops -d gitops/secrets/mailu/mailu.sops.yaml | yq '.stringData.API_TOKEN')
    ssh 192.168.1.143 "sudo kubectl exec -n mailu deploy/mailu-admin -- curl -s -X PATCH \\
        -H \"Authorization: Bearer $MAILU_API_TOKEN\" -H 'Content-Type: application/json' \\
        -d '{\"raw_password\": \"<a-generated-password>\"}' \\
        http://localhost:8080/api/v1/user/robin.chartier@offsystem.fr"
    # Save the password you generated — Mailu only stores its hash.

    export MAILU_IMAP_PASSWORD=<the password above>
    python3 phase5/imap_connector.py robin.chartier@offsystem.fr
"""

import email.header
import email.utils
import imaplib
import os
import sys

IMAP_HOST = os.environ.get("MAILU_IMAP_HOST", "192.168.1.143")
IMAP_PORT = 993


def info(msg: str) -> None:
    print(f"[imap] {msg}", file=sys.stderr)


def _decode_header(raw: str | None) -> str:
    if not raw:
        return ""
    parts = email.header.decode_header(raw)
    return "".join(
        part.decode(enc or "utf-8", errors="replace") if isinstance(part, bytes) else part
        for part, enc in parts
    )


def list_recent_messages(mailbox: str, password: str, folder: str = "INBOX", limit: int = 10) -> list[dict]:
    """Real IMAP, read-only mode (`readonly=True`) so selecting the folder
    itself can never flip a message's \\Seen flag as a side effect —
    peeks headers explicitly for the same reason, never plain FETCH."""
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    try:
        conn.login(mailbox, password)
        conn.select(folder, readonly=True)

        status, data = conn.search(None, "ALL")
        if status != "OK":
            raise RuntimeError(f"IMAP SEARCH failed: {status} {data}")
        uids = data[0].split()
        recent = uids[-limit:] if limit else uids

        messages = []
        for uid in reversed(recent):
            status, data = conn.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if status != "OK" or not data or data[0] is None:
                continue
            raw_headers = data[0][1].decode("utf-8", errors="replace")
            headers = email.message_from_string(raw_headers)
            messages.append({
                "uid": uid.decode(),
                "from": _decode_header(headers.get("From")),
                "subject": _decode_header(headers.get("Subject")),
                "date": headers.get("Date"),
            })
        return messages
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def fetch_message_text(mailbox: str, password: str, uid: str, folder: str = "INBOX") -> str:
    """Plain-text body of one message, still read-only (BODY.PEEK[]) —
    needed by the extraction pipeline (step 6), which list_recent_messages
    alone (headers only) can't feed. Falls back to the first text/html
    part, stripped of tags, if no text/plain part exists."""
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    try:
        conn.login(mailbox, password)
        conn.select(folder, readonly=True)

        status, data = conn.fetch(uid.encode() if isinstance(uid, str) else uid, "(BODY.PEEK[])")
        if status != "OK" or not data or data[0] is None:
            raise RuntimeError(f"IMAP FETCH failed for uid {uid}: {status} {data}")
        raw = data[0][1]
        msg = email.message_from_bytes(raw)

        text_part = None
        html_part = None
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            charset = part.get_content_charset() or "utf-8"
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            content = payload.decode(charset, errors="replace")
            if part.get_content_type() == "text/plain" and text_part is None:
                text_part = content
            elif part.get_content_type() == "text/html" and html_part is None:
                html_part = content

        if text_part:
            return text_part.strip()
        if html_part:
            import re
            return re.sub(r"<[^>]+>", " ", html_part).strip()
        return ""
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: imap_connector.py <mailbox-email>")
    mailbox = sys.argv[1]

    password = os.environ.get("MAILU_IMAP_PASSWORD")
    if not password:
        raise SystemExit("Set MAILU_IMAP_PASSWORD (see this script's usage notes).")

    info(f"Connecting to {IMAP_HOST}:{IMAP_PORT} as {mailbox} (read-only)...")
    messages = list_recent_messages(mailbox, password)
    info(f"{len(messages)} message(s) in INBOX, most recent first:")
    for m in messages:
        print(f"  [{m['uid']}] {m['date']} — {m['from']} — {m['subject']}")


if __name__ == "__main__":
    main()
