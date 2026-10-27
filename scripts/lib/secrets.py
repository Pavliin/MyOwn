#!/usr/bin/env python3
"""Secrets générés dans le cluster, jamais commités (installation-utilisateur.md,
« Secrets générés dans le cluster »).

Crée ce qui manque, n'écrase jamais une valeur existante, n'affiche jamais une
valeur : seulement des noms de Secrets et de clés. Appelé par scripts/install.sh ;
lançable seul sur une installation existante, y compris à distance sans checkout :

    ssh <serveur> 'KUBECTL="sudo k3s kubectl" python3 - ensure' < scripts/lib/secrets.py

Commandes :
  ensure [--apps a,b] [--domain d] [--admin-email e]
      Crée les Secrets manquants (et les clés manquantes des Secrets existants)
      des services installés. Sans --apps : services déduits des Applications
      présentes ; sans --domain : domaine lu dans root.
  protect   Pose Prune=false sur les Secrets du catalogue encore suivis par
      ArgoCD (anciens Secrets KSOPS) : à faire AVANT la synchronisation qui
      retire leurs sources, sinon ArgoCD les supprimerait.
  release   Retire le suivi ArgoCD de ces mêmes Secrets, APRÈS cette
      synchronisation : ils deviennent des objets ordinaires du cluster,
      valeurs inchangées.
  check-backup   Vérifie (sans cluster) que chaque Secret du catalogue est
      dans la liste sauvegardée (gitops/manifests/secrets-backup/values.yaml).

Codes de sortie : 0 succès, 3 provisoire (l'installeur réessaie), 1 sinon.
"""
import argparse
import base64
import json
import os
import re
import secrets as rnd
import shlex
import subprocess
import sys
import tomllib

KUBECTL = shlex.split(os.environ.get("KUBECTL", "kubectl"))
LABEL = "myown.offsystem.fr/generated"
TRACKING = "argocd.argoproj.io/tracking-id"
SYNC_OPTIONS = "argocd.argoproj.io/sync-options"


def kubectl(*args, stdin=None, check=True):
    return subprocess.run(KUBECTL + list(args), input=stdin, capture_output=True, text=True, check=check)


def get_object(kind, ns, name):
    res = kubectl("get", kind, name, "-n", ns, "-o", "json", check=False)
    if res.returncode != 0:
        if "NotFound" in res.stderr:
            return None
        sys.exit(f"lecture de {kind} {ns}/{name} impossible : {res.stderr.strip()}")
    return json.loads(res.stdout)


def get_secret(ns, name):
    """Données décodées d'un Secret, ou None s'il n'existe pas."""
    obj = get_object("secret", ns, name)
    if obj is None:
        return None
    return {k: base64.b64decode(v).decode() for k, v in (obj.get("data") or {}).items()}


def write_secret(ns, name, data):
    """Crée le Secret, ou y ajoute les clés manquantes (merge : jamais d'écrasement)."""
    if kubectl("get", "namespace", ns, check=False).returncode != 0:
        kubectl("create", "namespace", ns)
    if get_secret(ns, name) is None:
        body = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": name, "namespace": ns, "labels": {LABEL: "true"}},
            "type": "Opaque",
            "stringData": data,
        }
        kubectl("create", "-f", "-", stdin=json.dumps(body))
    else:
        kubectl("patch", "secret", name, "-n", ns, "--type", "merge",
                "-p", json.dumps({"metadata": {"labels": {LABEL: "true"}}, "stringData": data}))


# --- Générateurs -------------------------------------------------------------
# Chaque valeur est une fonction (ctx, valeurs déjà connues du Secret) -> str.

def rand(_ctx, _vals):
    return rnd.token_urlsafe(36)  # 48 caractères


def hexa(_ctx, _vals):
    return rnd.token_hex(32)  # 64 caractères hexadécimaux


def const(value):
    return lambda _ctx, _vals: value


def same_as(key):
    return lambda _ctx, vals: vals[key]


def admin_email(ctx, _vals):
    if not ctx.admin_email:
        print("e-mail de l'admin requis pour créer ce secret : relancer avec --admin-email "
              "(installeur : MYOWN_ADMIN_EMAIL).", file=sys.stderr)
        sys.exit(1)
    return ctx.admin_email


def livekit_keys(_ctx, vals):
    return f"{vals['LIVEKIT_KEY']}: {vals['LIVEKIT_SECRET']}\n"


def immich_oauth(ctx, _vals):
    return (
        "oauth:\n"
        "  enabled: true\n"
        f"  issuerUrl: https://authentik.{ctx.domain}/application/o/immich/\n"
        "  clientId: immich\n"
        f"  clientSecret: {rnd.token_urlsafe(33)}\n"
        "  scope: openid email profile\n"
        '  buttonText: "Se connecter via Authentik"\n'
    )


# Catalogue : service -> [(namespace, Secret, [(clé, générateur)])]. L'ordre des
# clés compte : une clé dérivée (same_as, livekit_keys) suit celle dont elle dépend.
# Les constantes et appariements reprennent ceux de l'installation de l'auteur,
# vérifiés en prod par comparaison (jamais en lisant une valeur), 2026-10-27.
CATALOG = {
    "authentik": [("authentik", "authentik-secrets", [
        ("AUTHENTIK_SECRET_KEY", rand),
        ("AUTHENTIK_POSTGRESQL__HOST", const("authentik-postgresql")),
        ("AUTHENTIK_POSTGRESQL__NAME", const("authentik")),
        ("AUTHENTIK_POSTGRESQL__USER", const("authentik")),
        ("AUTHENTIK_POSTGRESQL__PORT", const("5432")),
        ("password", rand),
        ("AUTHENTIK_POSTGRESQL__PASSWORD", same_as("password")),
        ("postgres-password", rand),
        ("RESTIC_PASSWORD", rand),
        ("AUTHENTIK_BOOTSTRAP_PASSWORD", rand),
        ("AUTHENTIK_BOOTSTRAP_EMAIL", admin_email),
    ])],
    "vaultwarden": [("vaultwarden", "vaultwarden-secrets", [
        ("ADMIN_TOKEN", rand),
        ("SSO_CLIENT_ID", const("vaultwarden")),
        ("SSO_CLIENT_SECRET", rand),
        ("RESTIC_PASSWORD", rand),
    ])],
    "nextcloud": [("nextcloud", "nextcloud-secrets", [
        ("NEXTCLOUD_USERNAME", const("admin")),
        ("NEXTCLOUD_PASSWORD", rand),
        ("DB_USERNAME", const("nextcloud")),
        ("password", rand),
        ("postgres-password", rand),
        ("REDIS_PASSWORD", rand),
        ("OIDC_CLIENT_ID", const("nextcloud")),
        ("OIDC_CLIENT_SECRET", rand),
        ("RESTIC_PASSWORD", rand),
    ])],
    "immich": [
        ("immich", "immich-secrets", [
            ("DB_USERNAME", const("immich")),
            ("DB_PASSWORD", hexa),
            ("RESTIC_PASSWORD", rand),
            ("ADMIN_EMAIL", admin_email),
            ("ADMIN_PASSWORD", rand),
        ]),
        # Configuration OAuth partielle d'Immich (IMMICH_CONFIG_FILE) : contient
        # le domaine, mais Immich ne sait pas lire un secret ailleurs que dans
        # ce fichier — générée une fois, avec le domaine de l'installation.
        ("immich", "immich-oauth-config", [("immich-config.yaml", immich_oauth)]),
    ],
    "jellyfin": [("jellyfin", "jellyfin-secrets", [
        ("SSO_CLIENT_ID", const("jellyfin")),
        ("SSO_CLIENT_SECRET", hexa),
        ("ADMIN_PASSWORD", rand),
        ("RESTIC_PASSWORD", rand),
    ])],
    "livekit": [("livekit", "livekit-secrets", [
        ("LIVEKIT_KEY", const("livekit")),
        ("LIVEKIT_SECRET", hexa),
        ("keys.yaml", livekit_keys),
    ])],
    "mailu": [("mailu", "mailu-secrets", [
        ("secret-key", hexa),
        ("initial-account-password", rand),
        ("roundcube-db-password", rand),
        ("API_TOKEN", hexa),
        ("RESTIC_PASSWORD", rand),
    ])],
    "monitoring": [("monitoring", "monitoring-secrets", [
        ("admin-user", const("admin")),
        ("admin-password", rand),
    ])],
    # Mot de passe du dépôt Restic des Secrets eux-mêmes : la seule valeur à
    # garder hors du cluster, elle ouvre toutes les autres. Toujours créé
    # (infrastructure), jamais inclus dans la sauvegarde qu'il chiffre.
    "secrets-backup": [("myown-backup", "secrets-backup", [("RESTIC_PASSWORD", rand)])],
    "tuwunel": [
        ("tuwunel", "tuwunel-secrets", [("RESTIC_PASSWORD", rand)]),
        ("tuwunel", "tuwunel-config-secrets", [
            ("registration_token", rand),
            ("client_secret", rand),
        ]),
    ],
}


def ensure_catalog(ctx):
    for svc in ctx.apps:
        for ns, name, keys in CATALOG.get(svc, []):
            current = get_secret(ns, name) or {}
            known = dict(current)
            wanted = {}
            for key, gen in keys:
                if key in known:
                    continue
                if name == "tuwunel-config-secrets":
                    value = legacy_tuwunel(key) or gen(ctx, known)
                else:
                    value = gen(ctx, known)
                known[key] = wanted[key] = value
            if wanted:
                write_secret(ns, name, wanted)
                print(f"  {ns}/{name} : {', '.join(wanted)} {'créé(s)' if current else '(Secret créé)'}")
            else:
                print(f"  {ns}/{name} : déjà complet")


def legacy_tuwunel(key):
    """Valeur reprise de l'ancien tuwunel.toml chiffré (installations antérieures à 2026-10-27)."""
    old = (get_secret("tuwunel", "tuwunel-secrets") or {}).get("tuwunel.toml")
    if not old:
        return None
    cfg = tomllib.loads(old)["global"]
    if key == "registration_token":
        return cfg.get("registration_token")
    idps = cfg.get("identity_provider") or []
    return idps[0].get("client_secret") if idps else None


def immich_client_secret():
    cfg = (get_secret("immich", "immich-oauth-config") or {}).get("immich-config.yaml", "")
    m = re.search(r"^\s*clientSecret:\s*[\"']?([^\"'\s]+)", cfg, re.M)
    return m.group(1) if m else None


# Service -> secret OIDC côté service. La moitié Authentik en est toujours dérivée :
# les deux moitiés d'un client OIDC ne peuvent pas diverger.
OIDC_SOURCES = {
    "vaultwarden": lambda: (get_secret("vaultwarden", "vaultwarden-secrets") or {}).get("SSO_CLIENT_SECRET"),
    "nextcloud": lambda: (get_secret("nextcloud", "nextcloud-secrets") or {}).get("OIDC_CLIENT_SECRET"),
    "jellyfin": lambda: (get_secret("jellyfin", "jellyfin-secrets") or {}).get("SSO_CLIENT_SECRET"),
    "immich": immich_client_secret,
    "tuwunel": lambda: (get_secret("tuwunel", "tuwunel-config-secrets") or {}).get("client_secret"),
}


def ensure_authentik_sso(ctx):
    ns, name = "authentik", "authentik-sso-clients"
    current = get_secret(ns, name) or {}
    wanted = {}
    for svc, source in OIDC_SOURCES.items():
        key = f"{svc.upper()}_CLIENT_SECRET"
        if svc not in ctx.apps or key in current:
            continue
        value = source()
        if not value:
            print(f"{svc} installé mais son secret OIDC côté service n'existe pas encore : rien n'a été écrit.",
                  file=sys.stderr)
            sys.exit(3)
        wanted[key] = value
        print(f"  {ns}/{name} : {key} dérivé du secret de {svc}")
    if wanted or not current:
        write_secret(ns, name, wanted)
    if not wanted:
        print(f"  {ns}/{name} : déjà complet")


def catalog_secrets():
    for entries in CATALOG.values():
        for ns, name, _keys in entries:
            yield ns, name


def protect():
    """Prune=false sur les Secrets du catalogue encore suivis par ArgoCD."""
    for ns, name in catalog_secrets():
        obj = get_object("secret", ns, name)
        if obj is None:
            continue
        ann = obj["metadata"].get("annotations") or {}
        if TRACKING not in ann:
            continue
        opts = ann.get(SYNC_OPTIONS, "")
        if "Prune=false" not in opts:
            opts = f"{opts},Prune=false" if opts else "Prune=false"
            kubectl("annotate", "secret", name, "-n", ns, "--overwrite", f"{SYNC_OPTIONS}={opts}")
        print(f"  {ns}/{name} : protégé (Prune=false)")


def release():
    """Retire le suivi ArgoCD des Secrets du catalogue (valeurs inchangées)."""
    for ns, name in catalog_secrets():
        obj = get_object("secret", ns, name)
        if obj is None:
            continue
        ann = obj["metadata"].get("annotations") or {}
        args = []
        if TRACKING in ann:
            args.append(f"{TRACKING}-")
        if ann.get(SYNC_OPTIONS) == "Prune=false":
            args.append(f"{SYNC_OPTIONS}-")
        if args:
            kubectl("annotate", "secret", name, "-n", ns, *args)
        kubectl("label", "secret", name, "-n", ns, "--overwrite", f"{LABEL}=true")
        print(f"  {ns}/{name} : détaché d'ArgoCD" if args else f"  {ns}/{name} : déjà détaché")


def check_backup():
    values = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                          "gitops", "manifests", "secrets-backup", "values.yaml")
    listed = set(re.findall(r"^\s*-\s*([a-z0-9-]+/[a-z0-9-]+)\s*$", open(values).read(), re.M))
    missing = [f"{ns}/{name}" for ns, name in catalog_secrets()
               if name != "secrets-backup" and f"{ns}/{name}" not in listed]
    if "authentik/authentik-sso-clients" not in listed:
        missing.append("authentik/authentik-sso-clients")
    if missing:
        sys.exit("Secrets du catalogue absents de la sauvegarde : " + ", ".join(missing))
    print(f"sauvegarde : les {len(listed)} Secrets listés couvrent le catalogue")


def installed_apps():
    res = kubectl("get", "applications", "-n", "argocd", "-o", "jsonpath={.items[*].metadata.name}")
    return set(res.stdout.split())


def root_domain():
    res = kubectl("get", "application", "root", "-n", "argocd",
                  "-o", "jsonpath={.spec.source.helm.valuesObject.domain}", check=False)
    return res.stdout.strip() if res.returncode == 0 else ""


def main():
    p = argparse.ArgumentParser(description="Secrets MyOwn générés dans le cluster.")
    p.add_argument("command", choices=["ensure", "protect", "release", "check-backup"])
    p.add_argument("--apps", help="services installés, séparés par des virgules")
    p.add_argument("--domain")
    p.add_argument("--admin-email", default=os.environ.get("MYOWN_ADMIN_EMAIL"))
    ctx = p.parse_args()
    if ctx.command == "protect":
        return protect()
    if ctx.command == "release":
        return release()
    if ctx.command == "check-backup":
        return check_backup()
    ctx.apps = set(ctx.apps.split(",")) if ctx.apps else installed_apps()
    ctx.apps.add("secrets-backup")
    ctx.domain = ctx.domain or root_domain()
    if "immich" in ctx.apps and not ctx.domain:
        sys.exit("domaine inconnu : relancer avec --domain.")
    ensure_catalog(ctx)
    if "authentik" in ctx.apps:
        ensure_authentik_sso(ctx)


if __name__ == "__main__":
    main()
