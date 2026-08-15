# Matériel — dimensionnement et choix

Trace de la réflexion et des décisions prises pour le matériel de la Phase 4 (bascule vers l'infra réelle) et la cible long terme. Complète `architecture.md` §10 (qui reste volontairement synthétique) avec le détail du raisonnement, les chiffres mesurés et les pistes d'achat concrètes — pour ne pas avoir à refaire cette recherche plus tard.

## Approche retenue : deux étapes, pas un seul achat

1. **Étape A (maintenant)** : machine minimale, pour sortir du cluster de dev et boucler la Phase 4 (domaine réel, mail, validations Android/fédération différées) + commencer à tester Ollama sans attendre l'étape B.
2. **Étape B (plus tard, quand Phase 5/6 deviennent réelles)** : la cible long terme, avec stockage à deux vitesses (NVMe rapide + baies HDD extensibles) et une vraie marge RAM pour Ollama + Mailcow + croissance du foyer.

Raison de ce découpage : le marché mémoire (DDR5 notamment) traverse une pénurie sévère mi-2026 (cf. plus bas) — étaler l'achat limite le risque de payer le pic de prix sur tout le budget d'un coup, et débloque la suite du projet sans attendre d'avoir réuni le budget complet.

## Étape A — machine minimale (maintenant)

**Cible retenue** : PC de bureau SFF reconditionné, Dell OptiPlex 5060 (ou équivalent HP EliteDesk/Lenovo ThinkCentre de génération comparable), Core i5-8500, **32 Go de RAM**, SSD ~1 To déjà inclus.

**Budget réel constaté** (Back Market, France, août 2026) : 481-567 € selon le modèle exact — au-dessus de la cible initiale de 300-400 €, écart accepté volontairement pour garder 32 Go de RAM (voir raisonnement ci-dessous).

**Achetée (2026-08-15)** : Dell OptiPlex 5060 SFF à 481 €, réception prévue sous ~1 semaine.

**Pourquoi 32 Go et pas 16 Go** : avec 16 Go, la machine aurait pu couvrir les services déjà validés (Phases 1-3) + Mailcow allégé, mais pas Ollama — un test réel du pipeline tri/résumé mail (Phase 5) aurait dû attendre l'étape B. Calcul avec Ollama actif :

| Poste | RAM |
|---|---|
| Services actuels (9 services + monitoring), mesuré en idle sur le cluster de dev | ~6,3 Gio |
| Marge réaliste usage concurrent (upload, appel LiveKit, ML Immich) | ×2 → ~13 Gio |
| Mailcow allégé (sans Solr, ClamAV conservé) | ~3-5 Gio |
| Ollama chargé (modèle 7-8B, quantization Q4) | ~6-8 Gio |
| **Total pic estimé** | **~22-26 Gio sur 32 Go dispo** |

Marge plus courte qu'à l'étape B, mais suffisante pour un test réel (pas un usage multi-utilisateurs simultané avec tout allumé en même temps) — cohérent avec le rôle transitoire de cette machine. Ollama décharge le modèle de la RAM après quelques minutes d'inactivité par défaut, donc il n'est pas résident en permanence.

**CPU** : i5-8500 (6 cœurs, 2018, sans accélération dédiée à l'inférence) — vitesse de génération modeste mais suffisante pour un résumé de mail asynchrone (usage batch, pas de chat temps réel). Cohérent avec le scope Phase 5 annoncé ("tri/résumé mail").

**Stockage** : pas besoin de migrer toute la photothèque (2-3 To) dès l'étape A — Immich n'exige pas d'avoir toute la bibliothèque le premier jour, migration progressive possible. Le 1 To déjà inclus dans ces configs suffit pour démarrer.

**Liens réels trouvés (Back Market, à vérifier prix/stock au moment de l'achat)** :

- [Dell OptiPlex 5060 SFF — i5-8500, 32 Go RAM, SSD 1 To — 481 €](https://www.backmarket.fr/fr-fr/p/dell-optiplex-9020-sff-core-i7-36-ghz-ssd-1-to-ram-32-go/f6fd44cb-5604-4ead-84b0-09dc58ed653c) *(retenu — le moins cher des trois, specs équivalentes aux deux autres pour cet usage)*
- Dell OptiPlex 7060 SFF — i5-8500, 32 Go RAM, SSD 1 To — 520 €
- Dell OptiPlex 7070 SFF — i5, 32 Go RAM, SSD 1 To — 567 €
- [Page catégorie "Dell reconditionné" — Back Market](https://www.backmarket.fr/fr-fr/l/ordinateur-fixe-dell-reconditionne/aa653d35-5403-42e8-93da-2e258a3a4c89)
- [Recherche "Dell OptiPlex i7" — leboncoin](https://www.leboncoin.fr/ck/ordinateurs/dell-optiplex-i7) (occasion entre particuliers, moins cher, sans garantie)
- [Recherche "Dell OptiPlex 32 Go" — leboncoin](https://www.leboncoin.fr/ck/ordinateurs/dell-optiplex-32-go)

## Étape B — cible long terme (plus tard)

**Cible retenue** : Minisforum N5 Air (ou N5 Pro si l'ECC/le châssis métal valent le supplément — voir arbitrage plus bas), plateforme "mini NAS" plutôt que mini PC pur.

**Pourquoi cette gamme** :

- 3x slots M.2 NVMe/U.2 (tier rapide : bases de données, photothèque Immich — décidé de tout garder sur NVMe, pas de tiering pour les photos, cf. raisonnement UX plus bas)
- **5 baies SATA 3,5"/2,5"** (tier lent/pas cher : dépôts de sauvegarde Restic — écriture séquentielle, pas de contrainte de latence, gros volume cumulé sur plusieurs mois de rétention × plusieurs services) — beaucoup de marge d'extension
- Jusqu'à 96 Go DDR5 — au-dessus de la cible ~64 Go
- CPU Ryzen Zen 4 8c/16t — bonne base pour Ollama (IPC mono-thread) sans avoir besoin de GPU dédié
- Un seul boîtier, pas de dock externe — cohérent avec le placement "bureau" retenu (pas de contrainte de discrétion façon salon)
- Conso mesurée (ServeTheHome) : ~32-36 W idle (NVMe seul), ~45-49 W avec les 5 baies HDD peuplées

**N5 Air vs N5 Pro** : même CPU, même plafond RAM/stockage. Le Pro ajoute RAM ECC (intégrité mémoire, pertinent pour un serveur 24/7 avec données sensibles) et châssis métal, pour ~440 $ de plus (~519 $ Air vs ~909-959 $ Pro, barebone). Arbitrage non tranché à ce stade — à revoir au moment de l'achat réel.

**Pourquoi tout garder sur NVMe pour la photothèque** (pas de tiering NVMe/HDD sur les photos) : le pattern d'accès d'une galerie photo (défilement = beaucoup de petites lectures aléatoires pour les miniatures) est mauvais sur HDD. Risque de latence perceptible pour la famille, contraire au principe "UX proche des standards grand public" (`architecture.md` §2). Décision : simplicité + UX garantie plutôt qu'optimisation coût sur ce poste précis.

**Pourquoi peupler progressivement plutôt que tout acheter d'un coup** : cf. section pénurie DDR5 ci-dessous — le barebone (boîtier + CPU) n'est pas touché par la pénurie mémoire, seule la RAM l'est. Recommandé : acheter le châssis N5 dès que la migration réelle est décidée, peupler avec 32 Go pour commencer (pas 64 Go), étendre RAM + baies HDD plus tard quand Mailcow/Ollama tournent réellement en production et que les prix mémoire ont eu une chance de se détendre.

## Contexte : pénurie mémoire mi-2026

Constaté par recherche (sources ci-dessous, prix US, ordre de grandeur) :

- DDR5 32 Go : ~80 $ mi-2025 → ~380-590 $ mi-2026 (+400 % en moins d'un an)
- DDR5 64 Go : ~680-800 $
- Raspberry Pi 5 16 Go : le fabricant lui-même a augmenté son prix à 305 $ à cause de la même pénurie LPDDR4/5
- Analystes : pas de détente attendue avant 2027 (demande des datacenters IA)

C'est la raison principale du découpage en deux étapes plutôt qu'un achat direct de la cible long terme.

## Piste rejetée : cluster de Raspberry Pi

Envisagé puis écarté. Raisons cumulées :

- Pénurie mémoire touche aussi le Pi (16 Go à 305 $ désormais)
- RAM non mutualisée entre nœuds Kubernetes — un pod doit tenir sur un seul nœud, pas sur la somme du cluster
- CPU ARM plus faible en mono-cœur, pénalise spécifiquement Ollama (inférence) et le ML d'Immich
- Compatibilité ARM non garantie sur tous les sous-composants (dépendances ML notamment) — travail de validation non fait
- Force une bascule multi-nœuds anticipée, alors que `architecture.md` §6 la prévoit comme évolution ultérieure, pas comme point de départ
- Une fois tous les à-côtés comptés (boîtier, refroidissement actif, stockage NVMe par nœud, alimentations, switch réseau), pas vraiment moins cher qu'un PC de bureau d'occasion pour une capacité par nœud inférieure

## Piste écartée : ancien PC gamer déjà en stock

Envisagé (matériel déjà possédé, coût marginal nul) puis écarté avant l'achat de l'OptiPlex ci-dessus. Config réelle vérifiée : carte mère Asus H87 Pro, CPU i5-4440 (2013, 4 cœurs sans HT), GPU GTX 650 OC2 (2012, Kepler, ~1-2 Go VRAM), 16 Go RAM DDR3 1600 MHz, pas de SSD. Raisons cumulées :

- CPU cinq générations en retrait par rapport à la cible retenue (i5-8500, 2018, 6 cœurs) — écart réel, pas marginal, pénalise les services concurrents et l'inférence Ollama.
- GPU trop ancien et sous-doté en VRAM pour accélérer Ollama : un modèle 7-8B quantifié Q4 a besoin d'environ 4-6 Go de VRAM, hors de portée d'une GTX 650, et le support CUDA/cuDNN de l'architecture Kepler est très limité dans les stacks d'inférence actuelles — le seul avantage espéré de cette machine (accélération GPU, absente du plan OptiPlex) ne se concrétise pas.
- RAM (16 Go) en dessous du seuil déjà écarté plus haut pour la même raison (Ollama). Un upgrade à 32 Go en DDR3 aurait été probablement bon marché (non touché par la pénurie DDR4/DDR5 de mi-2026), mais n'aurait pas comblé l'écart CPU/GPU.
- Pas de SSD à ajouter en plus, réduisant l'écart de coût réel avec l'OptiPlex (qui l'inclut déjà).

## Sources consultées

- [DDR5 Price Crisis 2026 — Newegg Insider](https://www.newegg.com/insider/ddr5-price-crisis-buying-guide-2026/)
- [RAM shortages until 2028 — TweakTown](https://www.tweaktown.com/news/109222/ram-shortages-are-here-until-2028-64gb-ddr5-is-now-dollars500-256gb-ddr4-costs-over-dollars3000/index.html)
- [32GB DDR5 now $375 minimum — Tom's Hardware](https://www.tomshardware.com/pc-components/ddr5/32gb-of-ddr5-now-costs-usd375-minimum-ai-shortage-continues-to-squeeze-pc-building)
- [Raspberry Pi 5 price increase — Raspberry Pi officiel](https://www.raspberrypi.com/news/1gb-raspberry-pi-5-now-available-at-45-and-memory-driven-price-rises/)
- [Minisforum N5 Pro Review — ServeTheHome](https://www.servethehome.com/minisforum-n5-pro-review-an-awesome-nas-platform/)
- [Minisforum N5 Pro AI NAS — page produit officielle](https://store.minisforum.com/products/minisforum-n5-pro-ai-nas)
- [MINISFORUM N5 Air — Liliputing](https://liliputing.com/minisforum-n5-air-is-a-cheaper-5-bay-nas-with-a-499-starting-price-and-a-plastic-body/)
- [Dell OptiPlex 5060 SFF 32 Go — Back Market](https://www.backmarket.fr/fr-fr/p/dell-optiplex-9020-sff-core-i7-36-ghz-ssd-1-to-ram-32-go/f6fd44cb-5604-4ead-84b0-09dc58ed653c)

## Non tranché — à trancher au moment de l'achat

- N5 Air vs N5 Pro (ECC/châssis métal vs prix)
- Date exacte de déclenchement de l'étape B (dépend de l'avancement réel Phase 4/5, pas une date calendaire fixe)
- Capacité et modèle exact du/des HDD pour le tier de sauvegarde (dépend du volume réel cumulé des dépôts Restic une fois Mailcow en place)
