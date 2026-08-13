# Plan de développement

Horizon visé : MVP démontrable à 3-6 mois (mots de passe + fichiers/photos + messagerie). Le mail est traité en dernier compte tenu de sa complexité, mais reste dans le périmètre du MVP élargi.

## Phase 0 — Socle d'infrastructure

Objectif : avoir une plateforme k3s opérationnelle, pilotée en GitOps, avant de déployer le moindre service applicatif.

- Installation k3s (mono-nœud)
- Environnement de dev miroir (k3d/kind) sur poste personnel
- ArgoCD connecté à ce dépôt Git
- Traefik (ingress + TLS) — certificats locaux (mkcert) en dev ; bascule vers Let's Encrypt avec le vrai domaine en Phase 4
- Prometheus + Grafana + Uptime Kuma
- Authentik (SSO/OIDC) — brique transverse, condition préalable à un onboarding simple des autres services
- Stratégie de secrets (SOPS ou Sealed Secrets) tranchée et mise en place

**Critère de sortie** : un service de test déployé via ArgoCD, exposé en HTTPS, protégé par SSO Authentik, visible dans Grafana/Uptime Kuma.

## Phase 1 — Mots de passe (Vaultwarden)

Objectif : premier service réel livré, risque faible, valeur immédiate.

- Déploiement Vaultwarden + intégration Authentik
- Sauvegarde Restic vers le nœud ami (première mise en place du pipeline de sauvegarde, réutilisée ensuite pour tous les services)
- Test de restauration

(App Android : différée à la Phase 4, qui regroupe tout ce qui nécessite l'infra réelle — mini PC + domaine.)

**Critère de sortie** : usage quotidien réel par l'auteur (dogfooding), sauvegarde/restauration validée.

## Phase 2 — Fichiers et photos (Nextcloud + Immich)

Objectif : couvrir le cas d'usage le plus visible pour convaincre (remplacement concret de Google Drive/Photos).

- Déploiement Nextcloud (fichiers, contacts, calendrier) + Immich (photos/vidéos)
- Intégration Authentik
- Sauvegarde Restic étendue à ces services
- Test avec 2-3 utilisateurs réels (famille proche) hors auteur

(Apps Android + backup automatique photos/vidéos en conditions réelles : différés à la Phase 4.)

**Critère de sortie** : migration effective des photos/fichiers d'au moins un membre de la famille.

## Phase 3 — Messagerie (Tuwunel + Element X + LiveKit)

Objectif : couvrir l'usage courant (groupes, appels vidéo à 3-4) avec un candidat crédible au remplacement de WhatsApp pour le cercle du projet.

- Déploiement Tuwunel (remplace Conduwuit, archivé/mort en amont — voir `docs/architecture.md` §5.5 et `docs/notes-techniques.md`)
- Déploiement LiveKit (appels vidéo de groupe)
- Test des appels vidéo de groupe en conditions réelles (3-4 participants, en LAN)

(App Android Element X et test de fédération avec un second serveur Matrix externe : différés à la Phase 4 — le premier a le même problème de résolution DNS locale sur mobile que les autres apps Android, le second nécessite une joignabilité publique réelle.)

**Critère de sortie** : un groupe familial migré sur la messagerie pour les échanges courants, appel vidéo de groupe fonctionnel.

**→ Point de démonstration MVP aux amis techos** (mdp + fichiers/photos + messagerie fonctionnels).

## Phase 3.5 — Préparation sans attendre l'infra réelle

Objectif : construire et valider sur le cluster de dev tout ce qui ne dépend ni du mini PC ni du nom de domaine (Phase 4), pendant que le matériel est en cours d'acquisition — pas de temps mort avant la bascule.

- Monitoring famille : moniteurs Uptime Kuma pour les services existants + page de statut publique
- Bot Tuwunel dédié : salon partagé "État du système" (alerting Uptime Kuma → Tuwunel) — mécanisme réutilisé tel quel par les propositions Ollama en Phase 5
- Déploiement Ollama + connecteur IMAP de tri/résumé mail, prototypé contre une boîte mail existante (pas besoin de Mailcow réel pour valider le connecteur)
- Extraction d'événements/tâches depuis les mails → Calendrier/Tasks Nextcloud, avec validation explicite par DM Tuwunel
- Script installeur (développé et testé contre une VM jetable ou un nouveau cluster k3d, pas le mini PC réel) — rejoue `manuel-installation.md`
- Prototype du modèle de comptes admin (secrets poussés dans Vaultwarden après le premier login) contre l'Authentik/Vaultwarden du cluster de dev
- Manifests WireGuard déployés et validés structurellement en dev — le test réel "depuis l'extérieur du LAN" attend le mini PC (Phase 4)

**Critère de sortie** : tout ce qui précède fonctionne sur le cluster de dev. Au basculement vers le mini PC réel (Phase 4), il ne reste plus qu'à migrer une configuration déjà validée, pas à la développer from scratch.

## Phase 4 — Bascule vers l'infra réelle & Mail

Objectif : quitter le cluster de dev pour la vraie infrastructure (mini PC + domaine) — le premier composant, Mail, en a de toute façon besoin dès le départ, donc cette bascule sert aussi à débloquer d'un coup toutes les validations différées des phases précédentes, avant de livrer la brique la plus complexe techniquement.

- Achat et mise en service du mini PC, migration du cluster GitOps du dev (k3d) vers le mini PC (mêmes manifests, changement de cible uniquement)
- Acquisition du nom de domaine, bascule Traefik vers Let's Encrypt réel (remplace les certificats mkcert du dev)
- **Accès distant admin** : VPN WireGuard auto-hébergé (pas de dépendance tierce type Tailscale, cohérent avec `architecture.md` §1) — aucun outil d'administration (ArgoCD, `kubectl`, SSH) exposé directement sur internet, tout passe par le VPN. Mitige le risque déjà assumé d'indisponibilité de l'admin (`architecture.md` §11) : déblocage à distance via le VPN, ou guidage téléphonique de quelqu'un sur place en cas de panne matérielle complète.
- **Monitoring famille** : configuration des moniteurs Uptime Kuma pour tous les services réels + publication d'une page de statut publique, intégrée au dashboard familial (Phase 6, cf. `installation-utilisateur.md`) — pas de Grafana pour la famille, réservé à l'admin.
- **Alerting admin** : bot Tuwunel dédié, salon Matrix partagé "État du système" (public/abonnable par qui veut dans le foyer, une seule occurrence de l'info) — Uptime Kuma y notifie les pannes. Réutilisé tel quel en Phase 5 pour les propositions Ollama, mais en DM privé strictement séparé de ce salon partagé (propositions personnelles, jamais dans un canal commun).
- Validation des items différés, désormais débloqués par l'exposition internet réelle :
  - App Android Vaultwarden (Phase 1)
  - Apps Android Nextcloud + Immich, backup automatique photos/vidéos en conditions réelles (Phase 2)
  - App Android Element X, test de fédération Matrix avec un second serveur externe (Phase 3)
- Provisionnement du VPS façade (Hetzner/OVH/Scaleway), configuration Postfix relay + SPF/DKIM/DMARC
- Déploiement Mailcow à domicile, connexion au relais VPS
- Migration progressive des correspondants (soi-même d'abord, en parallèle d'un compte existant le temps de valider la délivrabilité)
- Suivi de délivrabilité (tests d'envoi vers Gmail/Outlook, monitoring des blacklists)

**Critère de sortie** : tous les services précédemment validés en dev tournent sur le mini PC réel, toutes les validations différées sont passées avec succès, et le mail est envoyé/reçu de façon fiable vers/depuis Gmail et Outlook sur une période de test soutenue (pas de classement spam systématique).

## Phase 5 — Intelligence locale (Ollama)

Objectif : premier cas d'usage concret de la couche d'intégration IA, une fois le mail stable. Assistant en tâche de fond, pas de chat — dans l'esprit des fonctionnalités d'assistant ambiant type Apple Intelligence. Principe appliqué à toute action qui modifie une donnée : **l'IA propose, l'utilisateur valide**, jamais d'écriture automatique silencieuse.

- Déploiement Ollama + choix du modèle selon RAM disponible (nom exact à trancher au moment de l'implémentation — le paysage des petits modèles open évolue vite, pas figé aujourd'hui)
- Connecteur IMAP → tri/résumé automatique des mails
- Extraction d'événements/tâches depuis les mails → proposition d'ajout au Calendrier/Tasks Nextcloud (CalDAV), écriture uniquement après validation explicite
- Rappels basés sur les événements du calendrier
- Canal de proposition/validation pour ces deux derniers points : réutilise le bot Tuwunel mis en place en Phase 4 pour l'alerting admin, mais en DM privé à chaque utilisateur — strictement séparé du salon partagé "État du système", propositions personnelles jamais visibles des autres
- Évaluation de l'extension à d'autres automatisations (classement de documents Nextcloud, etc.)

**Critère de sortie** : tri automatique des mails opérationnel et jugé utile par l'auteur en usage réel.

## Phase 6 — Post-MVP : montée en échelle

Objectif : passer d'un projet personnel à une plateforme accueillant durablement famille et amis (4-9 utilisateurs et au-delà).

- Retour d'expérience de charge réelle → définition des profils de dimensionnement matériel (ex. 1-6 / 7-15 / 15+ utilisateurs)
- Évaluation du passage à une topologie k3s multi-nœuds (HA)
- **Installeur pour utilisateurs non-techos** : script unique (pas un ISO — s'appuie sur l'installeur graphique standard d'Ubuntu pour l'OS) qui rejoue l'installation aujourd'hui manuelle (`manuel-installation.md`). Inclut un modèle de gestion des comptes admin où Authentik reste la seule source de vérité d'identité et tous les secrets générés (y compris d'infrastructure) sont remis à l'utilisateur via son propre coffre Vaultwarden — aucun accès résiduel conservé par l'opérateur. Dashboard familial (premier point d'entrée + guide de première utilisation) fusionné avec ce chantier. Conception détaillée : [`installation-utilisateur.md`](installation-utilisateur.md).
- Ouverture à des amis souhaitant héberger leur propre nœud fédéré (messagerie, à terme mail)

## Suivi

Chaque phase doit se conclure par une démonstration fonctionnelle réelle avant de passer à la suivante — pas de passage à la phase suivante sur la seule base d'un déploiement technique sans usage réel validé.
