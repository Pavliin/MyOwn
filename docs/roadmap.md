# Plan de développement

Horizon visé : MVP démontrable à 3-6 mois (mots de passe + fichiers/photos + messagerie). Le mail est traité en dernier compte tenu de sa complexité, mais reste dans le périmètre du MVP élargi.

## Phase 0 — Socle d'infrastructure

Objectif : avoir une plateforme k3s opérationnelle, pilotée en GitOps, avant de déployer le moindre service applicatif.

- Achat et mise en service du mini PC
- Installation k3s (mono-nœud)
- Environnement de dev miroir (k3d/kind) sur poste personnel
- ArgoCD connecté à ce dépôt Git
- Traefik (ingress + TLS Let's Encrypt) — nécessite le nom de domaine (à acquérir)
- Prometheus + Grafana + Uptime Kuma
- Authentik (SSO/OIDC) — brique transverse, condition préalable à un onboarding simple des autres services
- Stratégie de secrets (SOPS ou Sealed Secrets) tranchée et mise en place

**Critère de sortie** : un service de test déployé via ArgoCD, exposé en HTTPS, protégé par SSO Authentik, visible dans Grafana/Uptime Kuma.

## Phase 1 — Mots de passe (Vaultwarden)

Objectif : premier service réel livré, risque faible, valeur immédiate.

- Déploiement Vaultwarden + intégration Authentik
- App Android (Bitwarden officielle, pointée vers le serveur)
- Sauvegarde Restic vers le nœud ami (première mise en place du pipeline de sauvegarde, réutilisée ensuite pour tous les services)
- Test de restauration

**Critère de sortie** : usage quotidien réel par l'auteur (dogfooding), sauvegarde/restauration validée.

## Phase 2 — Fichiers et photos (Nextcloud + Immich)

Objectif : couvrir le cas d'usage le plus visible pour convaincre (remplacement concret de Google Drive/Photos).

- Déploiement Nextcloud (fichiers, contacts, calendrier) + Immich (photos/vidéos)
- Intégration Authentik
- Apps Android : Nextcloud + Immich, configuration du backup automatique photos/vidéos
- Sauvegarde Restic étendue à ces services
- Test avec 2-3 utilisateurs réels (famille proche) hors auteur

**Critère de sortie** : migration effective des photos/fichiers d'au moins un membre de la famille, backup mobile automatique fonctionnel.

## Phase 3 — Messagerie (Conduwuit + Element X + LiveKit)

Objectif : couvrir l'usage courant (groupes, appels vidéo à 3-4) avec un candidat crédible au remplacement de WhatsApp pour le cercle du projet.

- Déploiement Conduwuit
- Déploiement LiveKit (appels vidéo de groupe)
- App Android Element X
- Test des appels vidéo de groupe en conditions réelles (3-4 participants)
- Test de fédération avec un second serveur Matrix externe (validation du besoin de "discovery")

**Critère de sortie** : un groupe familial migré sur la messagerie pour les échanges courants, appel vidéo de groupe fonctionnel.

**→ Point de démonstration MVP aux amis techos** (mdp + fichiers/photos + messagerie fonctionnels).

## Phase 4 — Mail (VPS façade + Mailcow)

Objectif : la brique la plus complexe, traitée une fois le socle et l'expérience opérationnelle acquis sur les phases précédentes.

- Acquisition du nom de domaine
- Provisionnement du VPS façade (Hetzner/OVH/Scaleway), configuration Postfix relay + SPF/DKIM/DMARC
- Déploiement Mailcow à domicile, connexion au relais VPS
- Migration progressive des correspondants (soi-même d'abord, en parallèle d'un compte existant le temps de valider la délivrabilité)
- Suivi de délivrabilité (tests d'envoi vers Gmail/Outlook, monitoring des blacklists)

**Critère de sortie** : mail envoyé/reçu de façon fiable vers/depuis Gmail et Outlook sur une période de test soutenue (pas de classement spam systématique).

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
