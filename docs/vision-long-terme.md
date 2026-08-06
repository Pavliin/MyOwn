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

## À retenir pour les décisions du présent

Rien dans ces deux pistes ne remet en cause les choix déjà faits pour le POC. Elles servent surtout de garde-fou : en cas de doute entre deux options techniques équivalentes pour le POC, préférer celle qui laisse ces portes ouvertes plutôt que celle qui les fermerait.
