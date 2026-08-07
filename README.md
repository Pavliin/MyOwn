# Un acte de possession numérique

Projet de cloud personnel auto-hébergé — fichiers, photos/vidéos, mots de passe, messagerie et mail, hébergés localement plutôt que chez Google/Meta/Microsoft, pour un usage personnel et un cercle proche (famille, amis).

Statut actuel : **Phase 0 (Socle) en cours**, sur un cluster de développement local — GitOps/ArgoCD, monitoring et SSO (Authentik) opérationnels. Pas encore de mini PC ni de nom de domaine réel.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — vision, principes directeurs, stack technique complète, sécurité, sauvegarde, risques assumés
- [`docs/roadmap.md`](docs/roadmap.md) — plan de développement phase par phase, avec critères de sortie
- [`docs/pitch.md`](docs/pitch.md) — présentation technique du projet
- [`docs/vision-long-terme.md`](docs/vision-long-terme.md) — pistes d'évolution à garder en tête (hors scope du POC actuel)
- [`docs/notes-techniques.md`](docs/notes-techniques.md) — état réel du déployé, choix de config, difficultés rencontrées
- [`docs/manuel-installation.md`](docs/manuel-installation.md) — étapes d'une première installation
- [`docs/manuel-utilisateur.md`](docs/manuel-utilisateur.md) — comment utiliser chaque service déployé

## Principes

Open source, sobre, accessible aux non-technophiles, chiffré, exploité avec de vraies pratiques SRE (GitOps, sauvegardes testées, monitoring) plutôt qu'en hobby. Détail dans [`architecture.md`](docs/architecture.md#2-principes-directeurs).

## Licence

[AGPL-3.0](LICENSE) — toute réutilisation, y compris en mode service réseau, doit rester open source.
