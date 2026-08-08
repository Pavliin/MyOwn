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

## Phase 3 — Messagerie (Conduwuit + Element X + LiveKit)

Objectif : couvrir l'usage courant (groupes, appels vidéo à 3-4) avec un candidat crédible au remplacement de WhatsApp pour le cercle du projet.

- Déploiement Conduwuit
- Déploiement LiveKit (appels vidéo de groupe)
- Test des appels vidéo de groupe en conditions réelles (3-4 participants, en LAN)

(App Android Element X et test de fédération avec un second serveur Matrix externe : différés à la Phase 4 — le premier a le même problème de résolution DNS locale sur mobile que les autres apps Android, le second nécessite une joignabilité publique réelle.)

**Critère de sortie** : un groupe familial migré sur la messagerie pour les échanges courants, appel vidéo de groupe fonctionnel.

**→ Point de démonstration MVP aux amis techos** (mdp + fichiers/photos + messagerie fonctionnels).

## Phase 4 — Bascule vers l'infra réelle & Mail

Objectif : quitter le cluster de dev pour la vraie infrastructure (mini PC + domaine) — le premier composant, Mail, en a de toute façon besoin dès le départ, donc cette bascule sert aussi à débloquer d'un coup toutes les validations différées des phases précédentes, avant de livrer la brique la plus complexe techniquement.

- Achat et mise en service du mini PC, migration du cluster GitOps du dev (k3d) vers le mini PC (mêmes manifests, changement de cible uniquement)
- Acquisition du nom de domaine, bascule Traefik vers Let's Encrypt réel (remplace les certificats mkcert du dev)
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

Objectif : premier cas d'usage concret de la couche d'intégration IA, une fois le mail stable.

- Déploiement Ollama + choix du modèle selon RAM disponible
- Connecteur IMAP → tri/résumé automatique des mails
- Évaluation de l'extension à d'autres automatisations (classement de documents Nextcloud, etc.)

**Critère de sortie** : tri automatique des mails opérationnel et jugé utile par l'auteur en usage réel.

## Phase 6 — Post-MVP : montée en échelle

Objectif : passer d'un projet personnel à une plateforme accueillant durablement famille et amis (4-9 utilisateurs et au-delà).

- Retour d'expérience de charge réelle → définition des profils de dimensionnement matériel (ex. 1-6 / 7-15 / 15+ utilisateurs)
- Évaluation du passage à une topologie k3s multi-nœuds (HA)
- Onboarding simplifié pour utilisateurs non-techos (documentation, assistant d'installation mobile)
- Ouverture à des amis souhaitant héberger leur propre nœud fédéré (messagerie, à terme mail)

## Suivi

Chaque phase doit se conclure par une démonstration fonctionnelle réelle avant de passer à la suivante — pas de passage à la phase suivante sur la seule base d'un déploiement technique sans usage réel validé.
