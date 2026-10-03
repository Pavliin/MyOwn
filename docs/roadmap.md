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
- Déploiement Ollama (fait — modèle **Qwen3 8B** retenu après comparatif réel contre Mistral 7B/Llama 3.1 8B, `notes-techniques.md`) + connecteur IMAP de tri/résumé mail, prototypé contre une boîte mail jetable auto-hébergée (GreenMail — Mailpit écarté après vérification, ne supporte pas IMAP)
- Extraction d'événements/tâches depuis les mails → Calendrier/Tasks Nextcloud, avec validation explicite par DM Tuwunel (fait — pipeline complet prototypé et validé de bout en bout : mail → extraction → proposition DM → confirmation humaine réelle → écriture CalDAV, `notes-techniques.md`)
- Script installeur (développé et testé contre une VM jetable ou un nouveau cluster k3d, pas le mini PC réel) — rejoue `manuel-installation.md`
- Prototype du modèle de comptes admin (fait — secrets poussés avec succès dans un coffre Vaultwarden de test via le CLI `bw`, chiffrement serveur vérifié directement par API, détail dans `installation-utilisateur.md`)
- WireGuard déployé et validé de bout en bout en LAN (service systemd sur l'hôte, volontairement hors GitOps — voir `wireguard/README.md` : le placer dans le cluster qu'il est censé dépanner créerait une dépendance circulaire), handshake réel confirmé avec un second appareil — le test réel "depuis l'extérieur du LAN" attend le mini PC (Phase 4)
- **Jellyfin** (bibliothèque films/musique) — **fait** : déploiement (chart officiel `jellyfin/jellyfin-helm`, bug d'`inotify` hôte et incompatibilité binaire plugin/image trouvés et corrigés), sauvegarde Restic (config + bibliothèque, cycle backup/restauration réel validé), SSO Authentik (plugin communautaire `scottfridwin/jellyfin-plugin-authentik`, connexion réelle validée au navigateur, `scripts/jellyfin-sso-setup.py` pour la reproductibilité) — tout détaillé dans `notes-techniques.md`. Bibliothèque de test uniquement à ce stade — l'usage réel visé (partager des films/musiques achetés avec la famille, dispersée sur plus de 800 km) dépend d'une exposition internet réelle, différé en Phase 4

**Critère de sortie** : tout ce qui précède fonctionne sur le cluster de dev. Au basculement vers le mini PC réel (Phase 4), il ne reste plus qu'à migrer une configuration déjà validée, pas à la développer from scratch.

## Phase 4 — Bascule vers l'infra réelle & Mail

Objectif : quitter le cluster de dev pour la vraie infrastructure (mini PC + domaine) — le premier composant, Mail, en a de toute façon besoin dès le départ, donc cette bascule sert aussi à débloquer d'un coup toutes les validations différées des phases précédentes, avant de livrer la brique la plus complexe techniquement.

- Achat et mise en service du mini PC, migration du cluster GitOps du dev (k3d) vers le mini PC (mêmes manifests, changement de cible uniquement)
- **Ambiguïté `myown-*.local` entre dev et minipc** : les deux clusters exposent les mêmes hostnames (manifests Ingress identiques, aucune séparation par environnement) — seul `/etc/hosts` sur la machine cliente décide lequel des deux est réellement atteint. Sur la machine de dev, ces entrées ont été repointées à la main vers l'IP LAN du minipc le 2026-08-20, sans que ça soit documenté nulle part ; un futur `install.sh` réappliquerait sa valeur `127.0.0.1` par-dessus sans détecter le conflit, ajoutant une ligne en doublon plutôt qu'une erreur explicite. Corriger `install.sh` pour qu'il détecte une IP différente sur une entrée déjà présente au lieu de dupliquer la ligne ; évaluer aussi une vraie séparation de nommage (`myown-dev-*` pour le cluster de dev) si une confusion récurrente le justifie — non trivial, demanderait d'introduire une séparation par environnement dans les manifests GitOps eux-mêmes, actuellement partagés verbatim entre dev et minipc.
- **IP fixe** : réservation DHCP pour le mini PC au niveau du routeur familial, pour qu'un redémarrage de la box ne lui attribue jamais une IP différente — élimine la cause déclenchante de l'incident de cluster de dev du 2026-08-20 (`notes-techniques.md`), moins probable mais pas exclue sur le vrai k3s bare-metal.
- Acquisition du nom de domaine, bascule Traefik vers Let's Encrypt réel (remplace les certificats mkcert du dev)
- **Accès distant admin** : VPN WireGuard auto-hébergé (pas de dépendance tierce type Tailscale, cohérent avec `architecture.md` §1) — aucun outil d'administration (ArgoCD, `kubectl`, SSH) exposé directement sur internet, tout passe par le VPN. Mitige le risque déjà assumé d'indisponibilité de l'admin (`architecture.md` §11) : déblocage à distance via le VPN, ou guidage téléphonique de quelqu'un sur place en cas de panne matérielle complète.
- **Watchdog de remédiation automatique** : un utilisateur non-technique ne peut pas diagnostiquer un cluster bloqué (cf. l'incident du 2026-08-20, `notes-techniques.md` — plusieurs minutes de diagnostic manuel, `Restart=always` de systemd seul n'aurait pas suffi puisque l'échec se reproduisait identiquement à chaque tentative). Service qui vérifie périodiquement l'état du cluster et, après un nombre d'échecs consécutifs dépassant un seuil, tente automatiquement une remédiation (redémarrage du service k3s/containerd) sans attendre une intervention humaine. Interface utilisateur associée : bouton de réparation dans le dashboard familial (Phase 6).
- ~~Pi-hole~~ — fait (2026-09-17) : blocage de trackers/pub au niveau DNS pour tout le réseau familial. Placement tranché en faveur du conteneur Docker hors cluster, sur l'hôte (`scripts/pihole-setup.sh`) — même raisonnement de dépendance circulaire que WireGuard/le watchdog, voir `architecture.md` §6. Garde-fou non négociable validé avec un vrai test (coupure du conteneur, bascule sur le DNS secondaire `1.1.1.1` en moins d'une seconde), DHCP Freebox basculé pour tout le foyer, overrides locaux pour `*.offsystem.fr` (split-horizon LAN), redémarrage complet du mini PC validé (Pi-hole répond en DNS avant même que k3s ait fini de redémarrer). Pas de sauvegarde Restic dédiée — décision explicite, contenu vérifié quasi entièrement reproductible, voir `notes-techniques.md`. Limitation connue acceptée : aucun équivalent de redirection pour le DNS IPv6 annoncé par la Freebox (RA), les requêtes AAAA d'appareils IPv6 natifs échappent au filtrage — même famille que les autres lacunes IPv6 déjà trackées dans ce projet.
- **Monitoring famille** : configuration des moniteurs Uptime Kuma pour tous les services réels + publication d'une page de statut publique, intégrée au dashboard familial (Phase 6, cf. `installation-utilisateur.md`) — pas de Grafana pour la famille, réservé à l'admin. **Angle mort assumé** : Uptime Kuma tourne dans le cluster qu'il surveille — si le nœud entier tombe (cf. incident du 2026-08-20), rien à l'intérieur ne peut alerter de sa propre indisponibilité. Un vrai correctif demande un signal externe au mini PC (surveillance depuis l'extérieur du réseau local), en tension directe avec le principe "pas de dépendance à un tiers" du projet — non résolu, à trancher consciemment plutôt qu'ignoré.
- **Alerting admin** : bot Tuwunel dédié, salon Matrix partagé "État du système" (public/abonnable par qui veut dans le foyer, une seule occurrence de l'info) — Uptime Kuma y notifie les pannes. Réutilisé tel quel en Phase 5 pour les propositions Ollama, mais en DM privé strictement séparé de ce salon partagé (propositions personnelles, jamais dans un canal commun). **Ce même salon sert aussi de canal d'annonce familial** (`scripts/tuwunel-announce.py`) avant un changement notable sur un service sensible — cf. `architecture.md` §6 pour le principe (chaque installation MyOwn reste souveraine, la synchronisation ArgoCD n'est jamais déclenchée à distance ; distinction entre services sensibles, à terme en synchronisation manuelle précédée d'une annonce, et services d'infrastructure qui restent automatiques).
- Validation des items différés, désormais débloqués par l'exposition internet réelle :
  - App Android Vaultwarden (Phase 1)
  - Apps Android Nextcloud + Immich, backup automatique photos/vidéos en conditions réelles (Phase 2)
  - App Android Element X, test de fédération Matrix avec un second serveur externe (Phase 3)
  - Jellyfin : accès distant réel validé par un membre de la famille éloigné (800 km), avec vérification de la bande passante en lecture simultanée (Phase 3.5)
- ~~Provisionnement du VPS façade~~ — fait (OVH VPS-1, voir `notes-techniques.md`)
- ~~Relais Postfix + SPF/DKIM/DMARC + tunnel WireGuard dédié VPS↔domicile~~ — fait et validé dans les deux sens (envoi/réception réels avec un compte Gmail externe, arrivée en boîte de réception), voir `notes-techniques.md`. Encore sur le cluster de dev, pas le mini PC — migration séparée, pas commencée
- ~~Déploiement Mailu à domicile~~ — fait (chart Helm officiel, `Application` ArgoCD comme le reste du projet, cluster de dev), SSO Authentik inclus, connecté au relais VPS
- Migration progressive des correspondants (soi-même d'abord, en parallèle d'un compte existant le temps de valider la délivrabilité)
- Suivi de délivrabilité (tests d'envoi vers Gmail/Outlook, monitoring des blacklists)

**Critère de sortie** : tous les services précédemment validés en dev tournent sur le mini PC réel, toutes les validations différées sont passées avec succès, et le mail est envoyé/reçu de façon fiable vers/depuis Gmail et Outlook sur une période de test soutenue (pas de classement spam systématique).

## Phase 5 — Intelligence locale (Ollama)

Objectif : premier cas d'usage concret de la couche d'intégration IA. Assistant en tâche de fond, pas de chat — dans l'esprit des fonctionnalités d'assistant ambiant type Apple Intelligence. Principe appliqué à toute action qui modifie une donnée : **l'IA propose, l'utilisateur valide**, jamais d'écriture automatique silencieuse.

**Pipeline mail implémenté et validé de bout en bout sur données réelles (2026-09-24)** — cadrage produit collaborativement dans un doc dédié avant tout code, puis neuf modules Python (`phase5/`, PR [#167](https://github.com/Pavliin/MyOwn/pull/167)) livrés en une session, chacun testé contre de vrais services avant de passer au suivant. Détail complet, bug par bug, dans `notes-techniques.md` section "Ollama (IA locale)" → "Pipeline réel implémenté et validé de bout en bout". Socle Ollama toujours valide sans changement : chart `otwld/ollama-helm`, **Qwen3 8B**, `"think": false`, `OLLAMA_MAX_LOADED_MODELS: "1"`.

- ~~Connecteur IMAP → tri/résumé automatique des mails, branché sur le vrai Mailu~~ — fait, `phase5/imap_connector.py`, strictement lecture seule (`readonly=True` + `BODY.PEEK`).
- ~~Extraction d'événements/tâches → proposition d'ajout au Calendrier/Tasks Nextcloud (CalDAV)~~ — fait, `phase5/extraction.py` (Qwen3, schéma JSON structuré, conversion de fuseau horaire faite en code plutôt que confiée au modèle, rejet des dates extraites dans le passé) + `phase5/caldav_writer.py` (VEVENT/VTODO, calendrier et liste de tâches résolus dynamiquement, jamais un nom supposé, durée par défaut 1h/20min).
- ~~Remplacement du polling d'historique par un vrai `/sync` Matrix en long-polling~~ — fait, `phase5/matrix_dm.py`.
- ~~Ordonnancement récurrent~~ — **partiel** : `phase5/orchestrator.py` gère les 3 cas d'erreur (mail déjà traité, réponse ambiguë, timeout de confirmation), validé en conditions réelles, mais reste lancé à la main — la bascule en CronJob (image de conteneur, `Application` GitOps, câblage de secrets) est un chantier à part de la logique métier, pas encore fait.
- ~~Un vrai annuaire utilisateur→identifiants~~ — fait, `phase5/user_directory.py`, via l'API Authentik + l'API OCS Nextcloud (matché par email, dérive détectée plutôt que devinée).
- ~~Canal de proposition/validation en DM privé~~ — fait, `phase5/matrix_dm.py`, réutilise `@alertbot` (affiché "Myo") strictement en DM, jamais le salon partagé.
- **Nouveau, pas prévu au départ** : opt-in explicite par service (`phase5/opt_in.py`) avant toute automatisation sur un service réel — ajouté suite à une revue du doc de cadrage, jamais d'action par défaut sur une réponse ambiguë.
- Classement de mail (règle Sieve) — **reporté**, bloqué sur une authentification ManageSieve qui échoue contre le Dovecot du mini PC (cause exacte non trouvée, investigation arrêtée pour ne pas continuer à générer des échecs d'auth contre un vrai compte ; détail dans `notes-techniques.md`). Le reste du pipeline n'en dépend pas.
- Évaluation de l'extension à d'autres automatisations (classement de documents Nextcloud, question de suivi proactive plutôt qu'un oui/non binaire) — toujours pas commencé.

**Critère de sortie** : tri automatique des mails opérationnel et jugé utile par l'auteur en usage réel — le pipeline événements/tâches est validé techniquement de bout en bout (y compris par une relecture humaine attentive qui a trouvé et fait corriger plusieurs bugs réels), mais le jugement "utile en usage réel" sur la durée reste à établir, et le classement de mail (une partie du "tri") reste bloqué sur Sieve.

## Phase 6 — Post-MVP : montée en échelle

Objectif : passer d'un projet personnel à une plateforme accueillant durablement famille et amis (4-9 utilisateurs et au-delà).

- Retour d'expérience de charge réelle → définition des profils de dimensionnement matériel (ex. 1-6 / 7-15 / 15+ utilisateurs)
- Évaluation du passage à une topologie k3s multi-nœuds (HA)
- **Installeur pour utilisateurs non-techos** : script unique (pas un ISO — s'appuie sur l'installeur graphique standard d'Ubuntu pour l'OS) qui rejoue l'installation aujourd'hui manuelle (`manuel-installation.md`). Inclut un modèle de gestion des comptes admin où Authentik reste la seule source de vérité d'identité et tous les secrets générés (y compris d'infrastructure) sont remis à l'utilisateur via son propre coffre Vaultwarden — aucun accès résiduel conservé par l'opérateur. Dashboard familial (premier point d'entrée + guide de première utilisation) fusionné avec ce chantier, y compris un **bouton de réparation** exposant le watchdog de remédiation automatique (Phase 4) — pour qu'un utilisateur non-technique puisse déclencher la même remédiation qu'un admin sans comprendre le diagnostic sous-jacent. Conception détaillée : [`installation-utilisateur.md`](installation-utilisateur.md).
- Ouverture à des amis souhaitant héberger leur propre nœud fédéré (messagerie, à terme mail)

## Suivi

Chaque phase doit se conclure par une démonstration fonctionnelle réelle avant de passer à la suivante — pas de passage à la phase suivante sur la seule base d'un déploiement technique sans usage réel validé.
