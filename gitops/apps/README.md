# apps/

App-of-apps de MyOwn, sous forme d'un petit chart Helm rendu par l'Application `root` (`gitops/bootstrap/root-app.yaml`).

- `templates/` : une `Application` ArgoCD par service (Authentik, Vaultwarden, Nextcloud, …), chacune pointant vers son chart upstream et, pour ses secrets et manifestes, vers ce dépôt.
- `values.yaml` :
  - `revision` : révision git que chaque Application utilise pour ses propres sources vers ce dépôt. `root` la remplace par la révision qu'il suit lui-même (`$ARGOCD_APP_SOURCE_TARGET_REVISION`) : `master` sur le cluster de dev, le tag de release en production. Suivre un tag fige donc tout l'arbre, secrets compris.
  - `domain` : domaine de l'installation, **obligatoire** (le rendu échoue sans lui). Transmis aux valeurs Helm des services et à chaque dossier de `gitops/manifests/` qui en a besoin (ces dossiers sont de petits charts recevant `domain`). Posé par l'installeur dans les valeurs de `root`.
  - `repoURL` : dépôt suivi par toutes les sources vers ce dépôt (celui du projet, ou un fork).
  - `apps` : Applications à déployer. Par défaut toutes ; `scripts/install.sh` y écrit les services choisis à l'installation.

**Ajouter un service** : créer `templates/<app>.yaml` en reprenant un fichier existant — encadré par `{{- if has "<app>" .Values.apps }}` / `{{- end }}`, `repoURL: {{ .Values.repoURL }}` + `targetRevision: {{ .Values.revision }}` sur chaque source qui pointe vers ce dépôt, et `{{ include "myown.domain" . }}` partout où le domaine apparaît (jamais `master` ni un domaine en dur). Un dossier de `gitops/manifests/` qui a besoin du domaine doit être un chart (`Chart.yaml`, `templates/`) et recevoir `helm.valuesObject.domain`. L'ajouter ensuite à `apps` dans `values.yaml` et au catalogue de l'installeur (`scripts/lib/services.sh`) — l'installeur refuse de tourner si un template n'y est rattaché à aucun service.

Vérifier le rendu en local, sans cluster :

```bash
helm template x gitops/apps --set revision=v0.1.22 --set domain=exemple.fr
```
