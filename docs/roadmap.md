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

Objectif : premier cas d'usage concret de la couche d'intégration IA, une fois le mail stable. Assistant en tâche de fond, pas de chat — dans l'esprit des fonctionnalités d'assistant ambiant type Apple Intelligence. Principe appliqué à toute action qui modifie une donnée : **l'IA propose, l'utilisateur valide**, jamais d'écriture automatique silencieuse.

**Prérequis déjà validés (Phase 3.5), rien à revalider avant de démarrer** — détail complet dans `notes-techniques.md` section "Ollama (IA locale)" :

- Ollama déployé sur le cluster (chart `otwld/ollama-helm`), modèle **Qwen3 8B** retenu après comparatif réel contre Mistral 7B/Llama 3.1 8B (9/12 champs corrects en extraction structurée vs 6/12 et 5/12) — `"think": false` dans chaque requête (sinon 40-130s de raisonnement caché inutile), `OLLAMA_MAX_LOADED_MODELS: "1"` (sinon OOM au chargement d'un second modèle).
- Chaîne complète prototypée et validée bout en bout, chaque maillon vérifié indépendamment plutôt que supposé : IMAP (`imaplib`) → extraction Qwen3 → proposition en DM Matrix (`@alertbot`, `createRoom` avec `is_direct: true` + `preset: trusted_private_chat` — **créée à la demande, pas pré-provisionnée** : pas besoin d'un mécanisme d'adhésion par défaut comme pour le salon `#etat-du-systeme`, le bot crée le DM au moment où il a une proposition à faire) → confirmation humaine réelle → écriture CalDAV dans Nextcloud (uniquement après confirmation).
- **Le prototype lui-même (scripts) n'est volontairement pas dans le dépôt** — outil de test jetable comme les scripts de comparatif de modèles, jamais commité. L'implémentation réelle repart de zéro côté code ; ce qui est acquis, c'est la conception validée et les bugs déjà trouvés (liste ci-dessous), pas du code réutilisable.

**Bugs déjà trouvés en prototype, à ne pas re-découvrir en vrai implémentation** :

- `DTSTART`/`DTEND` sans fuseau (floating time, RFC 5545) s'enregistrent et se relisent sans erreur via l'API, mais restent invisibles dans l'app Calendrier de Nextcloud — toujours écrire en UTC explicite (`Z`).
- Un compte Nextcloud provisionné par `user_oidc` a un identifiant opaque distinct du compte SSO visible par l'utilisateur (confirmé via `occ user:info`/l'API OCS) et refuse l'auth par mot de passe local — le connecteur doit résoudre cet identifiant par utilisateur (pas de nom supposé) et écrire via un jeton d'application (`occ user:auth-tokens:add`), jamais un mot de passe.
- Même logique d'identité à construire côté Matrix : l'ID Tuwunel d'un utilisateur est désormais fiable (`@username:offsystem.fr`, cf. le correctif du 2026-09-16 sur les usernames à un seul mot) mais reste à résoudre par utilisateur, pas à supposer.

**Reste à faire pour une vraie implémentation** (hors scope du prototype, volontairement) :

- Connecteur IMAP → tri/résumé automatique des mails, branché sur le vrai Mailu (plus GreenMail)
- Extraction d'événements/tâches → proposition d'ajout au Calendrier/Tasks Nextcloud (CalDAV), écriture uniquement après validation explicite
- Rappels basés sur les événements du calendrier
- Remplacement du polling d'historique par un vrai `/sync` Matrix en long-polling
- Ordonnancement récurrent (CronJob plutôt qu'un script lancé à la main)
- Gestion des cas d'erreur : mail déjà traité, réponse ambiguë, timeout de confirmation
- Un vrai annuaire utilisateur→identifiants (Matrix, compte Nextcloud, boîte mail) — à construire une fois, probablement via l'API Authentik (source de vérité identité unique du projet) plutôt qu'à improviser par utilisateur au fil de l'eau
- Canal de proposition/validation : réutilise le bot Tuwunel de Phase 4 (alerting admin), mais en DM privé à chaque utilisateur — strictement séparé du salon partagé "État du système", propositions personnelles jamais visibles des autres (déjà le comportement du prototype, rien à changer)
- Évaluation de l'extension à d'autres automatisations (classement de documents Nextcloud, etc.) — piste concrète notée en testant le tri de mail : un mail "colis livré" ou "colis disponible en point relais" pourrait devenir une **tâche** Nextcloud plutôt qu'un événement calendrier — pas de créneau horaire fixe, mais un état fait/pas fait naturel (cochable), avec échéance optionnelle (date limite de retrait) qui la ferait aussi apparaître dans le Calendrier. Nextcloud Tasks déployé en Phase 3.5 (`gitops/apps/nextcloud.yaml`), le mécanisme CalDAV pour l'écrire est le même que celui déjà validé pour les événements dans le prototype du pipeline mail — juste une collection VTODO plutôt que VEVENT. Envisager aussi une question de suivi proactive de l'IA ("dois-je te le rappeler quand tu seras chez toi ?", "à quelle heure ?") plutôt qu'une simple confirmation oui/non — un pattern différent de la validation binaire déjà posée, à explorer

**Critère de sortie** : tri automatique des mails opérationnel et jugé utile par l'auteur en usage réel.

## Phase 6 — Post-MVP : montée en échelle

Objectif : passer d'un projet personnel à une plateforme accueillant durablement famille et amis (4-9 utilisateurs et au-delà).

- Retour d'expérience de charge réelle → définition des profils de dimensionnement matériel (ex. 1-6 / 7-15 / 15+ utilisateurs)
- Évaluation du passage à une topologie k3s multi-nœuds (HA)
- **Installeur pour utilisateurs non-techos** : script unique (pas un ISO — s'appuie sur l'installeur graphique standard d'Ubuntu pour l'OS) qui rejoue l'installation aujourd'hui manuelle (`manuel-installation.md`). Inclut un modèle de gestion des comptes admin où Authentik reste la seule source de vérité d'identité et tous les secrets générés (y compris d'infrastructure) sont remis à l'utilisateur via son propre coffre Vaultwarden — aucun accès résiduel conservé par l'opérateur. Dashboard familial (premier point d'entrée + guide de première utilisation) fusionné avec ce chantier, y compris un **bouton de réparation** exposant le watchdog de remédiation automatique (Phase 4) — pour qu'un utilisateur non-technique puisse déclencher la même remédiation qu'un admin sans comprendre le diagnostic sous-jacent. Conception détaillée : [`installation-utilisateur.md`](installation-utilisateur.md).
- Ouverture à des amis souhaitant héberger leur propre nœud fédéré (messagerie, à terme mail)

## Suivi

Chaque phase doit se conclure par une démonstration fonctionnelle réelle avant de passer à la suivante — pas de passage à la phase suivante sur la seule base d'un déploiement technique sans usage réel validé.
