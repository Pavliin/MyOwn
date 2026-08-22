# Manuel d'installation

Reproduit l'état actuel du projet : un cluster de développement local (k3d), pas encore le mini PC de production ni un vrai nom de domaine. Ce document sera étendu avec une section "installation en production" une fois la Phase 0 de la roadmap déplacée sur le matériel cible.

## Prérequis

- Docker (avec accès au daemon)
- `git`, et [`gh`](https://cli.github.com/) authentifié (`gh auth login`)
- Node.js/npm (outillage de versioning du dépôt — voir `CLAUDE.md`)
- Une clé SSH de signature de commits configurée (obligatoire pour pousser sur `master` — voir `CLAUDE.md`, section "Commit signing")

## 1. Cloner le dépôt

```bash
git clone https://github.com/Pavliin/MyOwn.git
cd MyOwn
npm install
```

## 2. Installer les outils

```bash
# k3d, kubectl, helm : à adapter selon votre gestionnaire de paquets si des
# versions plus récentes existent — testé avec k3d v5.9.0, kubectl v1.36.2,
# helm v3.16.4.

# sops
curl -fsSL -o ~/.local/bin/sops \
  https://github.com/getsops/sops/releases/download/v3.10.2/sops-v3.10.2.linux.amd64
chmod +x ~/.local/bin/sops

# age (age-keygen) — souvent disponible via le gestionnaire de paquets système
```

## 3. Clé de chiffrement des secrets (age)

**Sur la toute première installation du projet** (pas votre cas si vous reproduisez ce dépôt) :

```bash
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt
```

Remplacer la clé publique dans `.sops.yaml` par celle affichée, committer.

**Pour reproduire ce dépôt sur une nouvelle machine** (le cas normal) : restaurer le fichier `~/.config/sops/age/keys.txt` depuis votre sauvegarde. Sans lui, tous les secrets déjà chiffrés dans le dépôt (Authentik, etc.) sont définitivement illisibles — ce fichier n'est jamais dans git, il faut le sauvegarder soi-même ailleurs (gestionnaire de mots de passe, coffre chiffré...).

## 4. Créer le cluster

```bash
k3d cluster create myown-dev \
  -p "8090:80@loadbalancer" -p "8453:443@loadbalancer" -p "443:443@loadbalancer" \
  -p "7880:7880@loadbalancer" -p "7881:7881@loadbalancer" -p "7882:7882/udp@loadbalancer" \
  --wait
kubectl config use-context k3d-myown-dev
```

Le mapping de ports doit être fait **à la création** — impossible à ajouter après coup sans recréer le cluster. Le port `443` littéral (en plus de `8453:443`) est nécessaire pour LiveKit/MatrixRTC : la découverte Matrix (`.well-known/matrix/client` et `/matrix/server`) est fetchée sur le port standard 443, implicite dans le nom de domaine, indépendamment du port `8453` utilisé partout ailleurs dans ce projet. Les trois ports `78xx` sont pour le SFU LiveKit (signalisation WebSocket, repli ICE TCP, média UDP — cf. section LiveKit de `notes-techniques.md`).

## 5. Installer ArgoCD

```bash
kubectl create namespace argocd
kubectl apply -n argocd --server-side --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=available --timeout=180s deployment --all -n argocd
```

`--server-side` est obligatoire (les CRDs d'ArgoCD dépassent la limite de taille d'annotation en `apply` classique).

Passer `argocd-server` en mode insecure (TLS géré par l'Ingress) :

```bash
kubectl patch configmap argocd-cmd-params-cm -n argocd --type merge \
  -p '{"data":{"server.insecure":"true"}}'
kubectl rollout restart deployment argocd-server -n argocd
```

**Mot de passe admin stable** (recommandé, évite de reproduire le piège `akadmin` documenté dans `notes-techniques.md` — sans ça, ArgoCD génère un mot de passe aléatoire à chaque install, jamais persisté) : restaurer le hash bcrypt déjà chiffré dans le dépôt plutôt que de garder celui généré à l'installation.

```bash
BCRYPT=$(sops -d --extract '["ARGOCD_ADMIN_PASSWORD_BCRYPT"]' gitops/secrets/argocd/argocd.sops.yaml)
kubectl patch secret argocd-secret -n argocd --type merge \
  -p "{\"stringData\":{\"admin.password\":\"$BCRYPT\",\"admin.passwordMtime\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}}"
kubectl delete secret argocd-initial-admin-secret -n argocd
```

Identifiants dans `gitops/secrets/argocd/argocd.sops.yaml` (hors GitOps, comme le bootstrap ArgoCD lui-même — ArgoCD ne peut pas déchiffrer via KSOPS un secret dont il a besoin pour exister).

## 6. Activer KSOPS (déchiffrement automatique des secrets)

```bash
kubectl create secret generic sops-age -n argocd \
  --from-file=keys.txt=$HOME/.config/sops/age/keys.txt

kubectl patch configmap argocd-cm -n argocd --type merge \
  -p '{"data":{"kustomize.buildOptions":"--enable-alpha-plugins --enable-exec"}}'

kubectl patch deployment argocd-repo-server -n argocd --type strategic \
  --patch-file gitops/bootstrap/argocd-repo-server-ksops-patch.yaml
```

## 7. Health check ArgoCD pour Prometheus Operator

ArgoCD ne fournit aucun health check intégré pour les CRDs de Prometheus Operator (`Prometheus`, `Alertmanager`, `ServiceMonitor`, `PrometheusRule`...) — sans ça, la ressource `Prometheus` de l'`Application` `monitoring` reste affichée "Unknown" (gris) dans l'UI même quand tout va bien en dessous, faute d'avis d'ArgoCD sur cette ressource.

```bash
kubectl patch configmap argocd-cm -n argocd --type merge \
  --patch-file gitops/bootstrap/argocd-cm-health-checks-patch.yaml
```

## 8. Bootstrap GitOps

```bash
kubectl apply -f gitops/bootstrap/root-app.yaml
kubectl apply -f gitops/bootstrap/argocd-ingress.yaml
```

À partir de là, tout le reste (monitoring, Authentik, futurs services) se synchronise automatiquement depuis `gitops/apps/` — plus aucune commande manuelle nécessaire pour les services eux-mêmes.

## 9. TLS local (mkcert) — nécessaire pour certains services

Certains services exigent HTTPS pour des raisons différentes selon le cas — Vaultwarden a besoin de l'API Subtle Crypto du navigateur, indisponible en HTTP sur un nom d'hôte personnalisé même pointé vers `127.0.0.1` (seuls `localhost`/`127.0.0.1` littéraux ou HTTPS comptent comme "contexte sécurisé") ; Nextcloud, lui, n'a pas cette contrainte pour son usage normal, mais son app SSO `user_oidc` refuse tout simplement de fonctionner en HTTP, quel que soit le navigateur ; Tuwunel, lui, fonctionne très bien en HTTP nu, mais le cookie de session que sa brique SSO pose pendant l'échange avec Authentik (`tuwunel_grant_session`) est marqué `Secure` — un navigateur le rejette silencieusement en HTTP, cassant la connexion (`"Missing cookie"` au retour de callback, constaté lors d'un test de connexion réel). Trois raisons différentes, même conséquence : ces services sont exposés en HTTPS sur le port 8453 plutôt qu'en HTTP sur 8090.

```bash
mkcert -install   # une fois par machine — installe une CA locale de confiance
mkcert -cert-file myown-vaultwarden.local.pem -key-file myown-vaultwarden.local-key.pem myown-vaultwarden.local
kubectl create secret tls vaultwarden-tls -n vaultwarden \
  --cert=myown-vaultwarden.local.pem --key=myown-vaultwarden.local-key.pem

mkcert -cert-file myown-nextcloud.local.pem -key-file myown-nextcloud.local-key.pem myown-nextcloud.local
kubectl create secret tls nextcloud-tls -n nextcloud \
  --cert=myown-nextcloud.local.pem --key=myown-nextcloud.local-key.pem

mkcert -cert-file myown-tuwunel.local.pem -key-file myown-tuwunel.local-key.pem myown-tuwunel.local
kubectl create secret tls tuwunel-tls -n tuwunel \
  --cert=myown-tuwunel.local.pem --key=myown-tuwunel.local-key.pem

mkcert -cert-file myown-livekit.local.pem -key-file myown-livekit.local-key.pem myown-livekit.local
kubectl create secret tls livekit-tls -n livekit \
  --cert=myown-livekit.local.pem --key=myown-livekit.local-key.pem

mkcert -cert-file myown-livekit-jwt.local.pem -key-file myown-livekit-jwt.local-key.pem myown-livekit-jwt.local
kubectl create secret tls livekit-jwt-tls -n livekit \
  --cert=myown-livekit-jwt.local.pem --key=myown-livekit-jwt.local-key.pem
```

Ces secrets sont volontairement **hors GitOps** (comme `sops-age`) : un certificat de dev est propre à chaque machine, pas quelque chose à committer ou à partager.

`lk-jwt-service` a en plus besoin de faire confiance à ce même CA mkcert pour ses propres requêtes sortantes vers Tuwunel (vérification du jeton OpenID, découverte `.well-known`) — le conteneur ne fait pas confiance au magasin de certs de l'hôte par défaut. Un `ConfigMap` (pas un `Secret`, le CA est public) monté dans le pod via `SSL_CERT_FILE` :

```bash
kubectl create configmap mkcert-ca -n livekit --from-file=ca.pem="$(mkcert -CAROOT)/rootCA.pem"
```

Même besoin pour Uptime Kuma (Phase 3.5, notification Matrix vers Tuwunel) — un `ConfigMap` séparé, un par namespace :

```bash
kubectl create configmap mkcert-ca -n monitoring --from-file=ca.pem="$(mkcert -CAROOT)/rootCA.pem"
```

**Si le navigateur affiche quand même "non sécurisé" après `mkcert -install`** (vécu avec Chromium/Firefox installés en snap — cas fréquent sur Ubuntu) :

- `mkcert -install` peut répondre "already installed" sans avoir réellement rien fait : les navigateurs snap utilisent leur propre profil isolé (`~/snap/firefox/common/.mozilla/...`, `~/snap/chromium/<revision>/.local/share/pki/nssdb`), pas les emplacements standards. Vérifier avec `certutil -L -d sql:<chemin du profil>` que `mkcert development CA` y figure bien avec les droits `CT,C,C`.
- Même avec cette entrée correcte, les versions récentes de Chrome/Chromium (Chrome Root Store) peuvent ignorer le magasin NSS système pour la validation TLS. Solution fiable : `chrome://certificate-manager` → **Personnalisé (installé par vous)** → **Certificats approuvés** → importer directement `$(mkcert -CAROOT)/rootCA.pem`. La section "Linux" du même écran peut lister le certificat mkcert en tant qu'« intermédiaire » sans qu'il serve réellement d'ancre de confiance — l'import manuel dans "Certificats approuvés" est ce qui a résolu le problème.
- Toujours quitter le navigateur **complètement** (vérifier qu'aucun processus ne reste : `ps aux | grep -i chromium`) avant de retester — fermer la fenêtre ne suffit pas, le profil réel n'est relu qu'au prochain vrai démarrage.

## 10. Accès local

Ajouter à `/etc/hosts` (une ligne par service exposé — voir `gitops/apps/*.yaml` pour la liste à jour) :

```
127.0.0.1 myown-argocd.local
127.0.0.1 myown-grafana.local
127.0.0.1 myown-uptime.local
127.0.0.1 myown-authentik.local
127.0.0.1 myown-vaultwarden.local
127.0.0.1 myown-nextcloud.local
127.0.0.1 myown-immich.local
127.0.0.1 myown-tuwunel.local
127.0.0.1 myown-livekit.local
127.0.0.1 myown-livekit-jwt.local
127.0.0.1 myown-jellyfin.local
```

## 11. Vérification

```bash
kubectl get application -n argocd
```

Toutes les `Application` doivent converger vers `Synced`/`Healthy` (quelques minutes le temps que les images se téléchargent). Détail de chaque service et de ses identifiants : [`manuel-utilisateur.md`](manuel-utilisateur.md).

## 12. VPN d'accès admin (WireGuard, optionnel en dev)

Pas requis pour utiliser le cluster de dev — pertinent surtout à partir du vrai déploiement (mini PC, Phase 4), où ArgoCD/`kubectl`/SSH ne doivent jamais être exposés directement sur internet (`architecture.md` §6/§11). Volontairement **hors GitOps** (service systemd sur l'hôte, pas un manifeste k8s — cf. [`wireguard/README.md`](../wireguard/README.md) pour le raisonnement).

```bash
scripts/wireguard-setup.sh
```

Nécessite `sudo` de façon interactive (installation du paquet, écriture dans `/etc/wireguard/`, activation du service) — à lancer directement dans votre terminal. Écrit la config serveur chiffrée dans `wireguard/wg0.conf.sops.yaml` et une config cliente locale (jamais commitée) à transférer à votre appareil. Relancer le même script avec `MYOWN_WG_PEER_NAME=<nom>` ajoute un nouveau pair sans toucher à la configuration existante.

## 13. Jellyfin — droits admin via Authentik

Après `scripts/jellyfin-sso-setup.py` (installe/configure le plugin SSO, voir `notes-techniques.md`) : un compte connecté via Authentik est créé automatiquement au premier login, mais **sans les droits administrateur** tant qu'il n'appartient pas au groupe Authentik `jellyfin-admins` (nom par défaut attendu par le plugin) — sans ça, "Bibliothèques" et le reste du tableau de bord restent invisibles dans l'IHM, même une fois connecté.

Ajouter le compte admin du foyer à ce groupe (`ak shell` sur le pod `authentik-server`, groupe créé automatiquement s'il n'existe pas encore) :

```python
from authentik.core.models import User, Group
u = User.objects.get(username='<votre nom d’utilisateur Authentik>')
g, _ = Group.objects.get_or_create(name='jellyfin-admins')
g.users.add(u)
```

La synchronisation des droits se fait à la connexion, pas en direct sur une session déjà ouverte — se déconnecter/reconnecter côté Jellyfin après ce changement. Le compte local `admin` (mot de passe dans `gitops/secrets/jellyfin/jellyfin.sops.yaml`) reste utilisable en secours sans attendre cette étape.

## 14. Installation en production (mini PC, k3s bare-metal)

Tout ce qui précède (sections 2-13) décrit le cluster de dev (**k3d**, k3s conteneurisé dans Docker). Sur le vrai mini PC (Phase 4), la cible est un **k3s bare-metal mono-nœud** — `architecture.md` §6, jamais k3d. Validé de bout en bout le 2026-08-20 sur le premier mini PC (Dell OptiPlex). Différences réelles par rapport au parcours dev :

### 14.1 Cluster

Pas de Docker requis pour le cluster lui-même (k3s embarque son propre containerd) :

```bash
curl -sfL https://get.k3s.io | sh -
mkdir -p ~/.kube
sudo cat /etc/rancher/k3s/k3s.yaml | sed "s/127.0.0.1/<IP LAN du nœud>/" > ~/.kube/config
chmod 600 ~/.kube/config
export KUBECONFIG=~/.kube/config   # + ajouter à ~/.bashrc pour les sessions interactives
kubectl get nodes   # Ready après quelques dizaines de secondes
```

`kubectl` de k3s (`/usr/local/bin/kubectl`, un symlink vers le binaire `k3s`) ne lit **pas** `~/.kube/config` par défaut comme un vrai `kubectl` — toujours passer par `$KUBECONFIG` explicitement (sinon il retombe sur `/etc/rancher/k3s/k3s.yaml`, illisible sans `sudo`).

### 14.2 Traefik — pas à déployer, à reconfigurer

k3s embarque Traefik par défaut (contrairement à k3d qui ne fournit qu'un load balancer nu) — inutile de le déployer via GitOps. Le Service Traefik généré par le Helm-controller de k3s écoute déjà nativement sur 80/443 (couvre le port 443 littéral requis par LiveKit/MatrixRTC, section 4 — rien à faire pour ça).

Pour les ports 8090/8453 (remplace le mapping de ports Docker de k3d), un Service `LoadBalancer` séparé (ne touche pas au Service géré par Helm, pour survivre à une reconciliation) : `gitops/bootstrap/traefik-external-svc.yaml`. Comme `traefik-internal-svc.yaml`/`coredns-custom.yaml` déjà utilisés en dev (section 6), ces trois fichiers sont hors GitOps, à appliquer manuellement :

```bash
kubectl apply -f gitops/bootstrap/traefik-external-svc.yaml
kubectl apply -f gitops/bootstrap/traefik-internal-svc.yaml
kubectl apply -f gitops/bootstrap/coredns-custom.yaml
kubectl rollout restart deployment coredns -n kube-system
```

Le nœud répond alors directement sur son IP LAN réelle (`k3s`'s ServiceLB/klipper) : `myown-*.local` doit résoudre vers cette IP (pas `127.0.0.1`) partout où ces services sont utilisés — `/etc/hosts` du/des poste(s) client(s) (section 10), pas seulement du serveur.

LiveKit n'a besoin d'aucun ajustement : ses ports RTC (`podHostNetwork: true`) se bindent directement sur la vraie interface du nœud, sans la couche de port-mapping Docker qu'il fallait pour k3d.

### 14.3 Étapes identiques

Sections 5 (ArgoCD), 6 (KSOPS — la clé age doit être **restaurée** depuis sa sauvegarde sur cette nouvelle machine, jamais régénérée), 7 (health check Prometheus Operator), 8 (bootstrap GitOps), 9 (mkcert) s'appliquent telles quelles. `scripts/install.sh` automatise ce chemin **k3d** uniquement à ce stade — pas encore adapté pour créer un vrai cluster k3s bare-metal (section 14.1 ci-dessus), à faire à la main jusqu'à ce que le script soit étendu et testé sur ce chemin.

### 14.4 Stockage `hostPath` — le dossier doit exister avec les bonnes permissions **avant** le premier démarrage

Nextcloud (`gitops/apps/nextcloud.yaml`, `persistence.hostPath`) monte un `hostPath` de type `Directory` — n'est **jamais créé automatiquement**, contrairement à Immich (`DirectoryOrCreate`, se crée tout seul). Sur le cluster de dev, ce dossier existait déjà de longue date (créé pendant la migration de données, `notes-techniques.md`) — jamais rejoué sur une machine neuve avant ce premier déploiement bare-metal, où l'absence de ce dossier a fait échouer le pod (`FailedMount`).

**Point critique trouvé en le faisant pour de vrai** : créer le dossier avec un simple `mkdir` ne suffit pas — il doit appartenir au groupe `www-data` (gid 33, celui du `fsGroup` du pod) avec droits d'écriture de groupe, **avant** le tout premier démarrage du conteneur. Sans ça, le tout premier `occ maintenance:install` automatique du conteneur échoue en écriture (`Cannot write into "config" directory!`), laisse un `config.php` vide, et plus aucune tentative d'auto-installation ne se redéclenche ensuite (l'entrypoint ne réinstalle jamais tant que ce fichier existe, même vide) — piège découvert après une bonne heure de diagnostic en aval (voir `notes-techniques.md`, section Nextcloud). Fait dès le départ, l'auto-installation standard du conteneur (pilotée par `NEXTCLOUD_ADMIN_USER`/`NEXTCLOUD_ADMIN_PASSWORD`, déjà câblés via `existingSecret`) se déroule normalement, sans intervention manuelle :

```bash
sudo mkdir -p /var/lib/rancher/k3s/storage/myown/nextcloud-data
sudo chown root:33 /var/lib/rancher/k3s/storage/myown/nextcloud-data
sudo chmod g+rwx /var/lib/rancher/k3s/storage/myown/nextcloud-data
```

### 14.5 Vérification

Identique à la section 11 — sur un cluster tout juste créé, les `Application` ArgoCD des services avec un `CronJob` de backup Restic (Vaultwarden, Nextcloud, Immich, Tuwunel, Authentik, Jellyfin) restent affichées `Progressing` jusqu'au lendemain matin : leur PVC de dépôt Restic reste `Pending` (`WaitForFirstConsumer`) tant que le `CronJob` n'a pas eu son tout premier passage planifié — pas un vrai problème, ça se résout tout seul (détail dans `notes-techniques.md`). Vérifier plutôt directement les endpoints HTTP de chaque service (`manuel-utilisateur.md`) en attendant.

## 15. Nextcloud — dossier partagé familial (app Group Folders)

Pour que plusieurs comptes personnels (SSO) puissent déposer dans un même dossier — au lieu d'un compte unique dédié — plutôt qu'une app tierce, Nextcloud a une app officielle faite pour ça (`groupfolders`). Utilisé notamment pour la médiathèque lue par Jellyfin (`gitops/apps/jellyfin.yaml`, `persistence.media.hostPath`).

```bash
php occ app:install groupfolders   # déjà dans le hook before-starting de nextcloud.yaml, idempotent
php occ group:add famille
php occ group:adduser famille <utilisateur>   # une fois par membre à ajouter
php occ groupfolders:create Mediatheque
php occ groupfolders:group <id-affiché> famille read write share delete
```

**Étape critique, sinon `403 Forbidden` sur tout dépôt de fichier** (voir `notes-techniques.md` pour le diagnostic complet) : ces commandes `occ`, lancées via `kubectl exec` (root par défaut), créent le dossier sur disque appartenant à `root:root` — inutilisable par les workers Apache réels, qui tournent en `www-data`. Corriger avant tout usage réel :

```bash
sudo chown -R www-data:www-data <hostPath Nextcloud>/data/__groupfolders
```

Le chemin réel sur disque (nécessaire si un autre service doit lire ce dossier, comme Jellyfin) : `<hostPath Nextcloud>/data/__groupfolders/<id>/files` — l'`id` est attribué à la création, pas prévisible à l'avance, à vérifier avec `php occ groupfolders:list --output=json` plutôt que deviné. Le `/files` final est nécessaire : un dossier de groupe a cette structure interne (`files/`, `trash/`, `versions/`), contrairement au dossier personnel classique d'un utilisateur.

Bibliothèques Jellyfin correspondantes (pas de mécanisme déclaratif — même limitation que le reste de la première config Jellyfin, `scripts/jellyfin-sso-setup.py`) :

```bash
curl -X POST "http://<jellyfin>/Library/VirtualFolders?name=Films&collectionType=movies" \
  -H "X-Emby-Authorization: ...Token=\"<token admin>\"" -H "Content-Type: application/json" \
  -d '{"LibraryOptions":{"PathInfos":[{"Path":"/media/files/Films"}]}}'
```

## 16. Nom de domaine réel + Let's Encrypt (Gandi, DNS-01)

Phase 4 : bascule des certificats `mkcert` (dev) vers de vrais certificats Let's Encrypt sur un nom de domaine réel. DNS-01 via l'API Gandi (pas HTTP-01) — pas besoin d'exposer le port 80, permet un certificat **wildcard** unique (`*.<domaine>` + apex) plutôt qu'un certificat par service. Détail complet du choix technique (pourquoi `cert-manager` a été écarté, comment le wildcard est réutilisé par tous les futurs services) dans `notes-techniques.md`.

**1. Token Gandi** — Personal Access Token scopé **LiveDNS uniquement**, restreint au domaine si possible (admin.gandi.net → profil → Sécurité → Personal Access Tokens). Ne jamais utiliser l'ancienne clé API (`GANDIV5_API_KEY`), dépréciée.

**2. Secret kube-system (bootstrap, hors GitOps — même statut que `sops-age`)** :

```bash
kubectl create secret generic gandi-dns-credentials -n kube-system --from-file=token=<fichier contenant le PAT>
```

**3. Résolveur ACME Traefik** — `kubectl apply -f gitops/bootstrap/traefik-acme-helmchartconfig.yaml` (overlay du `HelmChart` Traefik géré par k3s, ne jamais éditer ce dernier directement). Valider d'abord sur le serveur **staging** Let's Encrypt (`caServer` dans le fichier) avant de rebasculer en production — évite de brûler les quotas de production tant que le flow DNS-01/Gandi n'est pas prouvé. Après validation, retirer `caServer` (défaut Traefik = production), ré-appliquer, **et purger le certificat staging déjà en cache** avant de redémarrer, sinon Traefik continue de servir l'ancien certificat non reconnu :

```bash
POD=$(kubectl get pods -n kube-system -l app.kubernetes.io/name=traefik -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n kube-system "$POD" -- rm -f /data/acme.json
kubectl rollout restart deployment traefik -n kube-system
```

**4. DynDNS** — Free (Freebox) ne propose pas d'IP fixe ici (vérifié : pas d'option "IP fixe", fonctionnalité native "DNS dynamique" présente mais inutilisée). `gitops/apps/gandi-dyndns.yaml` maintient les enregistrements `@`/`*` à jour (CronJob, toutes les 5 min). Nécessite son propre secret SOPS (`gitops/secrets/gandi-dyndns/gandi-dyndns.sops.yaml`, clé `GANDIV5_PERSONAL_ACCESS_TOKEN`, même PAT que l'étape 1).

**5. Port-forward Freebox** — `mafreebox.freebox.fr` → Paramètres avancés → **Gestion des ports** → rediriger le port **443/tcp uniquement** (pas 80, inutile pour DNS-01) vers l'IP LAN du mini PC.

**Vérification** :

```bash
dig +short A <sous-domaine> @ns1.gandi.net   # résolution DNS publique
echo | openssl s_client -connect <IP mini PC>:8453 -servername <sous-domaine> 2>/dev/null | openssl x509 -noout -issuer
```

**6. SSO vers les hostnames publics** — pour qu'une connexion SSO externe aboutisse (pas juste que la page charge), deux étapes supplémentaires par service intégré (Vaultwarden, Nextcloud, Immich, Tuwunel, Jellyfin) :

- **DNS split-horizon d'abord** (`gitops/bootstrap/coredns-custom.yaml`, bloc `offsystem.override`) : sans ça, les appels serveur-à-serveur vers Authentik sortiraient par la Freebox pour revenir dessus. Réappliquer + `kubectl rollout restart deployment coredns -n kube-system`.
- Basculer `authority`/`discoveryuri`/`issuer_url` de chaque service vers `authentik.offsystem.fr` (jamais `myown-authentik.local` — Authentik reflète le `Host` de la requête de découverte dans la redirection de connexion elle-même). **Jamais `server_name` pour Tuwunel** — seuls `issuer_url`/`callback_url`.
- Ajouter (pas remplacer, sauf Tuwunel dont `callback_url` est un champ unique) une entrée `redirect_uris` par blueprint Authentik pour le nouveau callback public.

Voir `notes-techniques.md`, section "Migration SSO vers les hostnames publics", pour les bugs réels rencontrés par service (Vaultwarden : réassociation SQLite nécessaire ; Jellyfin : `ForceHttpsRedirect`).

**Piège critique, à ne jamais oublier sur une installation dont `root` suit un tag épinglé (mini PC)** : ne **jamais** réactiver `syncPolicy`/`selfHeal` après des tests en direct sans avoir d'abord coupé une release et rejoué `scripts/pin-release.sh` — sinon ArgoCD réécrase silencieusement tout ce qui vient d'être validé en direct dès la resynchronisation, sans que l'UI ne signale de régression (`Synced`/`Healthy` reste affiché).
