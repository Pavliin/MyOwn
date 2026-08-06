# apps/

Un fichier `Application` ArgoCD par service (Traefik, Authentik, monitoring, Vaultwarden, …), chacun pointant vers son chart Helm upstream et son fichier de valeurs. Le `root` app (`gitops/bootstrap/root-app.yaml`) surveille ce dossier automatiquement — ajouter un fichier ici suffit à faire déployer le service correspondant, aucune étape manuelle supplémentaire dans le cluster.
