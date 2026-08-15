# Installation et onboarding utilisateur — conception (Phase 6)

Trace la réflexion sur l'installeur destiné aux utilisateurs moins techniques et la gestion des comptes admin qui en découle. Rattaché à la roadmap Phase 6 ("Onboarding simplifié pour utilisateurs non-techos") — discussion de direction, rien n'est implémenté à ce stade.

## Trois paliers d'utilisateurs, trois besoins différents

1. **Très technique** : clone le dépôt, déploie lui-même. Déjà couvert par `manuel-installation.md`.
2. **Moins technique** : veut un script à lancer + quelques commandes.
3. **"Lambda"** : doit être pris par la main de bout en bout.

Objectif actuel (pas le modèle business "machines pré-installées expédiées", hors scope pour l'instant — cf. `vision-long-terme.md`) : couvrir le palier 2 avec un vrai soin d'exécution, ce qui rapproche naturellement du palier 3 sans payer le coût d'un installeur graphique complet.

## Type d'installeur retenu

**Pas un ISO remplaçant l'OS.** L'installeur graphique d'Ubuntu Server (ou Desktop) fait déjà très bien le travail de partitionnement/réseau/compte système — pas de raison de le réinventer. Le travail custom se limite à **un script unique** ("type .exe Windows" en esprit — un seul artefact à lancer, pas une suite de commandes manuelles) qui prend le relais une fois l'OS installé : rejoue ce qui est aujourd'hui manuel dans `manuel-installation.md` (k3s, ArgoCD, KSOPS, secrets, certificats, hosts), avec prompts minimaux et valeurs par défaut sensées.

Un vrai installeur graphique bootable resterait une évolution possible **plus tard**, une fois une vraie demande palier 3 validée en usage réel — pas un point de départ.

## Modèle de gestion des comptes admin

**Constat de départ** (état réel du projet, vérifié service par service) : trois mécanismes différents et non coordonnés aujourd'hui.

| Service | Mécanisme actuel |
|---|---|
| Authentik | Assistant de premier démarrage — quiconque le complète en premier |
| ArgoCD / Grafana | Mot de passe auto-généré, récupérable via `kubectl` |
| Vaultwarden (`/admin`) | Jeton partagé (`ADMIN_TOKEN`), pas un compte |
| Nextcloud | Compte local `admin` pré-défini dans le secret de déploiement |
| Immich, Tuwunel | Premier compte inscrit devient admin ("premier arrivé, premier servi") |

**Problème identifié** : rien ne garantit que la bonne identité récupère les bons droits, et les secrets d'infrastructure (ArgoCD, Grafana, clé privée SOPS) ne sont accessibles qu'à l'opérateur technique (Robin) — pas à l'utilisateur final, propriétaire réel de sa solution. Contraire au principe fondamental du projet ("reprendre possession de ses données", `architecture.md` §1).

**Modèle cible retenu** : Authentik reste la seule source de vérité pour l'identité admin humaine. **Tous les secrets générés à l'installation (y compris les identifiants d'infrastructure) sont poussés dans le coffre Vaultwarden de l'utilisateur** — l'opérateur/installeur ne conserve aucune copie résiduelle après la mise en place. Argument de confiance direct pour l'ambition business long terme : "aucun accès caché après installation" devient vérifiable, pas une promesse sur parole.

### Séquencement

Deux étapes ne peuvent **pas** être automatisées, par design de sécurité (pas une limite technique contournable) :

1. **Premier flow Authentik** (création de l'identité admin racine) — nécessite un humain devant le navigateur.
2. **Création du mot de passe maître Vaultwarden** — chiffrement zero-knowledge, dérivé uniquement côté navigateur, jamais connu du serveur (déjà documenté dans `manuel-utilisateur.md`). Aucun installeur ne peut le générer à la place de l'utilisateur sans casser cette garantie.

Tout le reste s'automatise une fois ces deux étapes passées, dans la continuité de la même séquence :

1. Une fois le coffre déverrouillé pour la première fois, l'installeur pousse directement les secrets déjà générés (jeton admin Vaultwarden lui-même, mot de passe admin Nextcloud, mots de passe ArgoCD/Grafana, **clé privée age SOPS** — actuellement uniquement sur la machine de dev de Robin, cf. risque documenté dans `CLAUDE.md`) comme entrées dans ce coffre, via l'API Vaultwarden/Bitwarden.
2. Pour les services "premier arrivé = admin" (Immich, Tuwunel) : l'installeur se connecte automatiquement avec l'identité Authentik qui vient d'être créée, immédiatement après le déploiement de chaque service — avant que quiconque d'autre puisse y accéder.

### Validé (2026-08-15)

**Création programmatique d'entrées Vaultwarden via API juste après un premier login** — prototypé et confirmé en conditions réelles contre un compte de test jetable (créé manuellement par l'utilisateur, la définition du mot de passe maître restant l'étape humaine incompressible identifiée plus haut), via le CLI officiel `bw` (installé en local dans un dossier de travail, pas globalement — évite le besoin de droits admin sur la machine, cohérent avec ce que ferait un vrai installeur). Deux types d'entrées testés avec succès : note sécurisée et identifiant complet (utilisateur/mot de passe/URL, le cas réel pour ArgoCD/Grafana). Propriété de sécurité vérifiée en plus du simple succès de l'opération : interrogation directe de l'API Vaultwarden (`GET /api/ciphers`, hors `bw`) pour confirmer que le serveur ne stocke que du chiffré (format `CipherString` Bitwarden `type.iv|ciphertext|mac`) — aucun mot de passe en clair, y compris dans la réponse API brute. Items de test supprimés et session fermée après validation.

### Pas encore intégré à `scripts/install.sh` (2026-08-15)

Le mécanisme ci-dessus (push des secrets, auto-enregistrement admin sur Immich/Tuwunel) est validé isolément mais **jamais branché au script d'installation réel**. `scripts/install.sh` s'arrête aujourd'hui après le bootstrap GitOps + mkcert + `/etc/hosts` — il ne pilote ni le flow Authentik, ni la création du coffre Vaultwarden, ni le push de secrets qui devrait suivre.

**Risque de séquencement identifié en réfléchissant à l'intégration** : l'étape de bootstrap GitOps (déjà dans le script) déploie tous les services d'un coup, y compris Immich et Tuwunel dont l'admin se décide au "premier arrivé, premier servi" — donc dans l'ordre actuel du script, ces deux services sont exposés et vulnérables à cette course **avant même** que l'admin ait fini son propre flow Authentik. Un vrai script d'installation doit soit retarder l'exposition de ces services jusqu'à ce que l'admin Authentik existe, soit accepter cette fenêtre de risque comme acceptable en LAN fermé (à trancher explicitement, pas par défaut).

**Problème de cadencement plus large** : le script ne peut aujourd'hui ni savoir quand l'admin a fini le flow Authentik dans son navigateur, ni quand le coffre Vaultwarden est déverrouillé pour la première fois — ces deux étapes sont humaines et se passent dans un navigateur totalement découplé du script shell. Deux pistes possibles pour synchroniser script et navigateur :

- **Poll + ouverture automatique du navigateur par défaut** (léger, dans l'esprit "un seul artefact à lancer" déjà retenu) : le script ouvre l'URL Authentik (`xdg-open`/`open`), interroge périodiquement l'API Authentik pour détecter qu'un compte admin existe désormais, puis ouvre automatiquement l'URL Vaultwarden, interroge son API pour détecter la création du compte/déverrouillage, et ne déclenche le push de secrets qu'une fois ces deux signaux confirmés — même mécanisme de principe que le polling déjà utilisé pour détecter la confirmation humaine dans le pipeline mail (`notes-techniques.md`).
- **IHM graphique avec navigateur intégré** (proposée par l'utilisateur, 2026-08-15) : un vrai installeur graphique embarquant/capturant une fenêtre de navigateur pour afficher Authentik puis Vaultwarden à l'intérieur de sa propre IHM, garantissant visuellement le bon ordre. Plus robuste sur le cadencement (l'admin ne peut pas ouvrir les deux onglets dans le désordre), mais un saut d'investissement bien plus lourd : framework GUI + composant webview (type Tauri, plus léger qu'Electron mais toujours un moteur de rendu web à embarquer), packaging multi-plateforme — cohérent avec ce que `installation-utilisateur.md` qualifiait déjà plus haut de "palier 3", explicitement mis de côté "une fois une vraie demande palier 3 validée en usage réel — pas un point de départ".

**Recommandation retenue pour l'instant** : partir sur poll + ouverture automatique du navigateur pour boucler `install.sh` de bout en bout au palier 2 actuel — ça résout le vrai problème (empêcher l'admin de faire les choses dans le désordre, ou du moins le détecter et attendre) sans changer de nature d'outil. L'IHM à navigateur intégré reste la bonne évolution palier 3, à reprendre si l'usage réel avec des utilisateurs non-techos montre que le polling en ligne de commande est insuffisant ou trop anxiogène pour eux.

### À valider techniquement avant implémentation

- Mapping groupe Authentik → groupe admin Nextcloud via `user_oidc` (piste pour remplacer le compte local `admin` par une identité SSO à terme — pas encore implémenté, le compte local resterait alors un filet de secours plutôt que l'identité admin courante).
- Intégration du push de secrets et de l'auto-enregistrement admin (Immich/Tuwunel) dans `scripts/install.sh`, avec le mécanisme de cadencement (poll + navigateur) décrit ci-dessus.

## Onboarding / dashboard familial — fusionnés

Pas de formulaire de création de compte maison à construire : Authentik a déjà un moteur de flows avec auto-enrôlement (lien/QR code). Le vrai manque identifié, c'est un **point d'entrée unique** pour la famille — exactement ce que `architecture.md` §3 appelle déjà le "dashboard familial simple", jusqu'ici sans phase de roadmap assignée. Décision : traiter l'assistant de première utilisation et ce dashboard comme **un seul livrable**, lié à Authentik, plutôt que deux choses séparées.

**Contenu retenu** (décidé en discutant maintenance/monitoring, cf. Phase 4 de `roadmap.md`) :

- Liens vers chaque service + guide de première utilisation
- **Page de statut publique Uptime Kuma** intégrée — jamais de lien vers Grafana, réservé à l'admin
- Pointeur vers le salon Matrix partagé "État du système" (abonnable, une seule occurrence de l'info par panne — pas un canal de plus à créer, juste indiquer qu'il existe et comment le rejoindre)

**Constat réel (2026-08-14), en essayant de rejoindre le salon "État du système" depuis Element Web** : aucune fonction "Rejoindre un salon par alias" trouvée dans l'IHM (le "+" à côté de "Salons" ne propose que créer une discussion/un salon, pas en rejoindre un ; la barre de recherche générale propose de **créer** un salon plutôt que de résoudre l'alias existant) — alors même que la résolution de l'alias fonctionne parfaitement côté serveur (confirmé via l'API `GET /_matrix/client/v3/directory/room/...`). Seul un **lien direct `matrix.to`** (`https://matrix.to/#/#alias:serveur`) a fonctionné, en l'ouvrant depuis le navigateur pendant une session Element Web déjà connectée — et a bien rejoint le salon pour de vrai (vérifié via `joined_members`, pas juste un aperçu).

**Conséquence pour le dashboard familial** : donner des **liens `matrix.to` directs** vers chaque salon pertinent (pas seulement "État du système" — tout salon qu'on veut rendre facilement accessible), plutôt que des instructions du type "cherchez cet alias" qui supposent une fonction de recherche/jointure qui ne s'est pas montrée à l'usage. **À revérifier avec les clients mobiles** (Element X notamment, différé à la Phase 4) une fois utilisés en conditions réelles — l'IHM desktop web n'est peut-être pas représentative.

## Mises à jour des services sensibles — choix proposé à l'installation

Prolonge la décision prise dans `architecture.md` §6 (services sensibles vs. services d'infrastructure, synchronisation ArgoCD automatique vs. manuelle) avec deux précisions issues d'une discussion explicite avec l'utilisateur.

**Vérification décentralisée, jamais un push centralisé** : aucune installation ne doit avoir de canal permettant de notifier ou de déclencher une action chez une autre — ça romprait la souveraineté de chaque installation déjà actée (`architecture.md` §6, `vision-long-terme.md`). Le modèle retenu : chaque installation vérifie **elle-même**, périodiquement, si une version plus récente que celle qu'elle suit existe (ex. l'API GitHub Releases de ce dépôt) ; si oui, **son propre** bot Tuwunel prévient **sa propre** famille dans **son propre** salon. Personne ne pousse quoi que ce soit vers personne.

**Principe non négociable, quel que soit le mode choisi : aucune modification de l'applicatif sans annonce préalable.** Le choix proposé à l'installation (pour les services sensibles uniquement — cf. la liste dans `architecture.md` §6) ne porte donc jamais sur "prévenir ou pas", mais sur **qui déclenche la synchronisation une fois l'annonce faite** :

- **Manuel** : annonce → attente indéfinie → l'admin de cette installation déclenche lui-même la synchronisation quand il le juge bon.
- **Automatique** : annonce → délai de prévenance fixe (ex. 24-48h, exact non tranché) → la synchronisation se déclenche à l'échéance sans action requise de l'admin — mais jamais sans être passée par l'annonce d'abord.

Défaut proposé : manuel (le plus prudent) — l'installeur laisse le choix explicite pour un admin qui préfère consciemment le confort du mode automatique, plutôt que d'imposer une politique unique à toutes les installations.

## Ouvert

- Forme exacte du script installeur (langage, gestion d'erreurs, reprise sur échec partiel).
- Contenu précis du dashboard familial (au-delà des liens par service).
- Mapping groupe Authentik → admin Nextcloud (cf. ci-dessus).
- Durée exacte du délai de prévenance en mode automatique (24h/48h/autre), et mécanisme technique de vérification décentralisée des nouvelles versions (fréquence, source exacte — API GitHub Releases pressentie mais pas validée).
