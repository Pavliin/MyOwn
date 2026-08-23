# WireGuard — tunnel relais mail VPS ↔ domicile

Tunnel dédié entre le VPS façade OVH (`notes-techniques.md`, section VPS façade)
et le service qui héberge réellement les boîtes mail à la maison (Mailu —
aujourd'hui le cluster de dev, le mini PC une fois la migration faite). Sert
uniquement à relayer le trafic SMTP entre Postfix (VPS) et Mailu, rien d'autre.

## Pourquoi une instance séparée du VPN admin (`wireguard/`)

**Topologie inversée** : ici le **serveur WireGuard tourne sur le VPS**, pas à
la maison — le VPS a une IP publique stable, la maison est derrière un NAT
Freebox sans redirection de port pour cet usage. La maison se connecte donc en
sortant (UDP sortant uniquement, aucune redirection de port supplémentaire à
poser sur la Freebox). C'est l'inverse exact du VPN admin (`wireguard/`),
serveur à la maison, clients qui se connectent depuis l'extérieur.

**Tunnel logiquement séparé, même si l'hôte "maison" est aujourd'hui la même
machine physique que pour le VPN admin** : le VPS est un environnement moins
sûr par nature (exposé publiquement sur le port 25/tcp) — s'il est un jour
compromis, il ne doit obtenir un accès réseau qu'au port SMTP de Mailu, jamais
à `kubectl`/ArgoCD/SSH admin. D'où une identité de clés et un sous-réseau
(`10.100.1.0/24`, port UDP `51821`) entièrement distincts du VPN admin
(`10.100.0.0/24`, port UDP `51820`).

## Contenu

- `wg-mail0.conf.sops.yaml` — config **serveur** chiffrée (clé privée serveur,
  pairs autorisés). Générée et mise à jour par
  `scripts/wireguard-mail-relay-setup.sh`, jamais éditée à la main.

La config **cliente** (clé privée du pair "maison") n'est jamais commitée,
même chiffrée — même principe que pour le VPN admin
(`wireguard/README.md`) : écrite localement par le script, appliquée
directement sur la machine "maison" (dev aujourd'hui, mini PC après
migration).

## Utilisation

Voir `scripts/wireguard-mail-relay-setup.sh` — pensé pour être lancé **depuis
la machine qui a ce dépôt git + la clé `age`** (dev aujourd'hui), pas
directement sur le VPS : le script applique la partie serveur sur le VPS via
SSH (le compte `ubuntu` y a `sudo` sans mot de passe, cf.
`notes-techniques.md`), puis écrit la config cliente localement pour
application sur la machine "maison" — qui, elle, a besoin d'un `sudo`
interactif (pas disponible pour Claude Code dans cet environnement), donc
cette dernière étape reste à lancer par l'utilisateur lui-même dans son
propre terminal.

## Migration prévue vers le mini PC

Une fois Mailu migré du cluster de dev vers le mini PC (chantier séparé), ce
tunnel devra être reconstruit avec le mini PC comme pair "maison" — même
schéma que la migration déjà faite pour le VPN admin
(`notes-techniques.md`, "WireGuard reinstalled on the mini PC itself,
dev-machine instance retired"). Le côté serveur (VPS) n'a pas besoin de
changer, seul le pair "maison" est remplacé.
