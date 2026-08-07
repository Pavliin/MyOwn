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

**Reporté à un travail séparé** : l'intégration SSO avec Authentik (mentionnée dans le périmètre de la roadmap Phase 1). Le chart supporte nativement l'OpenID Connect (`sso.*`), mais ça suppose de créer d'abord un provider/une application côté Authentik — une pièce de travail à part entière, pas juste un ajustement de valeurs Helm.

## Git / CI / signature de commits

Voir `CLAUDE.md` pour le détail (workflow trunk-based, conventional commits, versioning). Un point notable : GitHub refuse le merge "Rebase and merge" dès que les commits signés sont obligatoires sur la branche (il ne peut auto-signer que les commits qu'il crée lui-même) — `"Create a merge commit"` est la seule méthode compatible.
