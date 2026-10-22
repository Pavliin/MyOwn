# Manuel admin

Actions d'administration courantes, service par service. Pour l'installation
initiale, voir [`manuel-installation.md`](manuel-installation.md) ; pour le
détail technique et l'historique des bugs réels rencontrés, voir
[`notes-techniques.md`](notes-techniques.md) — ce document-ci reste
volontairement au niveau des gestes du quotidien.

**Convention** : tous les mots de passe cités ci-dessous sont **stables**
(fixés une fois pour toutes, pas régénérés à chaque déploiement) et se
récupèrent avec :

```bash
sops -d gitops/secrets/<service>/<service>.sops.yaml
```

ArgoCD, Grafana et l'admin Nextcloud/Uptime Kuma ne sont **jamais** exposés
publiquement, uniquement en LAN ou via le VPN d'administration (WireGuard) —
choix délibéré, pas un oubli.

## Accès aux outils réservés au LAN

ArgoCD, Grafana et l'admin Uptime Kuma répondent sur des noms
`myown-*.local:8090` que rien ne résout automatiquement — ni la Freebox, ni
Pi-hole (qui ne connaît que les `*.offsystem.fr`). Sur la machine d'admin,
ajouter à `/etc/hosts` :

```text
<IP LAN du mini PC> myown-argocd.local myown-grafana.local myown-uptime.local
```

Pas `127.0.0.1` : c'est la valeur du cluster de dev k3d
(`manuel-installation.md` §10), qui tourne sur la machine elle-même. Via le
VPN, remplacer l'IP LAN par l'adresse du mini PC dans le tunnel
(`10.100.0.1`). Retirer toute ligne qui forcerait un `*.offsystem.fr` vers
`127.0.0.1` : elle redirige silencieusement vers le cluster de dev au lieu
du vrai (piège déjà rencontré, voir `notes-techniques.md`).

## Enrôlement — ajouter un utilisateur

1. **Authentik** (<https://authentik.offsystem.fr/if/admin/>) → Répertoire →
   Utilisateurs → Créer. Si un accès Mailu est prévu, saisir directement
   l'email définitif en `@offsystem.fr` — le changer plus tard demande une
   manipulation admin en plus (voir Mailu ci-dessous). **Username : un seul
   mot, sans espace** (ex. `prenomnom`, pas `Prénom Nom`) — sert tel quel
   d'identifiant Tuwunel/LiveKit à la première connexion SSO, voir la section
   Tuwunel ci-dessous si ce point est raté.
2. Générer un **lien de récupération** pour ce compte (jamais choisir le mot
   de passe à sa place) et le transmettre à la personne.
3. Elle définit son propre mot de passe via ce lien, puis se connecte en SSO
   à chaque service — le compte s'y crée automatiquement à la première
   connexion.
4. **Après sa première connexion à Nextcloud**, l'ajouter au groupe
   `famille`, sans quoi le dossier partagé **Mediatheque** (et donc l'ajout
   de contenu à Jellyfin) lui reste invisible. Le compte SSO a un
   identifiant opaque, à retrouver d'abord (voir la section Nextcloud) :

   ```bash
   occ user:list
   occ group:adduser famille <identifiant>
   ```

5. Vérifier ces cas particuliers après le premier login :

   | Service | Point d'attention |
   |---|---|
   | Mailu | Refuse la connexion tant que l'email Authentik n'est pas en `@offsystem.fr` (erreur avec `domain=...`). |
   | Tuwunel | ID Matrix illisible (`@ai2f-…`) si le username Authentik contient une espace ou un accent — voir la section Tuwunel. |
   | Jellyfin, Mailu | Le compte SSO créé n'a **pas** les droits admin — normal pour un utilisateur ; pour le vôtre, voir les sections correspondantes. |

   Immich et Tuwunel donnent les droits admin au **tout premier** compte
   créé : c'est déjà fait (le vôtre), rien à vérifier pour les suivants.

6. Envoyer le [fichier de favoris](https://aide.offsystem.fr/downloads/myown-favoris.html){: download="myown-favoris.html" }
   et le lien du [manuel utilisateur](manuel-utilisateur.md) — ou simplement
   le lien de [l'accueil](https://aide.offsystem.fr), qui pointe déjà vers
   les deux.

## Authentik — identité (SSO)

- **Admin** : <https://authentik.offsystem.fr/if/admin/>
- **Compte de secours** (bootstrap, à utiliser si plus aucun admin ne peut se
  connecter) : utilisateur `akadmin`, identifiants dans
  `gitops/secrets/authentik/authentik.sops.yaml`
  (`AUTHENTIK_BOOTSTRAP_EMAIL` / `AUTHENTIK_BOOTSTRAP_PASSWORD`).
- **Actions courantes** : créer/désactiver un utilisateur (Répertoire →
  Utilisateurs), générer un lien de récupération, modifier l'email d'un
  compte (nécessaire avant sa première connexion à Mailu).
- Les intégrations SSO (Vaultwarden, Nextcloud, Immich, Tuwunel, Jellyfin,
  Mailu) sont définies par blueprint dans
  `gitops/secrets/authentik-blueprints/` — jamais à la main dans l'UI.
- La récupération en libre-service (identification + TOTP) exige que
  l'utilisateur ait déjà un authentificateur configuré — sans quoi le flow
  refuse délibérément (`not_configured_action: deny`, pas de contournement
  silencieux). Un lien admin-généré reste le seul recours pour un compte
  sans TOTP (voir `notes-techniques.md`).

## ArgoCD — déploiement GitOps

- **URL** : `http://myown-argocd.local:8090` (LAN/VPN uniquement)
- **Mot de passe** : `gitops/secrets/argocd/argocd.sops.yaml` →
  `ARGOCD_ADMIN_PASSWORD`
- La page d'accueil liste toutes les `Application` — vert
  (`Synced`/`Healthy`) = tout va bien. `root` (l'app-of-apps) reste
  volontairement en **synchronisation manuelle**, précédée d'une annonce
  dans le salon `#etat-du-systeme` pour les services sensibles à la famille
  (`scripts/tuwunel-announce.py`).
- **Déployer une nouvelle release** sur le mini PC (une fois la release
  coupée et sa PR fusionnée, voir `CLAUDE.md`, section Releases) : pointer
  `root` sur le nouveau tag puis le synchroniser — toutes les `Application`
  enfants, secrets compris, suivent automatiquement :

  ```bash
  kubectl patch application root -n argocd --type merge \
    -p '{"spec":{"source":{"targetRevision":"vX.Y.Z"}}}'
  argocd app sync root
  ```

- Ne jamais réactiver `selfHeal` sur une `Application` après un test en
  direct sans que la correction testée soit dans le tag suivi par `root` :
  ArgoCD réécraserait silencieusement le correctif en affichant toujours
  `Synced`/`Healthy`.

## Grafana — métriques du cluster

- **URL** : `http://myown-grafana.local:8090` (LAN/VPN uniquement)
- **Mot de passe** : `gitops/secrets/monitoring/monitoring.sops.yaml` →
  `admin-password`
- ~29 tableaux de bord préconfigurés (menu **Dashboards**), rien à
  configurer.

## Vaultwarden — mots de passe

- **Panneau admin** : <https://vaultwarden.offsystem.fr/admin>
- **Jeton** : `gitops/secrets/vaultwarden/vaultwarden.sops.yaml` →
  `ADMIN_TOKEN`
- **Actions courantes** : inviter/désactiver un compte, diagnostics serveur.
  Impossible de récupérer le mot de passe maître d'un utilisateur ni de
  déverrouiller son coffre (chiffrement zero-knowledge, volontaire).

## Nextcloud — fichiers, agenda, contacts

- **Compte admin local** : `gitops/secrets/nextcloud/nextcloud.sops.yaml` →
  `NEXTCLOUD_USERNAME` / `NEXTCLOUD_PASSWORD` (à garder en secours, en plus
  du SSO).
- **Identifiant interne d'un compte SSO** : les comptes provisionnés par
  `user_oidc` ont un identifiant opaque (pas l'email) — utile à connaître
  pour aider un utilisateur à relier son carnet d'adresses dans Mailu (voir
  la section Mailu du manuel utilisateur) :

  ```bash
  occ user:list
  ```

- **Actions via `occ`** (`kubectl exec` dans le pod Nextcloud) :

  ```bash
  # Gestion du dossier familial partagé
  occ groupfolders:create Mediatheque
  occ groupfolders:group <id> famille

  # Domaines de confiance : vérifier l'index déjà utilisé avant d'écrire,
  # occ écrase l'entrée existante à cet index plutôt que d'en ajouter une.
  occ config:system:get trusted_domains
  occ config:system:set trusted_domains <index> --value=<domaine>
  ```

- Toute commande `occ` lancée via `kubectl exec` s'exécute en `root`, pas en
  `www-data` — penser à `chown -R www-data:www-data` après toute action qui
  touche des fichiers sur le volume.

## Immich — photos et vidéos

- Pas de compte admin local séparé : l'admin est le tout premier compte créé
  via l'assistant de première visite (déjà fait).
- Réglages admin (gestion des utilisateurs, tâches de reconnaissance
  faciale/recherche sémantique) directement dans l'interface, menu
  Administration.

## Tuwunel — messagerie

- L'admin est le tout premier compte enregistré sur le serveur ; il rejoint
  automatiquement un salon d'administration où des commandes serveur
  peuvent être envoyées comme des messages (voir la documentation Tuwunel
  pour la liste).
- **Identifiant Matrix illisible après la première connexion SSO**
  (`@ai2f-xt4jrh-vxtx:offsystem.fr` au lieu de `@prenomnom:offsystem.fr`) :
  le username Authentik contenait un espace (ou un caractère non permis dans
  un ID Matrix — accent, ponctuation…). Tuwunel rejette silencieusement ce
  claim et retombe sur un identifiant généré à partir d'un hash, sans erreur
  visible pour l'utilisateur. Correction : éditer le username Authentik en
  un seul mot, puis faire refaire la connexion SSO — ça crée un **nouveau**
  compte Matrix propre (pas de renommage possible du côté Matrix), l'ancien
  restant orphelin à supprimer à la main si besoin. À vérifier avant la
  première connexion de chaque nouvel utilisateur, pas après (voir
  `notes-techniques.md` pour le détail du mécanisme côté code).
- **Salon `#etat-du-systeme` rejoint automatiquement** (`auto_join_rooms`
  dans `tuwunel.toml`, depuis 2026-09-16) : rien à faire à l'enrôlement, la
  première connexion SSO y ajoute le compte tout seul. Ne s'applique
  qu'aux comptes créés **après** l'activation de ce réglage — un compte déjà
  existant avant cette date doit encore rejoindre via le lien `matrix.to`
  donné dans `manuel-utilisateur.md`, ou être invité à la main
  (`POST /_matrix/client/v3/rooms/{roomId}/invite` avec le token de
  `alertbot`).
- Sauvegarde/restauration : voir `notes-techniques.md` (même mécanisme
  Restic que Vaultwarden, base RocksDB embarquée).

## Jellyfin — films et musique

- Le compte SSO créé à la première connexion n'a pas les droits admin par
  défaut — pour les donner au vôtre : voir `manuel-installation.md`,
  section 13.
- **Compte admin local de secours** : utilisateur `admin`, mot de passe dans
  `gitops/secrets/jellyfin/jellyfin.sops.yaml` → `ADMIN_PASSWORD`.
- Ajout de contenu : toujours via le dossier **Mediatheque** de Nextcloud,
  jamais d'upload direct dans Jellyfin.

## Mailu — courrier électronique

- **Panneau admin** : <https://mailu.offsystem.fr/admin>, avec votre
  propre compte SSO — à condition qu'il ait été promu admin. Tout
  `mailu.offsystem.fr` passe par Authentik : le compte bootstrap ne peut
  pas s'y connecter par cette adresse. Pour promouvoir un compte (après sa
  première connexion SSO, qui crée sa boîte) :

  ```bash
  export MAILU_API_TOKEN=$(sops -d gitops/secrets/mailu/mailu.sops.yaml | yq '.stringData.API_TOKEN')
  python3 scripts/mailu-promote-admin.py <email>@offsystem.fr
  ```

- **Compte de secours** (bootstrap) : `admin@offsystem.fr`, mot de passe
  dans `gitops/secrets/mailu/mailu.sops.yaml` →
  `initial-account-password`. Joignable uniquement en contournant
  l'Ingress public (`kubectl port-forward` vers `mailu-admin`), pas via
  l'adresse ci-dessus.
- **Actions courantes** : gestion des domaines/alias, consultation des
  files d'attente et du filtrage anti-spam.
- **DKIM** : la clé privée vit sur le volume persistant de Mailu
  (`/dkim/offsystem.fr.dkim.key`), **pas** dans un secret SOPS — un
  enregistrement DNS publié ne garantit pas qu'elle existe encore. En cas
  de doute (mails classés en spam, `dkim=none` dans les en-têtes reçus) :
  `python3 scripts/mailu-dkim-setup.py offsystem.fr` (même `MAILU_API_TOKEN`)
  la régénère si absente et la relit depuis le disque — détail dans
  `manuel-installation.md` §19.
- Une adresse `@offsystem.fr` est créée automatiquement pour chaque compte
  Authentik dont l'email est déjà sur ce domaine — pas de création manuelle
  nécessaire une fois l'email corrigé côté Authentik.
- **Carnet d'adresses (rcmcarddav)** : déjà activé par défaut dans l'image
  webmail, aucun réglage admin global — chaque utilisateur ajoute sa propre
  source CardDAV en libre-service (voir le manuel utilisateur). Pas de
  preset admin possible : les identifiants Nextcloud provisionnés par
  `user_oidc` sont opaques par personne, pas substituables par un preset
  commun.
- **"Le webmail n'affiche plus le contenu des mails" après un
  rafraîchissement de session Authentik** : gotcha connu (2026-09-17,
  `notes-techniques.md`) — la session IMAP interne de Roundcube peut se
  désynchroniser. Un simple rechargement de page ne suffit pas : demander
  une **déconnexion explicite du webmail** (menu utilisateur → Déconnexion)
  puis une reconnexion.

## Uptime Kuma — supervision

- **Admin** (LAN/VPN) : `http://myown-uptime.local:8090` — identifiants
  dans `gitops/secrets/uptime-kuma/uptime-kuma.sops.yaml`
  (`UPTIME_KUMA_USERNAME` / `UPTIME_KUMA_PASSWORD`).
- **Page publique** (lecture seule, pour la famille) :
  <https://status.offsystem.fr>
- Ajout d'un moniteur ou modification de la page de statut : configurés via
  `scripts/uptime-kuma-setup.py` plutôt qu'à la main, pour rester
  reproductible après une recréation du cluster.

## Pi-hole — DNS filtrant

- **Admin** (LAN/VPN) : `http://<IP LAN du mini PC>:8081/admin` — pas de
  panneau public, outil admin-only comme Grafana/ArgoCD.
- **Mot de passe** : authentification par mot de passe seul, pas de
  username. Généré à l'installation, transféré dans le Vaultwarden admin
  (voir `manuel-installation.md` §20) — si perdu, réinitialiser avec
  `sudo docker exec pihole-myown pihole setpassword`.
- **Actions courantes** :
  - Liste blanche d'un domaine faussement bloqué : onglet **Domains** →
    ajouter en `Allow` (exact ou regex).
  - Journal des requêtes en direct : onglet **Query Log**, filtrable par
    appareil (IP) — utile pour vérifier qu'un appareil du foyer utilise
    bien Pi-hole et voir ce qui lui est réellement bloqué.
  - Si un utilisateur signale "le blocage ne fait pas grand-chose" alors
    que le DNS est correctement configuré côté appareil : vérifier le
    "DNS sécurisé" (DoH) du navigateur (Edge/Chrome), qui contourne le
    DNS système par défaut sur beaucoup d'installations Windows récentes
    — pas un problème Pi-hole.
- Volontairement **hors GitOps et hors k3s** (conteneur Docker sur l'hôte,
  `scripts/pihole-setup.sh`) — voir `architecture.md` §6. Pas de
  sauvegarde Restic dédiée (décision explicite, voir `notes-techniques.md`).
- **Limitation connue** : le DNS IPv6 annoncé par la Freebox (RA) n'est
  pas redirigé — les appareils IPv6 natifs peuvent échapper au filtrage
  pour les domaines avec enregistrement AAAA.

## WireGuard — VPN d'administration

- Service systemd sur le mini PC (`wg-quick@wg0`), hors GitOps et hors k3s
  pour rester disponible même si le cluster est en panne (voir
  `wireguard/README.md`).
- **Ajouter un appareil** (sur le mini PC, `sudo` interactif nécessaire) :

  ```bash
  MYOWN_WG_PEER_NAME=<nom-appareil> scripts/wireguard-setup.sh
  ```

  Le nom est obligatoire dès que le serveur existe (pas de valeur par
  défaut, pour ne jamais écraser un pair existant). Le script met à jour
  `wireguard/wg0.conf.sops.yaml` (à committer) et écrit la config cliente
  hors dépôt, dans `~/myown-wireguard-<nom>.conf` — à importer dans l'appli
  WireGuard, ou à afficher en QR code avec `qrencode -t ansiutf8 <` ce
  fichier (scanner depuis l'appli WireGuard elle-même, pas depuis
  l'appareil photo du téléphone).
- **Limitation actuelle** : seul l'usage en LAN a été validé ; l'accès
  depuis l'extérieur demande encore une redirection de port sur la
  Freebox.

## Watchdog — redémarrage automatique de k3s

- Timer systemd sur le mini PC (`myown-watchdog.timer`), hors GitOps : si
  l'API k3s ne répond plus pendant 3 minutes d'affilée, il redémarre
  `k3s.service` tout seul, au maximum 3 fois par heure.
- **Messages `[MyOwn Watchdog]` dans `#etat-du-systeme`** : ils arrivent
  avec du retard (Tuwunel tourne dans le cluster surveillé, ils partent au
  retour du cluster).
  - *« redémarrage automatique de k3s tenté »* : rien à faire si tout est
    revenu au vert, sinon regarder pourquoi :
    `journalctl -t myown-watchdog` et `journalctl -u k3s`.
  - *« le watchdog abandonne »* : le cluster ne revient pas malgré 3
    redémarrages — intervention manuelle nécessaire (SSH ou VPN).

## Sauvegardes (Restic)

Chaque service avec état a son propre `CronJob` de sauvegarde et son propre
`RESTIC_PASSWORD` dans son secret (`gitops/manifests/<service>-backup/`) —
seule exception, Pi-hole (hors k3s, contenu jugé quasi entièrement
reproductible, voir `notes-techniques.md`). Procédure de sauvegarde/
restauration manuelle détaillée, service par service, dans
`notes-techniques.md` — pas dupliquée ici pour éviter la dérive entre les
deux documents.
