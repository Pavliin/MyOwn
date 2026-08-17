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

## Piste 2 — Réseau social fédéré, chaque "page" hébergée par son propriétaire

Chaque utilisateur héberge sa propre page/nœud ; les nœuds s'interconnectent pour former un réseau social sans opérateur central. C'est le modèle du **Fediverse**, standardisé par le protocole **ActivityPub** (W3C), déjà éprouvé par des logiciels open source matures :

- **Mastodon** — micro-blogging
- **Pixelfed** — partage de photos
- **PeerTube** — vidéo
- **WriteFreely** — blog

Cohérent avec la philosophie déjà posée du projet (assembler des briques matures plutôt que réinventer), et avec un choix déjà fait dans le POC : Matrix, retenu pour la messagerie, fédère selon exactement la même logique — chacun chez soi, interconnecté. Une partie du chemin technique vers cette vision est donc déjà défrichée par le POC actuel.

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
