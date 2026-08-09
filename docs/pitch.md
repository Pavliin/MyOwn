# Présentation du projet — reprendre possession de nos données

Ce document présente le projet à des profils techniques (devops, SRE, sécurité, dev). Il complète deux documents plus détaillés dans ce dépôt : [`architecture.md`](architecture.md) (choix techniques complets) et [`roadmap.md`](roadmap.md) (plan de développement phase par phase).

## Le constat

Nos données du quotidien — photos de famille, mots de passe, correspondance, messages — vivent sur les serveurs de quelques acteurs (Google, Meta, Microsoft...) qui les exploitent commercialement, en changent les conditions d'usage unilatéralement, et représentent chacun un point de défaillance unique pour des pans entiers de notre vie numérique. Ce n'est pas un problème théorique : c'est le compte Google qui centralise mail, photos, contacts et agenda d'une même personne, sans alternative crédible et accessible pour la plupart des gens.

Les alternatives open source existent depuis des années (Nextcloud, Immich, Vaultwarden, Matrix...) mais restent, prises séparément, hors de portée d'un utilisateur non technique : trop de services à assembler, à sécuriser, à maintenir.

## La vision

Un cloud personnel auto-hébergé, chez moi, ouvert à un cercle proche (famille, amis), qui couvre les usages numériques du quotidien — fichiers/photos, mots de passe, messagerie, mail — avec une expérience d'usage aussi simple que les services qu'il remplace, mais où les données restent possédées et maîtrisées par leurs utilisateurs.

Le détail des principes directeurs (open source, léger, accessible, sécurisé, stable) est dans [`architecture.md`](architecture.md#2-principes-directeurs).

## Pourquoi ce projet a une vraie chance d'aboutir

La plupart des projets d'auto-hébergement personnel s'essoufflent sur l'exploitation dans la durée : pas de sauvegarde testée, pas de monitoring, mises à jour manuelles oubliées, panne un jour et perte de données le lendemain. C'est précisément le métier que je pratique professionnellement — MCO d'applicatifs sous SLA, GitOps, CI avec scan de CVE, déploiement automatisé. Ce projet applique ces pratiques à un contexte personnel plutôt que de partir d'une approche "tutoriel + docker-compose" fragile.

## Ce qu'on construit — et ce qu'on ne construit pas

**On assemble des briques open source matures**, pas de réécriture des composants critiques (mot de passe, mail, stockage) : le risque sécurité/fiabilité d'une réimplémentation maison dépasse largement le gain de cohérence UX qu'on pourrait y gagner.

**Le développement custom se concentre sur l'intégration** : identité unique (SSO) devant tous les services, automatisations, IA locale (Ollama) pour des usages qui le justifient (tri de mail, à terme d'autres automatisations) — sans qu'aucune donnée ne sorte du réseau local.

| Brique | Solution retenue |
|---|---|
| Identité / SSO | Authentik |
| Mots de passe | Vaultwarden |
| Fichiers, contacts, calendrier | Nextcloud |
| Photos / vidéos | Immich |
| Messagerie (groupes, appels vidéo, fédération) | Tuwunel + Element X + LiveKit |
| Mail | Mailcow + façade VPS dédiée |
| IA locale | Ollama |
| Orchestration | k3s + ArgoCD (GitOps) + Traefik |
| Monitoring | Prometheus + Grafana + Uptime Kuma |
| Sauvegarde | Restic, chiffré, offsite chez un participant du projet |

Détail et justification de chaque choix : [`architecture.md`](architecture.md#5-composants-applicatifs).

## Feuille de route condensée

MVP démontrable visé à 3-6 mois (mots de passe + fichiers/photos + messagerie). Le mail, composant le plus complexe techniquement (délivrabilité, réputation IP), est traité après ce premier MVP.

1. **Socle** — k3s, ArgoCD, Traefik, SSO, monitoring
2. **Mots de passe** (Vaultwarden) — premier service en usage réel
3. **Fichiers & photos** (Nextcloud + Immich)
4. **Messagerie** (Tuwunel + Element X + LiveKit) — *point de démo MVP*
5. **Bascule infra réelle & Mail** (mini PC + domaine, façade VPS + Mailcow)
6. **IA locale** (Ollama)
7. **Montée en échelle** — profils de dimensionnement matériel, multi-nœuds, ouverture à d'autres serveurs fédérés

Détail phase par phase avec critères de sortie : [`roadmap.md`](roadmap.md).

## Compétences techniques mobilisées

Pour référence :

- **Kubernetes / GitOps** — exploitation de la plateforme, écriture de manifests/Helm charts
- **Sécurité** — durcissement, gestion des secrets, scan de vulnérabilités
- **Réseau** — DNS, TLS, exposition mail (SPF/DKIM/DMARC)
- **Mobile Android** — expérience utilisateur des apps, automatisation d'onboarding
- **Usage réel** — le critère de sortie de chaque phase de la roadmap est un usage réel, pas un déploiement technique qui fonctionne en théorie

## Risques assumés, sans les cacher

- **Mono-nœud en phase 1** : point de défaillance unique assumé au démarrage, la topologie k3s permet une évolution vers du multi-nœuds sans réécriture.
- **Dépendance à la disponibilité du nœud de sauvegarde** hébergé chez un participant.
- **Délivrabilité mail** : la façade VPS mitige le risque de blacklist résidentielle mais ne l'élimine pas complètement, en particulier au démarrage d'un nouveau domaine.
- **Responsabilité informelle d'opérateur** vis-à-vis de la famille/des amis qui utiliseront le service (disponibilité, sécurité de leurs données) — sujet encore ouvert.

Détail complet : [`architecture.md`](architecture.md#11-limites-connues-et-risques-assumés).
