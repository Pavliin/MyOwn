#!/usr/bin/env python3
"""Comptes et droits d'admin de MyOwn (installation-utilisateur.md, « Modèle de
gestion des comptes admin », étape 5).

Être admin de MyOwn, c'est être membre du groupe Authentik `myown-admins`
(blueprint gitops/manifests/authentik-blueprints/templates/admins.yaml).

Commandes :
  init [--email E] [--username U] [--name N]
      Crée (ou retrouve) le compte Authentik nominatif de l'admin dans
      `myown-admins` et affiche un lien de définition de son mot de passe
      (jamais connu de ce script). Occupe ensuite, avec des comptes techniques,
      les places « premier arrivé » des services installés : admin Immich,
      premier compte Tuwunel (le bot), assistant de démarrage et SSO de Jellyfin.
      Rejouable : ce qui est déjà fait est laissé tel quel.
  coffre
      Copie les secrets du cluster dans l'organisation Vaultwarden « MyOwn —
      administration » (collections Administration et Infrastructure), par `bw`
      connecté avec la clé d'API personnelle de l'admin et déverrouillé par son
      mot de passe maître — tous deux tapés par lui. Relit et compare chaque entrée
      par empreinte, puis sauvegarde Vaultwarden. Rejouable.
  transfert ajout --email E | verifier | retrait --preparateur U
      Remise des clés en deux temps : ajout du futur propriétaire, vérification
      par lui (droits partout, coffre complet), puis seulement retrait du
      préparateur (désactivé, droits retirés, identifiants d'admin régénérés).
  sync [--apply]
      Aligne les droits d'admin de Nextcloud, Immich, Tuwunel et Mailu sur les
      membres actifs du groupe (Authentik et Jellyfin le font seuls). Sans
      --apply : aperçu de ce qui changerait.

Ne lit les Secrets que pour s'en servir, n'affiche jamais une valeur. Appelé
par scripts/install.sh ; lançable seul (KUBECTL="sudo k3s kubectl" possible).
Bibliothèque standard seulement.
"""
import argparse
import base64
import getpass
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

KUBECTL = shlex.split(os.environ.get("KUBECTL", "kubectl"))
ADMIN_GROUP = "myown-admins"


class Warn(Exception):
    """Échec d'une place « premier arrivé » : signalé, les autres continuent."""


def say(msg):
    print(msg, flush=True)


def die(msg):
    sys.exit(f"ERREUR : {msg}")


# --- Cluster -------------------------------------------------------------------

def kubectl(*args, stdin=None, check=True):
    res = subprocess.run(KUBECTL + list(args), input=stdin, capture_output=True, text=True)
    if check and res.returncode != 0:
        die(f"kubectl {' '.join(args[:3])} : {res.stderr.strip()}")
    return res


def get_secret(ns, name):
    res = kubectl("get", "secret", name, "-n", ns, "-o", "json", check=False)
    if res.returncode != 0:
        return None
    data = json.loads(res.stdout).get("data") or {}
    return {k: base64.b64decode(v).decode() for k, v in data.items()}


def secret_value(ns, name, key):
    value = (get_secret(ns, name) or {}).get(key)
    if not value:
        die(f"secret {ns}/{name} sans clé {key} (scripts/lib/cluster-secrets.py ensure).")
    return value


def installed_apps():
    res = kubectl("get", "applications", "-n", "argocd", "-o", "jsonpath={.items[*].metadata.name}")
    return set(res.stdout.split())


def root_domain():
    res = kubectl("get", "application", "root", "-n", "argocd",
                  "-o", "jsonpath={.spec.source.helm.valuesObject.domain}", check=False)
    return res.stdout.strip()


def wait_rollout(ns, kind_name, timeout=900):
    """Attend qu'une ressource existe puis soit prête (premier démarrage : images à tirer)."""
    deadline = time.time() + timeout
    while kubectl("get", kind_name, "-n", ns, check=False).returncode != 0:
        if time.time() > deadline:
            raise Warn(f"{ns}/{kind_name} absent après {timeout // 60} min.")
        time.sleep(10)
    left = max(60, int(deadline - time.time()))
    res = kubectl("rollout", "status", kind_name, "-n", ns, f"--timeout={left}s", check=False)
    if res.returncode != 0:
        raise Warn(f"{ns}/{kind_name} pas prêt : {res.stderr.strip()}")


class ServiceURL:
    """Adresse HTTP d'un Service vue de la machine qui lance le script.

    k3s : l'adresse interne du Service est joignable depuis le nœud, et le reste
    quand le pod redémarre (installation du plugin Jellyfin). Ailleurs (k3d) :
    `kubectl port-forward` sur un port local libre."""

    def __init__(self, ns, svc, port):
        self.ns, self.svc, self.port = ns, svc, port
        self.args = ["port-forward", "-n", ns, f"svc/{svc}", f":{port}"]
        self.proc = None

    def __enter__(self):
        ip = kubectl("get", "svc", self.svc, "-n", self.ns, "-o", "jsonpath={.spec.clusterIP}").stdout.strip()
        try:
            socket.create_connection((ip, self.port), timeout=3).close()
            return f"http://{ip}:{self.port}"
        except OSError:
            pass
        self.proc = subprocess.Popen(KUBECTL + self.args, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True)
        line = self.proc.stdout.readline()
        m = re.search(r"127\.0\.0\.1:(\d+)", line)
        if not m:
            self.proc.kill()
            die(f"port-forward {' '.join(self.args[2:4])} : {line.strip() or self.proc.stderr.read().strip()}")
        return f"http://127.0.0.1:{m.group(1)}"

    def __exit__(self, *_):
        if self.proc:
            self.proc.terminate()
            self.proc.wait()


def http(method, url, body=None, headers=None, timeout=60):
    """(statut, réponse décodée si JSON sinon texte) ; ne lève pas sur un code HTTP d'erreur."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=dict(headers or {}))
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as err:
        status, raw = err.code, err.read()
    text = raw.decode(errors="replace")
    try:
        return status, json.loads(text) if text else None
    except ValueError:
        return status, text


def wait_http(url, timeout=600):
    deadline = time.time() + timeout
    while True:
        try:
            status, _ = http("GET", url, timeout=10)
            if status < 500:
                return
        except (urllib.error.URLError, OSError):
            pass
        if time.time() > deadline:
            raise Warn(f"{url} ne répond pas après {timeout // 60} min.")
        time.sleep(5)


# --- Authentik -----------------------------------------------------------------

def ak_shell(code, payload):
    """Code Python dans le shell Django d'Authentik ; `payload` (JSON) lu sur stdin,
    jamais sur la ligne de commande. Le code écrit une ligne `RESULT <json>`."""
    res = kubectl("exec", "-i", "-n", "authentik", "deploy/authentik-server", "-c", "server",
                  "--", "ak", "shell", "-c", code, stdin=json.dumps(payload), check=False)
    for line in res.stdout.splitlines():
        if line.startswith("RESULT "):
            return json.loads(line[7:])
    die(f"shell Authentik : {(res.stderr or res.stdout).strip()[-800:]}")


AK_ADMIN_USER = """
import json, sys
from urllib.parse import urlencode
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from authentik.brands.models import Brand
from authentik.core.models import Group, User
from authentik.flows.models import FlowToken
from authentik.flows.planner import FlowPlanner, PLAN_CONTEXT_PENDING_USER
from authentik.lib.utils.time import timedelta_from_string
from django.utils.timezone import now

d = json.loads(sys.stdin.read())
out = {}
group = Group.objects.filter(name=d["group"]).first()
if group is None:
    out["error"] = "group-missing"
else:
    user = User.objects.filter(username=d["username"]).first()
    if user is None and not d["username_forced"]:
        # Installation existante : l'admin a peut-être déjà son compte, sous un
        # autre nom — jamais de doublon.
        user = User.objects.filter(email__iexact=d["email"]).exclude(username="akadmin").first()
    if user is None:
        user = User.objects.create(username=d["username"], email=d["email"], name=d["name"])
        user.set_unusable_password()
        user.save()
        out["created"] = True
    elif user.email != d["email"]:
        out["error"] = "email-mismatch"
        out["email"] = user.email
    elif not user.is_active:
        # Préparateur sorti par `transfert retrait` (e-mail par défaut = celui
        # d'akadmin, donc le sien) : une relance de l'installeur ne doit jamais
        # lui rendre ses droits.
        out["inactive"] = True
        out["username"] = user.username
    if "error" not in out and not out.get("inactive"):
        group.users.add(user)
        out["username"] = user.username
        out["has_password"] = user.has_usable_password()
        if not out["has_password"]:
            brand = Brand.objects.filter(default=True).first()
            flow = brand.flow_recovery if brand else None
            if flow is None:
                out["error"] = "no-recovery-flow"
            else:
                request = RequestFactory().get("/", HTTP_HOST=d["host"], secure=True)
                request.user = AnonymousUser()
                request.brand = brand
                planner = FlowPlanner(flow)
                planner.allow_empty_flows = True
                plan = planner.plan(request, {PLAN_CONTEXT_PENDING_USER: user})
                token, _ = FlowToken.objects.update_or_create(
                    identifier=f"{user.uid}-password-reset",
                    defaults={"user": user, "flow": flow, "_plan": FlowToken.pickle(plan),
                              "revoke_on_execution": True,
                              "expires": now() + timedelta_from_string("hours=24")},
                )
                out["link"] = f"https://{d['host']}/if/flow/{flow.slug}/?" + urlencode({"flow_token": token.key})
print("RESULT " + json.dumps(out))
"""


def init_admin_user(email, username, name, domain, forced):
    say(f"Compte Authentik de l'admin ({email}, groupe {ADMIN_GROUP})")
    try:
        wait_rollout("authentik", "deployment/authentik-server")
    except Warn as w:
        die(str(w))
    payload = {"group": ADMIN_GROUP, "username": username, "email": email, "name": name,
               "host": f"authentik.{domain}", "username_forced": forced}
    deadline = time.time() + 600
    while True:
        out = ak_shell(AK_ADMIN_USER, payload)
        # Le groupe vient d'un blueprint appliqué par le worker d'Authentik :
        # quelques minutes au premier démarrage.
        if out.get("error") != "group-missing" or time.time() > deadline:
            break
        say(f"  groupe {ADMIN_GROUP} pas encore créé par son blueprint, nouvel essai dans 15 s...")
        time.sleep(15)
    err = out.get("error")
    if err == "group-missing":
        die(f"groupe {ADMIN_GROUP} absent après 10 min (blueprint authentik-blueprint-admins).")
    if err == "email-mismatch":
        die(f"le compte {username} existe déjà avec un autre e-mail ({out['email']}) : choisir --username.")
    if err == "no-recovery-flow":
        die("aucun flow de récupération sur la marque par défaut (blueprint account-recovery).")
    if out.get("inactive"):
        say(f"  compte {out['username']} désactivé (remise des clés faite) : laissé hors de {ADMIN_GROUP}")
        return out
    say(f"  compte {out['username']} créé" if out.get("created") else f"  compte {out['username']} déjà présent")
    if out.get("link"):
        say("  Définir le mot de passe (lien personnel, valable 24 h, à ouvrir par l'admin seulement) :")
        say(f"    {out['link']}")
    else:
        say("  mot de passe déjà défini")
    return out


# --- Places « premier arrivé » --------------------------------------------------

def claim_immich(_domain):
    """Compte admin technique d'Immich : tant qu'il n'existe pas, Immich propose
    son formulaire d'inscription d'admin au premier visiteur, à la place du SSO."""
    say("Immich : compte admin technique")
    wait_rollout("immich", "deployment/immich-server")
    email = secret_value("immich", "immich-secrets", "ADMIN_EMAIL")
    password = secret_value("immich", "immich-secrets", "ADMIN_PASSWORD")
    with ServiceURL("immich", "immich-server", 2283) as base:
        wait_http(f"{base}/api/server/ping")
        status, cfg = http("GET", f"{base}/api/server/config")
        if status != 200:
            die(f"Immich /api/server/config : {status}")
        if cfg.get("isInitialized"):
            say("  admin déjà en place")
            return
        status, body = http("POST", f"{base}/api/auth/admin-sign-up",
                            {"email": email, "password": password, "name": "Admin technique MyOwn"})
        if status not in (200, 201):
            die(f"Immich admin-sign-up : {status} {body}")
        say(f"  admin technique créé ({email})")


def matrix_login(base, user, password):
    status, body = http("POST", f"{base}/_matrix/client/v3/login", {
        "type": "m.login.password", "identifier": {"type": "m.id.user", "user": user},
        "password": password, "initial_device_display_name": "myown-admin"})
    return body["access_token"] if status == 200 else None


def tuwunel_room_id(base, auth, alias):
    status, body = http("GET", f"{base}/_matrix/client/v3/directory/room/{urllib.request.quote(alias)}",
                        headers=auth)
    return body.get("room_id") if status == 200 else None


def claim_tuwunel(domain):
    """Le premier compte inscrit sur Tuwunel en devient l'admin : le bot de MyOwn
    s'inscrit le premier, puis promeut les admins humains (`sync`)."""
    say("Tuwunel : bot inscrit en premier (admin du serveur)")
    wait_rollout("tuwunel", "deployment/tuwunel")
    bot = get_secret("tuwunel", "tuwunel-bot") or {}
    user, password = bot.get("username"), bot.get("password")
    if not (user and password):
        die("secret tuwunel/tuwunel-bot incomplet (scripts/lib/cluster-secrets.py ensure).")
    token = secret_value("tuwunel", "tuwunel-config-secrets", "registration_token")
    with ServiceURL("tuwunel", "tuwunel", 8008) as base:
        wait_http(f"{base}/_matrix/client/versions")
        access = matrix_login(base, user, password)
        if access is None:
            status, body = http("POST", f"{base}/_matrix/client/v3/register", {})
            session = (body or {}).get("session")
            if status != 401 or not session:
                die(f"Tuwunel register (session) : {status} {body}")
            status, body = http("POST", f"{base}/_matrix/client/v3/register", {
                "auth": {"type": "m.login.registration_token", "token": token, "session": session},
                "username": user, "password": password,
                "initial_device_display_name": "myown-admin"})
            if status == 400 and (body or {}).get("errcode") == "M_USER_IN_USE":
                raise Warn(f"@{user}:{domain} existe déjà avec un autre mot de passe que tuwunel/tuwunel-bot "
                    "(compte créé hors de myown-admin) : rien n'a été changé.")
            if status != 200:
                die(f"Tuwunel register : {status} {body}")
            access = body["access_token"]
            say(f"  @{user}:{domain} inscrit")
        else:
            say(f"  @{user}:{domain} déjà inscrit")
        auth = {"Authorization": f"Bearer {access}"}
        # Tuwunel tient pour admin tout membre du salon #admins (src/service/admin).
        admin_room = tuwunel_room_id(base, auth, f"#admins:{domain}")
        status, joined = http("GET", f"{base}/_matrix/client/v3/joined_rooms", headers=auth)
        if admin_room is None or admin_room not in (joined or {}).get("joined_rooms", []):
            raise Warn(f"@{user}:{domain} n'est pas admin de Tuwunel : un autre compte s'est inscrit avant lui.")
        say(f"  @{user}:{domain} est admin du serveur")
        alias = f"#etat-du-systeme:{domain}"
        if tuwunel_room_id(base, auth, alias):
            say(f"  salon {alias} déjà présent")
        else:
            status, body = http("POST", f"{base}/_matrix/client/v3/createRoom", headers=auth, body={
                "name": "État du système",
                "topic": "Alertes automatiques — panne/rétablissement des services.",
                "preset": "public_chat", "room_alias_name": "etat-du-systeme", "visibility": "private",
                "initial_state": [{"type": "m.room.history_visibility", "state_key": "",
                                   "content": {"history_visibility": "shared"}}]})
            if status != 200:
                die(f"Tuwunel createRoom : {status} {body}")
            say(f"  salon {alias} créé (rejoint d'office par chaque nouveau compte)")


def claim_jellyfin(domain):
    """Assistant de démarrage (sinon offert au premier visiteur) et plugin SSO,
    dont les droits d'admin suivent le groupe myown-admins."""
    say("Jellyfin : assistant de démarrage et SSO")
    wait_rollout("jellyfin", "deployment/jellyfin")
    env = dict(os.environ,
               MYOWN_DOMAIN=domain,
               JELLYFIN_ADMIN_PASSWORD=secret_value("jellyfin", "jellyfin-secrets", "ADMIN_PASSWORD"),
               JELLYFIN_SSO_CLIENT_SECRET=secret_value("jellyfin", "jellyfin-secrets", "SSO_CLIENT_SECRET"),
               KUBECTL=shlex.join(KUBECTL))
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jellyfin-sso-setup.py")
    with ServiceURL("jellyfin", "jellyfin", 8096) as base:
        wait_http(f"{base}/System/Info/Public")
        env["JELLYFIN_URL"] = base
        res = subprocess.run([sys.executable, script], env=env)
    if res.returncode != 0:
        raise Warn("configuration de Jellyfin en échec (voir ci-dessus).")


# --- Coffre (organisation Vaultwarden) ------------------------------------------
# Copie des secrets du cluster dans l'organisation « MyOwn — administration » :
# collection Administration (comptes d'admin, mot de passe de la sauvegarde des
# secrets), Infrastructure (tout le reste). Le cluster reste la source de vérité ;
# rejouer `coffre` remet le coffre à jour (après une rotation, un nouveau service).
# `bw` (client officiel Bitwarden) chiffre chaque entrée avant l'envoi : le
# serveur ne voit que du chiffré. Clé d'API et mot de passe maître tapés par
# l'admin, jamais affichés ni écrits ; session dans un dossier temporaire supprimé.

BW_VERSION = "2026.10.1"
BW_SHA256 = "53384064abe7555039281bc2e6fe51846368ba60db9b7ba89de183409d7f6738"
BW_URL = (f"https://github.com/bitwarden/clients/releases/download/cli-v{BW_VERSION}/"
          f"bw-oss-linux-{BW_VERSION}.zip")
ORG_HINT = "MyOwn"
COLLECTIONS = ("Administration", "Infrastructure")

# (Secret, clé, intitulé, identifiant, adresse) — collection Administration.
# L'identifiant peut être « secret:<clé> » (lu dans le même Secret).
ADMIN_ENTRIES = [
    ("authentik/authentik-secrets", "AUTHENTIK_BOOTSTRAP_PASSWORD",
     "Authentik — compte de secours akadmin", "akadmin", "https://authentik.{d}/if/admin/"),
    ("argocd/argocd-initial-admin-secret", "password", "ArgoCD — admin", "admin", "https://argocd.{d}"),
    ("monitoring/monitoring-secrets", "admin-password", "Grafana — admin", "admin", "https://grafana.{d}"),
    ("vaultwarden/vaultwarden-secrets", "ADMIN_TOKEN",
     "Vaultwarden — jeton de la page /admin", "", "https://vaultwarden.{d}/admin"),
    ("nextcloud/nextcloud-secrets", "NEXTCLOUD_PASSWORD",
     "Nextcloud — compte local admin", "secret:NEXTCLOUD_USERNAME", "https://nextcloud.{d}"),
    ("immich/immich-secrets", "ADMIN_PASSWORD",
     "Immich — admin technique", "secret:ADMIN_EMAIL", "https://immich.{d}"),
    ("jellyfin/jellyfin-secrets", "ADMIN_PASSWORD", "Jellyfin — admin technique", "admin", "https://jellyfin.{d}"),
    ("tuwunel/tuwunel-bot", "password", "Tuwunel — bot (admin du serveur Matrix)", "secret:username",
     "https://tuwunel.{d}"),
    ("mailu/mailu-secrets", "initial-account-password", "Mailu — compte initial", "admin@{d}",
     "https://mailu.{d}/admin"),
    ("myown-backup/secrets-backup", "RESTIC_PASSWORD",
     "Sauvegarde des secrets — mot de passe Restic (ouvre tous les autres)", "", ""),
]
# Secrets hors catalogue, créés par l'installeur (fournisseur DNS, DynDNS).
EXTRA_SECRETS = ["kube-system/dns-provider-credentials", "dyndns/dyndns-config"]


def catalog():
    """Catalogue de scripts/lib/cluster-secrets.py (nom de fichier non importable tel quel)."""
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib", "cluster-secrets.py")
    spec = importlib.util.spec_from_file_location("cluster_secrets", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def vault_entries(domain):
    """Entrées voulues : (collection, nom, identifiant, valeur, adresse, ns/secret, clé)."""
    cs = catalog()
    cache = {}

    def secret(ref):
        if ref not in cache:
            ns, name = ref.split("/")
            cache[ref] = get_secret(ns, name)
        return cache[ref]

    entries, taken = [], set()
    for ref, key, title, user, uri in ADMIN_ENTRIES:
        data = secret(ref)
        if not data or key not in data:
            continue
        if user.startswith("secret:"):
            user = data.get(user[7:], "")
        entries.append(("Administration", title, user.format(d=domain), data[key], uri.format(d=domain), ref, key))
        taken.add((ref, key))
    generated = {cs.rand, cs.hexa, cs.immich_oauth}  # immich_oauth : fichier contenant le secret OIDC
    for svc_entries in cs.CATALOG.values():
        for ns, name, keys in svc_entries:
            ref = f"{ns}/{name}"
            data = secret(ref)
            for key, gen in keys:
                # Seulement les valeurs aléatoires : constantes et clés dérivées se
                # reconstruisent à partir d'elles.
                if gen in generated and data and key in data and (ref, key) not in taken:
                    entries.append(("Infrastructure", f"{ref} — {key}", "", data[key], "", ref, key))
    for ref in EXTRA_SECRETS:
        for key, value in sorted((secret(ref) or {}).items()):
            entries.append(("Infrastructure", f"{ref} — {key}", "", value, "", ref, key))
    return entries


def bw_binary():
    found = shutil.which("bw")
    home = os.path.expanduser(f"~/.local/share/myown/bw-{BW_VERSION}")
    local = os.path.join(home, "bw")
    if found and not os.path.exists(local):
        return found
    if not os.path.exists(local):
        say(f"Téléchargement de bw {BW_VERSION} (client officiel Bitwarden)...")
        with urllib.request.urlopen(BW_URL, timeout=300) as resp:
            blob = resp.read()
        if hashlib.sha256(blob).hexdigest() != BW_SHA256:
            die("empreinte de bw inattendue : téléchargement refusé.")
        os.makedirs(home, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            zf.extract("bw", home)
        os.chmod(local, 0o755)
    return local


class Bw:
    """Session `bw` isolée dans un dossier temporaire, fermée et effacée en sortie."""

    def __init__(self, server):
        self.server = server

    def __enter__(self):
        self.bin = bw_binary()
        self.dir = tempfile.mkdtemp(prefix="myown-bw-")
        self.env = dict(os.environ, BITWARDENCLI_APPDATA_DIR=self.dir, BW_NOINTERACTION="true")
        self.run("config", "server", self.server)
        return self

    def __exit__(self, *_):
        self.run("lock", check=False)
        self.run("logout", check=False)
        shutil.rmtree(self.dir, ignore_errors=True)

    def run(self, *args, stdin=None, env=None, check=True):
        res = subprocess.run([self.bin, *args], input=stdin, capture_output=True, text=True,
                             env=dict(self.env, **(env or {})))
        if check and res.returncode != 0:
            # Message d'erreur de bw seulement (jamais de valeur : elles passent par stdin/env).
            raise Warn(f"bw {args[0]} : {(res.stderr or res.stdout).strip().splitlines()[-1:]}")
        return res.stdout

    def json(self, *args):
        return json.loads(self.run(*args))

    def login(self):
        say("Clé d'API PERSONNELLE de votre compte Vaultwarden (Paramètres du compte → Sécurité → Clés →")
        say("« Afficher la clé d'API » ; pas celle de l'organisation) :")
        client_id = input("  client_id (commence par « user. ») : ").strip()
        if not client_id.startswith("user."):
            die("ce n'est pas une clé d'API personnelle (elle commence par « user. »).")
        client_secret = getpass.getpass("  client_secret (rien ne s'affiche) : ").strip()
        self.run("login", "--apikey", env={"BW_CLIENTID": client_id, "BW_CLIENTSECRET": client_secret})
        password = getpass.getpass("Mot de passe maître du coffre (rien ne s'affiche) : ")
        session = self.run("unlock", "--passwordenv", "MYOWN_BW_PASSWORD", "--raw",
                           env={"MYOWN_BW_PASSWORD": password}).strip()
        self.env["BW_SESSION"] = session
        self.run("sync")


def item_body(org, coll, entry, existing=None):
    collection, name, user, value, uri, ref, key = entry
    body = dict(existing or {})
    body.update({
        "organizationId": org, "collectionIds": [coll], "name": name,
        "notes": (f"Copie du Secret Kubernetes {ref}, clé {key} — la valeur de référence est dans le "
                  f"cluster. Mise à jour par « myown-admin coffre » le {time.strftime('%Y-%m-%d')}."),
    })
    if "\n" in value.strip():
        body.update({"type": 2, "secureNote": {"type": 0}, "login": None,
                     "notes": value + "\n\n---\n" + body["notes"]})
    else:
        body.update({"type": 1, "secureNote": None, "login": {
            "username": user or None, "password": value,
            "uris": [{"match": None, "uri": uri}] if uri else []}})
    return base64.b64encode(json.dumps(body).encode()).decode()


def item_value(item):
    if item.get("type") == 2:
        return (item.get("notes") or "").split("\n\n---\n")[0]
    return ((item.get("login") or {}).get("password")) or ""


def cmd_coffre(args):
    domain = root_domain() or die("domaine inconnu.")
    host = f"vaultwarden.{domain}"
    try:
        socket.getaddrinfo(host, 443)
    except OSError:
        die(f"{host} ne se résout pas depuis cette machine : l'enregistrement DNS des services "
            "(wildcard du domaine, ou Pi-hole) doit pointer vers elle.")
    entries = vault_entries(domain)
    say(f"{len(entries)} secrets à copier ({sum(e[0] == 'Administration' for e in entries)} en Administration).")
    with Bw(f"https://{host}") as bw:
        try:
            bw.login()
            orgs = [o for o in bw.json("list", "organizations") if ORG_HINT.lower() in o["name"].lower()]
            if len(orgs) != 1:
                die(f"il faut exactement une organisation dont le nom contient « {ORG_HINT} » "
                    f"(trouvé : {len(orgs)}). La créer dans Vaultwarden : « MyOwn — administration », "
                    f"avec les collections {' et '.join(COLLECTIONS)}.")
            org = orgs[0]["id"]
            colls = {c["name"]: c["id"] for c in bw.json("list", "collections", "--organizationid", org)}
            missing = [c for c in COLLECTIONS if c not in colls]
            if missing:
                die(f"collection(s) absente(s) de l'organisation : {', '.join(missing)}.")
            items = {i["name"]: i for i in bw.json("list", "items", "--organizationid", org)}
            created = updated = same = 0
            for entry in entries:
                coll = colls[entry[0]]
                current = items.get(entry[1])
                if current is None:
                    bw.run("create", "item", stdin=item_body(org, coll, entry))
                    created += 1
                elif item_value(current) != entry[3] or coll not in current.get("collectionIds", []):
                    bw.run("edit", "item", current["id"], stdin=item_body(org, coll, entry, current))
                    updated += 1
                else:
                    same += 1
            say(f"  {created} créée(s), {updated} mise(s) à jour, {same} déjà à jour")
            # Vérification : relecture depuis le serveur, comparaison par empreinte.
            bw.run("sync")
            items = {i["name"]: i for i in bw.json("list", "items", "--organizationid", org)}
            bad = [e[1] for e in entries
                   if hashlib.sha256(item_value(items.get(e[1], {})).encode()).digest()
                   != hashlib.sha256(e[3].encode()).digest()]
            if bad:
                die(f"{len(bad)} entrée(s) différente(s) du cluster après écriture : {', '.join(bad)}")
            say(f"  vérifié : les {len(entries)} entrées relues sont identiques au cluster")
        except Warn as w:
            die(str(w))
    backup_now("vaultwarden", "vaultwarden-restic-backup")


def backup_now(ns, cronjob):
    """Sauvegarde Restic immédiate (après une écriture importante), sans attendre la nuit."""
    if kubectl("get", "cronjob", cronjob, "-n", ns, check=False).returncode != 0:
        say(f"  (pas de sauvegarde {ns}/{cronjob} sur cette installation)")
        return
    job = f"{cronjob[:40]}-myown-{int(time.time())}"
    kubectl("create", "job", job, "-n", ns, f"--from=cronjob/{cronjob}")
    say(f"Sauvegarde immédiate de {ns}...")
    res = kubectl("wait", "-n", ns, f"job/{job}", "--for=condition=complete", "--timeout=600s", check=False)
    if res.returncode != 0:
        die(f"sauvegarde {ns}/{job} non terminée : kubectl logs -n {ns} job/{job}")
    say("  sauvegarde faite")


# --- Synchronisation des droits ------------------------------------------------
# Nextcloud, Immich, Tuwunel et Mailu ne savent pas déduire les droits d'admin du
# groupe (validé en VM le 2026-11-22) : `sync` les aligne sur ses membres actifs —
# donne les droits qui manquent, retire ceux d'une personne sortie du groupe. Les
# comptes techniques (admin local Nextcloud, admin technique Immich, bot Tuwunel)
# ne sont jamais touchés. Un membre qui ne s'est encore jamais connu à un service
# n'y a pas de compte : signalé, traité à la prochaine synchronisation.

AK_ADMINS = """
import json
from authentik.core.models import Group
g = Group.objects.filter(name="%s").first()
users = [] if g is None else [{"username": u.username, "email": u.email}
                              for u in g.users.filter(is_active=True)]
print("RESULT " + json.dumps({"exists": g is not None, "users": users}))
""" % ADMIN_GROUP


def group_admins():
    out = ak_shell(AK_ADMINS, {})
    if not out["exists"]:
        die(f"groupe {ADMIN_GROUP} absent (blueprint authentik-blueprint-admins).")
    if not out["users"]:
        die(f"groupe {ADMIN_GROUP} vide : refus de retirer les droits de tout le monde.")
    return out["users"]


def occ(*args):
    cmd = "php occ " + " ".join(shlex.quote(a) for a in args)
    return kubectl("exec", "-n", "nextcloud", "deploy/nextcloud", "-c", "nextcloud", "--",
                   "su", "-s", "/bin/sh", "www-data", "-c", cmd, check=False)


def sync_nextcloud(admins, apply):
    say("Nextcloud (groupe admin)")
    res = occ("user:list", "--info", "--output=json")
    if res.returncode != 0:
        raise Warn(f"occ user:list : {res.stderr.strip() or res.stdout.strip()}")
    users = json.loads(res.stdout)
    by_email = {}
    for uid, info in users.items():
        if info.get("backend") == "user_oidc" and info.get("email"):
            by_email.setdefault(info["email"].lower(), []).append(uid)
    wanted = set()
    for a in admins:
        uids = by_email.get(a["email"].lower(), [])
        if not uids:
            say(f"  {a['username']} : pas encore de compte (première connexion à faire)")
            NO_ACCOUNT.setdefault("nextcloud", set()).add(a["username"])
        wanted.update(uids)
    for uid, info in sorted(users.items()):
        is_admin = "admin" in (info.get("groups") or [])
        if info.get("backend") != "user_oidc":
            continue  # compte local (admin technique) : jamais touché
        label = f"{info.get('email') or uid}"
        if uid in wanted and not is_admin:
            say(f"  {label} : droits d'admin donnés")
            if apply:
                occ("group:adduser", "admin", uid)
        elif uid not in wanted and is_admin:
            say(f"  {label} : droits d'admin retirés (hors du groupe {ADMIN_GROUP})")
            if apply:
                occ("group:removeuser", "admin", uid)
        elif uid in wanted:
            say(f"  {label} : déjà admin")


def sync_immich(admins, apply):
    say("Immich")
    email = secret_value("immich", "immich-secrets", "ADMIN_EMAIL")
    password = secret_value("immich", "immich-secrets", "ADMIN_PASSWORD")
    with ServiceURL("immich", "immich-server", 2283) as base:
        status, body = http("POST", f"{base}/api/auth/login", {"email": email, "password": password})
        if status not in (200, 201):
            raise Warn(f"connexion du compte admin technique impossible ({status}) : "
                       "« myown-admin init » l'a-t-il créé ?")
        auth = {"Authorization": f"Bearer {body['accessToken']}"}
        status, users = http("GET", f"{base}/api/admin/users", headers=auth)
        if status != 200:
            raise Warn(f"liste des utilisateurs Immich : {status}")
        wanted = {a["email"].lower() for a in admins}
        present = {u["email"].lower() for u in users}
        for a in admins:
            if a["email"].lower() not in present:
                say(f"  {a['username']} : pas encore de compte (première connexion à faire)")
                NO_ACCOUNT.setdefault("immich", set()).add(a["username"])
        for u in sorted(users, key=lambda u: u["email"]):
            mail = u["email"].lower()
            if mail == email.lower():
                continue  # admin technique : jamais touché
            if mail in wanted and not u["isAdmin"]:
                say(f"  {u['email']} : droits d'admin donnés")
            elif mail not in wanted and u["isAdmin"]:
                say(f"  {u['email']} : droits d'admin retirés (hors du groupe {ADMIN_GROUP})")
            else:
                if mail in wanted:
                    say(f"  {u['email']} : déjà admin")
                continue
            if apply:
                status, body = http("PUT", f"{base}/api/admin/users/{u['id']}", headers=auth,
                                    body={"isAdmin": mail in wanted})
                if status != 200:
                    raise Warn(f"mise à jour de {u['email']} : {status} {body}")


def sync_tuwunel(admins, apply, domain):
    say("Tuwunel (salon d'admin)")
    bot = get_secret("tuwunel", "tuwunel-bot") or {}
    with ServiceURL("tuwunel", "tuwunel", 8008) as base:
        access = matrix_login(base, bot.get("username"), bot.get("password"))
        if access is None:
            raise Warn("connexion du bot impossible : « myown-admin init » l'a-t-il inscrit ?")
        auth = {"Authorization": f"Bearer {access}"}
        room = tuwunel_room_id(base, auth, f"#admins:{domain}")
        q = urllib.request.quote
        status, joined = http("GET", f"{base}/_matrix/client/v3/joined_rooms", headers=auth)
        if room is None or room not in (joined or {}).get("joined_rooms", []):
            raise Warn("le bot n'est pas admin de Tuwunel : impossible de gérer les droits.")
        status, body = http("GET", f"{base}/_matrix/client/v3/rooms/{q(room)}/joined_members", headers=auth)
        members = set((body or {}).get("joined", {}))
        bot_id = f"@{bot['username']}:{domain}"
        server_user = f"@conduit:{domain}"
        wanted = {f"@{a['username']}:{domain}": a for a in admins}
        commands = []
        for mxid, a in wanted.items():
            if mxid in members:
                say(f"  {mxid} : déjà admin")
                continue
            status, _ = http("GET", f"{base}/_matrix/client/v3/profile/{q(mxid)}", headers=auth)
            if status != 200:
                say(f"  {a['username']} : pas encore de compte (première connexion à faire)")
                NO_ACCOUNT.setdefault("tuwunel", set()).add(a["username"])
                continue
            say(f"  {mxid} : droits d'admin donnés")
            commands.append(f"!admin users make-user-admin {mxid}")
        for mxid in sorted(members - set(wanted) - {bot_id, server_user}):
            say(f"  {mxid} : droits d'admin retirés (hors du groupe {ADMIN_GROUP})")
            # Pas de commande de retrait en 1.8.3 : quitter le salon d'admin suffit,
            # c'est l'appartenance que Tuwunel vérifie.
            commands.append(f"!admin users force-leave-room {mxid} {room}")
        if not apply:
            return
        for i, cmd in enumerate(commands):
            txn = f"myown-admin-{int(time.time() * 1000)}-{i}"
            status, body = http("PUT", f"{base}/_matrix/client/v3/rooms/{q(room)}/send/m.room.message/{txn}",
                                headers=auth, body={"msgtype": "m.text", "body": cmd})
            if status != 200:
                raise Warn(f"commande d'admin Tuwunel : {status} {body}")
        # Vérification : l'appartenance au salon d'admin est la vérité de Tuwunel.
        if commands:
            time.sleep(3)
            status, body = http("GET", f"{base}/_matrix/client/v3/rooms/{q(room)}/joined_members",
                                headers=auth)
            members = set((body or {}).get("joined", {}))
            for cmd in commands:
                mxid = cmd.split()[3]
                ok = (mxid in members) == ("make-user-admin" in cmd)
                if not ok:
                    raise Warn(f"{mxid} : la commande « {cmd.split()[2]} » n'a pas pris effet.")


def sync_mailu(admins, apply):
    say("Mailu (admin global)")
    token = secret_value("mailu", "mailu-secrets", "API_TOKEN")
    auth = {"Authorization": f"Bearer {token}"}
    with ServiceURL("mailu", "mailu-admin", 8080) as base:
        status, users = http("GET", f"{base}/api/v1/user", headers=auth)
        if status != 200:
            raise Warn(f"API Mailu : {status}")
        wanted = {a["email"].lower() for a in admins}
        present = {u["email"].lower() for u in users}
        for a in admins:
            if a["email"].lower() not in present:
                NO_ACCOUNT.setdefault("mailu", set()).add(a["username"])
                say(f"  {a['username']} : pas de boîte {a['email']} dans Mailu (créée à la première connexion "
                    "si le domaine est géré par Mailu)")
        initial = f"admin@{root_domain()}".lower()
        for u in sorted(users, key=lambda u: u["email"]):
            mail = u["email"].lower()
            if mail == initial:
                continue  # compte bootstrap : jamais touché
            if (mail in wanted) == bool(u.get("global_admin")):
                if mail in wanted:
                    say(f"  {u['email']} : déjà admin")
                continue
            say(f"  {u['email']} : droits d'admin " + ("donnés" if mail in wanted else
                f"retirés (hors du groupe {ADMIN_GROUP})"))
            if apply:
                status, body = http("PATCH", f"{base}/api/v1/user/{urllib.request.quote(u['email'])}",
                                    headers=auth, body={"global_admin": mail in wanted})
                if status != 200:
                    raise Warn(f"mise à jour de {u['email']} : {status} {body}")


NO_ACCOUNT = {}  # service -> membres du groupe sans compte (relevé par les sync_*)


def run_sync(apply):
    """Synchronise les droits ; renvoie les services en échec."""
    domain = root_domain() or die("domaine inconnu.")
    apps = installed_apps()
    admins = group_admins()
    say(f"Membres de {ADMIN_GROUP} : {', '.join(a['username'] for a in admins)}"
        + ("" if apply else "   (aperçu : rien n'est changé sans --apply)"))
    failed = []
    for app, fn in (("nextcloud", lambda: sync_nextcloud(admins, apply)),
                    ("immich", lambda: sync_immich(admins, apply)),
                    ("tuwunel", lambda: sync_tuwunel(admins, apply, domain)),
                    ("mailu", lambda: sync_mailu(admins, apply))):
        if app in apps:
            try:
                fn()
            except Warn as w:
                say(f"  ATTENTION : {w}")
                failed.append(app)
    return failed


def cmd_sync(args):
    failed = run_sync(args.apply)
    if failed:
        die(f"synchronisation incomplète : {', '.join(failed)}.")



# --- Remise des clés (transfert) -----------------------------------------------
# Deux temps qui ne se chevauchent jamais (installation-utilisateur.md, « Remise
# des clés ») :
#   ajout     le futur propriétaire entre dans myown-admins ;
#   verifier  lancé par LUI : droits d'admin partout, et il voit dans le coffre
#             toutes les entrées, identiques au cluster. Marqueur posé ;
#   retrait   seulement après ce marqueur : le préparateur est sorti du groupe et
#             désactivé (jamais supprimé), ses droits retirés, et les identifiants
#             d'admin qu'il a pu voir sont régénérés.

STATE = ("myown-backup", "myown-admin-state")       # ConfigMap, sans secret
PENDING = ("myown-backup", "myown-admin-pending")   # nouvelles valeurs en cours d'application


def state():
    res = kubectl("get", "configmap", STATE[1], "-n", STATE[0], "-o", "json", check=False)
    return json.loads(res.stdout).get("data") or {} if res.returncode == 0 else {}


def set_state(**data):
    body = {"apiVersion": "v1", "kind": "ConfigMap",
            "metadata": {"name": STATE[1], "namespace": STATE[0]}, "data": {**state(), **data}}
    kubectl("apply", "-f", "-", stdin=json.dumps(body))


def patch_secret(ns, name, data):
    kubectl("patch", "secret", name, "-n", ns, "--type", "merge", "-p", json.dumps({"stringData": data}))


AK_USER_STATE = """
import json, sys
from authentik.core.models import User
d = json.loads(sys.stdin.read())
u = User.objects.filter(email__iexact=d["email"]).exclude(username="akadmin").first()
out = {"found": u is not None}
if u:
    out.update(username=u.username, active=u.is_active, has_password=u.has_usable_password(),
               admin=u.ak_groups.filter(name=d["group"]).exists())
print("RESULT " + json.dumps(out))
"""

AK_DISABLE = """
import json, sys
from authentik.core.models import AuthenticatedSession, Group, Token, User
d = json.loads(sys.stdin.read())
u = User.objects.filter(username=d["username"]).first()
out = {"found": u is not None}
if u:
    Group.objects.get(name=d["group"]).users.remove(u)
    u.is_active = False
    u.save()
    out["sessions"] = AuthenticatedSession.objects.filter(user=u).delete()[0]
    out["tokens"] = Token.objects.filter(user=u).delete()[0]
print("RESULT " + json.dumps(out))
"""

AK_SET_PASSWORD = """
import json, sys
from authentik.core.models import User
d = json.loads(sys.stdin.read())
u = User.objects.get(username=d["username"])
u.set_password(d["password"])
u.save()
print("RESULT " + json.dumps({"ok": True}))
"""


def cmd_transfert_ajout(args):
    domain = root_domain() or die("domaine inconnu.")
    username = args.username or re.sub(r"[^a-z0-9._-]", "", args.email.split("@")[0].lower())
    out = init_admin_user(args.email, username, args.name or username, domain, forced=bool(args.username))
    if out.get("inactive"):
        die(f"le compte {out['username']} est désactivé : le réactiver d'abord dans Authentik, s'il le faut vraiment.")
    set_state(transfer_owner=args.email.lower(), transfer_verified="")
    first = ("Le futur propriétaire ouvre le lien ci-dessus et choisit son mot de passe."
             if out.get("link") else "Son mot de passe Authentik est déjà défini : rien à faire.")
    say(f"""
Suite, dans l'ordre :
  1. {first}
  2. Il se connecte une fois à chaque service (bouton de connexion Authentik) :
     ses comptes y sont créés à cette première connexion.
  3. Il crée son coffre Vaultwarden (https://vaultwarden.{domain}, « Utiliser
     l'authentification unique »), puis son mot de passe maître.
  4. Vous l'invitez dans l'organisation (rôle Propriétaire), puis le confirmez
     (Membres → ⋮ → Confirmer) : sans serveur mail, l'invitation est acceptée
     d'office et seule la confirmation lui ouvre l'organisation.
  5. Lui, sur ce serveur : python3 scripts/myown-admin.py transfert verifier""")


def vault_compare(bw, entries, owner):
    """Relit l'organisation et compare chaque entrée au cluster (empreintes)."""
    orgs = [o for o in bw.json("list", "organizations") if ORG_HINT.lower() in o["name"].lower()]
    if len(orgs) != 1:
        raise Warn(f"organisation « {ORG_HINT} » introuvable dans ce coffre (invitation confirmée ?)")
    if owner and orgs[0].get("type") != 0:
        raise Warn("ce compte n'est pas Propriétaire de l'organisation.")
    items = {i["name"]: i for i in bw.json("list", "items", "--organizationid", orgs[0]["id"])}
    bad = [e[1] for e in entries
           if hashlib.sha256(item_value(items.get(e[1], {})).encode()).digest()
           != hashlib.sha256(e[3].encode()).digest()]
    if bad:
        raise Warn(f"{len(bad)} entrée(s) absente(s) ou différente(s) du cluster : {', '.join(bad)}")
    return len(entries)


def cmd_transfert_verifier(_args):
    domain = root_domain() or die("domaine inconnu.")
    owner = state().get("transfer_owner") or die("aucun transfert en cours (transfert ajout).")
    say(f"Vérification du futur propriétaire {owner}")
    u = ak_shell(AK_USER_STATE, {"email": owner, "group": ADMIN_GROUP})
    if not (u["found"] and u["active"] and u["admin"] and u["has_password"]):
        die(f"compte Authentik incomplet : {u} (lien de mot de passe : transfert ajout).")
    say(f"  Authentik : {u['username']} actif, mot de passe défini, dans {ADMIN_GROUP}")
    failed = run_sync(apply=True)
    lacking = [app for app, names in NO_ACCOUNT.items() if u["username"] in names]
    if failed or lacking:
        die("droits d'admin incomplets — " + "; ".join(
            ([f"en échec : {', '.join(failed)}"] if failed else [])
            + ([f"première connexion à faire : {', '.join(lacking)}"] if lacking else [])))
    say("Coffre : connexion avec VOTRE clé d'API et VOTRE mot de passe maître (futur propriétaire).")
    with Bw(f"https://vaultwarden.{domain}") as bw:
        try:
            bw.login()
            n = vault_compare(bw, vault_entries(domain), owner=True)
        except Warn as w:
            die(str(w))
    say(f"  coffre : {n} entrées visibles, identiques au cluster")
    set_state(transfer_verified=time.strftime("%Y-%m-%dT%H:%M:%S"))
    say("Transfert vérifié. Le préparateur peut maintenant lancer : "
        "python3 scripts/myown-admin.py transfert retrait --preparateur <son nom d'utilisateur>")


# Identifiants d'admin régénérés au retrait : (Secret, clé, application de la
# nouvelle valeur au service). Chaque fonction reçoit (ancienne, nouvelle) et doit
# pouvoir être rejouée (coupure) : elle essaie l'ancienne, puis la nouvelle.

def regen_akadmin(_old, new):
    ak_shell(AK_SET_PASSWORD, {"username": "akadmin", "password": new})


def regen_argocd(_old, new):
    res = kubectl("exec", "-i", "-n", "argocd", "deploy/argocd-server", "--", "sh", "-c",
                  'read -r p; argocd account bcrypt --password "$p"', stdin=new + "\n", check=False)
    hashed = res.stdout.strip()
    if res.returncode != 0 or not hashed.startswith("$2"):
        raise Warn(f"argocd account bcrypt : {res.stderr.strip()}")
    kubectl("patch", "secret", "argocd-secret", "-n", "argocd", "--type", "merge", "-p", json.dumps(
        {"stringData": {"admin.password": hashed,
                        "admin.passwordMtime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}}))


def regen_grafana(_old, new):
    pod = kubectl("get", "pod", "-n", "monitoring", "-l", "app.kubernetes.io/name=grafana",
                  "-o", "jsonpath={.items[0].metadata.name}").stdout.strip()
    res = kubectl("exec", "-i", "-n", "monitoring", pod, "-c", "grafana", "--",
                  "grafana", "cli", "admin", "reset-admin-password", "--password-from-stdin",
                  stdin=new + "\n", check=False)
    if res.returncode != 0:
        raise Warn(f"Grafana : {res.stderr.strip()[-300:]}")


def regen_vaultwarden(_old, _new):
    pass  # lu au démarrage : redémarrage après mise à jour du Secret (voir AFTER)


def regen_nextcloud(_old, new):
    user = secret_value("nextcloud", "nextcloud-secrets", "NEXTCLOUD_USERNAME")
    res = kubectl("exec", "-i", "-n", "nextcloud", "deploy/nextcloud", "-c", "nextcloud", "--",
                  "su", "-s", "/bin/sh", "www-data", "-c",
                  f'read -r OC_PASS; export OC_PASS; php occ user:resetpassword --password-from-env {shlex.quote(user)}',
                  stdin=new + "\n", check=False)
    if res.returncode != 0:
        raise Warn(f"Nextcloud : {(res.stderr or res.stdout).strip()}")


def regen_mailu(_old, new):
    token = secret_value("mailu", "mailu-secrets", "API_TOKEN")
    with ServiceURL("mailu", "mailu-admin", 8080) as base:
        status, body = http("PATCH", f"{base}/api/v1/user/{urllib.request.quote('admin@' + root_domain())}",
                            headers={"Authorization": f"Bearer {token}"}, body={"raw_password": new})
    if status != 200:
        raise Warn(f"Mailu : {status} {body}")


def regen_immich(old, new):
    email = secret_value("immich", "immich-secrets", "ADMIN_EMAIL")
    with ServiceURL("immich", "immich-server", 2283) as base:
        for current in (old, new):
            status, body = http("POST", f"{base}/api/auth/login", {"email": email, "password": current})
            if status in (200, 201):
                break
        else:
            raise Warn("Immich : connexion de l'admin technique impossible (ancien et nouveau mot de passe)")
        if current == new:
            return
        status, body = http("POST", f"{base}/api/auth/change-password",
                            headers={"Authorization": f"Bearer {body['accessToken']}"},
                            body={"password": old, "newPassword": new})
    if status not in (200, 201):
        raise Warn(f"Immich : {status} {body}")


def regen_jellyfin(old, new):
    hdr = 'MediaBrowser Client="myown-admin", Device="myown-admin", DeviceId="myown-admin", Version="1.0.0"'
    with ServiceURL("jellyfin", "jellyfin", 8096) as base:
        for current in (old, new):
            status, body = http("POST", f"{base}/Users/AuthenticateByName",
                                {"Username": "admin", "Pw": current}, {"X-Emby-Authorization": hdr})
            if status == 200:
                break
        else:
            raise Warn("Jellyfin : connexion de l'admin technique impossible")
        if current == new:
            return
        auth = {"X-Emby-Authorization": f'{hdr}, Token="{body["AccessToken"]}"'}
        status, resp = http("POST", f"{base}/Users/{body['User']['Id']}/Password", headers=auth,
                            body={"CurrentPw": old, "NewPw": new})
    if status not in (200, 204):
        raise Warn(f"Jellyfin : {status} {resp}")


def regen_tuwunel_bot(old, new):
    user = secret_value("tuwunel", "tuwunel-bot", "username")
    with ServiceURL("tuwunel", "tuwunel", 8008) as base:
        if matrix_login(base, user, new):
            return
        access = matrix_login(base, user, old)
        if not access:
            raise Warn("Tuwunel : connexion du bot impossible (ancien et nouveau mot de passe)")
        status, body = http("POST", f"{base}/_matrix/client/v3/account/password",
                            headers={"Authorization": f"Bearer {access}"},
                            body={"new_password": new, "logout_devices": False,
                                  "auth": {"type": "m.login.password", "password": old,
                                           "identifier": {"type": "m.id.user", "user": user}}})
    if status != 200:
        raise Warn(f"Tuwunel : {status} {body}")


def restic_pod(name, password_ref, command):
    """Pod restic ponctuel sur le dépôt de la sauvegarde des secrets."""
    ns = "myown-backup"
    body = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": name, "namespace": ns},
            "spec": {"restartPolicy": "Never", "containers": [{
                "name": "restic", "image": "restic/restic:0.20.0", "command": ["sh", "-c", command],
                "env": [{"name": "RESTIC_REPOSITORY", "value": "/repo"},
                        {"name": "RESTIC_PASSWORD", "valueFrom": {"secretKeyRef": password_ref}}],
                "volumeMounts": [{"name": "repo", "mountPath": "/repo"},
                                 {"name": "pending", "mountPath": "/pending", "readOnly": True}]}],
                "volumes": [{"name": "repo", "persistentVolumeClaim": {"claimName": "secrets-restic-repo"}},
                            {"name": "pending", "secret": {"secretName": PENDING[1], "optional": True}}]}}
    kubectl("delete", "pod", name, "-n", ns, "--ignore-not-found")
    kubectl("create", "-f", "-", stdin=json.dumps(body))
    kubectl("wait", "-n", ns, f"pod/{name}", "--for=jsonpath={.status.phase}=Succeeded", "--timeout=300s",
            check=False)
    phase = kubectl("get", "pod", name, "-n", ns, "-o", "jsonpath={.status.phase}").stdout
    logs = kubectl("logs", "-n", ns, name, check=False).stdout.strip()
    kubectl("delete", "pod", name, "-n", ns, "--ignore-not-found")
    if phase != "Succeeded":
        raise Warn(f"restic ({name}) : {logs[-400:]}")
    return logs


def regen_secrets_backup(_old, _new):
    """Nouvelle clé du dépôt Restic (l'ancienne l'ouvre encore pour s'authentifier),
    puis retrait des autres clés avec la nouvelle — le contenu n'est pas rechiffré."""
    pkey = "myown-backup.secrets-backup.RESTIC_PASSWORD"
    keys = json.loads(restic_pod("myown-admin-restic-keys", {"name": "secrets-backup", "key": "RESTIC_PASSWORD"},
                                 "restic key list --json"))
    new_ok = None
    try:
        restic_pod("myown-admin-restic-probe", {"name": PENDING[1], "key": pkey}, "restic cat config >/dev/null")
        new_ok = True
    except Warn:
        new_ok = False
    if not new_ok:
        restic_pod("myown-admin-restic-add", {"name": "secrets-backup", "key": "RESTIC_PASSWORD"},
                   f"restic key add --new-password-file /pending/{pkey}")
    say(f"    clé ajoutée au dépôt ({len(keys)} ancienne(s) clé(s) à retirer après mise à jour du Secret)")


def secrets_backup_drop_old_keys():
    ref = {"name": "secrets-backup", "key": "RESTIC_PASSWORD"}
    keys = json.loads(restic_pod("myown-admin-restic-keys", ref, "restic key list --json"))
    old = [k["id"] for k in keys if not k.get("current")]
    if old:
        restic_pod("myown-admin-restic-drop", ref, " && ".join(f"restic key remove {i}" for i in old))
    keys = json.loads(restic_pod("myown-admin-restic-keys", ref, "restic key list --json"))
    if len(keys) != 1:
        raise Warn(f"dépôt Restic : {len(keys)} clés restantes au lieu d'une")


REGEN = [
    ("authentik/authentik-secrets", "AUTHENTIK_BOOTSTRAP_PASSWORD", regen_akadmin),
    ("argocd/argocd-initial-admin-secret", "password", regen_argocd),
    ("monitoring/monitoring-secrets", "admin-password", regen_grafana),
    ("vaultwarden/vaultwarden-secrets", "ADMIN_TOKEN", regen_vaultwarden),
    ("nextcloud/nextcloud-secrets", "NEXTCLOUD_PASSWORD", regen_nextcloud),
    ("mailu/mailu-secrets", "initial-account-password", regen_mailu),
    ("immich/immich-secrets", "ADMIN_PASSWORD", regen_immich),
    ("jellyfin/jellyfin-secrets", "ADMIN_PASSWORD", regen_jellyfin),
    ("tuwunel/tuwunel-bot", "password", regen_tuwunel_bot),
    ("myown-backup/secrets-backup", "RESTIC_PASSWORD", regen_secrets_backup),
]


def regenerate(ref, key, fn):
    """Nouvelle valeur notée d'abord dans PENDING, appliquée au service, puis
    recopiée dans le Secret : une coupure à n'importe quel moment se rejoue."""
    ns, name = ref.split("/")
    current = (get_secret(ns, name) or {}).get(key)
    if current is None:
        return False
    pkey = f"{ns}.{name}.{key}"
    if pkey in state().get("regen_done", "").split():
        return "déjà fait"
    pending_obj = get_secret(*PENDING)
    pending = pending_obj or {}
    new = pending.get(pkey)
    if new is None:
        new = rnd_token()
        if pending_obj is None:  # {} = Secret existant mais vide
            kubectl("create", "secret", "generic", PENDING[1], "-n", PENDING[0])
        patch_secret(*PENDING, {pkey: new})
    if current != new:
        fn(current, new)
        patch_secret(ns, name, {key: new})
    set_state(regen_done=" ".join(state().get("regen_done", "").split() + [pkey]))
    kubectl("patch", "secret", PENDING[1], "-n", PENDING[0], "--type", "json",
            "-p", json.dumps([{"op": "remove", "path": f"/data/{pkey}"}]), check=False)
    return "régénéré"


def rnd_token():
    import secrets as rnd
    return rnd.token_urlsafe(36)


def cmd_transfert_retrait(args):
    st = state()
    owner, verified = st.get("transfer_owner"), st.get("transfer_verified")
    if not (owner and verified):
        die("transfert non vérifié : le futur propriétaire doit d'abord lancer « transfert verifier ».")
    prep = ak_shell(AK_USER_STATE.replace('email__iexact=d["email"]', 'username=d["username"]'),
                    {"username": args.preparateur, "email": "", "group": ADMIN_GROUP})
    if not prep["found"]:
        die(f"aucun compte Authentik {args.preparateur}.")
    owner_user = ak_shell(AK_USER_STATE, {"email": owner, "group": ADMIN_GROUP})
    if owner_user.get("username") == args.preparateur:
        die("le préparateur et le nouveau propriétaire sont le même compte.")
    say(f"""Retrait du préparateur {args.preparateur} — transfert vérifié pour {owner} le {verified}.
  - sortie de {ADMIN_GROUP}, compte Authentik désactivé (pas supprimé), sessions fermées ;
  - droits d'admin retirés dans chaque service ;
  - identifiants d'admin régénérés : {', '.join(r[0].split('/')[1] + '/' + r[1] for r in REGEN)}.""")
    if input("Taper « oui » pour continuer : ").strip().lower() != "oui":
        die("abandon, rien n'a été changé.")
    backup_now("myown-backup", "secrets-restic-backup")
    out = ak_shell(AK_DISABLE, {"username": args.preparateur, "group": ADMIN_GROUP})
    say(f"Authentik : {args.preparateur} désactivé ({out['sessions']} session(s), {out['tokens']} jeton(s) supprimés)")
    failed = run_sync(apply=True)
    say("Régénération des identifiants d'admin")
    for ref, key, fn in REGEN:
        try:
            done = regenerate(ref, key, fn)
            if done:
                say(f"  {ref} {key} : {done}")
        except Warn as w:
            say(f"  ATTENTION : {ref} {key} : {w}")
            failed.append(ref)
    if "myown-backup/secrets-backup" not in failed and get_secret("myown-backup", "secrets-backup"):
        try:
            secrets_backup_drop_old_keys()
            say("  dépôt Restic des secrets : anciennes clés retirées")
        except Warn as w:
            say(f"  ATTENTION : {w}")
            failed.append("restic")
    if kubectl("get", "statefulset", "vaultwarden", "-n", "vaultwarden", check=False).returncode == 0:
        kubectl("rollout", "restart", "statefulset/vaultwarden", "-n", "vaultwarden")
        kubectl("rollout", "status", "statefulset/vaultwarden", "-n", "vaultwarden", "--timeout=300s", check=False)
    backup_now("myown-backup", "secrets-restic-backup")
    set_state(transfer_done=time.strftime("%Y-%m-%dT%H:%M:%S"), previous_admin=args.preparateur)
    say(f"""
Reste à faire, hors de ce script :
  1. Le nouveau propriétaire retire {args.preparateur} de l'organisation Vaultwarden
     (Membres → ⋮ → Retirer), puis relance « python3 scripts/myown-admin.py coffre »
     pour y recopier les identifiants régénérés.
  2. Retirer les clés SSH du préparateur (~/.ssh/authorized_keys) et ses pairs
     WireGuard (scripts/wireguard-setup.sh).
  3. Les copies de la sauvegarde des secrets faites AVANT ce retrait (clé USB)
     s'ouvrent encore avec l'ancien mot de passe : les remplacer par une copie neuve.""")
    if failed:
        die(f"retrait incomplet : {', '.join(failed)} — corriger puis relancer (rien n'est refait deux fois).")

# --- Commandes -----------------------------------------------------------------

def cmd_init(args):
    domain = args.domain or root_domain() or die("domaine inconnu : --domain.")
    apps = installed_apps()
    # Par défaut, l'e-mail donné à l'installation (celui du compte de secours akadmin).
    email = args.email or secret_value("authentik", "authentik-secrets", "AUTHENTIK_BOOTSTRAP_EMAIL")
    username = args.username or re.sub(r"[^a-z0-9._-]", "", email.split("@")[0].lower())
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", username):
        die(f"nom d'utilisateur {username!r} invalide : --username.")
    init_admin_user(email, username, args.name or username, domain, forced=bool(args.username))
    failed = []
    for app, claim in (("immich", claim_immich), ("tuwunel", claim_tuwunel), ("jellyfin", claim_jellyfin)):
        if app in apps:
            try:
                claim(domain)
            except Warn as w:
                say(f"  ATTENTION : {w}")
                failed.append(app)
    if failed:
        die(f"places « premier arrivé » non confirmées : {', '.join(failed)} (voir ci-dessus).")
    # Tous les secrets d'admin existent désormais (bot Tuwunel compris) : copie
    # immédiate plutôt qu'au passage nocturne.
    backup_now("myown-backup", "secrets-restic-backup")


def main():
    p = argparse.ArgumentParser(description="Comptes et droits d'admin de MyOwn.")
    sub = p.add_subparsers(dest="command", required=True)
    i = sub.add_parser("init", help="compte de l'admin et places « premier arrivé »")
    i.add_argument("--email", help="défaut : e-mail donné à l'installation (MYOWN_ADMIN_EMAIL)")
    i.add_argument("--username")
    i.add_argument("--name")
    i.add_argument("--domain")
    sy = sub.add_parser("sync", help="aligne les droits d'admin des services sur le groupe")
    sy.add_argument("--apply", action="store_true", help="appliquer (sinon : aperçu)")
    sub.add_parser("coffre", help="copie les secrets du cluster dans l'organisation Vaultwarden")
    t = sub.add_parser("transfert", help="remise des clés à un nouveau propriétaire")
    tsub = t.add_subparsers(dest="etape", required=True)
    ta = tsub.add_parser("ajout", help="le futur propriétaire entre dans myown-admins")
    ta.add_argument("--email", required=True)
    ta.add_argument("--username")
    ta.add_argument("--name")
    tsub.add_parser("verifier", help="lancé par le futur propriétaire : droits et coffre vérifiés")
    tr = tsub.add_parser("retrait", help="après vérification : le préparateur est retiré")
    tr.add_argument("--preparateur", required=True, help="nom d'utilisateur Authentik du préparateur")
    args = p.parse_args()
    if args.command == "transfert":
        {"ajout": cmd_transfert_ajout, "verifier": cmd_transfert_verifier,
         "retrait": cmd_transfert_retrait}[args.etape](args)
    else:
        {"init": cmd_init, "sync": cmd_sync, "coffre": cmd_coffre}[args.command](args)


if __name__ == "__main__":
    main()
