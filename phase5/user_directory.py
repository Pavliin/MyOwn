"""Resolves, for each real Authentik user, the identifiers the other Phase 5
connectors need: Matrix ID, Nextcloud `user_oidc` account, Mailu mailbox.

Phase 5 step 1 (see the Phase 5 planning doc, "Plan d'implémentation") —
blocking for every later connector (IMAP, Matrix DM, CalDAV/Sieve writers):
none of them can stay scoped to one user without this existing first.

Matrix ID is a direct, reliable mapping from the Authentik username
(Tuwunel's `userid_claims = ["preferred_username"]`, confirmed since the
2026-09-16 username-space fix — see notes-techniques.md) — no lookup
needed, just string formatting.

Nextcloud is NOT a direct mapping: `user_oidc` provisions an opaque
per-user id (a SHA-256 hash) at first SSO login. Tried recomputing it in
advance instead of looking it up — `user_oidc`'s own `LocalIdService.php`
computes it as `sha256(f"{provider_id}_0_{sub}")`, and the Nextcloud
provider's Authentik blueprint sets `sub_mode: user_uuid` — but no format
of the Authentik user's UUID (with/without dashes, with/without the
provider prefix) reproduced the real observed uid when checked live
against the dev cluster. Not chased further blind: this resolves it the
tested way instead, via Nextcloud's own OCS Provisioning API, matching on
email between Authentik and Nextcloud's `user_oidc` accounts.

Real gap found building this: Authentik's own `email` field can silently
drift from what's actually synced into Nextcloud, because each service
only pulls the claim at its *own* last login, not continuously. Confirmed
live on the dev cluster: `akadmin`'s Authentik email was still the
pre-bootstrap-fix default `root@example.com`, while Nextcloud's
`user_oidc` account still held the earlier `chartier.ro@gmail.com` value
synced at an older login — the two had quietly diverged. Matching
Authentik's *current* email against Nextcloud's would have silently
resolved nothing for that account. Resolved by fixing the drift as a
one-off (see the correction command in this script's usage notes) rather
than by guessing — and this script warns on a mismatch it can detect
(Nextcloud account exists but no Authentik user has that email) instead of
silently ignoring it, so a future drift doesn't fail silently either.

Mailu mailbox: no lookup exists yet for "does this mailbox really exist" —
this only checks whether the Authentik email's domain is one Mailu
manages (`MAILU_DOMAIN`), which is a real limitation: a user whose
Authentik email hasn't yet been switched to an `@offsystem.fr` address
(the roadmap's "migration progressive des correspondants") resolves to no
mailbox at all, correctly, but a user whose email *looks* right and simply
hasn't logged into Mailu yet (so `proxyAuth.create` hasn't auto-provisioned
them) will resolve to a mailbox guess that doesn't exist. Verifying against
Mailu's own admin API (same pattern as mailu-promote-admin.py) is a
reasonable next step once a connector actually needs to write to a
mailbox, not added here to avoid a premature dependency on
MAILU_API_TOKEN for a step that doesn't strictly need it yet.

Usage:
    python3 phase5/user_directory.py
    # Requires kubectl pointed at the right cluster/context.

    # One-off fix for the email-drift gap found above (dev cluster only,
    # run by hand — Claude Code is blocked from mutating account data):
    kubectl exec -n authentik deploy/authentik-server -- ak shell -c '
    from authentik.core.models import User
    u = User.objects.get(username="akadmin")
    u.email = "chartier.ro@gmail.com"
    u.save()
    print("email now:", u.refresh_from_db() or u.email)
    '

Read-only: this module only ever reads from Authentik/Nextcloud, never
writes. Safe to run repeatedly.
"""

import base64
import json
import subprocess
import sys
import time
from contextlib import contextmanager

import requests

AUTHENTIK_NAMESPACE = "authentik"
AUTHENTIK_DEPLOY = "deploy/authentik-server"

NEXTCLOUD_NAMESPACE = "nextcloud"
NEXTCLOUD_SERVICE = "svc/nextcloud"
NEXTCLOUD_LOCAL_PORT = 18099

# offsystem.fr, not a per-service *.offsystem.fr hostname: this is the
# Matrix server_name (fixed since the 2026-09-23 federation migration) and
# the domain Mailu manages for mailboxes — same value, two different roles.
MATRIX_SERVER_NAME = "offsystem.fr"
MAILU_DOMAIN = "offsystem.fr"

# AnonymousUser is Authentik's own internal pseudo-user, never a real
# person. internal_service_account covers outpost accounts (e.g.
# ak-outpost-...) — infrastructure, not family members.
EXCLUDED_USERNAMES = {"AnonymousUser"}
EXCLUDED_TYPES = {"internal_service_account"}


def info(msg: str) -> None:
    print(f"[user-directory] {msg}", file=sys.stderr)


def _kubectl_secret_value(namespace: str, secret: str, key: str) -> str:
    out = subprocess.run(
        [
            "kubectl", "get", "secret", "-n", namespace, secret,
            "-o", f"jsonpath={{.data.{key}}}",
        ],
        capture_output=True, text=True, check=True,
    ).stdout
    return base64.b64decode(out).decode()


def fetch_authentik_users() -> list[dict]:
    """Real Authentik accounts (username, email, display name)."""
    py = (
        "from authentik.core.models import User\n"
        "import json\n"
        "users = list(User.objects.filter(is_active=True).values("
        "'username', 'email', 'name', 'type'))\n"
        "print('###JSON###' + json.dumps(users))\n"
    )
    result = subprocess.run(
        ["kubectl", "exec", "-n", AUTHENTIK_NAMESPACE, AUTHENTIK_DEPLOY,
         "--", "ak", "shell", "-c", py],
        capture_output=True, text=True, check=True,
    )
    marker = "###JSON###"
    idx = result.stdout.find(marker)
    if idx == -1:
        raise RuntimeError(
            f"ak shell output missing the JSON marker — got:\n{result.stdout}\n{result.stderr}"
        )
    users = json.loads(result.stdout[idx + len(marker):].strip().splitlines()[0])
    return [
        u for u in users
        if u["username"] not in EXCLUDED_USERNAMES and u["type"] not in EXCLUDED_TYPES
    ]


@contextmanager
def nextcloud_port_forward():
    """Yields Nextcloud's base URL over a live `kubectl port-forward`.

    Shared by every Phase 5 module that needs to reach Nextcloud's HTTP API
    (OCS here, WebDAV in user_memory.py) — Nextcloud isn't reachable
    directly from the dev machine outside the cluster's own Ingress
    hostnames, and those require the mkcert/Let's Encrypt TLS dance this
    kind of short-lived script doesn't need.
    """
    base = f"http://127.0.0.1:{NEXTCLOUD_LOCAL_PORT}"
    info(f"Port-forwarding {NEXTCLOUD_SERVICE} in namespace {NEXTCLOUD_NAMESPACE} on :{NEXTCLOUD_LOCAL_PORT}...")
    pf = subprocess.Popen(
        ["kubectl", "port-forward", "-n", NEXTCLOUD_NAMESPACE, NEXTCLOUD_SERVICE,
         f"{NEXTCLOUD_LOCAL_PORT}:8080"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(30):
            try:
                requests.get(f"{base}/status.php", timeout=2)
                break
            except requests.exceptions.ConnectionError:
                time.sleep(0.5)
        else:
            raise RuntimeError("Port-forward to Nextcloud never became reachable.")
        yield base
    finally:
        pf.terminate()
        pf.wait()


def fetch_nextcloud_oidc_users_by_email() -> dict[str, str]:
    """email -> opaque Nextcloud user_oidc uid, for every SSO-provisioned account."""
    nc_user = _kubectl_secret_value(NEXTCLOUD_NAMESPACE, "nextcloud-secrets", "NEXTCLOUD_USERNAME")
    nc_pass = _kubectl_secret_value(NEXTCLOUD_NAMESPACE, "nextcloud-secrets", "NEXTCLOUD_PASSWORD")
    auth = (nc_user, nc_pass)
    headers = {"OCS-APIRequest": "true"}

    with nextcloud_port_forward() as base:
        r = requests.get(f"{base}/ocs/v2.php/cloud/users?format=json", auth=auth, headers=headers, timeout=10)
        r.raise_for_status()
        uids = r.json()["ocs"]["data"]["users"]

        by_email: dict[str, str] = {}
        for uid in uids:
            r = requests.get(f"{base}/ocs/v2.php/cloud/users/{uid}?format=json", auth=auth, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()["ocs"]["data"]
            if data.get("backend") != "user_oidc":
                continue
            email = data.get("email")
            if email:
                by_email[email] = uid
        return by_email


def build_directory() -> list[dict]:
    authentik_users = fetch_authentik_users()
    nextcloud_by_email = fetch_nextcloud_oidc_users_by_email()

    directory = []
    for u in authentik_users:
        username = u["username"]
        email = u["email"]
        entry = {
            "authentik_username": username,
            "email": email or None,
            "matrix_id": f"@{username}:{MATRIX_SERVER_NAME}",
            "nextcloud_uid": None,
            "mailu_mailbox": None,
        }
        if email:
            nc_uid = nextcloud_by_email.get(email)
            if nc_uid:
                entry["nextcloud_uid"] = nc_uid
            if email.endswith(f"@{MAILU_DOMAIN}"):
                entry["mailu_mailbox"] = email
        directory.append(entry)

    resolved_emails = {u["email"] for u in authentik_users if u.get("email")}
    for email, nc_uid in nextcloud_by_email.items():
        if email not in resolved_emails:
            info(
                f"WARNING: Nextcloud account {nc_uid} (user_oidc) has email {email!r}, "
                "which doesn't match any active Authentik user's current email — "
                "likely drift (email changed on one side after the last SSO login). "
                "Not resolved for anyone; check by hand."
            )

    return directory


def main() -> None:
    directory = build_directory()
    print(json.dumps(directory, indent=2, ensure_ascii=False))
    unresolved = [e for e in directory if e["nextcloud_uid"] is None]
    if unresolved:
        info(
            f"{len(unresolved)}/{len(directory)} user(s) have no resolved Nextcloud account "
            "(never logged into Nextcloud via SSO yet, or email drift — see warnings above)."
        )


if __name__ == "__main__":
    main()
