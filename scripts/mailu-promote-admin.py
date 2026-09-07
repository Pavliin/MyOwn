"""Promotes an existing Mailu user (identified by email) to global admin.

Needed because Mailu's admin-account model is entirely disconnected from
Authentik SSO: the bootstrap `admin@<domain>` account (chart's
`initialAccount`) is the only account with `global_admin` set at install
time. A user who logs in via SSO gets auto-provisioned as a completely
ordinary mailbox (see `proxyAuth.create`) with no admin rights at all — the
only way to grant them today is to log into the bootstrap account (which
means bypassing the ForwardAuth SSO gate on the whole public Ingress via a
direct port-forward to mailu-admin) and click through the Administrators
page by hand. See docs/installation-utilisateur.md, "Modèle de gestion des
comptes admin", Mailu row.

Not GitOps-managed for the same reason as Jellyfin's admin bootstrap
(jellyfin-sso-setup.py): this is per-user state living in Mailu's own
database, not a declarative resource ArgoCD can own.

Requires the Mailu admin REST API to be enabled (gitops/apps/mailu.yaml,
`admin.extraEnvVars` -> `API_TOKEN`, unregistered entirely otherwise). That
API sits behind the exact same ForwardAuth-gated public Ingress as
everything else on mailu.offsystem.fr, so a Bearer token alone can't reach
it externally — this script reaches mailu-admin directly via a
`kubectl port-forward`, the same bypass used manually the first time this
gap was hit.

Usage:
    export MAILU_API_TOKEN=$(sops -d gitops/secrets/mailu/mailu.sops.yaml | yq '.stringData.API_TOKEN')
    python3 mailu-promote-admin.py robin.chartier@offsystem.fr
    # Requires kubectl pointed at the right cluster/context.

Idempotent: does nothing (exit 0) if the account is already a global admin.
Fails loudly (non-zero exit) if the account doesn't exist yet — it has to
have logged in via SSO at least once first, so proxyAuth has provisioned
the mailbox Mailu needs to attach admin rights to.
"""

import os
import subprocess
import sys
import time

import requests

NAMESPACE = "mailu"
SERVICE = "svc/mailu-admin"
LOCAL_PORT = 18080
BASE = f"http://127.0.0.1:{LOCAL_PORT}"


def info(msg: str) -> None:
    print(f"[mailu-promote-admin] {msg}", file=sys.stderr)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: mailu-promote-admin.py <email>")
    email = sys.argv[1]

    token = os.environ.get("MAILU_API_TOKEN")
    if not token:
        raise SystemExit(
            "Set MAILU_API_TOKEN (from gitops/secrets/mailu/mailu.sops.yaml) before running."
        )
    headers = {"Authorization": f"Bearer {token}"}

    info(f"Port-forwarding {SERVICE} in namespace {NAMESPACE} on :{LOCAL_PORT}...")
    pf = subprocess.Popen(
        ["kubectl", "port-forward", "-n", NAMESPACE, SERVICE, f"{LOCAL_PORT}:8080"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(30):
            try:
                requests.get(f"{BASE}/api/v1/domain", headers=headers, timeout=2)
                break
            except requests.exceptions.ConnectionError:
                time.sleep(0.5)
        else:
            raise SystemExit("Port-forward never became reachable.")

        r = requests.get(f"{BASE}/api/v1/user/{email}", headers=headers, timeout=10)
        if r.status_code == 404:
            raise SystemExit(
                f"{email} does not exist in Mailu yet — they need to log in via SSO at "
                "least once first (proxyAuth auto-provisions the mailbox on first login)."
            )
        r.raise_for_status()
        user = r.json()

        if user.get("global_admin"):
            info(f"{email} is already a global admin, nothing to do.")
            return

        info(f"Promoting {email} to global admin...")
        r = requests.patch(
            f"{BASE}/api/v1/user/{email}",
            headers=headers,
            json={"global_admin": True},
            timeout=10,
        )
        r.raise_for_status()

        r = requests.get(f"{BASE}/api/v1/user/{email}", headers=headers, timeout=10)
        r.raise_for_status()
        if not r.json().get("global_admin"):
            raise SystemExit(f"Promotion silently failed — {email} is still not a global admin.")
        info(f"Done — {email} is now a global admin.")
    finally:
        pf.terminate()
        pf.wait()


if __name__ == "__main__":
    main()
