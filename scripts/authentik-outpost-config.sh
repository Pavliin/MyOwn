#!/usr/bin/env bash
# Sets authentik_host / authentik_host_browser on the embedded outpost —
# needed for ANY ForwardAuth-mode Proxy Provider (first used by Mailu's
# webmail/admin SSO, gitops/secrets/authentik-blueprints/mailu-sso.sops.yaml)
# to build correct browser-facing login redirects.
#
# Real bug found live (2026-08-23): left unset, the embedded outpost
# defaults to "http://localhost" for the OAuth2 authorize redirect it
# sends the browser to — the redirect_uri parameter itself is correctly
# derived from X-Forwarded-Host, but the authorize endpoint's own base
# URL isn't. Confirmed via a real browser ForwardAuth test against a
# throwaway `traefik/whoami` target before ever touching Mailu.
#
# Not a blueprint: Outpost.config is a JSON field holding several other
# chart-managed keys (kubernetes_namespace, kubernetes_replicas, ...) —
# a blueprint's `attrs: {config: {...}}` would need to reproduce that
# whole dict to avoid clobbering it on every sync, which is more fragile
# than a small idempotent script that only touches the two keys this
# project actually needs (same reasoning as uptime-kuma-setup.py/
# jellyfin-sso-setup.py: declarative blueprint config that doesn't fit
# cleanly falls back to a script here, not a blueprint).
#
# Also (optionally) binds a Proxy Provider to the embedded outpost's
# `providers` M2M list, additively (`.add()`, never `.set()`) — a
# blueprint's `attrs: {providers: [...]}` on the Outpost model would
# REPLACE the whole list on every ArgoCD selfHeal sync, silently
# unbinding any other ForwardAuth provider added later (e.g. a future
# ArgoCD/Grafana protection, noted as a follow-up in the Mailu plan).
# Additive binding belongs here, not in the provider's own blueprint.
#
# Usage:
#   scripts/authentik-outpost-config.sh                              # this kubectl context, config only
#   scripts/authentik-outpost-config.sh --bind-provider mailu         # also bind the "mailu" ProxyProvider
#   scripts/authentik-outpost-config.sh --ssh user@host [--bind-provider mailu]   # remote (e.g. mini PC)
#
# Safe to rerun (idempotent — sets the same two keys, `.add()` is a no-op if already bound).

set -euo pipefail

AUTHENTIK_HOST_URL="${AUTHENTIK_HOST_URL:-https://authentik.offsystem.fr}"

SSH_TARGET=""
BIND_PROVIDER=""
while [ $# -gt 0 ]; do
  case "$1" in
    --ssh) SSH_TARGET="$2"; shift 2 ;;
    --bind-provider) BIND_PROVIDER="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

PY=$(cat <<EOF
from authentik.outposts.models import Outpost
o = Outpost.objects.get(name="authentik Embedded Outpost")
o._config["authentik_host"] = "${AUTHENTIK_HOST_URL}"
o._config["authentik_host_browser"] = "${AUTHENTIK_HOST_URL}"
o.save()
o.refresh_from_db()
print("authentik_host_browser =", o.config.authentik_host_browser)

bind_provider = "${BIND_PROVIDER}"
if bind_provider:
    from authentik.providers.proxy.models import ProxyProvider
    p = ProxyProvider.objects.get(name=bind_provider)
    o.providers.add(p)
    print("bound provider:", bind_provider, "| outpost providers now:", list(o.providers.values_list("name", flat=True)))
EOF
)

if [ -n "$SSH_TARGET" ]; then
  ssh "$SSH_TARGET" "sudo kubectl exec -n authentik deploy/authentik-server -- ak shell -c \"$PY\""
else
  kubectl exec -n authentik deploy/authentik-server -- ak shell -c "$PY"
fi
