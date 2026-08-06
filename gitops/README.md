# GitOps

Pattern app-of-apps. ArgoCD ne surveille qu'un seul point d'entrée (`bootstrap/root-app.yaml`), qui à son tour surveille `apps/` : chaque service du projet a son propre manifest `Application` dans ce dossier, qui pointe vers son chart Helm (upstream, communautaire) et son fichier de valeurs.

- `bootstrap/` — l'`Application` racine, seul objet installé manuellement (une fois) dans le cluster
- `apps/` — un manifest `Application` par service ; c'est le seul dossier qui grandit à mesure que la roadmap avance

Rien dans `apps/` pour l'instant — le bootstrap est fonctionnel mais vide, c'est attendu à ce stade (cf. `docs/roadmap.md`, Phase 0).
