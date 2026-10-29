# Un acte de possession numérique

Projet de cloud personnel auto-hébergé — fichiers, photos/vidéos, mots de passe, messagerie et mail, hébergés localement plutôt que chez Google/Meta/Microsoft, pour un usage personnel et un cercle proche (famille, amis).

Statut actuel : en usage réel sur un mini PC à la maison (mots de passe, fichiers, photos, messagerie et appels, mail, IA locale). En cours : l'installeur, pour qu'un autre foyer puisse installer MyOwn chez lui sans dépendre de l'installation de l'auteur.

## Ce qu'il faut pour l'installer

- **Une machine** allumée en permanence à la maison (un mini PC suffit, voir [`docs/materiel.md`](docs/materiel.md)).
- **Un nom de domaine** (une dizaine d'euros par an), chez un fournisseur dont le DNS se pilote par API ([liste de lego](https://go-acme.github.io/lego/dns/) : Gandi, OVH, Infomaniak, Cloudflare…). Il donne de vrais certificats sans rien ouvrir vers internet.
- **Deux niveaux au choix**, modifiables ensuite sans rien perdre : **B**, services joignables à la maison seulement, rien d'ouvert vers internet ; **C**, joignables partout (redirections de ports sur la box), seul niveau qui permet le mail — avec en plus un petit serveur relais loué.

**Pour essayer sans acheter de domaine** : un sous-domaine gratuit `<nom>.dedyn.io` de [deSEC](https://desec.io) suffit pour le niveau B. Limites : les comptes de messagerie (`@marie:<nom>.dedyn.io`) seraient à recréer si l'on passe ensuite à un vrai domaine, le mail n'y est pas crédible, et deSEC a suspendu la création de ces sous-domaines en octobre 2026, sans date de reprise.

Détail : [`docs/installation-utilisateur.md`](docs/installation-utilisateur.md) (choix et niveaux) et [`docs/manuel-installation.md`](docs/manuel-installation.md) (procédure).

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
