"""Registers the "alertbot" Matrix account and the shared "État du
système" room it posts to, used by Uptime Kuma's Matrix notification
provider (configured separately, see uptime-kuma-setup.py).

Deliberately a distinct account/room from anything Ollama will use in
Phase 5: infra alerts are shared/subscribable by the whole household,
AI proposals are personal and go out as private 1:1 DMs — never the
same channel (see roadmap.md Phase 4/5, installation-utilisateur.md).

Usage:
    uv venv && source .venv/bin/activate && uv pip install requests
    python3 tuwunel-alertbot-setup.py
    # prints the bot's user_id/password/access_token/room_id once —
    # save them (e.g. into gitops/secrets/uptime-kuma/), this script
    # doesn't persist anything itself and isn't idempotent (registering
    # twice fails outright — Matrix usernames aren't reusable once taken).
"""

import json
import secrets
import string

import requests

BASE = "https://myown-tuwunel.local:8453"
SERVER_NAME = "myown-tuwunel.local"
BOT_USER = "alertbot"
ROOM_ALIAS = "etat-du-systeme"
ROOM_NAME = "État du système"

# Registration requires Tuwunel's registration_token — see
# gitops/secrets/tuwunel/tuwunel.sops.yaml.
REG_TOKEN = None  # fill in before running, never commit a real value here

BOT_PASS = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))

s = requests.Session()
# requests bundles its own CA store (certifi), separate from the OS trust
# store `mkcert -install` configures — same gotcha as every other outbound
# HTTPS call to *.local services made from outside a browser this project
# has hit (lk-jwt-service's SSL_CERT_FILE, Uptime Kuma's NODE_EXTRA_CA_CERTS).
s.verify = f"{__import__('subprocess').run(['mkcert', '-CAROOT'], capture_output=True, text=True).stdout.strip()}/rootCA.pem"

if not REG_TOKEN:
    raise SystemExit("Set REG_TOKEN (from gitops/secrets/tuwunel/tuwunel.sops.yaml) before running.")

# Step 1: get a UIAA session
r = s.post(f"{BASE}/_matrix/client/v3/register", json={})
session = r.json()["session"]

# Step 2: complete with the registration token
r = s.post(
    f"{BASE}/_matrix/client/v3/register",
    json={
        "auth": {"type": "m.login.registration_token", "token": REG_TOKEN, "session": session},
        "username": BOT_USER,
        "password": BOT_PASS,
        "initial_device_display_name": "alertbot-setup",
    },
)
r.raise_for_status()
reg = r.json()
access_token = reg["access_token"]
user_id = reg["user_id"]
print(f"Registered {user_id}")

headers = {"Authorization": f"Bearer {access_token}"}

# Public join rule (not listed in the public directory, but anyone in the
# household who knows the alias can join without an invite) + shared
# history so latecomers can scroll back through past alerts.
r = s.post(
    f"{BASE}/_matrix/client/v3/createRoom",
    headers=headers,
    json={
        "name": ROOM_NAME,
        "topic": "Alertes automatiques (Uptime Kuma) — panne/rétablissement des services.",
        "preset": "public_chat",
        "room_alias_name": ROOM_ALIAS,
        "visibility": "private",
        "initial_state": [
            {"type": "m.room.history_visibility", "state_key": "", "content": {"history_visibility": "shared"}}
        ],
    },
)
r.raise_for_status()
room_id = r.json()["room_id"]
print(f"Room created: {room_id} (#{ROOM_ALIAS}:{SERVER_NAME})")

print(json.dumps({
    "user_id": user_id,
    "password": BOT_PASS,
    "access_token": access_token,
    "room_id": room_id,
}, indent=2))
