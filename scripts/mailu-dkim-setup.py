"""Ensures a Mailu domain has a real, persisted DKIM key — and proves it by
reading it back, rather than assuming the admin UI's button did its job.

Real incident this closes (2026-09-07): offsystem.fr had a DKIM DNS TXT
record published for weeks, but the private key had never actually been
written to Mailu's persistent /dkim/ path on the mini PC — every outbound
message sent through the client-facing submission ports went out
completely unsigned, silently (no error anywhere, Rspamd's vault lookup for
the domain just came back with an empty `selectors` list). Exactly how the
key was lost was never fully reconstructed; what matters for next time is
that nothing in the original setup ever verified the key actually landed
on disk. See docs/notes-techniques.md for the full investigation.

Run this once right after Mailu's first deployment, and again any time DKIM
delivery is in doubt — safe to rerun, does nothing if a key already exists.

Requires the Mailu admin REST API (gitops/apps/mailu.yaml,
`admin.extraEnvVars` -> `API_TOKEN`). Reaches mailu-admin directly via a
`kubectl port-forward`, same ForwardAuth-SSO-bypass reasoning as
mailu-promote-admin.py — this API sits behind the same gated public
Ingress as everything else on mailu.offsystem.fr.

Usage:
    export MAILU_API_TOKEN=$(sops -d gitops/secrets/mailu/mailu.sops.yaml | yq '.stringData.API_TOKEN')
    python3 mailu-dkim-setup.py offsystem.fr
    # Requires kubectl pointed at the right cluster/context.

Prints the DNS TXT record to publish. This does NOT touch DNS itself —
scripts/gandi-mail-dns-setup.sh does that, and its own hardcoded
DKIM_PUBKEY constant needs updating to match whatever this prints before
it's (re-)run. Two separate scripts, one for each side of the same fact
(the key), so a fresh install has to look at the actual current value
instead of trusting a copy hardcoded from whenever the script was written.
"""

import os
import re
import subprocess
import sys
import time

import requests

NAMESPACE = "mailu"
SERVICE = "svc/mailu-admin"
LOCAL_PORT = 18082
BASE = f"http://127.0.0.1:{LOCAL_PORT}"


def info(msg: str) -> None:
    print(f"[mailu-dkim-setup] {msg}", file=sys.stderr)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: mailu-dkim-setup.py <domain>")
    domain = sys.argv[1]

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

        r = requests.get(f"{BASE}/api/v1/domain/{domain}", headers=headers, timeout=10)
        if r.status_code == 404:
            raise SystemExit(f"Domain {domain} does not exist in Mailu yet.")
        r.raise_for_status()
        dns_dkim = r.json().get("dns_dkim")

        if not dns_dkim:
            info(f"No DKIM key on disk for {domain} — generating one now...")
            r = requests.post(f"{BASE}/api/v1/domain/{domain}/dkim", headers=headers, timeout=10)
            r.raise_for_status()

            r = requests.get(f"{BASE}/api/v1/domain/{domain}", headers=headers, timeout=10)
            r.raise_for_status()
            dns_dkim = r.json().get("dns_dkim")
            if not dns_dkim:
                raise SystemExit(
                    f"Generation reported success but {domain} still has no readable key — "
                    "check the admin pod's /dkim/ mount and logs before trusting DKIM at all."
                )
            info("Key generated and confirmed present on disk.")
        else:
            info(f"{domain} already has a DKIM key on disk — nothing to do.")

        selector_match = re.match(r"^([\w.-]+)\._domainkey\.", dns_dkim)
        selector = selector_match.group(1) if selector_match else "dkim"
        info(
            f"Verified live: querying the key back confirms it's really readable, not just "
            f"reported as generated. Selector: {selector!r}."
        )
        print(f"\nDNS TXT record to publish (selector {selector!r}):\n")
        print(dns_dkim)
        print(
            "\nThis does not touch DNS — update DKIM_PUBKEY in "
            "scripts/gandi-mail-dns-setup.sh with the 'p=' value above (only the base64 blob, "
            "not the surrounding v=DKIM1/k=rsa wrapper) before (re-)running it."
        )
    finally:
        pf.terminate()
        pf.wait()


if __name__ == "__main__":
    main()
