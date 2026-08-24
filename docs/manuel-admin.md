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

## Enrôlement — ajouter un utilisateur

1. **Authentik** (<https://authentik.offsystem.fr/if/admin/>) → Répertoire →
   Utilisateurs → Créer. Si un accès Mailu est prévu, saisir directement
   l'email définitif en `@offsystem.fr` — le changer plus tard demande une
   manipulation admin en plus (voir Mailu ci-dessous).
2. Générer un **lien de récupération** pour ce compte (jamais choisir le mot
   de passe à sa place) et le transmettre à la personne.
3. Elle définit son propre mot de passe via ce lien, puis se connecte en SSO
   à chaque service — le compte s'y crée automatiquement à la première
   connexion.
4. Vérifier ces cas particuliers après le premier login :

   | Service | Point d'attention |
   |---|---|
   | Jellyfin | Le compte SSO créé n'a **pas** les droits admin par défaut — normal pour un utilisateur, voir plus bas si c'est le vôtre. |
   | Immich, Tuwunel | Le **tout premier** compte créé sur le service devient son admin — à réserver au vôtre, avant d'inviter qui que ce soit d'autre. |
   | Mailu | Refuse la connexion tant que l'email Authentik n'est pas en `@offsystem.fr` (erreur avec `domain=...`). |

5. Envoyer le [fichier de favoris](https://aide.offsystem.fr/downloads/myown-favoris.html)
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
  dans le salon `#etat-du-systeme` pour les services sensibles à la famille.

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

- **Panneau admin** : <https://mailu.offsystem.fr/admin>
- **Compte** : `admin@offsystem.fr`, mot de passe dans
  `gitops/secrets/mailu/mailu.sops.yaml` → `initial-account-password`
- **Actions courantes** : gestion des domaines/alias, consultation des
  files d'attente et du filtrage anti-spam. DKIM déjà configuré (clé privée
  dans le même secret, ne jamais l'afficher en clair).
- Une adresse `@offsystem.fr` est créée automatiquement pour chaque compte
  Authentik dont l'email est déjà sur ce domaine — pas de création manuelle
  nécessaire une fois l'email corrigé côté Authentik.
- **Carnet d'adresses (rcmcarddav)** : déjà activé par défaut dans l'image
  webmail, aucun réglage admin global — chaque utilisateur ajoute sa propre
  source CardDAV en libre-service (voir le manuel utilisateur). Pas de
  preset admin possible : les identifiants Nextcloud provisionnés par
  `user_oidc` sont opaques par personne, pas substituables par un preset
  commun.

## Uptime Kuma — supervision

- **Admin** (LAN/VPN) : `http://myown-uptime.local:8090` — identifiants
  dans `gitops/secrets/uptime-kuma/uptime-kuma.sops.yaml`
  (`UPTIME_KUMA_USERNAME` / `UPTIME_KUMA_PASSWORD`).
- **Page publique** (lecture seule, pour la famille) :
  <https://status.offsystem.fr>
- Ajout d'un moniteur ou modification de la page de statut : configurés via
  `scripts/uptime-kuma-setup.py` plutôt qu'à la main, pour rester
  reproductible après une recréation du cluster.

## Sauvegardes (Restic)

Chaque service avec état a son propre `CronJob` de sauvegarde et son propre
`RESTIC_PASSWORD` dans son secret (`gitops/manifests/<service>-backup/`).
Procédure de sauvegarde/restauration manuelle détaillée, service par
service, dans `notes-techniques.md` — pas dupliquée ici pour éviter la
dérive entre les deux documents.
