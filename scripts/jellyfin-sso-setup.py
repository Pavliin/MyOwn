"""Completes the Jellyfin startup wizard and installs/configures the
Authentik SSO plugin (scottfridwin/jellyfin-plugin-authentik).

Not GitOps-managed: Jellyfin has no declarative way to install a plugin
or complete first-run setup (same category as Uptime Kuma, see
uptime-kuma-setup.py) — this script is the reproducible alternative to
clicking through the Dashboard, kept in git so it doesn't have to be
redone by hand after every cluster recreation. The Authentik side (OAuth2
Provider + Application) IS GitOps-managed, see
gitops/secrets/authentik-blueprints/jellyfin-sso.sops.yaml.

Usage:
    uv venv && source .venv/bin/activate && uv pip install requests
    # Pull the real client secret out of the encrypted secret rather than
    # retyping it — it must match gitops/secrets/authentik-blueprints/
    # jellyfin-sso.sops.yaml exactly, both sides of the same OAuth2 client.
    export JELLYFIN_SSO_CLIENT_SECRET=$(sops -d gitops/secrets/jellyfin/jellyfin.sops.yaml | yq '.stringData.SSO_CLIENT_SECRET')
    python3 jellyfin-sso-setup.py
    # On first run against a fresh instance, omit JELLYFIN_ADMIN_PASSWORD —
    # a random local admin account is created and printed once; save it
    # (e.g. into gitops/secrets/jellyfin/) and re-export it for reruns.
    # Requires kubectl pointed at the right cluster/context: Jellyfin's own
    # /System/Restart API accepts the call (204) but does not actually
    # cycle the container in this deployment (no supervisor process inside
    # it to relaunch — confirmed live, restart count stayed at 0) — a
    # freshly installed plugin only loads after a real pod restart, done
    # here via `kubectl rollout restart`.

Idempotent: safe to rerun against an already-configured instance (skips
the startup wizard if already completed, skips plugin install/restart if
already installed, always re-applies the plugin configuration).
"""

import os
import secrets
import string
import subprocess
import sys
import time

import requests

BASE = "http://myown-jellyfin.local:8090"
HOST_HEADER = {"Host": "myown-jellyfin.local"}
ADMIN_USER = "admin"
PLUGIN_NAME = "Authentik SSO"
PLUGIN_ID = "f4c1d2a3b5e647899abcdef012345678"
PLUGIN_REPO_URL = "https://scottfridwin.github.io/jellyfin-plugin-authentik/manifest.json"

AUTHENTIK_URL = os.environ.get("JELLYFIN_SSO_AUTHENTIK_URL", "http://myown-authentik.local:8090")
SSO_CLIENT_ID = os.environ.get("JELLYFIN_SSO_CLIENT_ID", "jellyfin")
SSO_CLIENT_SECRET = os.environ.get("JELLYFIN_SSO_CLIENT_SECRET")
if not SSO_CLIENT_SECRET:
    raise SystemExit(
        "Set JELLYFIN_SSO_CLIENT_SECRET (from gitops/secrets/jellyfin/jellyfin.sops.yaml) before running."
    )

ADMIN_PASS = os.environ.get("JELLYFIN_ADMIN_PASSWORD")
generated_password = False
if not ADMIN_PASS:
    ADMIN_PASS = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
    generated_password = True

AUTH_HEADER_TMPL = 'MediaBrowser Client="myown-setup", Device="setup-script", DeviceId="myown-setup-script", Version="1.0.0"'


def info(msg: str) -> None:
    print(f"[jellyfin-sso-setup] {msg}", file=sys.stderr)


s = requests.Session()
s.headers.update(HOST_HEADER)

public_info = s.get(f"{BASE}/System/Info/Public").json()

if not public_info["StartupWizardCompleted"]:
    info("Completing startup wizard...")
    s.post(
        f"{BASE}/Startup/Configuration",
        json={
            "ServerName": "MyOwn Jellyfin",
            "UICulture": "fr-FR",
            "MetadataCountryCode": "FR",
            "PreferredMetadataLanguage": "fr",
        },
    ).raise_for_status()
    s.post(f"{BASE}/Startup/User", json={"Name": ADMIN_USER, "Password": ADMIN_PASS}).raise_for_status()
    s.post(
        f"{BASE}/Startup/RemoteAccess",
        json={"EnableRemoteAccess": True, "EnableAutomaticPortMapping": False},
    ).raise_for_status()
    s.post(f"{BASE}/Startup/Complete").raise_for_status()
    if generated_password:
        info(f"Generated admin password (save this): {ADMIN_PASS}")
else:
    info("Startup wizard already completed, skipping.")
    if not os.environ.get("JELLYFIN_ADMIN_PASSWORD"):
        raise SystemExit("Startup wizard already done — set JELLYFIN_ADMIN_PASSWORD to authenticate.")

s.headers["X-Emby-Authorization"] = AUTH_HEADER_TMPL
auth_resp = s.post(f"{BASE}/Users/AuthenticateByName", json={"Username": ADMIN_USER, "Pw": ADMIN_PASS})
auth_resp.raise_for_status()
token = auth_resp.json()["AccessToken"]
s.headers["X-Emby-Authorization"] = f'{AUTH_HEADER_TMPL}, Token="{token}"'

plugins = s.get(f"{BASE}/Plugins").json()
plugin = next((p for p in plugins if p["Name"] == PLUGIN_NAME), None)

if plugin is None:
    info("Installing Authentik SSO plugin...")
    s.post(f"{BASE}/Repositories", json=[{"Name": PLUGIN_NAME, "Url": PLUGIN_REPO_URL, "Enabled": True}]).raise_for_status()
    s.post(
        f"{BASE}/Packages/Installed/{PLUGIN_NAME.replace(' ', '%20')}",
        params={"repositoryUrl": PLUGIN_REPO_URL},
    ).raise_for_status()

    info("Restarting the Jellyfin pod (Jellyfin's own /System/Restart doesn't"
         " actually cycle the container in this deployment)...")
    subprocess.run(
        ["kubectl", "rollout", "restart", "deployment/jellyfin", "-n", "jellyfin"],
        check=True,
    )
    subprocess.run(
        ["kubectl", "rollout", "status", "deployment/jellyfin", "-n", "jellyfin", "--timeout=120s"],
        check=True,
    )

    info("Waiting for the plugin to report Active...")
    for _ in range(30):
        time.sleep(2)
        plugins = s.get(f"{BASE}/Plugins").json()
        plugin = next((p for p in plugins if p["Name"] == PLUGIN_NAME), None)
        if plugin and plugin["Status"] == "Active":
            break
    else:
        raise SystemExit(f"Plugin did not become Active in time, last status: {plugin}")
else:
    info("Plugin already installed, skipping install/restart.")

if plugin["Status"] != "Active":
    raise SystemExit(
        f"Plugin status is {plugin['Status']!r}, not Active — check server logs for an assembly-load error "
        "(known cause: Jellyfin image tag out of sync with the plugin's compiled Jellyfin.Controller version, "
        "see notes-techniques.md)."
    )

info("Configuring plugin...")
s.post(
    f"{BASE}/Plugins/{PLUGIN_ID}/Configuration",
    json={
        "AuthentikUrl": AUTHENTIK_URL,
        "ClientId": SSO_CLIENT_ID,
        "ClientSecret": SSO_CLIENT_SECRET,
        "AdminGroup": "jellyfin-admins",
        "AllowedGroup": "",
        "ForceHttpsRedirect": False,
        "AutoCreateUsers": True,
        "EnableGroupSync": True,
        "EnableContentPolicySync": False,
        "GGroup": "",
        "TvY7Group": "",
        "PgGroup": "",
        "Pg13Group": "",
        "Tv14Group": "",
        "EnableProfileImageSync": True,
        "ProfileImageClaim": "picture",
    },
).raise_for_status()

info(f"Done — SSO login available at {BASE}/authentik/login")
