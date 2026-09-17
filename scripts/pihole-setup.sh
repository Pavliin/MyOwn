#!/usr/bin/env bash
# Deploys Pi-hole as a host-level Docker container — see architecture.md §6
# for why this is deliberately NOT a Kubernetes manifest (same
# circular-dependency reasoning as WireGuard/the watchdog: this is the
# DNS server for the whole family network, so it can't depend on the
# health of the k3s cluster it happens to share a host with).
#
# Needs Docker installed (see manuel-installation.md) and sudo (container
# management, bind-mount directory under /opt) — run this yourself on the
# target host, never via an automated tool.
#
# Non-negotiable safeguard (roadmap.md Phase 4): the router's DHCP must
# hand out a secondary fallback DNS (1.1.1.1 / 9.9.9.9) alongside this
# host's IP, so a Pi-hole outage degrades ad-blocking rather than cutting
# internet access for the whole house. That's a router-side step, not
# something this script can do.
#
# Idempotent: safe to re-run — does nothing if the container already
# exists (recreate manually with `docker rm -f pihole-myown` first if you
# really want to reset it; that also wipes the admin password unless
# MYOWN_PIHOLE_DATA_DIR already holds a previous /etc/pihole).
#
# Env vars (all optional, sane defaults):
#   MYOWN_PIHOLE_IMAGE_TAG   pihole/pihole image tag, default "2026.07.2"
#                            (pinned, not :latest — see CLAUDE.md conventions)
#   MYOWN_PIHOLE_WEB_PORT    host+container port for the admin web UI,
#                            default 8081 (80/443 already held by Traefik)
#   MYOWN_PIHOLE_DATA_DIR    bind-mount host dir for /etc/pihole, default
#                            /opt/myown-pihole/etc-pihole
#   MYOWN_PIHOLE_TZ          default "Europe/Paris"
#   MYOWN_PIHOLE_UPSTREAMS   semicolon-separated upstream resolvers Pi-hole
#                            queries after filtering, default
#                            "1.1.1.1;9.9.9.9" (same resolvers already
#                            used as the router's DHCP fallback)
#   MYOWN_PIHOLE_ADMIN_PASSWORD  admin password; random if unset (written
#                            once to $HOME/myown-pihole-admin-password.txt,
#                            never committed — same pattern as the
#                            WireGuard client conf)
#   MYOWN_PIHOLE_LAN_IP      this host's LAN IP, default auto-detected
#   MYOWN_PIHOLE_LOCAL_HOSTS space-separated FQDNs to resolve directly to
#                            MYOWN_PIHOLE_LAN_IP instead of round-tripping
#                            through the Freebox's public IP + hairpin NAT
#                            (same split-horizon reasoning as
#                            gitops/bootstrap/coredns-custom.yaml, this
#                            time for LAN clients instead of in-cluster
#                            ones) — default: the 9 offsystem.fr hostnames
#                            already exposed publicly (coredns-custom.yaml)

set -euo pipefail

CONTAINER_NAME="pihole-myown"
IMAGE_TAG="${MYOWN_PIHOLE_IMAGE_TAG:-2026.07.2}"
WEB_PORT="${MYOWN_PIHOLE_WEB_PORT:-8081}"
DATA_DIR="${MYOWN_PIHOLE_DATA_DIR:-/opt/myown-pihole/etc-pihole}"
TZ_VALUE="${MYOWN_PIHOLE_TZ:-Europe/Paris}"
UPSTREAMS="${MYOWN_PIHOLE_UPSTREAMS:-1.1.1.1;9.9.9.9}"
LOCAL_HOSTS="${MYOWN_PIHOLE_LOCAL_HOSTS:-authentik.offsystem.fr vaultwarden.offsystem.fr nextcloud.offsystem.fr immich.offsystem.fr tuwunel.offsystem.fr jellyfin.offsystem.fr livekit.offsystem.fr livekit-jwt.offsystem.fr status.offsystem.fr}"

step() { echo -e "\n\033[1;34m==> $1\033[0m"; }

step "Vérification des outils requis"
command -v docker >/dev/null || { echo "Docker introuvable (voir manuel-installation.md)."; exit 1; }
sudo docker info >/dev/null 2>&1 || { echo "Docker installé mais injoignable (démon lancé ? sudo requis ?)."; exit 1; }

# Bug réel trouvé en testant pour de vrai : systemd-resolved tient
# 127.0.0.53:53/127.0.0.54:53 (stub listener) par défaut sur Ubuntu — sous
# Linux, un bind en wildcard (0.0.0.0:53, ce que fait Docker en mode
# bridge avec port publié) échoue en EADDRINUSE dès qu'une adresse
# spécifique est déjà bindée sur ce port, même si les adresses ne se
# recouvrent pas littéralement. Confirmé par un bind Python brut hors
# Docker, qui échouait à l'identique — donc pas un artefact Docker.
# Corrigé une fois pour toutes ici plutôt que redécouvert à chaque
# installation : désactive le stub listener et repointe /etc/resolv.conf
# vers le fichier non-stub de systemd-resolved (liste directement les
# résolveurs amont réels, ex. la Freebox) — la résolution DNS de l'hôte
# lui-même continue de fonctionner, CoreDNS (qui lit ce même fichier)
# n'est pas affecté (vérifié en direct : résolution externe et interne
# toujours correctes après ce changement).
if sudo ss -tulnp 2>/dev/null | grep -q 'systemd-resolve.*:53 '; then
  step "systemd-resolved occupe le port 53 — désactivation du stub listener"
  if ! grep -q '^DNSStubListener=no' /etc/systemd/resolved.conf 2>/dev/null; then
    sudo sed -i 's/^\[Resolve\]$/[Resolve]\nDNSStubListener=no/' /etc/systemd/resolved.conf
  fi
  sudo systemctl restart systemd-resolved
  sudo ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
  getent hosts github.com >/dev/null || { echo "Résolution DNS de l'hôte cassée après le correctif — à diagnostiquer avant de continuer."; exit 1; }
  echo "Port 53 libéré, résolution DNS de l'hôte reconfirmée fonctionnelle."
fi

CONTAINER_EXISTED=0
PASSWORD_GENERATED=0
PASSWORD_FILE=""
if sudo docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  CONTAINER_EXISTED=1
  step "Conteneur déjà présent — création ignorée"
  sudo docker ps --filter "name=$CONTAINER_NAME" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
  echo "Pour recréer : sudo docker rm -f $CONTAINER_NAME puis relancer ce script."
else
  step "Préparation du répertoire de données ($DATA_DIR)"
  sudo install -d -m 755 "$DATA_DIR"

  ADMIN_PASSWORD="${MYOWN_PIHOLE_ADMIN_PASSWORD:-}"
  if [ -z "$ADMIN_PASSWORD" ]; then
    ADMIN_PASSWORD="$(openssl rand -base64 24)"
    PASSWORD_GENERATED=1
  fi

  step "Démarrage du conteneur Pi-hole ($IMAGE_TAG)"
  # Réseau bridge + mappings de ports explicites, conformément à la doc
  # officielle actuelle (docs.pi-hole.net/docker/configuration) — pas de
  # `--network host` : Docker ne réécrit pas l'IP source sur un simple
  # port-forward, les vraies IP clientes du LAN restent donc visibles dans
  # les logs Pi-hole sans les complications du mode host (chevauchement
  # potentiel avec les règles iptables de Traefik/klipper sur 80/443).
  # Aucune capacité additionnelle (NET_ADMIN/SYS_TIME) : pas de DHCP Pi-hole
  # ici (la Freebox reste le serveur DHCP du foyer), principe du moindre
  # privilège (architecture.md §8).
  sudo docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -p 53:53/tcp -p 53:53/udp \
    -p "${WEB_PORT}:${WEB_PORT}/tcp" \
    -e TZ="$TZ_VALUE" \
    -e FTLCONF_dns_listeningMode=ALL \
    -e FTLCONF_dns_upstreams="$UPSTREAMS" \
    -e FTLCONF_webserver_port="$WEB_PORT" \
    -e FTLCONF_webserver_api_password="$ADMIN_PASSWORD" \
    -v "${DATA_DIR}:/etc/pihole" \
    "pihole/pihole:${IMAGE_TAG}"

  if [ "$PASSWORD_GENERATED" -eq 1 ]; then
    PASSWORD_FILE="$HOME/myown-pihole-admin-password.txt"
    echo "$ADMIN_PASSWORD" > "$PASSWORD_FILE"
    chmod 600 "$PASSWORD_FILE"
  fi

  step "Attente que FTL soit prêt"
  for _ in $(seq 1 30); do
    sudo docker exec "$CONTAINER_NAME" pihole-FTL --config dns.hosts >/dev/null 2>&1 && break
    sleep 1
  done
fi

step "Overrides DNS locaux pour *.offsystem.fr (split-horizon LAN)"
LAN_IP="${MYOWN_PIHOLE_LAN_IP:-$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i=="src") print $(i+1)}')}"
[ -n "$LAN_IP" ] || { echo "Impossible de détecter l'IP LAN — définissez MYOWN_PIHOLE_LAN_IP." >&2; exit 1; }
sudo docker exec "$CONTAINER_NAME" pihole-FTL --config dns.hosts "[ \"${LAN_IP} ${LOCAL_HOSTS}\" ]" >/dev/null
echo "Configuré : ${LAN_IP} -> ${LOCAL_HOSTS}"

step "Terminé"
echo "Interface admin : http://<IP LAN de cet hôte>:${WEB_PORT}/admin"
if [ "$PASSWORD_GENERATED" -eq 1 ]; then
  echo "Mot de passe admin généré, écrit hors dépôt : ${PASSWORD_FILE}"
  echo "  - Jamais committé — à transférer dans le Vaultwarden admin, puis supprimer ce fichier."
fi
echo ""
echo "Vérification : sudo docker logs -f $CONTAINER_NAME"
echo "Rappel garde-fou non négociable (roadmap.md) : configurer un DNS secondaire de repli"
echo "(1.1.1.1 / 9.9.9.9) au niveau du DHCP du routeur avant toute bascule réseau complète —"
echo "une panne de ce conteneur ne doit jamais couper l'accès internet de toute la maison."
