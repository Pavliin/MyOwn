# Dossier d'architecture

## 1. Vision

Reprendre possession de ses données et services numériques du quotidien (fichiers, photos/vidéos, mots de passe, messagerie, mail) en les auto-hébergeant, pour soi et un cercle proche (famille, amis), sans dépendre des GAFAM — y compris depuis le téléphone Android, le point d'entrée principal des fuites de données au quotidien.

## 2. Principes directeurs

| Principe | Implication concrète |
|---|---|
| Open source / libre | Toutes les briques retenues sont open source ; le code d'intégration développé pour ce projet le sera aussi |
| Léger / peu coûteux | Un seul mini PC en phase 1, coûts récurrents minimisés (un seul poste accepté : la façade mail) |
| Accessible aux non-techos | Une identité unique (SSO), une seule app par usage (pas de doublons), UX proche des standards grand public |
| Sécurisé | Chiffrement au repos et en transit, secrets gérés hors du dépôt Git, principe du moindre privilège |
| Stable | GitOps + orchestration k8s (déjà maîtrisés professionnellement), sauvegardes testées, monitoring actif |

## 3. Approche : assembler, pas réinventer

Le projet n'est pas une réécriture des briques critiques (mot de passe, mail, stockage) — ces domaines sont matures, audités et à fort coût d'erreur. Le développement custom se concentre sur la **couche d'intégration** :

- Identité unique (SSO) devant tous les services
- Automatisations inter-services (ex : notification unifiée, tri intelligent)
- IA locale (Ollama) pour des fonctions qui justifient du code maison : tri/résumé de mails, à terme d'autres automatisations
- Dashboard familial simple (état des services, accès rapides)

## 4. Vue d'ensemble

```
                         Utilisateurs (famille/amis, 4-9)
                                     │
                    Android (apps dédiées par service)
                                     │
                         Domaine (à acquérir) + DNS
                                     │
                ┌────────────────────┴────────────────────┐
                │                                          │
        VPS façade mail (~5€/mois)                 Accès direct (HTTPS)
        Postfix relay IN/OUT                        via Traefik + Let's Encrypt
        (bonne réputation IP)                                │
                │                                          │
                └──────────────► Domicile (mini PC, k3s) ◄──┘
                                     │
        ┌───────────┬───────────┬───────────┬───────────┬───────────┐
        │ Authentik  │ Vaultwarden│ Nextcloud │  Immich   │  Tuwunel  │
        │   (SSO)    │   (mdp)   │ (fichiers)│ (photos)  │(messagerie)│
        └───────────┴───────────┴───────────┴───────────┴───────────┘
                │                                          │
             Mailcow                                    LiveKit
           (stockage mail)                          (appels vidéo groupe)
                │
        Ollama (tri/résumé mail, local)

        Monitoring : Prometheus + Grafana + Uptime Kuma
        Sauvegarde : Restic (chiffré) ──────────► NAS chez un ami (offsite)
```

## 5. Composants applicatifs

### 5.1 Identité — Authentik

SSO/OIDC devant tous les services. Un seul compte par personne. Choisi plutôt que Keycloak pour une empreinte plus légère et une administration plus simple.

### 5.2 Mots de passe — Vaultwarden

Réimplémentation Rust légère de l'API Bitwarden. Compatible avec toutes les apps officielles Bitwarden (Android, extensions navigateur, desktop). Premier service à livrer : risque faible, valeur immédiate.

### 5.3 Fichiers, contacts, calendrier — Nextcloud

Suite complète plutôt qu'un empilement de services séparés (fichiers + Radicale/Baïkal pour contacts/calendrier) : moins de composants à opérer et à sécuriser pour un gain de légèreté marginal à l'échelle de 4-9 utilisateurs.

### 5.4 Photos / vidéos — Immich

Remplace Google Photos. ML local embarqué (reconnaissance faciale, recherche sémantique), backup automatique depuis Android très proche en UX de l'original. Pas de développement custom nécessaire ici.

### 5.5 Messagerie — Tuwunel + Element X + LiveKit

- **Tuwunel** (serveur Matrix, Rust) : successeur officiel de Conduwuit — **Conduwuit lui-même est archivé et n'est plus maintenu en amont**, découvert en préparant le déploiement de la Phase 3, donc écarté avant tout déploiement réel. Deux successeurs actifs existaient : Continuwuity (continuation communautaire, pas de SSO natif confirmé) et Tuwunel (adopté à l'échelle gouvernementale — Suisse —, staffé à temps plein, support OIDC natif déjà mergé, cohérent avec le "tout par Authentik" du reste de ce projet) ; Tuwunel retenu. Léger, adapté à un petit serveur personnel/familial, sans base Postgres séparée (RocksDB embarqué).
- **Fédération native** : condition du besoin exprimé de "discovery" avec d'autres serveurs personnels tiers (comme l'email), impossible avec WhatsApp/Signal.
- **Spaces** : équivalent Matrix des "communautés" WhatsApp.
- **LiveKit** : SFU léger pour les appels vidéo de groupe (3-4 personnes) via Element Call.
- **Element X** : client Android.

### 5.6 Mail — Mailcow + façade VPS

Le composant le plus risqué techniquement (cf. §7). Mailcow (Postfix/Dovecot/Rspamd/SOGo) pour la maturité et le webmail intégré, stockage réel à domicile. Un VPS à bonne réputation IP (Hetzner/OVH/Scaleway, ~5€/mois) sert de façade SMTP entrée/sortie et relaie vers le domicile — seule dépense récurrente acceptée du projet.

### 5.7 IA locale — Ollama

Modèle local **Qwen3 8B**, retenu après un comparatif réel contre Mistral 7B et Llama 3.1 8B sur le tri/résumé multilingue (français/anglais/russe) et l'extraction structurée d'événements/échéances — net devant sur ce dernier point (le vrai besoin pour la création d'événements/tâches Calendrier/Tasks Nextcloud), chiffrage complet dans `notes-techniques.md`. Origine chinoise (Alibaba Cloud) acceptée en connaissance de cause malgré une préférence de départ pour une solution française, l'écart mesuré étant net. Aucune donnée ne sort du réseau local. Assistant en tâche de fond, pas de chat — principe appliqué à toute action qui modifie une donnée : l'IA propose, l'utilisateur valide (canal : bot Tuwunel), jamais d'écriture automatique silencieuse. Extension possible à d'autres automatisations une fois le socle stable.

## 6. Infrastructure & orchestration

- **k3s mono-nœud** sur le mini PC en phase 1 (base sqlite embarquée), avec bascule vers etcd embarqué prévue pour une topologie multi-nœuds ultérieure — pas de réécriture nécessaire, changement de topologie uniquement.
- **Développement** sur poste personnel via k3d/kind, miroir de la prod.
- **GitOps via ArgoCD** : déploiement piloté par ce dépôt Git, cohérent avec la pratique professionnelle de l'auteur. **ArgoCD n'est pas l'orchestrateur** — k3s l'est, et continue de faire tourner tous les services indépendamment d'ArgoCD ; ArgoCD ne fait que réconcilier l'état du cluster avec git, rien ne dépend de lui à l'exécution. Chaque déploiement MyOwn a sa propre instance ArgoCD, locale à son propre cluster — aucun mécanisme central ne peut ni ne doit déclencher une synchronisation sur l'installation de quelqu'un d'autre (cohérent avec le principe déjà posé dans `vision-long-terme.md` : chaque installation reste souveraine, pas d'opérateur central unique). Aujourd'hui (POC, une seule installation), toutes les `Application` restent en synchronisation automatique (`selfHeal: true`) — un `git push` sur `master` se propage au cluster en quelques minutes. **Décidé mais pas encore implémenté** : à terme, distinction entre services sensibles (basculeraient en synchronisation manuelle, déclenchée par l'admin de l'installation concernée, précédée d'une annonce — cf. ci-dessous) et services d'infrastructure invisibles pour la famille (peuvent rester automatiques sans risque) :
  - **Sensibles** (impact direct sur l'usage familial) : Authentik (SSO, point d'entrée unique — une régression y bloque l'accès à tout le reste), Vaultwarden, Nextcloud, Immich, Tuwunel, LiveKit, Ollama (une fois la Phase 5 réelle).
  - **Sûrs, restent automatiques** : `monitoring` (Prometheus/Grafana, admin uniquement), `uptime-kuma` (outil de supervision — la page de statut publique reste visible même si le service se met à jour), `root` (le mécanisme de bootstrap GitOps lui-même, doit rester automatique pour continuer à découvrir les nouvelles `Application`).
  - Ampleur exacte du passage en manuel (tout ou partiellement) non tranchée — à décider au moment de l'implémentation, une fois un usage familial réel en place.
- **Canal d'annonce familial** : réutilise le salon Matrix partagé `#etat-du-systeme` déjà en place pour l'alerting (`gitops/apps/uptime-kuma.yaml`, `scripts/tuwunel-alertbot-setup.py`) plutôt que d'en créer un nouveau — les deux relèvent du même besoin ("que se passe-t-il avec notre système ?") du point de vue de la famille. `scripts/tuwunel-announce.py` permet de poster une annonce formatée avant un changement notable.
- **Traefik** comme reverse proxy / ingress, gestion automatique TLS via Let's Encrypt.
- **Helm charts** communautaires réutilisés quand ils existent (Nextcloud, Immich, Vaultwarden) plutôt que des manifests réécrits from scratch.
- **Accès administrateur distant** : VPN WireGuard auto-hébergé (Phase 4) — aucune dépendance tierce (écarté volontairement : Tailscale, plus simple à poser mais qui ajoute un service de coordination propriétaire externe), aucun outil d'administration exposé directement sur internet.

## 7. Mail : risques et mitigation

Un domicile résidentiel français est structurellement inadapté à l'envoi de mail direct :

- **Blacklist par politique** (ex. Spamhaus PBL) sur les plages IP résidentielles, indépendamment du comportement — n'affecte que l'**envoi**, pas la réception.
- **Port 25 bloqué** par la plupart des FAI résidentiels en sortie (anti-botnet).
- Aucun des deux points n'est une question légale : ce sont des mécanismes privés/techniques, pas une interdiction réglementaire.

**Mitigation retenue** : VPS façade (IP à bonne réputation par défaut) gérant l'entrée et la sortie SMTP, relayant vers le stockage réel à domicile. Compromis de confiance assumé : le VPS voit transiter le mail en clair au moment de l'envoi (SMTP n'est chiffré que saut par saut par défaut) — le choix du fournisseur (juridiction UE, RGPD) mitige ce risque par rapport à un acteur GAFAM.

## 8. Sécurité

- Secrets (mots de passe DB, tokens API, clés TLS) jamais en clair dans le dépôt Git — SOPS ou Sealed Secrets à trancher en phase d'implémentation.
- Chiffrement au repos pour les volumes de données sensibles (Vaultwarden, Nextcloud, Mailcow).
- Principe du moindre privilège entre services (réseaux k8s séparés / NetworkPolicies).
- Scan de vulnérabilités des images (Trivy), cohérent avec la pratique professionnelle de l'auteur.

## 9. Sauvegarde & continuité

- Règle 3-2-1 : copie locale (mini PC) + copie chiffrée chez un ami technophile (réciprocité communautaire, sans coût récurrent).
- **Restic** pour les sauvegardes (snapshots, déduplication, rétention), pas Syncthing (qui répliquerait aussi les suppressions/corruptions en temps réel et n'offre pas de politique de rétention).
- Restauration à tester régulièrement (une sauvegarde non testée n'est pas une sauvegarde).

## 10. Matériel cible

- **Déploiement initial** (roadmap Phase 4, bascule infra réelle) : un mini PC (32-64 Go RAM, NVMe), single-node k3s. Budget : achat correct one-shot, coûts récurrents proches de zéro (hors VPS mail).
- **Cible à terme** : plusieurs profils de dimensionnement matériel selon le nombre d'utilisateurs (ex. 1-6 / 7-15 / 15+), à définir une fois le profil de charge réel observé en production réelle.
- **Décision détaillée (2026-08-13)** : achat en deux étapes plutôt qu'un seul — une machine minimale d'occasion pour boucler la Phase 4 sans attendre, puis la cible long terme une fois Phase 5/6 réelles (raisonnement complet, chiffrage, pistes d'achat concrètes : voir [`materiel.md`](materiel.md)).

## 11. Limites connues et risques assumés

- **Point de défaillance unique** en mono-nœud (phase 1) : accepté comme compromis de démarrage, la topologie k3s permet une évolution vers du multi-nœud sans réécriture.
- **Dépendance à la disponibilité du nœud de sauvegarde chez l'ami** : à documenter comme risque, pas de solution de repli en phase 1.
- **Responsabilité informelle** d'opérateur de service pour la famille/les amis (disponibilité, support, sécurité de leurs données) : risque assumé plutôt que traité par une procédure de continuité formelle, cohérent avec l'échelle POC (cercle proche). Mitigation : accès distant admin via VPN (voir §6) en priorité, déblocage téléphonique guidé de quelqu'un sur place en dernier recours (panne matérielle complète). À communiquer clairement à la famille/aux amis, pas seulement assumé en interne.
- **Délivrabilité mail** : la façade VPS mitige mais n'élimine pas complètement le risque de classement en spam par les gros acteurs, en particulier au démarrage d'un nouveau domaine.
