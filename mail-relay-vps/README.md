# Relais mail VPS OVH — Postfix + tunnel + DNS

Chantier roadmap Phase 4 : le VPS façade OVH (`notes-techniques.md`, section
"VPS façade OVH") reçoit le courrier entrant sur le port 25 public et le
relaie vers Mailu à la maison via le tunnel WireGuard dédié
(`wireguard-mail-relay/`) ; en sortant, Mailu relaie via le même tunnel vers
Postfix sur le VPS, qui délivre sur Internet. Postfix sur le VPS reste
volontairement "bête" — aucune signature DKIM côté VPS, c'est Rspamd côté
Mailu qui signe déjà.

## Joignabilité Mailu:25 depuis le tunnel — port-forward, pas hostPort

`scripts/mailu-portforward-setup.sh` installe un service systemd hôte qui
maintient un `kubectl port-forward` permanent entre l'interface du tunnel
(`10.100.1.2`, côté maison) et `svc/mailu-front:25` dans le cluster de dev.

**Décision explicite (2026-08-23), pas la solution "la plus propre" en
théorie** : la vraie alternative — réactiver `front.hostPort` côté Mailu
(désactivé exprès à cause d'un deadlock de rollout sur ce cluster
mono-nœud, contournable comme pour LiveKit avec
`deploymentStrategy: Recreate`) — demanderait *en plus* un nouveau mapping
de port k3d, donc une troisième recréation du cluster de dev (déjà fait
deux fois pour LiveKit, avec la danse sauvegarde Restic + `kubectl cp`
préalable). Ce cluster de dev sera de toute façon abandonné à la migration
de Mailu vers le mini PC (k3s réel bare-metal, `hostPort` fonctionne
nativement, sans couche de traduction de ports) — recréer le cluster de dev
maintenant pour une exposition qui sera de toute façon reconstruite
proprement plus tard n'a pas été jugé rentable. Le port-forward est le
palliatif volontairement jetable en attendant cette migration : fragile par
nature (redémarre si `kubectl`/réseau a un accroc — `Restart=on-failure`
mitigue ça), mais zéro changement cluster et réversible en une commande.

**À refaire lors de la migration Mailu → mini PC** : ce port-forward
disparaît, remplacé par un vrai `hostPort`/`NodePort` k3s natif — cohérent
avec le sort déjà connu du tunnel WireGuard lui-même
(`wireguard-mail-relay/README.md`, section migration).

## Contenu (au fur et à mesure du chantier)

- `scripts/mailu-portforward-setup.sh` — port-forward hôte (ci-dessus).
- Config Postfix VPS — à venir (relay_domains, transport_maps vers
  `10.100.1.2:25`, mynetworks incluant `10.100.1.0/24`).
- Enregistrements DNS (A/MX/SPF/DKIM/DMARC) — à venir, voir le plan de ce
  chantier pour le détail exact.
