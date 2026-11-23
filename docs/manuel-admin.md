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

ArgoCD, Grafana, Ollama et l'admin Uptime Kuma ne sont **jamais** accessibles
depuis internet : uniquement depuis le réseau de la maison ou via le VPN
d'administration (WireGuard) — choix délibéré, pas un oubli. (Les pages
d'administration de Nextcloud, Immich, Mailu… font partie de leur application,
accessible publiquement mais derrière la connexion SSO.)

## Accès aux outils réservés au LAN

Chaque outil a son nom dans le domaine, résolu à la maison par Pi-hole —
plus rien à ajouter dans `/etc/hosts` :

| Outil | Adresse |
|---|---|
| ArgoCD | `https://argocd.offsystem.fr` |
| Grafana | `https://grafana.offsystem.fr` |
| Admin Uptime Kuma | `https://uptime.offsystem.fr` |
| Ollama (API) | `https://ollama.offsystem.fr` |

Depuis internet, ces noms existent (le DNS public couvre tout le domaine)
mais Traefik répond **403** : seules les adresses du réseau local, du VPN
d'administration et des pods sont acceptées (valeur `adminSourceRanges` de
l'installation). **Hors de la maison, pas encore d'accès par ces noms** : la
configuration client WireGuard ne fait passer que le sous-réseau du tunnel,
sans DNS — ces noms se résolvent donc vers l'adresse publique et reçoivent
**403**. Il faudra faire passer l'adresse du mini PC dans le tunnel et utiliser
Pi-hole comme DNS (`scripts/wireguard-setup.sh`, à faire). En attendant, à
distance : `kubectl port-forward` via SSH dans le tunnel.

La page d'état publique, `https://status.offsystem.fr`, ne montre que l'état
des services — l'administration d'Uptime Kuma n'y est pas accessible.

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
   | Tous | Le compte SSO créé n'a **pas** les droits admin — normal pour un utilisateur. Un admin se nomme par le groupe `myown-admins` (section suivante). |

   Les places d'admin « premier arrivé » d'Immich et de Tuwunel sont prises
   à l'installation par des comptes techniques : rien à surveiller pour les
   comptes suivants.

6. Envoyer le [fichier de favoris](https://aide.offsystem.fr/downloads/myown-favoris.html){: download="myown-favoris.html" }
   et le lien du [manuel utilisateur](manuel-utilisateur.md) — ou simplement
   le lien de [l'accueil](https://aide.offsystem.fr), qui pointe déjà vers
   les deux.

## Comptes et droits d'admin (`myown-admin`)

Être admin de MyOwn, c'est être membre du groupe Authentik **`myown-admins`**
(super-utilisateur Authentik, admin Jellyfin à la connexion suivante). Pour
Nextcloud, Immich, Tuwunel et Mailu, le groupe ne suffit pas : la commande
`sync` y reporte les droits. Conception : `installation-utilisateur.md`,
« Modèle de gestion des comptes admin ».

Toutes les commandes se lancent **sur le serveur**, dans le dépôt cloné :

```bash
python3 scripts/myown-admin.py <commande>
```

| Besoin | Commande |
|---|---|
| Voir qui manque ou a de trop des droits d'admin | `sync` (rien n'est changé) |
| Les corriger | `sync --apply` |
| Remettre le coffre à jour (nouveau service, restauration, après un retrait) | `coffre` |
| Recréer son compte ou un lien de mot de passe, reprendre les comptes techniques | `init` (rejouable) |

**Ajouter un co-admin** : l'ajouter au groupe `myown-admins` dans Authentik
(Répertoire → Groupes), lui demander une connexion à chaque service, puis
`sync --apply`. **En retirer un** : le sortir du groupe, puis `sync --apply`.
Un membre qui ne s'est jamais connecté à un service y est signalé « pas
encore de compte » : relancer `sync --apply` après sa connexion.

**Le coffre** est l'organisation Vaultwarden dont le nom contient « MyOwn »,
avec deux collections, **Administration** (comptes d'admin, mot de passe de
la sauvegarde des secrets) et **Infrastructure** (tout le reste). À créer
une fois dans Vaultwarden (Nouvelle organisation, puis les deux
collections). `coffre` demande la **clé d'API personnelle** (Paramètres →
Sécurité → Clés → Clé d'API : `client_id` en `user.…`, pas celle de
l'organisation) puis le mot de passe maître, sans jamais les afficher ni les
écrire. Les entrées viennent du cluster, qui reste la référence : une entrée
modifiée à la main dans le coffre est réécrite à la relance suivante.

**Remettre les clés** à un nouveau propriétaire, en trois temps :

1. Préparateur : `transfert ajout --email <adresse>`. Le nouveau propriétaire
   ouvre le lien affiché, se connecte une fois à chaque service, crée son
   coffre ; le préparateur l'invite dans l'organisation (rôle
   **Propriétaire**) puis le **confirme** (Membres → ⋮ → Confirmer — sans
   serveur mail, l'invitation est acceptée d'office et seule la
   confirmation lui ouvre l'organisation).
2. Nouveau propriétaire, sur le serveur : `transfert verifier` (sa propre
   clé d'API et son mot de passe maître). Rien n'est retiré tant que cette
   vérification n'a pas réussi.
3. Préparateur : `transfert retrait --preparateur <son nom d'utilisateur>`.
   Son compte est désactivé (jamais supprimé), ses droits retirés, et tous
   les identifiants d'admin régénérés. Puis, comme la commande le rappelle :
   le nouveau propriétaire le retire de l'organisation et relance `coffre` ;
   retirer ses clés SSH et pairs WireGuard ; remplacer les copies hors
   machine de la sauvegarde des secrets.

Une commande interrompue se relance telle quelle : elle reprend où elle
s'était arrêtée.

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
  `gitops/manifests/authentik-blueprints/` (en clair, rendus avec le domaine)
  — jamais à la main dans l'UI. Leurs secrets OIDC sont dans le Secret
  `authentik/authentik-sso-clients`, dérivés de ceux des services par
  `scripts/lib/cluster-secrets.py`.
- La récupération en libre-service (identification + TOTP) exige que
  l'utilisateur ait déjà un authentificateur configuré — sans quoi le flow
  refuse délibérément (`not_configured_action: deny`, pas de contournement
  silencieux). Un lien admin-généré reste le seul recours pour un compte
  sans TOTP (voir `notes-techniques.md`).

## ArgoCD — déploiement GitOps

- **URL** : `https://argocd.offsystem.fr` (LAN/VPN uniquement)
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

- **URL** : `https://grafana.offsystem.fr` (LAN/VPN uniquement)
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

- Le premier compte (admin d'office) est un **compte technique**,
  `immich-admin@<domaine>`, créé à l'installation (mot de passe dans le
  coffre). Les admins de MyOwn reçoivent les droits par `myown-admin sync`.
  Installations antérieures à l'étape 5 : ce premier compte est le vôtre.
- Réglages admin (gestion des utilisateurs, tâches de reconnaissance
  faciale/recherche sémantique) directement dans l'interface, menu
  Administration.

## Tuwunel — messagerie

- Le tout premier compte enregistré est admin du serveur : c'est le bot
  (`@alertbot`), inscrit à l'installation. Être admin, c'est être membre du
  salon d'administration (`#admins`), où des commandes serveur s'envoient
  comme des messages (voir la documentation Tuwunel). `myown-admin sync`
  y fait entrer les membres de `myown-admins` et en fait sortir les autres.
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
  pas s'y connecter par cette adresse. Les membres de `myown-admins` sont
  promus par `myown-admin sync --apply` (après leur première connexion SSO,
  qui crée leur boîte). Pour un autre compte, à la main :

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

- **Admin** (LAN/VPN) : `https://uptime.offsystem.fr` — identifiants
  dans `gitops/secrets/uptime-kuma/uptime-kuma.sops.yaml`
  (`UPTIME_KUMA_USERNAME` / `UPTIME_KUMA_PASSWORD`).
- **Page publique** (lecture seule, pour la famille) :
  <https://status.offsystem.fr>
- Ajout d'un moniteur ou modification de la page de statut : configurés via
  `scripts/uptime-kuma-setup.py` plutôt qu'à la main, pour rester
  reproductible après une recréation du cluster.

## Domaine — certificats et DynDNS

Les identifiants du fournisseur DNS vivent dans deux Secrets, créés par l'installeur et jamais commités (`manuel-installation.md` §16) : `kube-system/dns-provider-credentials` (Traefik, certificats Let's Encrypt) et `dyndns/dyndns-config` (ddns-updater).

- **État du DynDNS** : `kubectl logs -n dyndns deploy/dyndns`. Rien n'est journalisé tant que les enregistrements sont à jour ; une mise à jour ou une erreur du fournisseur apparaît en clair. Ne jamais passer `LOG_LEVEL=debug` : ce niveau affiche la configuration, jeton compris.
- **Rotation du jeton** : préparer les mêmes fichiers qu'à l'installation (`dns.env`, `ddns.json`), puis remplacer les deux Secrets et redémarrer leurs consommateurs. La configuration DynDNS se régénère avec le domaine : le plus simple est de supprimer `dyndns-config` et de relancer l'installeur avec `MYOWN_DDNS_CREDENTIALS_FILE=ddns.json`, qui ne recrée que ce qui manque (il garde le niveau C en place).

```bash
kubectl create secret generic dns-provider-credentials -n kube-system --from-env-file=dns.env \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl rollout restart deployment traefik -n kube-system
kubectl delete secret dyndns-config -n dyndns
MYOWN_DDNS_CREDENTIALS_FILE=ddns.json scripts/install.sh
kubectl rollout restart deployment dyndns -n dyndns
```

Supprimer les deux fichiers ensuite.

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

## Sauvegarde des secrets

Les Secrets des services sont générés dans le cluster (`scripts/lib/cluster-secrets.py`) et n'existent nulle part ailleurs. Une sauvegarde quotidienne (02:30, Application `secrets-backup`, namespace `myown-backup`) les chiffre dans un dépôt Restic dédié.

- **Mot de passe de cette sauvegarde** : la seule valeur à garder **hors du serveur** (coffre de mots de passe, papier) — sans lui, aucun secret ne peut être restauré, et sans les secrets, aucune autre sauvegarde ne s'ouvre (chaque service chiffre la sienne avec un mot de passe qui fait partie de ces Secrets). À relever une fois :

```bash
kubectl get secret secrets-backup -n myown-backup -o jsonpath='{.data.RESTIC_PASSWORD}' | base64 -d; echo
```

- **Contenu du dernier snapshot** : `scripts/secrets-restore.sh --list` (noms et nombre de clés, jamais de valeur).
- **Restaurer un Secret** supprimé ou abîmé : `scripts/secrets-restore.sh <namespace>/<nom>` (plusieurs possibles, `SNAPSHOT=<id>` pour un autre que le dernier). Les valeurs passent d'un pod jetable directement à `kubectl apply`, sans être affichées ni écrites sur disque. Redémarrer ensuite le service concerné pour qu'il relise ses variables.
- **Limite actuelle** : le dépôt de sauvegarde est sur le même disque que le cluster, comme celui des autres services. Il protège d'une erreur de manipulation ou d'une réinstallation du cluster, **pas de la perte du disque** : la copie hors machine (« nœud ami ») reste à faire.

## Mises à jour des briques

**Renovate** (GitHub App, configuration `renovate.json`) ouvre, chaque lundi avant 9 h, une PR par nouvelle version détectée. Rien n'est fusionné automatiquement. Ce qu'il suit :

- les charts Helm des Applications (`gitops/apps/templates/`) ;
- les images des manifestes (`gitops/manifests/`, `gitops/bootstrap/`) ;
- les tags d'image fixés dans les valeurs Helm et les versions des scripts (k3s, ArgoCD, Pi-hole), repérés par un commentaire `# renovate: datasource=… depName=…` juste au-dessus. Le contrôle CI `renovate` (`scripts/check-renovate-coverage.py`) refuse une source `chart:` ou un `tag:` de template qu'il ne verrait pas.

Les montées majeures de Postgres sont désactivées (la version suit celle du serveur). Les commits sont en `fix(deps): …` : ils apparaissent dans le CHANGELOG et déclenchent une version de correctif à la release. Vue d'ensemble dans l'issue « Tableau de bord des mises à jour (Renovate) ».

Fusionner une PR la déploie sur le cluster de dev (qui suit `master`) ; la production ne bouge qu'à la release suivante, après validation (`CLAUDE.md`, section Releases). Une PR qui modifie `scripts/install.sh` (k3s, ArgoCD) ne met pas à jour le mini PC : elle change la version d'une installation neuve, la montée de la production reste à faire à la main.
