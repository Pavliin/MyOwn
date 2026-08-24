#!/usr/bin/env bash
# Installs a host-level systemd service that keeps a long-lived
# `kubectl port-forward` open from the WireGuard mail-relay tunnel
# interface (wireguard-mail-relay/, 10.100.1.2 on this machine) straight
# into Mailu's SMTP port inside the dev k3d cluster (svc/mailu-front:25,
# namespace mailu).
#
# Why not a real hostPort/NodePort instead: Mailu's own hostPort was
# deliberately disabled when it was first deployed (deadlocks any future
# rollout on this single-node k3d cluster, see notes-techniques.md), and
# k3d additionally needs a *new port mapping declared at cluster
# creation* to expose anything new on the host at all — meaning fixing
# this "properly" would mean recreating the whole dev cluster a third
# time, for a cluster this project is going to abandon anyway once Mailu
# migrates to the mini PC (real k3s, hostPort works natively there, no
# port-mapping translation layer). A persistent port-forward is the
# deliberately cheap, disposable stand-in for that migration — see
# mail-relay-vps/README.md.
#
# Needs interactive sudo (systemd unit install, binding port 25 requires
# root) — run this yourself in your own terminal, never via an automated
# tool.
#
# Env vars (all optional):
#   MYOWN_MAILU_PF_TUNNEL_ADDR  address to bind on, default 10.100.1.2
#                               (this machine's wg-mail0 address — binding
#                               here, not 0.0.0.0, keeps this off the LAN)
#   MYOWN_MAILU_PF_NAMESPACE    default "mailu"
#   MYOWN_MAILU_PF_SERVICE      default "mailu-front"
#   MYOWN_MAILU_PF_PORT         default 25
#
# Idempotent: safe to re-run, just rewrites the unit and restarts it.

set -euo pipefail

TUNNEL_ADDR="${MYOWN_MAILU_PF_TUNNEL_ADDR:-10.100.1.2}"
NAMESPACE="${MYOWN_MAILU_PF_NAMESPACE:-mailu}"
SERVICE="${MYOWN_MAILU_PF_SERVICE:-mailu-front}"
PORT="${MYOWN_MAILU_PF_PORT:-25}"
UNIT_FILE="/etc/systemd/system/myown-mailu-portforward.service"

step() { echo -e "\n\033[1;34m==> $1\033[0m"; }

step "Vérification des outils requis"
KUBECTL_BIN="$(command -v kubectl)" || { echo "Manquant : kubectl."; exit 1; }
KUBECONFIG_PATH="${KUBECONFIG:-$HOME/.kube/config}"
[ -f "$KUBECONFIG_PATH" ] || { echo "Kubeconfig introuvable : $KUBECONFIG_PATH"; exit 1; }
ip -4 addr show wg-mail0 2>/dev/null | grep -q "$TUNNEL_ADDR" || {
  echo "L'interface wg-mail0 n'a pas l'adresse $TUNNEL_ADDR — tunnel monté ? (voir wireguard-mail-relay/README.md)"
  exit 1
}

step "Écriture de l'unité systemd (sudo requis, port <1024 => root)"
sudo tee "$UNIT_FILE" >/dev/null <<EOF
[Unit]
Description=MyOwn — port-forward relais mail (tunnel wg-mail0 -> ${SERVICE}:${PORT} ns ${NAMESPACE})
After=network-online.target wg-quick@wg-mail0.service
Requires=wg-quick@wg-mail0.service

[Service]
Type=simple
Environment=KUBECONFIG=${KUBECONFIG_PATH}
ExecStart=${KUBECTL_BIN} port-forward --address ${TUNNEL_ADDR} -n ${NAMESPACE} svc/${SERVICE} ${PORT}:${PORT}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

step "Activation (sudo requis)"
sudo systemctl daemon-reload
sudo systemctl enable --now myown-mailu-portforward.service
sleep 2
sudo systemctl status myown-mailu-portforward.service --no-pager || true

step "Terminé"
echo "Écoute sur ${TUNNEL_ADDR}:${PORT}, relaie vers svc/${SERVICE}:${PORT} (namespace ${NAMESPACE})."
echo "Journal :   journalctl -u myown-mailu-portforward.service -f"
echo "Test local (depuis cette machine) :  nc -zv ${TUNNEL_ADDR} ${PORT}"
echo "Test depuis le VPS (une fois lancé) :  ssh <vps> -- nc -zv ${TUNNEL_ADDR} ${PORT}"
