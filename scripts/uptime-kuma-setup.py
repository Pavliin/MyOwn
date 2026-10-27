"""Configures Uptime Kuma monitors + the public "État du système" status page.

Not GitOps-managed: Uptime Kuma has no declarative config, its state lives
in a SQLite DB inside its own PVC (same category as sops-age, see
CLAUDE.md) — this script is the reproducible alternative to clicking
through the UI, kept in git so it doesn't have to be redone by hand after
every cluster recreation.

Usage:
    uv venv && source .venv/bin/activate
    uv pip install uptime-kuma-api
    MYOWN_DOMAIN=<domaine> UPTIME_KUMA_USERNAME=... UPTIME_KUMA_PASSWORD=... python3 uptime-kuma-setup.py
    # (UPTIME_KUMA_URL pour viser une autre adresse que https://uptime.<domaine>)
    # on first run against a fresh instance, omit the env vars — a random
    # admin account is created and printed once; save it (e.g. into the
    # gitops/secrets/uptime-kuma/ SOPS file) and re-export it for reruns.

    # Optional: also wire up the shared Matrix alert room (run
    # tuwunel-alertbot-setup.py first to get these two values):
    #   TUWUNEL_ALERTBOT_TOKEN=... TUWUNEL_ALERT_ROOM_ID=... python3 uptime-kuma-setup.py

uptime-kuma-api 1.2.1 (latest on PyPI at the time of writing) predates
several Uptime Kuma 2.x schema changes and needs three workarounds below,
found by hitting each error live rather than guessed in advance:

1. A fresh Uptime Kuma 2.x instance requires a "/setup-database" step
   (choosing SQLite vs. an external DB) before the old single-step
   "create admin account" flow even becomes reachable — the API library
   has no method for this, so it's done here as a raw HTTP POST.
2. add_monitor() omits the "conditions" column added in 2.x (NOT NULL in
   the schema) — the raw insert fails. Patched via add_monitor_compat().
3. save_status_page() calls get_status_page(), which hardcodes an
   "incident" (singular) key that this version renamed to "incidents"
   (plural) — and separately, save_status_page()'s own config rebuilder
   drops several newer fields (autoRefreshInterval, analyticsType, ...)
   that the server now requires. Patched via save_status_page_compat(),
   which keeps the server's own config object as-is and only overlays the
   specific fields being changed.
"""

import os
import secrets
import string
import sys

import requests
from uptime_kuma_api import Event, MonitorType, NotificationType, UptimeKumaApi
from uptime_kuma_api.api import _check_arguments_monitor, _convert_monitor_input

# Domaine de l'installation (valeur `domain` de gitops/apps), obligatoire.
DOMAIN = os.environ.get("MYOWN_DOMAIN") or sys.exit("MYOWN_DOMAIN est obligatoire (domaine de l'installation).")
# Interface d'admin : uptime.<domaine>, réservée au réseau local et au VPN.
URL = os.environ.get("UPTIME_KUMA_URL", f"https://uptime.{DOMAIN}")
ADMIN_USER = os.environ.get("UPTIME_KUMA_USERNAME", "admin")
ADMIN_PASS = os.environ.get("UPTIME_KUMA_PASSWORD")

# From tuwunel-alertbot-setup.py — the shared "État du système" room,
# strictly separate from Ollama's private per-user DMs (Phase 5).
ALERTBOT_TOKEN = os.environ.get("TUWUNEL_ALERTBOT_TOKEN")
ALERT_ROOM_ID = os.environ.get("TUWUNEL_ALERT_ROOM_ID")

# Family-facing services only — ArgoCD/Grafana stay admin-only, never on
# this page (cf. installation-utilisateur.md, roadmap.md Phase 4).
# Public names, resolved inside the cluster to Traefik's internal Service
# (gitops/bootstrap/coredns-custom.yaml) — the same path a family member's
# request takes, with a real Let's Encrypt certificate, so TLS verification
# stays on (ignoreTls=False explicitly: edit_monitor keeps a field it isn't
# given, and the former .local monitors had it on). Each service's own health
# route where it has one.
SERVICES = [
    dict(name="Authentik", type=MonitorType.HTTP, url=f"https://authentik.{DOMAIN}/-/health/live/", interval=60, ignoreTls=False),
    dict(name="Vaultwarden", type=MonitorType.HTTP, url=f"https://vaultwarden.{DOMAIN}/alive", interval=60, ignoreTls=False),
    dict(name="Nextcloud", type=MonitorType.HTTP, url=f"https://nextcloud.{DOMAIN}/status.php", interval=60, ignoreTls=False),
    dict(name="Immich", type=MonitorType.HTTP, url=f"https://immich.{DOMAIN}/api/server/ping", interval=60, ignoreTls=False),
    dict(name="Tuwunel", type=MonitorType.HTTP, url=f"https://tuwunel.{DOMAIN}/_matrix/client/versions", interval=60, ignoreTls=False),
    dict(name="LiveKit", type=MonitorType.HTTP, url=f"https://livekit.{DOMAIN}/", interval=60, ignoreTls=False),
]

STATUS_PAGE_SLUG = "etat-du-systeme"


def setup_database_if_needed(url):
    info = requests.get(f"{url}/setup-database-info", timeout=10).json()
    if info.get("needSetup", False):
        print("Running first-boot database setup (SQLite)...")
        requests.post(
            f"{url}/setup-database",
            json={"dbConfig": {"type": "sqlite", "port": 3306, "hostname": "", "username": "", "password": "", "dbName": "kuma", "ssl": False, "ca": ""}},
            timeout=10,
        ).raise_for_status()


def add_monitor_compat(api, **kwargs):
    data = api._build_monitor_data(**kwargs)
    data["conditions"] = []
    _convert_monitor_input(data)
    _check_arguments_monitor(data)
    with api.wait_for_event(Event.MONITOR_LIST):
        return api._call("add", data)


def save_status_page_compat(api, slug, publicGroupList=None, **kwargs):
    r1 = api._call("getStatusPage", slug)
    config = r1["config"]
    config.update(kwargs)
    icon = config.get("icon", "/icon.svg")
    data = (slug, config, icon, publicGroupList or [])
    return api._call("saveStatusPage", data)


def main():
    setup_database_if_needed(URL)
    api = UptimeKumaApi(URL, timeout=30)

    try:
        if api.need_setup():
            password = ADMIN_PASS or "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
            print(f"Setting up admin account ({ADMIN_USER})...")
            api.setup(ADMIN_USER, password)
            print(f"CREDENTIALS (save these — e.g. into gitops/secrets/uptime-kuma/): {ADMIN_USER} / {password}", file=sys.stderr)
            api.login(ADMIN_USER, password)
        else:
            if not ADMIN_PASS:
                print("Instance already set up — set UPTIME_KUMA_PASSWORD to log in.", file=sys.stderr)
                sys.exit(1)
            api.login(ADMIN_USER, ADMIN_PASS)

        monitor_ids = {}
        existing = {m["name"]: m["id"] for m in api.get_monitors()}
        for svc in SERVICES:
            if svc["name"] in existing:
                monitor_ids[svc["name"]] = existing[svc["name"]]
                api.edit_monitor(existing[svc["name"]], **{k: v for k, v in svc.items() if k != "name"})
                print(f"Updated monitor: {svc['name']} (id={existing[svc['name']]})")
                continue
            result = add_monitor_compat(api, **svc)
            monitor_ids[svc["name"]] = result["monitorID"]
            print(f"Created monitor: {svc['name']} (id={result['monitorID']})")

        pages = {p["slug"]: p for p in api.get_status_pages()}
        if STATUS_PAGE_SLUG not in pages:
            api.add_status_page(slug=STATUS_PAGE_SLUG, title="État du système")
            print(f"Created status page: {STATUS_PAGE_SLUG}")

        save_status_page_compat(
            api,
            slug=STATUS_PAGE_SLUG,
            title="État du système",
            description="Statut en temps réel des services auto-hébergés.",
            published=True,
            publicGroupList=[
                {
                    "name": "Services",
                    "weight": 1,
                    "monitorList": [{"id": mid} for mid in monitor_ids.values()],
                }
            ],
        )
        print(f"Status page published: https://status.{DOMAIN}/status/{STATUS_PAGE_SLUG}")

        if ALERTBOT_TOKEN and ALERT_ROOM_ID:
            notif_name = "Tuwunel État du système"
            existing_notifs = {n["name"] for n in api.get_notifications()}
            if notif_name not in existing_notifs:
                api.add_notification(
                    name=notif_name,
                    type=NotificationType.MATRIX,
                    isDefault=True,
                    applyExisting=True,
                    homeserverUrl="https://tuwunel.offsystem.fr",
                    internalRoomId=ALERT_ROOM_ID,
                    accessToken=ALERTBOT_TOKEN,
                )
                print(f"Notification configured: {notif_name}")
            else:
                print(f"Notification already exists: {notif_name}")
        else:
            print("TUWUNEL_ALERTBOT_TOKEN/TUWUNEL_ALERT_ROOM_ID not set — skipping Matrix notification setup.", file=sys.stderr)

    finally:
        api.disconnect()


if __name__ == "__main__":
    main()
