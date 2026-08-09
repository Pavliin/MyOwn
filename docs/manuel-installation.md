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
k3d cluster create myown-dev -p "8090:80@loadbalancer" -p "8453:443@loadbalancer" --wait
kubectl config use-context k3d-myown-dev
```

Le mapping de ports doit être fait **à la création** — impossible à ajouter après coup sans recréer le cluster.

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

## 6. Activer KSOPS (déchiffrement automatique des secrets)

```bash
kubectl create secret generic sops-age -n argocd \
  --from-file=keys.txt=$HOME/.config/sops/age/keys.txt

kubectl patch configmap argocd-cm -n argocd --type merge \
  -p '{"data":{"kustomize.buildOptions":"--enable-alpha-plugins --enable-exec"}}'

kubectl patch deployment argocd-repo-server -n argocd --type strategic \
  --patch-file gitops/bootstrap/argocd-repo-server-ksops-patch.yaml
```

## 7. Bootstrap GitOps

```bash
kubectl apply -f gitops/bootstrap/root-app.yaml
kubectl apply -f gitops/bootstrap/argocd-ingress.yaml
```

À partir de là, tout le reste (monitoring, Authentik, futurs services) se synchronise automatiquement depuis `gitops/apps/` — plus aucune commande manuelle nécessaire pour les services eux-mêmes.

## 8. TLS local (mkcert) — nécessaire pour certains services

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
```

Ces secrets sont volontairement **hors GitOps** (comme `sops-age`) : un certificat de dev est propre à chaque machine, pas quelque chose à committer ou à partager.

**Si le navigateur affiche quand même "non sécurisé" après `mkcert -install`** (vécu avec Chromium/Firefox installés en snap — cas fréquent sur Ubuntu) :

- `mkcert -install` peut répondre "already installed" sans avoir réellement rien fait : les navigateurs snap utilisent leur propre profil isolé (`~/snap/firefox/common/.mozilla/...`, `~/snap/chromium/<revision>/.local/share/pki/nssdb`), pas les emplacements standards. Vérifier avec `certutil -L -d sql:<chemin du profil>` que `mkcert development CA` y figure bien avec les droits `CT,C,C`.
- Même avec cette entrée correcte, les versions récentes de Chrome/Chromium (Chrome Root Store) peuvent ignorer le magasin NSS système pour la validation TLS. Solution fiable : `chrome://certificate-manager` → **Personnalisé (installé par vous)** → **Certificats approuvés** → importer directement `$(mkcert -CAROOT)/rootCA.pem`. La section "Linux" du même écran peut lister le certificat mkcert en tant qu'« intermédiaire » sans qu'il serve réellement d'ancre de confiance — l'import manuel dans "Certificats approuvés" est ce qui a résolu le problème.
- Toujours quitter le navigateur **complètement** (vérifier qu'aucun processus ne reste : `ps aux | grep -i chromium`) avant de retester — fermer la fenêtre ne suffit pas, le profil réel n'est relu qu'au prochain vrai démarrage.

## 9. Accès local

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
```

## 10. Vérification

```bash
kubectl get application -n argocd
```

Toutes les `Application` doivent converger vers `Synced`/`Healthy` (quelques minutes le temps que les images se téléchargent). Détail de chaque service et de ses identifiants : [`manuel-utilisateur.md`](manuel-utilisateur.md).
