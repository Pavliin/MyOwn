# apps/

App-of-apps de MyOwn, sous forme d'un petit chart Helm rendu par l'Application `root` (`gitops/bootstrap/root-app.yaml`).

- `templates/` : une `Application` ArgoCD par service (Authentik, Vaultwarden, Nextcloud, …), chacune pointant vers son chart upstream et, pour ses secrets et manifestes, vers ce dépôt.
- `values.yaml` :
  - `revision` : révision git que chaque Application utilise pour ses propres sources vers ce dépôt. `root` la remplace par la révision qu'il suit lui-même (`$ARGOCD_APP_SOURCE_TARGET_REVISION`) : `master` sur le cluster de dev, le tag de release en production. Suivre un tag fige donc tout l'arbre, secrets compris.
  - `apps` : Applications à déployer. Par défaut toutes ; `scripts/install.sh` y écrit les services choisis à l'installation.

**Ajouter un service** : créer `templates/<app>.yaml` en reprenant un fichier existant — encadré par `{{- if has "<app>" .Values.apps }}` / `{{- end }}`, et `targetRevision: {{ .Values.revision }}` sur chaque source qui pointe vers ce dépôt (jamais `master` en dur). L'ajouter ensuite à `apps` dans `values.yaml` et au catalogue de l'installeur (`scripts/lib/services.sh`) — l'installeur refuse de tourner si un template n'y est rattaché à aucun service.

Vérifier le rendu en local, sans cluster :

```bash
helm template x gitops/apps --set revision=v0.1.22
```
