# Manuel d'utilisation

Guide des services déployés : à quoi chacun sert, comment y accéder, comment s'en servir. Pour l'instant, tous les services en place sont des outils d'administration/supervision (aucun service "famille" comme Nextcloud ou Vaultwarden n'existe encore) — ce document grandira au même rythme que la roadmap.

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

- **URL** : <http://myown-uptime.local:8090>
- **Identifiants** : aucun compte créé automatiquement — un écran de création de compte admin apparaît au premier accès (email/mot de passe au choix, stockés localement dans Uptime Kuma, sans lien avec Authentik).
- **Usage** : actuellement vide (aucun moniteur configuré) — à ajouter vous-même. Pour ajouter un moniteur : **+ Add New Monitor**, choisir un type (HTTP(s), TCP, DNS...), renseigner l'URL/hôte à vérifier (par exemple Vaultwarden ci-dessous) et l'intervalle de check.

## Authentik — identité et authentification (SSO)

**À quoi ça sert** : à terme, le point d'entrée unique pour se connecter à tous les services du projet (un seul compte par personne). Pour l'instant, aucun autre service n'est encore branché dessus — uniquement Authentik lui-même est accessible.

- **URL** : <http://myown-authentik.local:8090>
- **Identifiants** : aucun compte bootstrap configuré — au premier accès, Authentik propose son propre flow de configuration initiale pour créer le compte administrateur (`akadmin`).
- **Usage** : rien à configurer pour l'instant côté applications. L'intégration SSO de Vaultwarden (premier candidat) est un travail séparé, pas encore fait — ce manuel sera mis à jour quand ce sera le cas.

## Vaultwarden — mots de passe

**À quoi ça sert** : gestionnaire de mots de passe auto-hébergé, compatible avec toutes les applications officielles Bitwarden (navigateur, mobile, desktop) — c'est le premier service applicatif "réel" du projet.

- **URL** : <http://myown-vaultwarden.local:8090> (interface web classique) — le panneau d'administration est à `/admin`
- **Identifiants utilisateur** : aucun compte par défaut — créez le vôtre depuis la page d'accueil (**Create Account**), comme sur bitwarden.com
- **Jeton du panneau admin** (`/admin`) :

  ```bash
  kubectl -n vaultwarden get secret vaultwarden-secrets -o jsonpath="{.data.ADMIN_TOKEN}" | base64 -d
  ```

- **Usage** : pour vous y connecter depuis une app Bitwarden (navigateur ou mobile), il faut changer le "serveur" dans les réglages de l'application vers l'URL ci-dessus avant de vous connecter — Bitwarden pointe vers bitwarden.com par défaut. Non encore intégré au SSO Authentik : connexion par email/mot de passe classique pour l'instant.

## À venir

Chaque nouveau service applicatif (Vaultwarden en premier, cf. `roadmap.md`) aura sa propre section ici : URL, identifiants, prise en main de base, et pour les services destinés à la famille/aux amis, des instructions pensées pour un public non technique.
