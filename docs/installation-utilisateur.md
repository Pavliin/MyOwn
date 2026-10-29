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

Objectif : qu'un autre foyer puisse installer MyOwn avec son propre domaine, sans dépendre de l'installation de l'auteur. État des lieux de départ (2026-10-22) : le domaine `offsystem.fr` était écrit en dur dans 26 fichiers GitOps, 12 scripts **et dans 12 secrets chiffrés** (blueprints SSO, config Tuwunel…), et tous les secrets étaient chiffrés avec la clé de l'auteur — l'installeur ne savait que réinstaller cette installation-là.

Principe directeur : **une installation n'exige que ce que réclament les services cochés.** Un foyer qui n'ouvre rien vers internet n'a besoin ni de DynDNS ni de redirection de ports ; le mail, lui, exige en plus un serveur relais loué.

### Les deux niveaux réseau

Avoir un **nom de domaine** et être **accessible depuis internet** sont deux choses différentes : un domaine suffit à obtenir de vrais certificats (le cadenas du navigateur) sans ouvrir la moindre porte vers la maison. D'où deux niveaux, choisis en premier à l'installation. Le nom de domaine est donc **obligatoire** : c'est la seule barrière d'entrée, une dizaine d'euros par an.

**Pas de niveau sans domaine** (prévu au départ comme « niveau A », abandonné le 2026-10-29 avant d'être implémenté). En HTTP, sans certificat, il ne restait qu'Immich derrière Authentik : Vaultwarden, Nextcloud, Tuwunel, LiveKit et Mailu exigent HTTPS, Jellyfin dépend de Nextcloud, Ollama ne sert qu'au tri des mails. Les identifiants y auraient circulé en clair sur le réseau de la maison (Wi-Fi invité compris), passer ensuite à un domaine aurait changé toutes les adresses, et il aurait fallu maintenir des Ingress HTTP en double et imposer Pi-hole pour la résolution des noms. À réintroduire seulement si un vrai besoin « photos seules, zéro domaine » apparaît.

#### B — Accès à la maison seulement

**En clair** : on achète un nom (par exemple `famille-dupont.fr`) chez un fournisseur dont le service DNS est compatible. Tous les services fonctionnent, avec le cadenas, sur tous les appareils et dans les applications mobiles — sauf le mail. Mais uniquement à la maison : en déplacement, rien n'est accessible. C'est le niveau le plus prudent, puisque rien n'est ouvert vers internet. Passer plus tard au niveau C se fait sans rien perdre ni rien renommer.

**Techniquement** :

- Certificats Let's Encrypt obtenus par **défi DNS-01** (lego, via l'API du fournisseur DNS) : aucun port entrant n'est ouvert.
- DNS « split-horizon » : CoreDNS résout `*.domaine` vers Traefik pour le cluster ; pour les appareils de la maison, c'est le wildcard public (ou Pi-hole, optionnel) qui fait de même.
- Le fournisseur DNS doit être pris en charge par lego — plus d'une centaine le sont. **Fournisseur testé : Gandi.**
- Tuwunel sans fédération, mais son identité Matrix (`server_name` = le domaine) est définitive dès maintenant — c'est ce qui permet de passer en C sans recréer les comptes.
- LiveKit : appels possibles entre appareils de la maison seulement.
- Exclu : Mailu (recevoir du mail exige d'être joignable depuis internet) — l'installeur le retire de la sélection en l'expliquant.
- Accès d'administration à distance toujours possible via le VPN WireGuard (réservé à l'admin, pas aux services familiaux).

#### C — Accessible partout

**En clair** : comme B, mais les services sont joignables partout — depuis le téléphone en 4G, en vacances, par la famille qui habite loin. C'est aussi ce niveau qui permet les appels vidéo hors de la maison, d'échanger avec des personnes inscrites sur d'autres serveurs Matrix, et d'avoir sa propre adresse mail (ce dernier point demande en plus de louer un petit serveur relais, quelques euros par mois). La contrepartie : la maison devient visible depuis internet, et garder les mises à jour et les sauvegardes à jour devient indispensable.

**Techniquement** :

- B, plus des redirections de ports sur la box (listées par l'installeur selon les services choisis) : `443/tcp` ; LiveKit `7881/tcp`, `7882/udp`, `5349/tcp` (TURN) ; Mailu `993/tcp`, `465/tcp`.
- DynDNS (ddns-updater) : l'apex et le wildcard, en IPv4 et (si la machine en a) en IPv6.
- Fédération Matrix via `.well-known/matrix/server`.
- Mailu : en plus, un VPS relais (le port 25 sortant est bloqué par la plupart des box résidentielles), un enregistrement PTR, et les enregistrements DNS MX/SPF/DKIM/DMARC — à créer chez le fournisseur.
- Tous les services web sont exposés, derrière l'authentification Authentik ; les outils d'administration (ArgoCD, `kubectl`, SSH) ne le sont jamais.
- Lacunes connues : IPv6 entrant non pris en charge par le cluster (voir `notes-techniques.md`).

#### Compatibilité par service

| Service | B | C | Contrainte |
|---|---|---|---|
| Authentik, Vaultwarden, Nextcloud, Jellyfin, Immich, Ollama, Uptime Kuma, supervision | ✅ | ✅ | — |
| Tuwunel | ✅ sans fédération | ✅ | identité Matrix définitive |
| LiveKit | ✅ à la maison | ✅ | certificat TURN |
| Mailu | — | ✅ + VPS | réception internet, relais |

**Changer de niveau** : relancer l'installeur avec `MYOWN_EXPOSURE=internet` (ou `lan`) — mêmes noms, mêmes données. De B à C, il démarre le DynDNS et liste les ports à ouvrir ; de C à B, il arrête le DynDNS (son Secret est conservé pour un retour en C) et Mailu s'il était installé. Les enregistrements DNS publics déjà écrits restent chez le fournisseur : à supprimer à la main si l'on veut que le nom ne pointe plus vers la maison. Validé en VM le 2026-10-29 dans les deux sens (`notes-techniques.md`).

#### Quel domaine ?

- **Le cas courant** : un domaine acheté chez un registraire qui fournit aussi le DNS, inclus dans le prix (Gandi, OVH, Infomaniak…). Vérifier avant d'acheter que ce fournisseur figure dans la [liste de lego](https://go-acme.github.io/lego/dns/). On peut aussi acheter le domaine n'importe où et confier son DNS gratuitement à un fournisseur compatible (Cloudflare, deSEC).
- **Pour essayer gratuitement : un sous-domaine `<nom>.dedyn.io` de [deSEC](https://desec.io)** (association à but non lucratif, DNS géré par API, pris en charge par lego et ddns-updater). Suffisant pour une installation complète en B. Limites à connaître avant de s'en servir :
  - **l'identité Matrix est définitive** : les comptes seraient `@marie:<nom>.dedyn.io`, et passer plus tard à un vrai domaine obligerait à recréer les comptes de messagerie ;
  - **le mail n'y est pas crédible** : les grandes messageries se méfient des domaines gratuits ;
  - **la création de sous-domaines `dedyn.io` est suspendue** par deSEC depuis octobre 2026 (vague d'enregistrements abusifs), sans date de reprise — l'option ne vaut que lorsqu'elle sera rouverte, et n'a donc pas encore été testée avec MyOwn.
- **Ne conviennent pas** : le nom offert par la box (`xxxx.freeboxos.fr`) — ni sous-noms, ni accès au DNS par API pour le défi DNS-01 ; DuckDNS — un seul enregistrement de vérification à la fois, incompatible avec un certificat apex + wildcard.

#### Prérequis et protections transverses (ajoutés le 2026-10-22)

- **Vérification des signatures de commits par ArgoCD, avant toute ouverture à d'autres foyers.** Une installation applique ce que dit le dépôt suivi, avec tous les droits sur le cluster : suivre le dépôt du projet, c'est faire confiance au compte qui le publie (un compte compromis atteindrait toutes les installations qui synchronisent). Synchronisation manuelle et tags limitent déjà ce risque ; ArgoCD peut en plus refuser tout commit non signé par une clé de confiance. Le paramètre `repoURL` (suivre un fork) n'ajoute pas ce risque, il le rend seulement visible.
- **Adresse réelle des visiteurs** : le Service de Traefik est en `externalTrafficPolicy: Local` (corrigé le 2026-10-22, voir `notes-techniques.md`). C'est la condition pour que le filtrage par adresse des outils d'administration (ArgoCD, Grafana, Ollama : `<outil>.<domaine>`, réservés au réseau local et au VPN) ait un sens, et pour qu'Authentik distingue un attaquant du reste de la famille.

### Configuration d'installation

Un seul jeu de paramètres, dans les valeurs du chart `gitops/apps` lues par l'Application `root` — au même endroit que `revision` et `apps`, sans fichier d'état à part :

| Valeur | Rôle |
|---|---|
| `domain` | domaine de l'installation (obligatoire) |
| `exposure` | `lan` / `internet` (B / C) |
| `dnsProvider` | nom du fournisseur pour lego — générique dans le code, Gandi n'est cité que dans la documentation. Finalement **hors des valeurs de `root`** : seul Traefik s'en sert, et sa configuration est du bootstrap ; l'installeur le pose dans la surcouche Traefik et l'y relit à chaque relance (fait le 2026-10-27, avec l'e-mail ACME) |
| `repoURL` | dépôt suivi (celui du projet, ou un fork) |

Un seul schéma de noms : `<service>.<domain>`, à la maison comme depuis internet. Les noms `myown-*.local` historiques sont retirés.

### Secrets générés dans le cluster

Les secrets ne sont **plus jamais commités**. L'installeur les génère dans le cluster (`kubectl create secret`) :

- **idempotent** : une relance ne crée que ce qui manque, n'écrase jamais un secret existant ;
- **apparié** : les identifiants OIDC sont créés en une fois pour le service et pour Authentik ;
- ce qui contient le domaine sans être secret (blueprints Authentik, configuration Tuwunel) devient un fichier en clair dans le dépôt, le domaine étant injecté par Helm et les secrets lus à part (balise `!Env` des blueprints Authentik).

Environ 90 % des secrets sont aléatoires ou dérivés et se génèrent sans intervention ; restent à demander : l'e-mail de l'admin, les identifiants du fournisseur DNS, et ceux du relais mail (Mailu).

**Conséquence à ne pas sous-estimer** : les secrets n'existant plus ailleurs, leur sauvegarde devient critique — sauvegarde chiffrée des Secrets avec le reste (Restic), et dépôt dans le coffre Vaultwarden de l'admin (voir « Modèle de gestion des comptes admin » ci-dessous). SOPS, KSOPS et la clé age ne sont plus nécessaires à une nouvelle installation ; les fichiers `*.sops.yaml` de l'installation de l'auteur seront retirés du dépôt une fois sa propre installation migrée.

### Fournisseur DNS et DynDNS

- Certificats : fournisseur lego et identifiants en paramètres (secret générique `dns-provider-credentials`, avec les variables qu'attend lego pour ce fournisseur).
- DynDNS : **ddns-updater** (composant open source, nombreux fournisseurs) remplace le script maison.
- **Fait le 2026-10-27** (étape 2 ci-dessous) : `manuel-installation.md` §16 pour les paramètres, `notes-techniques.md` pour la migration de l'installation de l'auteur.
- DNS du mail : enregistrements affichés par l'installeur, à créer chez n'importe quel fournisseur.

### Ordre de réalisation

Chaque étape laisse l'installation de l'auteur fonctionnelle, et se vérifie par un rendu identique avant tout déploiement :

1. Domaine paramétré (les manifestes bruts deviennent de petits charts) et nouvelles valeurs `domain`/`dnsProvider`/`repoURL` ; retrait des noms `.local`.
2. Fournisseur DNS générique et DynDNS via ddns-updater.
3. Secrets générés, sauvegarde des secrets, migration de l'installation de l'auteur hors de KSOPS (les secrets existants conservés, jamais régénérés), retrait des fichiers SOPS. *Génération, sortie de KSOPS et sauvegarde faites le 2026-10-27 (`notes-techniques.md`) ; le retrait des fichiers chiffrés attend une copie hors machine de la sauvegarde (pour l'installation de l'auteur, ces fichiers sont aujourd'hui la seule copie hors machine des secrets).*
4. Niveaux B/C dans l'installeur (valeur `exposure`), validés en VM pour chaque niveau et pour le passage de l'un à l'autre. *Fait le 2026-10-29 ; second fournisseur DNS (deSEC) à tester quand ses inscriptions rouvriront.*
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
