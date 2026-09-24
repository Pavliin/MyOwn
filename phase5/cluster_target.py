"""Talks to whichever cluster Phase 5 is currently targeting.

Every other Phase 5 module goes through this instead of calling `kubectl`
directly, so switching target is one env var, not a per-module edit.

Default: local `kubectl` context (the dev k3d cluster, `k3d-myown-dev`).
Set `PHASE5_SSH_HOST` to route every call through
`ssh <host> sudo kubectl ...` instead — needed for the mini PC, which has
no local kubectl context on this machine, only SSH (confirmed working,
passwordless sudo already granted per the mini PC bootstrap). Real reason
this exists: dev's own Mailu started crash-looping partway through Phase 5
step 3 testing, so steps 4 onward target the mini PC's already-working
Mailu/Nextcloud/Tuwunel instead — this module is what makes that a one-line
switch rather than a rewrite.

Usage:
    export PHASE5_SSH_HOST=192.168.1.143   # mini PC; unset = local dev cluster
"""

import base64
import os
import shlex
import subprocess
import sys
import time
from contextlib import contextmanager

import requests

SSH_HOST = os.environ.get("PHASE5_SSH_HOST")


def info(msg: str) -> None:
    print(f"[cluster] {msg}", file=sys.stderr)


def kubectl(args: list[str]) -> subprocess.CompletedProcess:
    """Runs `kubectl <args>`, locally or via SSH to PHASE5_SSH_HOST."""
    if SSH_HOST:
        # SSH takes a single remote command string, not argv — shlex.quote
        # each arg individually (real bug found live: the Authentik ak-shell
        # Python snippets passed via `-c` contain spaces, quotes and
        # newlines, which a naive " ".join() silently mangled into a
        # different, broken command on the remote shell).
        remote_cmd = "sudo kubectl " + " ".join(shlex.quote(a) for a in args)
        cmd = ["ssh", SSH_HOST, remote_cmd]
    else:
        cmd = ["kubectl"] + args
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def secret_value(namespace: str, secret: str, key: str) -> str:
    out = kubectl(["get", "secret", "-n", namespace, secret, "-o", f"jsonpath={{.data.{key}}}"]).stdout
    return base64.b64decode(out).decode()


@contextmanager
def port_forward(namespace: str, service: str, remote_port: int, local_port: int):
    """Yields http://127.0.0.1:<local_port>, tunneled to <service>:<remote_port>
    in the target cluster — via a plain `kubectl port-forward` locally, or an
    SSH `-L` tunnel wrapping a remote `kubectl port-forward` when
    PHASE5_SSH_HOST is set (the remote side binds the same local_port on its
    own loopback, which the SSH tunnel then re-exposes on ours)."""
    base = f"http://127.0.0.1:{local_port}"
    if SSH_HOST:
        info(f"SSH tunnel to {SSH_HOST}: port-forwarding {service} ({namespace}) on :{local_port}...")
        cmd = [
            "ssh", "-L", f"{local_port}:127.0.0.1:{local_port}", SSH_HOST,
            f"sudo kubectl port-forward -n {namespace} {service} {local_port}:{remote_port}",
        ]
    else:
        info(f"Port-forwarding {service} ({namespace}) on :{local_port}...")
        cmd = ["kubectl", "port-forward", "-n", namespace, service, f"{local_port}:{remote_port}"]

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(30):
            try:
                # allow_redirects=False: some backends (Nextcloud) redirect
                # "/" to an https:// URL on the same port, which a plain
                # HTTP port-forward can never follow — any response at all,
                # redirect included, proves the tunnel itself is up.
                requests.get(base, timeout=2, allow_redirects=False)
                break
            except requests.exceptions.ConnectionError:
                time.sleep(0.5)
        else:
            raise RuntimeError(f"Port-forward to {service} never became reachable.")
        yield base
    finally:
        proc.terminate()
        proc.wait()
