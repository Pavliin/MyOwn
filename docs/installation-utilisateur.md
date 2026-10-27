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

## Choix des services à installer (décidé le 2026-10-10)

Toutes les personnes qui installent MyOwn ne voudront pas toute la solution. L'installeur laisse donc choisir les services, et ce choix évolue dans le temps : **relancer l'installeur** permet d'ajouter un service non installé, ou d'arrêter un service déjà actif.

- **Socle non désactivable : Authentik et Vaultwarden.** Authentik est la seule source d'identité. Vaultwarden reçoit tous les secrets générés à l'installation (modèle admin ci-dessous). Choix de l'utilisateur : socle minimal plutôt qu'un socle incluant Tuwunel/Uptime Kuma. **Conséquence assumée** : sans Tuwunel, il n'y a ni salon d'alertes, ni annonces avant mise à jour (règle « aucune modification sans annonce préalable », plus bas). Un canal de repli reste à définir pour ce cas, pas encore traité.
- **Dépendances imposées** : Jellyfin requiert Nextcloud (médiathèque), LiveKit requiert Tuwunel. Les synchros de certificats suivent leur service.
- **Arrêter ne supprime jamais les données** (choix de l'utilisateur) : pods supprimés, volumes conservés, réactivation à l'identique. Une purge définitive, si elle est un jour nécessaire, sera une action séparée et explicite.
- **L'état installé vit dans le cluster** (filtre de l'Application `root`), pas dans un fichier qui pourrait diverger.

Implémenté dans `scripts/install.sh` + `scripts/lib/services.sh`, mode d'emploi dans `manuel-installation.md` §14.3.

**Limites connues** : les blueprints Authentik de **tous** les services sont appliqués quel que soit le choix (un service non installé apparaît quand même comme application SSO dans Authentik) ; même chose pour les noms d'hôte de `coredns-custom.yaml` et les sondes d'Uptime Kuma. Sans conséquence fonctionnelle, à rendre conditionnel plus tard.

## Installation indépendante — niveaux réseau, configuration, secrets (décidé le 2026-10-22)

Objectif : qu'un autre foyer puisse installer MyOwn avec son propre domaine (ou sans domaine), sans dépendre de l'installation de l'auteur. État des lieux de départ (2026-10-22) : le domaine `offsystem.fr` était écrit en dur dans 26 fichiers GitOps, 12 scripts **et dans 12 secrets chiffrés** (blueprints SSO, config Tuwunel…), et tous les secrets étaient chiffrés avec la clé de l'auteur — l'installeur ne savait que réinstaller cette installation-là.

Principe directeur : **une installation n'exige que ce que réclament les services cochés.** Un foyer qui ne veut que Jellyfin et Immich n'a besoin ni de nom de domaine, ni de fournisseur DNS, ni de serveur loué ; le mail, lui, exige tout cela.

### Les trois niveaux réseau

Avoir un **nom de domaine** et être **accessible depuis internet** sont deux choses différentes : un domaine suffit à obtenir de vrais certificats (le cadenas du navigateur) sans ouvrir la moindre porte vers la maison. D'où trois niveaux, choisis en premier à l'installation.

#### A — Sans nom de domaine

**En clair** : tout reste à la maison, sur le réseau de la box, sans rien acheter ni rien régler sur la box. C'est l'installation la plus simple. En contrepartie, il n'y a pas de cadenas dans le navigateur : les services qui exigent une connexion sécurisée — les mots de passe, les fichiers et l'agenda, la messagerie, les appels, le mail — ne sont pas disponibles. Les services restent inaccessibles en dehors de la maison, et toute personne connectée au même réseau (Wi-Fi d'un invité compris) pourrait en théorie lire ce qui y circule, mots de passe de connexion inclus.

**Techniquement** :

- Services servis en **HTTP**, sous un suffixe local (`<service>.<suffixe>`) résolu par Pi-hole ou `/etc/hosts`.
- Aucun certificat valide (une autorité locale type mkcert est possible mais doit être installée sur chaque appareil, et n'est pas reconnue par la plupart des applications mobiles — non retenu).
- Compatibles : Authentik, Jellyfin, Immich, Ollama, Uptime Kuma, supervision.
- Exclus : Vaultwarden (le chiffrement côté navigateur exige un contexte sécurisé), Nextcloud (`user_oidc` refuse le HTTP), Tuwunel (cookie de session SSO marqué `Secure`), LiveKit, Mailu.
- Le trafic, y compris l'authentification SSO, circule en clair sur le réseau local.

#### B — Nom de domaine, accès à la maison seulement

**En clair** : on achète un nom (par exemple `famille-dupont.fr`, une dizaine d'euros par an) chez un fournisseur dont le service DNS est compatible. Tous les services fonctionnent, avec le cadenas, sur tous les appareils et dans les applications mobiles — sauf le mail. Mais uniquement à la maison : en déplacement, rien n'est accessible. C'est le niveau le plus prudent, puisque rien n'est ouvert vers internet. Passer plus tard au niveau C se fait sans rien perdre ni rien renommer.

**Techniquement** :

- Certificats Let's Encrypt obtenus par **défi DNS-01** (lego, via l'API du fournisseur DNS) : aucun port entrant n'est ouvert.
- DNS « split-horizon » : Pi-hole (ou CoreDNS pour le cluster) résout `*.domaine` vers l'adresse locale du serveur.
- Le fournisseur DNS doit être pris en charge par lego — plus d'une centaine le sont. **Premier fournisseur testé : Gandi.**
- Tuwunel sans fédération, mais son identité Matrix (`server_name` = le domaine) est définitive dès maintenant — c'est ce qui permet de passer en C sans recréer les comptes.
- LiveKit : appels possibles entre appareils de la maison seulement.
- Exclu : Mailu (recevoir du mail exige d'être joignable depuis internet).
- Accès d'administration à distance toujours possible via le VPN WireGuard (réservé à l'admin, pas aux services familiaux).

#### C — Nom de domaine, accessible partout

**En clair** : comme B, mais les services sont joignables partout — depuis le téléphone en 4G, en vacances, par la famille qui habite loin. C'est aussi ce niveau qui permet les appels vidéo hors de la maison, d'échanger avec des personnes inscrites sur d'autres serveurs Matrix, et d'avoir sa propre adresse mail (ce dernier point demande en plus de louer un petit serveur relais, quelques euros par mois). La contrepartie : la maison devient visible depuis internet, et garder les mises à jour et les sauvegardes à jour devient indispensable.

**Techniquement** :

- B, plus des redirections de ports sur la box (listées par l'installeur selon les services choisis) : `443/tcp` ; LiveKit `7881/tcp`, `7882/udp`, `5349/tcp` (TURN) ; Mailu `993/tcp`, `465/tcp`.
- DynDNS (ddns-updater) si l'adresse IP publique change.
- Fédération Matrix via `.well-known/matrix/server`.
- Mailu : en plus, un VPS relais (le port 25 sortant est bloqué par la plupart des box résidentielles), un enregistrement PTR, et les enregistrements DNS MX/SPF/DKIM/DMARC — l'installeur les affiche, à créer chez le fournisseur.
- Tous les services web sont exposés, derrière l'authentification Authentik ; les outils d'administration (ArgoCD, `kubectl`, SSH) ne le sont jamais.
- Lacunes connues : IPv6 entrant non pris en charge par le cluster (voir `notes-techniques.md`).

#### Compatibilité par service

| Service | A | B | C | Contrainte |
|---|---|---|---|---|
| Authentik, Jellyfin, Immich, Ollama, Uptime Kuma, supervision | ✅ | ✅ | ✅ | — |
| Vaultwarden | — | ✅ | ✅ | HTTPS obligatoire |
| Nextcloud | — | ✅ | ✅ | HTTPS obligatoire |
| Tuwunel | — | ✅ sans fédération | ✅ | identité Matrix définitive |
| LiveKit | — | ✅ à la maison | ✅ | certificat TURN |
| Mailu | — | — | ✅ + VPS | réception internet, relais |

**Changer de niveau** : de B à C, il suffit d'ouvrir les ports et d'activer le DynDNS — mêmes noms, mêmes données. De A à B, les adresses des services changent (suffixe local → domaine) et les appareils doivent être reconfigurés. Conseil donné à l'installation : choisir B dès qu'un passage à C est envisageable.

#### Prérequis et protections transverses (ajoutés le 2026-10-22)

- **Pi-hole est un prérequis du niveau A.** Sans domaine public, rien d'autre ne fait connaître aux appareils de la maison les noms `<service>.<suffixe>` : l'installeur met Pi-hole en place avec une entrée couvrant tout le suffixe, et la seule action manuelle est de régler, dans la box, le DNS distribué aux appareils sur l'adresse du serveur. Suffixe recommandé : `home.arpa` (RFC 8375, réservé aux réseaux domestiques) — jamais `.local`, réservé à la découverte automatique (mDNS) et source de conflits sur macOS/iOS/Linux. En B et C, Pi-hole reste optionnel (il ne sert qu'au filtrage et à éviter le détour par la box).
- **Vérification des signatures de commits par ArgoCD, avant toute ouverture à d'autres foyers.** Une installation applique ce que dit le dépôt suivi, avec tous les droits sur le cluster : suivre le dépôt du projet, c'est faire confiance au compte qui le publie (un compte compromis atteindrait toutes les installations qui synchronisent). Synchronisation manuelle et tags limitent déjà ce risque ; ArgoCD peut en plus refuser tout commit non signé par une clé de confiance. Le paramètre `repoURL` (suivre un fork) n'ajoute pas ce risque, il le rend seulement visible.
- **Adresse réelle des visiteurs** : le Service de Traefik est en `externalTrafficPolicy: Local` (corrigé le 2026-10-22, voir `notes-techniques.md`). C'est la condition pour que le filtrage par adresse des outils d'administration (ArgoCD, Grafana, Ollama : `<outil>.<domaine>`, réservés au réseau local et au VPN) ait un sens, et pour qu'Authentik distingue un attaquant du reste de la famille.

### Configuration d'installation

Un seul jeu de paramètres, dans les valeurs du chart `gitops/apps` lues par l'Application `root` — au même endroit que `revision` et `apps`, sans fichier d'état à part :

| Valeur | Rôle |
|---|---|
| `domain` | domaine (niveaux B/C) ou suffixe local (niveau A) |
| `exposure` | `none` / `lan` / `internet` (A / B / C) |
| `dnsProvider` | nom du fournisseur pour lego (B/C) — générique dans le code, Gandi n'est cité que dans la documentation. Finalement **hors des valeurs de `root`** : seul Traefik s'en sert, et sa configuration est du bootstrap ; l'installeur le pose dans la surcouche Traefik et l'y relit à chaque relance (fait le 2026-10-27, avec l'e-mail ACME) |
| `repoURL` | dépôt suivi (celui du projet, ou un fork) |

Un seul schéma de noms : `<service>.<domain>`, à la maison comme depuis internet. Les noms `myown-*.local` historiques sont retirés.

### Secrets générés dans le cluster

Les secrets ne sont **plus jamais commités**. L'installeur les génère dans le cluster (`kubectl create secret`) :

- **idempotent** : une relance ne crée que ce qui manque, n'écrase jamais un secret existant ;
- **apparié** : les identifiants OIDC sont créés en une fois pour le service et pour Authentik ;
- ce qui contient le domaine sans être secret (blueprints Authentik, configuration Tuwunel) devient un fichier en clair dans le dépôt, le domaine étant injecté par Helm et les secrets lus à part (balise `!Env` des blueprints Authentik).

Environ 90 % des secrets sont aléatoires ou dérivés et se génèrent sans intervention ; restent à demander : l'e-mail de l'admin, les identifiants du fournisseur DNS (B/C), et ceux du relais mail (Mailu).

**Conséquence à ne pas sous-estimer** : les secrets n'existant plus ailleurs, leur sauvegarde devient critique — sauvegarde chiffrée des Secrets avec le reste (Restic), et dépôt dans le coffre Vaultwarden de l'admin (voir « Modèle de gestion des comptes admin » ci-dessous). SOPS, KSOPS et la clé age ne sont plus nécessaires à une nouvelle installation ; les fichiers `*.sops.yaml` de l'installation de l'auteur seront retirés du dépôt une fois sa propre installation migrée.

### Fournisseur DNS et DynDNS

- Certificats : fournisseur lego et identifiants en paramètres (secret générique `dns-provider-credentials`, avec les variables qu'attend lego pour ce fournisseur).
- DynDNS : **ddns-updater** (composant open source, nombreux fournisseurs) remplace le script maison.
- **Fait le 2026-10-27** (étape 2 ci-dessous) : `manuel-installation.md` §16 pour les paramètres, `notes-techniques.md` pour la migration de l'installation de l'auteur.
- DNS du mail : enregistrements affichés par l'installeur, à créer chez n'importe quel fournisseur.

### Ordre de réalisation

Chaque étape laisse l'installation de l'auteur fonctionnelle, et se vérifie par un rendu identique avant tout déploiement :

1. Domaine paramétré (les manifestes bruts deviennent de petits charts) et nouvelles valeurs `domain`/`exposure`/`dnsProvider`/`repoURL` ; retrait des noms `.local`.
2. Fournisseur DNS générique et DynDNS via ddns-updater.
3. Secrets générés, sauvegarde des secrets, migration de l'installation de l'auteur hors de KSOPS (les secrets existants conservés, jamais régénérés), retrait des fichiers SOPS. *Génération et sortie de KSOPS faites le 2026-10-27 (`notes-techniques.md`) ; restent la sauvegarde et le retrait des fichiers.*
4. Niveaux A/B/C dans l'installeur, validés en VM pour chaque niveau.
5. Flow admin : les secrets générés rangés dans le coffre Vaultwarden.

## Modèle de gestion des comptes admin

**Constat de départ** (état réel du projet, vérifié service par service) : trois mécanismes différents et non coordonnés aujourd'hui.

| Service | Mécanisme actuel |
|---|---|
| Authentik | Assistant de premier démarrage — quiconque le complète en premier |
| ArgoCD / Grafana | Mot de passe auto-généré, récupérable via `kubectl` |
| Vaultwarden (`/admin`) | Jeton partagé (`ADMIN_TOKEN`), pas un compte |
| Nextcloud | Compte local `admin` pré-défini dans le secret de déploiement |
| Immich, Tuwunel | Premier compte inscrit devient admin ("premier arrivé, premier servi") |
| Mailu | Compte bootstrap `admin@<domaine>` (secret de déploiement), totalement séparé de l'identité SSO — celle-ci n'obtient les droits admin qu'après une promotion manuelle |

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

### Pas encore intégré à `scripts/install.sh` (2026-08-15, toujours vrai au 2026-10-10)

Le mécanisme ci-dessus (push des secrets, auto-enregistrement admin sur Immich/Tuwunel) est validé isolément mais **jamais branché au script d'installation réel**. `scripts/install.sh` installe désormais le vrai k3s bare-metal avec choix des services (2026-10-10), mais s'arrête toujours après le bootstrap GitOps — il ne pilote ni le flow Authentik, ni la création du coffre Vaultwarden, ni le push de secrets qui devrait suivre.

**Risque de séquencement identifié en réfléchissant à l'intégration** : l'étape de bootstrap GitOps (déjà dans le script) déploie tous les services d'un coup, y compris Immich et Tuwunel dont l'admin se décide au "premier arrivé, premier servi" — donc dans l'ordre actuel du script, ces deux services sont exposés et vulnérables à cette course **avant même** que l'admin ait fini son propre flow Authentik. Un vrai script d'installation doit soit retarder l'exposition de ces services jusqu'à ce que l'admin Authentik existe, soit accepter cette fenêtre de risque comme acceptable en LAN fermé (à trancher explicitement, pas par défaut).

**Problème de cadencement plus large** : le script ne peut aujourd'hui ni savoir quand l'admin a fini le flow Authentik dans son navigateur, ni quand le coffre Vaultwarden est déverrouillé pour la première fois — ces deux étapes sont humaines et se passent dans un navigateur totalement découplé du script shell. Deux pistes possibles pour synchroniser script et navigateur :

- **Poll + ouverture automatique du navigateur par défaut** (léger, dans l'esprit "un seul artefact à lancer" déjà retenu) : le script ouvre l'URL Authentik (`xdg-open`/`open`), interroge périodiquement l'API Authentik pour détecter qu'un compte admin existe désormais, puis ouvre automatiquement l'URL Vaultwarden, interroge son API pour détecter la création du compte/déverrouillage, et ne déclenche le push de secrets qu'une fois ces deux signaux confirmés — même mécanisme de principe que le polling déjà utilisé pour détecter la confirmation humaine dans le pipeline mail (`notes-techniques.md`).
- **IHM graphique avec navigateur intégré** (proposée par l'utilisateur, 2026-08-15) : un vrai installeur graphique embarquant/capturant une fenêtre de navigateur pour afficher Authentik puis Vaultwarden à l'intérieur de sa propre IHM, garantissant visuellement le bon ordre. Plus robuste sur le cadencement (l'admin ne peut pas ouvrir les deux onglets dans le désordre), mais un saut d'investissement bien plus lourd : framework GUI + composant webview (type Tauri, plus léger qu'Electron mais toujours un moteur de rendu web à embarquer), packaging multi-plateforme — cohérent avec ce que `installation-utilisateur.md` qualifiait déjà plus haut de "palier 3", explicitement mis de côté "une fois une vraie demande palier 3 validée en usage réel — pas un point de départ".

**Recommandation retenue pour l'instant** : partir sur poll + ouverture automatique du navigateur pour boucler `install.sh` de bout en bout au palier 2 actuel — ça résout le vrai problème (empêcher l'admin de faire les choses dans le désordre, ou du moins le détecter et attendre) sans changer de nature d'outil. L'IHM à navigateur intégré reste la bonne évolution palier 3, à reprendre si l'usage réel avec des utilisateurs non-techos montre que le polling en ligne de commande est insuffisant ou trop anxiogène pour eux.

### À valider techniquement avant implémentation

- Mapping groupe Authentik → groupe admin Nextcloud via `user_oidc` (piste pour remplacer le compte local `admin` par une identité SSO à terme — pas encore implémenté, le compte local resterait alors un filet de secours plutôt que l'identité admin courante).
- **Promotion automatique de l'identité SSO en admin Mailu** : Mailu expose une vraie API REST pour ça (`PATCH /api/v1/user/<email>` avec `{"global_admin": true}`), protégée par un jeton (`API_TOKEN`, désactivé par défaut — à générer comme secret SOPS). Un script dans l'esprit de `scripts/jellyfin-sso-setup.py`/`scripts/authentik-outpost-config.sh` attendrait que le compte SSO cible existe réellement (auto-provisionné par `proxyAuth` à sa première connexion) avant d'appeler cette API — évite le contournement actuel (port-forward direct vers `mailu-admin`, connexion avec le compte bootstrap `admin@<domaine>`, promotion manuelle via l'UI). Existe aussi une commande CLI (`flask mailu admin`) côté conteneur, mais elle est pensée pour créer/mettre à jour un compte (exige un mot de passe en argument) — pas adaptée pour ne toucher que `global_admin` sur un compte existant sans effet de bord sur son mot de passe.
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

- Forme exacte du script installeur : tranché en partie (2026-10-10) — bash, liste à cocher `whiptail`, chaque étape rejouable donc une simple relance sert de reprise sur échec partiel. Reste ouvert : l'intégration du flow admin (Authentik, Vaultwarden) dans ce script.
- Contenu précis du dashboard familial (au-delà des liens par service).
- Mapping groupe Authentik → admin Nextcloud (cf. ci-dessus).
- Durée exacte du délai de prévenance en mode automatique (24h/48h/autre), et mécanisme technique de vérification décentralisée des nouvelles versions (fréquence, source exacte — API GitHub Releases pressentie mais pas validée).
