# Vision long terme (hors scope du POC actuel)

Ce document capture des pistes d'évolution du projet à ne pas perdre de vue. Elles ne font pas partie du périmètre actuel — cf. [`architecture.md`](architecture.md) et [`roadmap.md`](roadmap.md) pour le POC personnel réellement engagé.

## Pourquoi documenter ça maintenant

- **Sérieux** : l'ambition n'est pas seulement un usage personnel fonctionnel, mais un projet assez abouti et sécurisé pour être distribué largement. Si une poignée de personnes sortent leurs données des GAFAM, c'est anecdotique. Si des milliers le font, le rapport de force change.
- **Traction** : un projet mené avec une rigueur professionnelle inspire davantage confiance et a plus de chances de se populariser.
- **Perspective entrepreneuriale** : monter une entreprise à partir de ce projet fait partie des objectifs personnels à long terme.

Le scope reste volontairement restreint aujourd'hui — POC personnel, famille et amis proches (cf. roadmap) — pour grandir sainement. Mais à choix technique égal, le POC privilégie les options qui n'empêchent pas ces évolutions plutôt que celles qui les compromettraient (protocoles ouverts/fédérés plutôt que propriétaires, standards plutôt que formats maison, pas d'hypothèse d'opérateur central unique).

## Piste 1 — Offre professionnelle pour institutions (écoles, mairies)

Modèle fédéré : chaque établissement héberge et reste maître de ses propres données ; les nœuds s'interconnectent entre établissements (ex. entre écoles d'une même académie). La gouvernance/contractualisation se fait à l'échelle région/académie (accord-cadre, mécanisme déjà existant dans la commande publique française), le déploiement reste établissement par établissement.

Le logiciel reste intégralement open source — le modèle économique porte sur le service de déploiement et de maintenance, pas sur la vente de licence. C'est la tendance dominante, et souvent la seule politiquement acceptable, dans le secteur public français actuel (doctrine des "communs numériques").

Contraintes identifiées :

- Les données de santé (hôpitaux) restent un mur dur même en fédéré : la certification HDS s'attache aussi à l'infogérance (accès technique à distance), pas seulement au lieu d'hébergement. À vérifier précisément avec un juriste avant d'envisager ce segment.
- Écoles/mairies sont nettement plus praticables via ce modèle, à condition de rester sur le périmètre du **personnel administratif** (mail, fichiers, mots de passe internes) plutôt que sur les données d'élèves, qui relèvent d'un régime de protection et d'homologation plus lourd (ENT/GAR).
- Techniquement, l'architecture du POC tient bien à l'échelle d'un établissement (20-100 utilisateurs par nœud, proche de l'échelle familiale déjà validée). Le déploiement en flotte multi-établissements correspond au modèle "hub-and-spoke" déjà permis par ArgoCD (ApplicationSets multi-clusters) — pas de réarchitecture nécessaire.
- Ce qui doit être durci par nœud à cette échelle : sauvegarde professionnelle (pas de solution informelle), et le statut non-certifié de Vaultwarden à assumer ou traiter contractuellement.

## Piste 2 — Réseau social

### Court terme : couvert par les partages Nextcloud/Immich, sans rien construire

Pour le besoin réel à l'échelle famille/amis proches — partager avec des personnes précises et connues, pas se rendre découvrable par des inconnus — les fonctionnalités de partage déjà déployées suffisent, dès aujourd'hui :

- **Nextcloud** : partage natif d'un dossier ou fichier avec des comptes/groupes précis (lecture seule ou lecture-écriture) — ex. un dossier "fichiers familiaux" partagé avec les parents, un "livret de famille" partagé en couple.
- **Immich** : albums partagés natifs avec des comptes précis de l'instance, avec option collaborative — ex. un album "notre chat" partagé avec la famille, likes/commentaires inclus.

Ce que ça ne couvre pas, et qui reste le vrai delta avec un réseau social : pas de page publique consultable par des inconnus, pas de fil agrégeant automatiquement les publications de plusieurs personnes. C'est précisément ce que les options ci-dessous ajouteraient.

### Long terme : deux architectures candidates, retenue actuelle = Solid

Deux familles de solutions étudiées pour un vrai réseau social auto-hébergé, avec des implications très différentes :

**Fediverse/ActivityPub (Mastodon)** — modèle *push/réplication* : chaque nouveau post d'un compte suivi est livré et copié en local dans la base de l'abonné. Conséquences :

- Croissance du stockage proportionnelle à ce qu'on suit, pas seulement à ce qu'on produit soi-même — nécessite un TTL de cache média pour la borner (paramètre en jours, pas en minutes ; ne purge que les médias, jamais le texte/les métadonnées, répliqués indéfiniment par le protocole de base).
- Résilience forte : le contenu déjà livré reste visible même si le serveur d'origine tombe.
- Découverte native : fils fédérés, hashtags, relais.
- Maturité : logiciel prêt à déployer (Mastodon, Pixelfed, PeerTube, WriteFreely), cohérent avec le choix déjà fait pour Matrix (même logique de fédération pour la messagerie).

**Solid (WebID + Pods, initié par Tim Berners-Lee)** — modèle *pull/consultation en direct* : un WebID identifie la personne et pointe vers son Pod (stockage personnel auto-hébergeable, multi-tenant comme Nextcloud/Immich — un seul serveur peut porter les Pods de toute la famille) ; le fil d'un utilisateur est reconstruit à la volée en interrogeant en direct les Pods des comptes suivis, sans réplication permanente ailleurs. Conséquences :

- Stockage borné à ce qu'on partage réellement soi-même — pas d'accumulation du contenu des autres.
- Contrôle d'accès fin par ressource (WAC/ACP : tel WebID précis pour tel post précis), plus granulaire que les 4 niveaux de visibilité de Mastodon.
- Résilience plus faible : un post d'un compte suivi disparaît du fil si son Pod est temporairement hors ligne au moment de la consultation — dépendance à la disponibilité simultanée de tous les Pods suivis, contrairement au modèle push.
- Découverte : aucun mécanisme natif standardisé (pas d'équivalent aux relais/hashtags/fils fédérés) — repose sur le partage du lien WebID par un canal externe, ou des annuaires ad hoc non standardisés.
- Rendu public pour un visiteur externe (lien direct, sans compte) non garanti par le protocole — contrairement à Mastodon où un post public est toujours une page HTML consultable par n'importe qui, Solid sert nativement des données structurées (RDF/JSON-LD) et nécessite un rendu HTML explicite côté app pour être présentable à un visiteur externe.
- Maturité : le serveur (Community Solid Server) est mature et déployable, mais **la couche applicative "réseau social" (fil, découverte) n'existe pas en brique prête à assembler** — contrairement à Mastodon, ce serait du développement, pas de l'assemblage.

**Pourquoi Solid est la piste préférée malgré ce dernier point** :

- Alignement philosophique encore plus poussé que le modèle Fediverse : aucune réplication forcée chez des tiers, contrôle d'accès nominatif par ressource plutôt que par niveau de visibilité générique, pas d'hypothèse d'opérateur central — cohérent avec le principe déjà posé en tête de ce document plutôt qu'un compromis.
- Garde à chaque utilisateur la maîtrise de son propre espace disque (pas d'engagement de stockage ouvert dépendant du comportement d'autrui, contrairement à ActivityPub).
- Cohérent avec l'ambition de garder le projet global abordable et accessible à un large public plutôt que de le complexifier — sans pour autant demander à un utilisateur lambda d'administrer activement son serveur pour l'espace disque (la contrepartie en disponibilité réseau ci-dessus reste à assumer).
- Potentiel de différenciation ("produit d'appel") pour MyOwn spécifiquement, plutôt qu'une énième instance Mastodon parmi d'autres.

**Ce qu'un vrai projet Solid impliquerait de construire**, pour situer l'ampleur réelle du chantier :

- La logique d'agrégation de fil (parcours du graphe WebID, requêtes live vers les Pods suivis).
- Un mécanisme de découverte (inexistant nativement, à concevoir).
- Un rendu HTML public pour les visiteurs externes sans compte.
- Le déploiement multi-tenant des Pods (un Pod par utilisateur sur une instance Community Solid Server partagée).
- Une éventuelle passerelle avec Immich/Nextcloud si on veut réutiliser du contenu qui y existe déjà (aucun pont natif — partager une photo Immich sur ce RS impliquerait une copie dédiée dans le Pod, pas une réutilisation directe).

Un projet à part entière, pas une brique de plus à assembler dans le POC actuel. **Le jour où ce chantier est engagé pour de vrai, il commence par un cahier des charges précis de ce que ce réseau social doit et ne doit pas faire** — volontairement non défini à ce stade.

## Piste 3 — Diffusion publique en deux temps

Décidé le principe, pas encore le calendrier ni les détails d'exécution :

1. **Mise à disposition** : le dépôt GitHub public (déjà le cas aujourd'hui) reste le point d'entrée technique, complété par le bouche-à-oreille et, potentiellement, un site vitrine/une présence réseaux sociaux.
2. **Évolutions d'accessibilisation grand public et de confort d'usage (QoL)**, une fois une première base d'utilisateurs réelle validée — recoupe naturellement l'installeur non-technique déjà prévu en Phase 6 (`installation-utilisateur.md`) et le dashboard familial.

Le positionnement exact du site/réseaux sociaux (dans l'étape 1, ou plutôt entre les deux étapes) reste ouvert — dépend surtout du niveau de préparation du projet à absorber un afflux d'utilisateurs non accompagnés individuellement. Cohérent avec le principe déjà posé plus haut (§"Pourquoi documenter ça maintenant" — sérieux, traction) : ne pas sur-exposer avant que l'onboarding (Phase 6) soit prêt à recevoir des utilisateurs sans accompagnement individuel, sous peine de mauvaise première impression difficile à rattraper.

## Piste 4 — Assistant IA sensible à la localisation

Détection de présence dans un lieu inconnu et suggestions de restaurants/lieux à visiter, dans l'esprit des autres fonctionnalités d'assistant ambiant envisagées pour Ollama (`architecture.md` §5.7) — mais structurellement différente des automatisations mail/calendrier de la Phase 5, donc gardée hors scope proche plutôt que d'y être mêlée :

- **Casse le principe "aucune donnée ne sort du réseau local"** posé pour Ollama : une IA locale n'a aucune connaissance à jour des lieux réels sans source externe (API de lieux type OpenStreetMap Overpass, ou base géographique auto-hébergée à évaluer en volume).
- **Nécessite un pipeline complet absent du projet aujourd'hui** : récupération de la position depuis le téléphone (app de tracking type OwnTracks/PhoneTrack vers un endpoint self-hosted), avec un enjeu de consentement plus sensible qu'un simple accès mail (position en continu, pas un événement ponctuel).

À reprendre une fois le socle Ollama (Phase 5) stable, et seulement si l'usage réel des automatisations mail/calendrier confirme l'intérêt d'aller plus loin dans cette direction.

## À retenir pour les décisions du présent

Rien dans ces pistes ne remet en cause les choix déjà faits pour le POC. Elles servent surtout de garde-fou : en cas de doute entre deux options techniques équivalentes pour le POC, préférer celle qui laisse ces portes ouvertes plutôt que celle qui les fermerait.
