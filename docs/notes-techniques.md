# Notes techniques

Documentation "as-built" : ce qui est réellement déployé, avec quelle configuration, et les difficultés rencontrées en le construisant. Complète [`architecture.md`](architecture.md) (vision et choix cibles) sans le dupliquer — mise à jour à chaque nouvelle brique ajoutée au projet, pas rédigée une fois pour toutes.

## État actuel

Roadmap Phase 0 ("Socle") complète, sur un cluster **k3d local de développement** (`myown-dev`) — pas encore le mini PC cible ni de nom de domaine réel. Tous les services sont exposés en HTTP (pas HTTPS) sur des hosts `myown-<service>.local:8090`, à ajouter soi-même dans `/etc/hosts`.

| Brique | Version déployée |
|---|---|
| k3d | v5.9.0 (Kubernetes via k3s v1.35.5+k3s1) |
| ArgoCD | v3.5.0 |
| kube-prometheus-stack | chart 88.1.5 |
| Uptime Kuma (chart `dirsigler/uptime-kuma-helm`) | chart 4.1.0, app 2.3.0 |
| Authentik | chart/app 2026.5.6 |
| PostgreSQL (Authentik, via sous-chart Bitnami) | 17.10-bookworm |
| Vaultwarden (chart `guerzon/vaultwarden`) | chart 0.46.0, app 1.37.1 |
| Restic (image `restic/restic`) | 0.19.1 |
| SOPS | 3.10.2 |
| KSOPS | v4.5.1 |

## Infrastructure de base

### Cluster de dev (k3d)

Cluster dédié `myown-dev`, séparé de tout autre cluster local existant sur la même machine (pas de mutualisation — cf. réflexion dans `vision-long-terme.md` sur l'isolation par projet). Ports du load balancer k3d mappés explicitement à la création (`-p "8090:80@loadbalancer" -p "8453:443@loadbalancer"`) pour permettre un accès HTTP/HTTPS stable — **ce mapping ne peut pas être ajouté après coup à un cluster existant**, il faut le prévoir dès la création ou recréer le cluster.

Traefik est inclus par défaut dans k3s/k3d — aucune installation séparée nécessaire, y compris pour la future prod sur mini PC (même comportement par défaut).

### ArgoCD

Installé via le manifest officiel (`kubectl apply --server-side -f .../install.yaml`) — **`--server-side` est obligatoire**, un `apply` classique échoue sur les CRDs d'ArgoCD (annotation `metadata.annotations` limitée à 262144 octets par l'API Kubernetes, dépassée par les CRDs volumineuses appliquées en client-side).

`argocd-server` tourne en mode `insecure` (TLS géré par l'Ingress plutôt que par ArgoCD lui-même) pour simplifier l'exposition locale — à revoir en prod où le TLS sera géré par Traefik + Let's Encrypt sur le vrai domaine.

Pattern app-of-apps : une seule `Application` racine (`gitops/bootstrap/root-app.yaml`) surveille `gitops/apps/`, chaque fichier de ce dossier est une `Application` pour un service. Voir `gitops/README.md`.

### Secrets (SOPS + age + KSOPS)

Décidé après discussion explicite : décryptage automatique par ArgoCD (KSOPS) plutôt que `sops -d | kubectl apply` manuel, malgré la complexité de mise en place plus élevée — pour que la reconstruction du cluster reste entièrement automatique une fois la clé privée restaurée, dans l'idée que ce projet doit rester installable proprement par quelqu'un d'autre.

Mécanisme : un init-container (`viaductoss/ksops:v4.5.1`) copie un binaire `kustomize` incluant `ksops` dans `argocd-repo-server`, en lieu et place du `kustomize` standard. La clé privée age est montée depuis un Secret Kubernetes (`sops-age`, namespace `argocd`) créé **hors GitOps** (bootstrap manuel, comme ArgoCD lui-même). Détail complet et commandes exactes dans `CLAUDE.md`.

**Incident** : la clé privée age initiale n'avait jamais été sauvegardée nulle part (probablement affichée dans un terminal puis perdue) — rotation vers un nouvel emplacement standard (`~/.config/sops/age/keys.txt`, lu automatiquement par `sops` sans variable d'environnement) sans conséquence puisqu'aucun secret n'était encore chiffré avec l'ancienne clé.

## Monitoring (kube-prometheus-stack + Uptime Kuma)

Alertmanager désactivé (`alertmanager.enabled: false`) — hors périmètre documenté dans `architecture.md`. Rétention Prometheus réduite à 3 jours pour un cluster de dev.

Uptime Kuma choisi via un chart communautaire (`dirsigler/uptime-kuma-helm`, 303 étoiles, maintenu activement) faute de chart officiel — le projet Uptime Kuma lui-même n'en publie pas. Vérifié avant usage : le chart pointe bien vers l'image Docker officielle (`louislam/uptime-kuma`), donc seule l'empaquetage Helm est tiers, pas l'application.

**Incidents rencontrés (deux, indépendants) :**

1. **CRDs Prometheus Operator trop volumineuses pour `kubectl apply` classique** — même cause que pour ArgoCD (limite d'annotation à 262144 octets). Contournement : `syncOptions: [ServerSideApply=true]` sur l'`Application` ArgoCD. Insuffisant seul la première fois (CRDs déjà en échec partiel) — il a fallu les appliquer une fois manuellement en `--server-side` avant que le `selfHeal` d'ArgoCD ne reprenne la main proprement.
2. **Mot de passe Grafana auto-généré différemment à chaque rendu** — en laissant `grafana.adminPassword` vide, le chart génère une valeur aléatoire à *chaque* `helm template`, donc à chaque comparaison faite par ArgoCD, créant un `OutOfSync` permanent. Résolu par `ignoreDifferences` ciblé sur le Secret et l'annotation de checksum du Deployment qui en dépend — pas de mot de passe en clair committé pour autant.
3. **Cache de découverte d'API figé au démarrage de l'opérateur** — le pod `kube-prometheus-operator`, démarré avant que les CRDs existent réellement dans le cluster (à cause de l'incident 1), ne "voyait" plus le type `Prometheus` même une fois les CRDs corrigées et les permissions RBAC en place. Un simple `kubectl rollout restart` a suffi — les opérateurs Kubernetes construisent souvent leur RESTMapper/cache de découverte une fois au démarrage et ne le rafraîchissent pas dynamiquement.

## Authentik (SSO)

Chart officiel `authentik/authentik`. PostgreSQL via le sous-chart Bitnami bundlé (`postgresql.enabled: true`, désactivé par défaut dans le chart). Pas de Redis — les versions récentes d'Authentik n'en dépendent plus (chart sans dépendance Redis, à la différence des versions historiques du projet).

Secret unique (`gitops/secrets/authentik/authentik.sops.yaml`, chiffré) référencé via `authentik.existingSecret.secretName` et `postgresql.auth.existingSecret` — même nom de Secret pour les deux, les clés ne se chevauchent pas.

**Incident** : `authentik.existingSecret` remplace **l'intégralité** du Secret de configuration généré par le chart, pas seulement ses champs sensibles — la connexion PostgreSQL (host/port/nom/utilisateur), non sensible, y est mélangée par le chart et disparaît donc aussi si on ne la fournit pas explicitement. Symptôme : `authentik-server`/`authentik-worker` en `CrashLoopBackOff`, tentant de se connecter à `localhost:5432` (repli interne d'Authentik en l'absence totale de configuration PostgreSQL) plutôt qu'au vrai service `authentik-postgresql`.

**Leçon retenue pour les prochains services** (Vaultwarden, Nextcloud, Mailcow auront le même genre d'option) : avant de configurer un `existingSecret` sur un nouveau chart, toujours rendre le chart sans cette option (`helm template ...`) pour voir la liste complète des clés que le Secret généré contient normalement, et répliquer cette liste intégrale — ne pas supposer que seuls les champs visiblement sensibles sont concernés.

## Vaultwarden (mots de passe)

Premier service de la Phase 1 de la roadmap. Chart communautaire `guerzon/vaultwarden` (342 étoiles, mis à jour la veille du déploiement — même vérification de fraîcheur que pour Uptime Kuma), faute de chart officiel. Base SQLite par défaut du chart — pas de service de base de données séparé à ce stade. Modèle de secrets par option (`adminToken.existingSecret`, `database.existingSecret`, etc.) plutôt qu'un seul Secret monolithique comme Authentik : plus précis, pas le même risque d'oubli de champ.

**Incidents rencontrés (deux) :**

1. **`volumeClaimTemplates` invalide si seul `storage.data.size` est renseigné** — le nom (`metadata.name`) et les modes d'accès (`accessModes`) du template de PVC restent vides malgré des valeurs par défaut suggérées dans les commentaires du chart, produisant un StatefulSet rejeté par l'API Kubernetes. Trouvé et corrigé *avant* le push grâce à `kubectl apply --dry-run=client` sur le rendu complet — pas besoin d'un cycle d'échec en cluster réel pour l'attraper.
2. **`OutOfSync` persistant sur le StatefulSet malgré un état réellement synchronisé** — Kubernetes normalise chaque `volumeClaimTemplate` une fois le PVC provisionné : ajoute `apiVersion`/`kind`, positionne `spec.volumeMode` par défaut, et remplit `status`. Aucun de ces champs n'existe dans le manifest désiré. `ignoreDifferences` (`jqPathExpressions`) nécessaire sur les quatre champs, pas seulement `status` comme il semblait suffisant au premier abord. Distinction importante faite pendant le diagnostic : `argocd app diff --hard-refresh` (calcul en direct) confirmait déjà un état propre alors que le badge `Sync Status` agrégé restait bloqué sur `OutOfSync` — un vrai bug d'affichage ArgoCD sur ce type de ressource, vérifié inoffensif (0 redémarrage du pod, dernière opération de synchro terminée en 0 seconde, donc no-op) plutôt qu'un signe de dérive réelle à corriger davantage.
3. **Web vault inutilisable en HTTP** — erreur navigateur "Subtle Crypto API... you need to enable HTTPS". Bitwarden/Vaultwarden chiffrent tout côté client via l'API Web Crypto du navigateur, qui exige un "contexte sécurisé" : HTTPS, ou littéralement les hostnames `localhost`/`127.0.0.1` — un nom personnalisé comme `myown-vaultwarden.local` ne compte pas, même pointé vers `127.0.0.1` via `/etc/hosts`. Résolu avec un certificat local via `mkcert`, servi sur le port HTTPS du load balancer k3d déjà réservé depuis la création du cluster (8453). Le Secret TLS est créé hors GitOps, au même titre que `sops-age` : un certificat de dev est propre à une machine, pas à distribuer via git.
4. **Une resynchro forcée de `vaultwarden` seule ne suffit pas toujours** — après avoir modifié `gitops/apps/vaultwarden.yaml` et mergé, `kubectl annotate application root argocd.argoproj.io/refresh=hard` a recalculé le diff de `root` mais n'a pas fait redescendre le changement vers l'`Application` `vaultwarden` elle-même (son `.spec` restait sur l'ancienne valeur `ingress.tls: false`). Il a fallu un `argocd app sync root` explicite (pas juste un refresh) pour que `root` réapplique réellement l'`Application` enfant, puis un `argocd app sync vaultwarden` pour que le changement atteigne l'Ingress. À garder en tête : *refresh* recalcule un diff, *sync* l'applique — les deux sont parfois nécessaires en pratique même avec `selfHeal: true`.
5. **`mkcert -install` ne suffisait pas pour de vrai, malgré son message de succès** — CA générée et certificat serveur corrects (vérifiés côté serveur avec `openssl s_client`), mais Chromium (installé en snap) affichait quand même "non sécurisé". Cause : les navigateurs installés en snap ont leur propre profil isolé (`~/snap/chromium/<revision>/.local/share/pki/nssdb`), que `mkcert -install` ne détecte pas — son message "already installed" ne portait que sur le magasin système générique. Même après avoir manuellement ajouté la CA au bon endroit avec `certutil` (confirmé présente avec les droits corrects `CT,C,C` via `certutil -L`) et redémarré le navigateur pour de vrai (un `ps aux` a montré qu'il tournait encore en arrière-plan après la première tentative de fermeture), l'avertissement persistait — les versions récentes de Chrome/Chromium peuvent ignorer le magasin NSS système au profit de leur "Chrome Root Store" intégré. La CA apparaissait même classée en "intermédiaire" plutôt qu'en racine dans `chrome://certificate-manager` → Linux. Résolu uniquement en important `rootCA.pem` manuellement dans `chrome://certificate-manager` → **Personnalisé → Certificats approuvés**. Détail des étapes : `manuel-installation.md`.

## Vaultwarden ↔ Authentik (SSO)

Provider OAuth2/OIDC + Application déclarés côté Authentik via un **blueprint** (mécanisme natif d'Authentik pour la config déclarative), pas via l'interface d'administration — cohérent avec le reste du projet, reproductible. Le blueprint lui-même vit dans un Secret chiffré SOPS/KSOPS (`gitops/secrets/authentik-blueprints/`), monté dans le worker Authentik via `blueprints.secrets` (valeur du chart). Champs exacts (notamment `redirect_uris`, qui a changé de format — désormais une liste d'objets `{matching_mode, url}` et non plus de simples chaînes) vérifiés directement contre le schéma OpenAPI et le `schema.json` des blueprints de l'instance réellement déployée, pas devinés depuis la documentation.

**Un vrai trou d'architecture découvert en le construisant** : Vaultwarden doit atteindre Authentik *côté serveur* (échange OIDC) pour valider une connexion — mais `myown-authentik.local` ne se résolvait jusque-là que depuis la machine hôte (`/etc/hosts`), pas depuis l'intérieur du cluster, et le port externe (8090) n'est mappé que sur le load balancer k3d, pas à l'intérieur. Résolu par deux ressources additives, hors GitOps (même statut que l'installation d'ArgoCD) :

- `gitops/bootstrap/traefik-internal-svc.yaml` — un Service séparé (ne touche pas au Service `traefik` géré par Helm/k3s) exposant les ports 8090/8453 à l'intérieur du cluster, en miroir du load balancer externe
- `gitops/bootstrap/coredns-custom.yaml` — réécrit `myown-*.local` vers ce service via le mécanisme `import /etc/coredns/custom/*.override` officiellement supporté par k3s. Un bloc `hosts {}` classique était impossible (déjà utilisé une fois dans le Corefile par défaut — un seul autorisé par bloc serveur) ; `rewrite name exact` utilisé à la place, avec l'avantage de ne pas figer une IP en dur.

Ce n'est pas qu'un détail pour le SSO : sans ça, le document de découverte OIDC qu'Authentik renvoie (construit à partir du Host de la requête reçue) aurait perdu le port `:8090`, cassant la redirection du navigateur vers la page de connexion. Vérifié explicitement après coup : `authorization_endpoint` renvoyé contient bien `myown-authentik.local:8090`.

**Trois échecs réels lors du premier test de connexion en conditions réelles** (le déploiement seul ne suffit jamais à valider un flow OIDC — il faut le cliquer vraiment) :

1. **`redirect_uris` avec `matching_mode: regex`, tolérant un port absent** — hypothèse initiale basée sur un avertissement de la documentation Vaultwarden ("ignore parfois le port du callback sur un port non standard"), qui s'est avérée non pertinente : la vraie cause de l'échec de connexion était ailleurs (`domain` jamais configuré côté Vaultwarden, cf. ci-dessous), pas le port. Une fois `domain` corrigé, la valeur réelle envoyée par Vaultwarden a pu être capturée dans les logs Authentik et le `redirect_uris` resserré en `matching_mode: strict` sur cette valeur exacte plutôt que de garder une tolérance qui n'était finalement pas nécessaire.
2. **`DOMAIN` jamais configuré côté Vaultwarden** → il construit ses URLs de callback (SSO et autres) à partir de ce paramètre, absent = replié sur `http://localhost`. Authentik rejetait donc un `redirect_uri=http://localhost/...` qui ne correspondait à rien. Trouvé en lisant le log d'accès Authentik (`redirect_uri` intégralement loggé sur l'événement de rejet), pas en devinant. Fix : `domain: "https://myown-vaultwarden.local:8453"` dans les valeurs Helm.
3. **`grant_types` vide par défaut sur le `OAuth2Provider`** — le blueprint ne le renseignait pas explicitement ; Authentik rejette silencieusement toute requête `authorize` avec `response_type=code` si `authorization_code` n'est pas dans la liste (vide par défaut, confirmé via `ak shell`). Message d'erreur générique côté Vaultwarden ("malformed"), cause précise seulement visible dans les logs Authentik ("Invalid grant_type for provider"). Fix : `grant_types: [authorization_code, refresh_token]` explicite dans le blueprint.
4. **Mapping de scope `email` par défaut d'Authentik : `email_verified` codé en dur à `False`** — repéré après une 4ème tentative de connexion échouant avec "Email is not verified by the SSO provider" malgré `sso.ignoreEmailVerification: true` côté Vaultwarden (ce réglage ne couvre que le cas où le claim est *absent*, pas *présent et faux*). Confirmé en lisant directement l'expression du mapping système via `ak shell` (`ScopeMapping.objects.get(scope_name='email').expression`). Fix : mapping de scope dédié à ce provider (même `scope_name`, `name` différent pour coexister avec le mapping système) renvoyant `email_verified: True` — justifié ici parce qu'Authentik est le seul opérateur d'identité de confiance du projet, pas un tiers fédérant des comptes non vérifiés.

**Méthode qui a permis de résoudre les quatre** : à chaque échec, aller lire le log d'accès complet côté Authentik (`kubectl logs deploy/authentik-server`) plutôt que de se fier au message d'erreur, générique et tardif, affiché côté Vaultwarden — Authentik loggue le `redirect_uri` complet et la raison précise du rejet sur chaque requête `/application/o/authorize/`.

**Découverte automatique des blueprints montés** : fonctionne (le mécanisme est réel, testé), mais pas instantanément — après le montage ou la modification du Secret, il faut souvent déclencher manuellement `ak apply_blueprint <chemin>` (ou la tâche `blueprints_discovery`) pour que le changement s'applique tout de suite, plutôt que d'attendre son prochain passage périodique. Piège additionnel rencontré : le **volume monté lui-même** met aussi un peu de temps (kubelet) à refléter un Secret mis à jour — vérifier le contenu du fichier monté avant de conclure que l'application du blueprint a échoué.

## Sauvegarde Restic (Vaultwarden)

Premier pipeline de sauvegarde du projet (roadmap Phase 1), pensé pour être copié tel quel sur les prochains services (Nextcloud, Immich, ...). Reste dans l'`Application` ArgoCD `vaultwarden` existante (un 3ᵉ `source` pointant vers `gitops/manifests/vaultwarden-backup/`, manifests bruts sans chart Helm) plutôt qu'une `Application` séparée — cohérent avec "une Application par service".

**Cible temporaire** : le nœud ami n'existe pas encore, donc le dépôt Restic vit sur une PVC `local-path` dédiée (`vaultwarden-restic-repo`) dans le même cluster que les données qu'elle sauvegarde — ce n'est pas une vraie protection 3-2-1 tant que ce n'est pas déplacé, juste la mise en place de la mécanique. Migration future vers le nœud ami : changement de `RESTIC_REPOSITORY` uniquement (ex. `sftp:...` ou `rest:...`), aucune réécriture du CronJob.

CronJob quotidien (`0 3 * * *`), image officielle `restic/restic:0.19.1`, mot de passe du dépôt dans le Secret SOPS existant `vaultwarden-secrets` (clé `RESTIC_PASSWORD`, ajoutée par `sops --set` — pas de nouveau dossier de secret, même modèle qu'`ADMIN_TOKEN`/`SSO_CLIENT_*`). Auto-initialisation idempotente du dépôt (`restic snapshots || restic init`) plutôt qu'un Job d'init séparé hors GitOps. Rétention `keep-daily 7 / keep-weekly 4 / keep-monthly 3` + `prune`, appliquée juste après chaque backup dans le même CronJob.

Monte la PVC de données Vaultwarden (`data-vaultwarden-0`) en lecture seule à côté de la PVC du dépôt — fonctionne parce que le cluster est mono-nœud (vrai en dev k3d comme sur la future prod mini PC) : RWO restreint l'attachement à un seul *nœud*, pas à un seul pod ; deux pods sur le même nœud peuvent donc monter la même PVC `local-path` simultanément. **À revoir si la Phase 6 passe en topologie multi-nœuds** (le pod de backup pourrait alors être ordonnancé sur un nœud différent de celui qui tient la PVC).

**Incident rencontré lors du test de restauration** : un pod de test montait la PVC du dépôt en lecture seule (cohérent avec l'intention de ne pas risquer de corrompre le dépôt lors d'une simple restauration) — mais `restic restore`/`snapshots` échouent quand même à l'écriture, même en lecture, car restic pose systématiquement un verrou (`/repo/locks/...`) avant toute opération, y compris en lecture. Résolu en montant le dépôt en lecture-écriture pour toute opération restic (backup **et** restauration) ; seule la PVC de données source (`/data`) a réellement besoin d'être montée en lecture seule.

**Validé en conditions réelles** : run manuel du CronJob (snapshot créé, ~400 KiB, politique de rétention appliquée), puis restauration complète dans un pod jetable avec `diff -rq` contre les données live — contenu restauré strictement identique.

## Git / CI / signature de commits

Voir `CLAUDE.md` pour le détail (workflow trunk-based, conventional commits, versioning). Un point notable : GitHub refuse le merge "Rebase and merge" dès que les commits signés sont obligatoires sur la branche (il ne peut auto-signer que les commits qu'il crée lui-même) — `"Create a merge commit"` est la seule méthode compatible.
