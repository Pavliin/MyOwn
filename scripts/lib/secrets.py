#!/usr/bin/env python3
"""Secrets générés dans le cluster, jamais commités (installation-utilisateur.md,
« Secrets générés dans le cluster »).

Crée ce qui manque, n'écrase jamais une valeur existante, n'affiche jamais une
valeur : seulement des noms de Secrets et de clés. Appelé par scripts/install.sh ;
lançable seul sur une installation existante, y compris à distance sans checkout :

    ssh <serveur> 'KUBECTL="sudo k3s kubectl" python3 - ensure' < scripts/lib/secrets.py

Secrets gérés ici :
  tuwunel/tuwunel-config-secrets     registration_token, client_secret
      Lus par tuwunel.toml (*_file). Repris de l'ancien tuwunel.toml chiffré
      (tuwunel-secrets) s'il existe, sinon générés.
  authentik/authentik-sso-clients    <SERVICE>_CLIENT_SECRET par service OIDC installé
      Lus par les blueprints (!Env). Toujours DÉRIVÉS du secret côté service :
      les deux moitiés d'un client OIDC ne peuvent pas diverger. Si l'ancien
      blueprint chiffré est encore là, son secret doit être identique, sinon
      refus (rien n'est écrit).
"""
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


def kubectl(*args, stdin=None, check=True):
    return subprocess.run(KUBECTL + list(args), input=stdin, capture_output=True, text=True, check=check)


def get_secret(ns, name):
    """Données décodées d'un Secret, ou None s'il n'existe pas."""
    res = kubectl("get", "secret", name, "-n", ns, "-o", "json", check=False)
    if res.returncode != 0:
        if "NotFound" in res.stderr:
            return None
        sys.exit(f"lecture de {ns}/{name} impossible : {res.stderr.strip()}")
    data = json.loads(res.stdout).get("data") or {}
    return {k: base64.b64decode(v).decode() for k, v in data.items()}


def write_secret(ns, name, data):
    """Crée le Secret, ou y ajoute les clés manquantes (merge : jamais d'écrasement)."""
    body = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": name, "namespace": ns, "labels": {"myown.offsystem.fr/generated": "true"}},
        "type": "Opaque",
        "stringData": data,
    }
    if get_secret(ns, name) is None:
        kubectl("create", "-f", "-", stdin=json.dumps(body))
    else:
        kubectl("patch", "secret", name, "-n", ns, "--type", "merge", "-p", json.dumps({"stringData": data}))


def app_installed(app):
    return kubectl("get", "application", app, "-n", "argocd", check=False).returncode == 0


def namespace_exists(ns):
    return kubectl("get", "namespace", ns, check=False).returncode == 0


def new_secret():
    return rnd.token_urlsafe(48)


def ensure_tuwunel():
    ns, name = "tuwunel", "tuwunel-config-secrets"
    current = get_secret(ns, name) or {}
    wanted = {}
    legacy = {}
    old = get_secret(ns, "tuwunel-secrets") or {}
    if "tuwunel.toml" in old:
        cfg = tomllib.loads(old["tuwunel.toml"])["global"]
        legacy["registration_token"] = cfg.get("registration_token")
        idps = cfg.get("identity_provider") or []
        legacy["client_secret"] = idps[0].get("client_secret") if idps else None
    for key in ("registration_token", "client_secret"):
        if key in current:
            continue
        wanted[key] = legacy.get(key) or new_secret()
        print(f"  {ns}/{name} : {key} {'repris de tuwunel.toml' if legacy.get(key) else 'généré'}")
    if wanted:
        if not namespace_exists(ns):
            kubectl("create", "namespace", ns)
        write_secret(ns, name, wanted)
    else:
        print(f"  {ns}/{name} : déjà complet")


def immich_client_secret():
    cfg = (get_secret("immich", "immich-oauth-config") or {}).get("immich-config.yaml", "")
    m = re.search(r"^\s*clientSecret:\s*[\"']?([^\"'\s]+)", cfg, re.M)
    return m.group(1) if m else None


# Service -> (source du secret côté service). La moitié Authentik en est dérivée.
OIDC_SOURCES = {
    "vaultwarden": lambda: (get_secret("vaultwarden", "vaultwarden-secrets") or {}).get("SSO_CLIENT_SECRET"),
    "nextcloud": lambda: (get_secret("nextcloud", "nextcloud-secrets") or {}).get("OIDC_CLIENT_SECRET"),
    "jellyfin": lambda: (get_secret("jellyfin", "jellyfin-secrets") or {}).get("SSO_CLIENT_SECRET"),
    "immich": immich_client_secret,
    "tuwunel": lambda: (get_secret("tuwunel", "tuwunel-config-secrets") or {}).get("client_secret"),
}


def legacy_blueprint_secret(svc):
    """client_secret de l'ancien blueprint chiffré (Secret authentik-blueprint-<svc>-sso), s'il existe."""
    bp = get_secret("authentik", f"authentik-blueprint-{svc}-sso") or {}
    text = bp.get(f"{svc}-sso.yaml", "")
    m = re.search(r"^\s*client_secret:\s*[\"']?([^\"'\s]+)", text, re.M)
    return m.group(1) if m else None


def ensure_authentik_sso():
    ns, name = "authentik", "authentik-sso-clients"
    current = get_secret(ns, name) or {}
    wanted = {}
    for svc, source in OIDC_SOURCES.items():
        key = f"{svc.upper()}_CLIENT_SECRET"
        if not app_installed(svc) or key in current:
            continue
        value = source()
        if not value:
            # Pas encore créé (première synchronisation en cours) : code 3,
            # l'installeur réessaie. Les autres échecs (code 1) sont définitifs.
            print(f"{svc} installé mais son secret OIDC côté service n'existe pas encore : rien n'a été écrit.", file=sys.stderr)
            sys.exit(3)
        legacy = legacy_blueprint_secret(svc)
        if legacy is not None and legacy != value:
            sys.exit(f"{svc} : le secret côté service diffère de celui de l'ancien blueprint — rien n'a été écrit.")
        wanted[key] = value
        print(f"  {ns}/{name} : {key} dérivé du secret de {svc}" + (" (identique à l'ancien blueprint)" if legacy else ""))
    if wanted:
        write_secret(ns, name, wanted)
    elif current:
        print(f"  {ns}/{name} : déjà complet")
    else:
        write_secret(ns, name, {})
        print(f"  {ns}/{name} : créé vide (aucun service OIDC installé)")


def main():
    if sys.argv[1:] != ["ensure"]:
        sys.exit("usage : secrets.py ensure")
    if app_installed("tuwunel"):
        ensure_tuwunel()
    ensure_authentik_sso()


if __name__ == "__main__":
    main()
