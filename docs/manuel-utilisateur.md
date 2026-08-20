# Manuel d'utilisation

Guide des services déployés : à quoi chacun sert, comment y accéder, comment s'en servir. Ce document grandit au même rythme que la roadmap.

Tous les accès ci-dessous supposent l'entrée `/etc/hosts` correspondante ajoutée (voir [`manuel-installation.md`](manuel-installation.md)) et un accès HTTP simple (`:8090`) — pas de HTTPS tant qu'on est sur le cluster de dev local.

## ArgoCD — orchestration GitOps

**À quoi ça sert** : c'est le tableau de bord qui montre l'état de tout ce qui est déployé, et qui applique automatiquement les changements poussés sur `master` du dépôt. En pratique : on ne déploie jamais rien "à la main", on modifie un fichier dans `gitops/apps/` et ArgoCD synchronise le cluster tout seul.

- **URL** : <http://myown-argocd.local:8090>
- **Identifiants** : utilisateur `admin`, mot de passe :

  ```bash
  kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
  ```

- **Usage** : la page d'accueil liste toutes les `Application`. Vert (`Synced`/`Healthy`) = tout va bien. Cliquer sur une application affiche l'arbre complet des ressources Kubernetes qu'elle a créées, utile pour diagnostiquer un problème.

## Grafana — métriques du cluster

**À quoi ça sert** : visualiser la santé technique du cluster (CPU, mémoire, état des pods) via des graphiques. Utile pour repérer un service qui consomme anormalement ou qui redémarre en boucle.

- **URL** : <http://myown-grafana.local:8090>
- **Identifiants** : utilisateur `admin`, mot de passe :

  ```bash
  kubectl -n monitoring get secret monitoring-grafana -o jsonpath="{.data.admin-password}" | base64 -d
  ```

- **Usage** : ~29 tableaux de bord préconfigurés (fournis par défaut avec kube-prometheus-stack) sont disponibles dans le menu **Dashboards** à gauche — par exemple "Kubernetes / Compute Resources / Cluster" pour une vue d'ensemble. Rien à configurer pour les avoir, ils sont déjà provisionnés.

## Uptime Kuma — disponibilité des services

**À quoi ça sert** : vérifie régulièrement que chaque service répond, et affiche un statut simple (vert/rouge) avec historique. C'est la vue pensée pour être lisible même par quelqu'un de non technique, à terme.

- **URL** : <http://myown-uptime.local:8090> — identifiants admin dans `gitops/secrets/uptime-kuma/uptime-kuma.sops.yaml` (compte local à Uptime Kuma, sans lien avec Authentik).
- **Page de statut publique** (pensée pour toute la famille, pas seulement l'admin) : <http://myown-uptime.local:8090/status/etat-du-systeme> — six services suivis (Authentik, Vaultwarden, Nextcloud, Immich, Tuwunel, LiveKit), configurés via `scripts/uptime-kuma-setup.py` plutôt qu'à la main dans l'UI (reproductible après une recréation du cluster — détails et vrais bugs rencontrés dans `notes-techniques.md`).
- **Alertes en cas de panne** : salon Matrix `#etat-du-systeme:myown-tuwunel.local`, ouvert à quiconque dans le foyer veut le rejoindre (depuis Element Web par exemple — rechercher/rejoindre l'alias directement). Le bot `@alertbot` y publie automatiquement les changements d'état (panne/rétablissement) — une seule fois, visible par tous, pas besoin de solliciter l'admin pour savoir "c'est en panne pour tout le monde ou juste chez moi ?".

## Authentik — identité et authentification (SSO)

**À quoi ça sert** : à terme, le point d'entrée unique pour se connecter à tous les services du projet (un seul compte par personne). Pour l'instant, aucun autre service n'est encore branché dessus — uniquement Authentik lui-même est accessible.

- **URL** : <http://myown-authentik.local:8090>
- **Identifiants** : aucun compte bootstrap configuré — au premier accès, Authentik propose son propre flow de configuration initiale pour créer le compte administrateur (`akadmin`).
- **Usage** : l'application "Vaultwarden" y est déclarée automatiquement (via blueprint, pas besoin de la créer à la main). Menu **Applications** pour voir/gérer qui peut y accéder.

## Vaultwarden — mots de passe

**À quoi ça sert** : gestionnaire de mots de passe auto-hébergé, compatible avec toutes les applications officielles Bitwarden (navigateur, mobile, desktop) — c'est le premier service applicatif "réel" du projet.

- **URL** : <https://myown-vaultwarden.local:8453> (⚠️ HTTPS et port 8453, pas 8090 comme les autres services — le web vault a besoin de l'API Subtle Crypto du navigateur pour chiffrer/déchiffrer côté client, indisponible en HTTP sur un nom d'hôte personnalisé même si celui-ci pointe vers `127.0.0.1`) — le panneau d'administration est à `/admin`
- **Premier accès** : le certificat est signé par une CA locale (mkcert) déjà approuvée sur cette machine — pas d'avertissement de sécurité attendu. Sur une autre machine, voir `manuel-installation.md` pour régénérer/faire confiance au certificat.
- **Identifiants utilisateur** : aucun compte par défaut — créez le vôtre depuis la page d'accueil (**Create Account**), comme sur bitwarden.com
- **Jeton du panneau admin** (`/admin`) :

  ```bash
  kubectl -n vaultwarden get secret vaultwarden-secrets -o jsonpath="{.data.ADMIN_TOKEN}" | base64 -d
  ```

- **Usage** : pour vous y connecter depuis une app Bitwarden (navigateur ou mobile), il faut changer le "serveur" dans les réglages de l'application vers l'URL ci-dessus avant de vous connecter — Bitwarden pointe vers bitwarden.com par défaut.
- **Connexion via Authentik (SSO)** : sur l'écran de connexion, un bouton "Se connecter via SSO" (ou équivalent selon le client) redirige vers Authentik. La connexion classique par email/mot de passe reste aussi disponible — les deux ne sont pas exclusives à ce stade.
- **Le mot de passe principal reste demandé après le SSO — c'est normal.** Le SSO prouve *qui* vous êtes (authentification) ; il ne peut pas fournir la clé qui déchiffre votre coffre (chiffrement), parce que cette clé est dérivée du mot de passe principal **côté navigateur uniquement** — le serveur ne le connaît jamais, même l'opérateur du serveur ne peut pas lire vos mots de passe sans lui. Les deux mécanismes sont volontairement séparés (zero-knowledge encryption) ; ce n'est pas une étape de connexion en trop.

## Nextcloud — fichiers, contacts, calendrier, notes, tâches

**À quoi ça sert** : remplace Google Drive/Docs pour le stockage et le partage de fichiers, plus contacts (CardDAV), calendrier (CalDAV), notes texte libre et listes de tâches. Pas encore de sauvegarde Restic ni d'app Android à ce stade (cf. `roadmap.md`).

- **URL** : <https://myown-nextcloud.local:8453> (⚠️ HTTPS et port 8453, pas 8090 — comme Vaultwarden, mais pour une raison différente ici : l'app SSO `user_oidc` refuse purement et simplement de fonctionner en HTTP, indépendamment de toute question de navigateur)
- **Premier accès** : certificat signé par la CA locale mkcert déjà approuvée sur cette machine — pas d'avertissement attendu. Sur une autre machine, voir `manuel-installation.md`.
- **Identifiants (compte admin local)** : utilisateur `admin`, mot de passe :

  ```bash
  kubectl -n nextcloud get secret nextcloud-secrets -o jsonpath="{.data.NEXTCLOUD_PASSWORD}" | base64 -d
  ```

- **Usage** : interface web classique Nextcloud, glisser-déposer pour envoyer des fichiers.
- **Connexion via Authentik (SSO)** : sur l'écran de connexion, un bouton "Se connecter via authentik" (ou équivalent) redirige vers Authentik — un seul compte, comme pour Vaultwarden. La connexion classique par mot de passe local reste disponible (utile notamment pour le compte `admin` ci-dessus, qui n'existe pas dans Authentik).
- **Contacts et calendrier** : apps installées et activées, utilisables directement depuis l'interface web ou via un client CalDAV/CardDAV externe (Thunderbird, l'app calendrier d'un téléphone, etc.) — pas besoin d'attendre l'app mobile dédiée, différée en Phase 4.
- **Notes et Tâches** : deux usages différents, pas redondants. **Notes** (app `notes`) pour du texte libre en markdown — personnel par défaut, partageable via le partage de fichiers/dossiers classique de Nextcloud (ex. une liste de cadeaux visible par toute la famille). **Tasks** (app `tasks`) pour des listes à cocher basées CalDAV, partageables en temps réel entre comptes (ex. une liste de courses synchronisée avec son/sa conjoint·e) ; une tâche avec date d'échéance apparaît aussi directement dans le Calendrier, cochable depuis cette vue.
- **Photos** : l'app Photos native de Nextcloud est désactivée — Immich (section ci-dessous) est la seule app photo du projet, pour éviter une double bibliothèque déroutante.

## Immich — photos et vidéos

**À quoi ça sert** : remplace Google Photos — stockage, organisation, recherche sémantique et reconnaissance faciale sur les photos/vidéos, avec sauvegarde automatique depuis mobile (app Android/iOS officielle). Pas encore de sauvegarde Restic ni d'app Android configurée à ce stade — cf. `roadmap.md`.

- **URL** : <http://myown-immich.local:8090>
- **Premier accès** : aucun compte par défaut — un écran de création de compte administrateur apparaît à la première visite.
- **Usage** : glisser-déposer des photos/vidéos depuis le navigateur pour tester. La reconnaissance faciale et la recherche sémantique tournent en local (service `machine-learning` du même déploiement, aucune donnée envoyée à l'extérieur) — les premières analyses peuvent prendre un moment le temps que les modèles se chargent.
- **Connexion via Authentik (SSO)** : sur l'écran de connexion, un bouton "Se connecter via Authentik" redirige vers Authentik — un seul compte, comme pour les autres services. Configuré nativement dans Immich (pas d'app tierce comme pour Nextcloud), sans aucune manipulation à faire : la configuration OAuth est posée automatiquement au déploiement.

## Tuwunel — messagerie (texte + appels vidéo de groupe)

**À quoi ça sert** : serveur Matrix (texte, et maintenant appels vidéo de groupe via LiveKit), remplace Conduwuit prévu initialement (archivé en amont, voir `notes-techniques.md`). Pas de client mobile dédié pour l'instant — Element X, l'app prévue, est différée à la Phase 4 pour les mêmes raisons de résolution DNS locale que les autres apps Android — mais **Element Web, hébergé sur app.element.io, fonctionne dès maintenant** comme client complet (texte et appels), pointé vers notre serveur.

- **URL (API, pas d'interface web ici)** : <https://myown-tuwunel.local:8453> — répond au protocole client-serveur Matrix. HTTPS (pas `:8090`) à cause du cookie de session SSO, marqué `Secure` par Tuwunel — voir `notes-techniques.md`.
- **Se connecter via Element Web** : aller sur <https://app.element.io>, à l'écran de connexion choisir **Modifier** en face du serveur proposé par défaut, saisir `myown-tuwunel.local:8453`, puis se connecter (compte créé via l'API, ou SSO Authentik).
- **Appels vidéo de groupe** : dans une room, bouton d'appel — rejoint automatiquement un appel Element Call, média géré par LiveKit. Fonctionne pour 3-4 participants d'après l'architecture ciblée ; validé à ce stade avec un compte réel en navigateur (audio, réactions), pas encore avec plusieurs appareils simultanés sur le LAN.
- **Statut** : déploiement nu, SSO Authentik et sauvegarde Restic quotidienne tous validés en conditions réelles. LiveKit validé de bout en bout (découverte MatrixRTC, connexion média réelle, réactions).

## Jellyfin — films et musique

**À quoi ça sert** : bibliothèque de films/séries/musique (achetés) avec lecture en streaming — le complément de Nextcloud/Immich pour ce cas d'usage précis, pensé pour une famille dispersée géographiquement. Déploiement, sauvegarde et SSO validés ; **bibliothèque encore vide** (pas de contenu réel chargé à ce stade).

- **URL** : <http://myown-jellyfin.local:8090>
- **Connexion via Authentik (SSO)** : sur l'écran de connexion, un bouton "Se connecter avec Authentik" redirige vers Authentik — un seul compte, comme pour les autres services. Premier compte créé automatiquement à la première connexion.
- **Compte admin local** (`admin`) : reste disponible en secours si Authentik est indisponible, mot de passe dans `gitops/secrets/jellyfin/jellyfin.sops.yaml`.
- **Statut** : déploiement, sauvegarde Restic et SSO Authentik tous validés en conditions réelles (`notes-techniques.md`). Pas encore de contenu dans la bibliothèque.

## À venir

Chaque nouveau service applicatif aura sa propre section ici : URL, identifiants, prise en main de base, et pour les services destinés à la famille/aux amis, des instructions pensées pour un public non technique.
