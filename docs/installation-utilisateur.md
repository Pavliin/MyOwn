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

### À valider techniquement avant implémentation

- Création programmatique d'entrées Vaultwarden via API juste après un premier login (mécanisme établi dans l'écosystème Bitwarden/CLI `bw`, mais jamais essayé dans ce projet précis).
- Mapping groupe Authentik → groupe admin Nextcloud via `user_oidc` (piste pour remplacer le compte local `admin` par une identité SSO à terme — pas encore implémenté, le compte local resterait alors un filet de secours plutôt que l'identité admin courante).

## Onboarding / dashboard familial — fusionnés

Pas de formulaire de création de compte maison à construire : Authentik a déjà un moteur de flows avec auto-enrôlement (lien/QR code). Le vrai manque identifié, c'est un **point d'entrée unique** pour la famille — exactement ce que `architecture.md` §3 appelle déjà le "dashboard familial simple", jusqu'ici sans phase de roadmap assignée. Décision : traiter l'assistant de première utilisation et ce dashboard comme **un seul livrable**, lié à Authentik, plutôt que deux choses séparées.

**Contenu retenu** (décidé en discutant maintenance/monitoring, cf. Phase 4 de `roadmap.md`) :

- Liens vers chaque service + guide de première utilisation
- **Page de statut publique Uptime Kuma** intégrée — jamais de lien vers Grafana, réservé à l'admin
- Pointeur vers le salon Matrix partagé "État du système" (abonnable, une seule occurrence de l'info par panne — pas un canal de plus à créer, juste indiquer qu'il existe et comment le rejoindre)

## Ouvert

- Forme exacte du script installeur (langage, gestion d'erreurs, reprise sur échec partiel).
- Contenu précis du dashboard familial (au-delà des liens par service).
- Mapping groupe Authentik → admin Nextcloud (cf. ci-dessus).
