#!/usr/bin/env bash
# Installs the host-level auto-remediation watchdog — see
# watchdog-check.sh's own header and architecture.md §6 for why this is
# deliberately NOT a Kubernetes manifest (same circular-dependency
# reasoning as WireGuard: the watchdog exists to fix the cluster when
# it's down, so it can't live inside the cluster it's meant to rescue).
#
# Needs interactive sudo (systemd unit install, /var/lib/, restarting
# k3s) — run this yourself in your own terminal, never via an automated
# tool.
#
# Env vars (all optional, sane defaults):
#   MYOWN_WD_THRESHOLD                 consecutive failed checks before
#                                       remediation, default 3
#   MYOWN_WD_MAX_REMEDIATIONS_PER_HOUR anti-loop cap, default 3
#   MYOWN_WD_INTERVAL                  seconds between checks, default 60
#
# Idempotent: safe to re-run after pulling repo changes, re-copies the
# check script and unit files and reloads systemd.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INTERVAL="${MYOWN_WD_INTERVAL:-60}"
THRESHOLD="${MYOWN_WD_THRESHOLD:-3}"
MAX_REMEDIATIONS_PER_HOUR="${MYOWN_WD_MAX_REMEDIATIONS_PER_HOUR:-3}"

CHECK_SCRIPT_DEST="/usr/local/bin/myown-watchdog-check.sh"
SERVICE_FILE="/etc/systemd/system/myown-watchdog.service"
TIMER_FILE="/etc/systemd/system/myown-watchdog.timer"

step() { echo -e "\n\033[1;34m==> $1\033[0m"; }

step "Vérification des outils requis"
SOPS_BIN="$(command -v sops)" || { echo "Manquant : sops (voir manuel-installation.md)."; exit 1; }
command -v k3s >/dev/null || { echo "k3s introuvable — ce watchdog cible k3s bare-metal (Phase 4), pas le cluster de dev k3d."; exit 1; }
# Chemin absolu résolu ici (shell interactif) plutôt que de compter sur
# `sops` dans le PATH du service systemd, plus restreint (n'inclut pas
# ~/.local/bin, où sops est souvent installé sans gestionnaire de
# paquets système) — bug réel trouvé en testant pour de vrai : le
# contrôle de santé et le redémarrage fonctionnaient, seule la
# notification échouait silencieusement ("sops: command not found").

step "Installation du script de contrôle (sudo requis)"
sudo install -d -m 755 /var/lib/myown-watchdog
sudo install -m 755 "$REPO_ROOT/scripts/watchdog-check.sh" "$CHECK_SCRIPT_DEST"

step "Écriture des unités systemd (sudo requis)"
sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=MyOwn — controle de sante k3s + remediation automatique
After=network-online.target

[Service]
Type=oneshot
Environment=MYOWN_WD_THRESHOLD=${THRESHOLD}
Environment=MYOWN_WD_MAX_REMEDIATIONS_PER_HOUR=${MAX_REMEDIATIONS_PER_HOUR}
Environment=MYOWN_WD_SOPS_BIN=${SOPS_BIN}
ExecStart=${CHECK_SCRIPT_DEST}
EOF

sudo tee "$TIMER_FILE" >/dev/null <<EOF
[Unit]
Description=MyOwn — declenche le controle de sante watchdog toutes les ${INTERVAL}s

[Timer]
OnBootSec=${INTERVAL}
OnUnitActiveSec=${INTERVAL}
Persistent=true

[Install]
WantedBy=timers.target
EOF

step "Activation (sudo requis)"
sudo systemctl daemon-reload
sudo systemctl enable --now myown-watchdog.timer
sudo systemctl status myown-watchdog.timer --no-pager || true

step "Terminé"
echo "Verifie toutes les ${INTERVAL}s ; remediation (redemarrage de k3s) apres ${THRESHOLD} echecs consecutifs (~$((THRESHOLD * INTERVAL / 60)) min),"
echo "plafonnee a ${MAX_REMEDIATIONS_PER_HOUR} tentatives/heure au-dela desquelles le watchdog abandonne et alerte plutot que boucler indefiniment."
echo ""
echo "Journal :         journalctl -t myown-watchdog -f"
echo "Etat persiste :    /var/lib/myown-watchdog/"
echo "Test manuel :      sudo systemctl start myown-watchdog.service  (execute un controle immediatement)"
echo "Test de panne :    sudo systemctl stop k3s   (observer le journal ~${THRESHOLD} minutes, puis la reprise automatique)"
