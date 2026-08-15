# WireGuard — accès admin distant

VPN d'accès distant pour l'administration (`architecture.md` §6/§11) : ArgoCD,
`kubectl`, SSH ne doivent jamais être exposés directement sur internet — tout
passe par ce tunnel. Volontairement **hors GitOps** : un service systemd sur
l'hôte, pas un `Deployment` Kubernetes.

**Pourquoi hors cluster** : WireGuard est un protocole UDP à point d'ancrage
unique — aucun bénéfice du modèle réplicas/LoadBalancer de k8s ici, seulement
de la friction (pod privilégié `NET_ADMIN`/`SYS_MODULE`, stratégie `Recreate`
imposée). Plus important : ce VPN sert justement à accéder au cluster pour
intervenir dessus. Le placer *dans* le cluster qu'il est censé dépanner crée
une dépendance circulaire — si le cluster est en panne, le VPN censé permettre
d'y remédier tombe avec lui.

## Contenu

- `wg0.conf.sops.yaml` — config serveur chiffrée (clé privée serveur, pairs
  autorisés). Générée et mise à jour par `scripts/wireguard-setup.sh`, jamais
  éditée à la main.

Les configs **clientes** (clé privée de chaque pair) ne sont jamais commitées,
même chiffrées — écrites localement par le script hors du dépôt, à transférer
directement à l'appareil de l'admin (cohérent avec le modèle déjà retenu pour
les autres secrets générés à l'installation, `installation-utilisateur.md`).

## Utilisation

Voir `scripts/wireguard-setup.sh` — un seul script gère à la fois
l'amorçage initial (première exécution) et l'ajout d'un nouveau pair
(exécutions suivantes), cf. l'en-tête du script pour les variables d'env.

Nécessite `sudo` de façon interactive (installation du paquet, écriture dans
`/etc/wireguard/`, activation du service) — à lancer par l'admin lui-même
dans son propre terminal, jamais par un outil automatisé.
