# Changelog

All notable changes to this project will be documented in this file. See [commit-and-tag-version](https://github.com/absolute-version/commit-and-tag-version) for commit guidelines.

## [0.1.10](https://github.com/Pavliin/MyOwn/compare/v0.1.9...v0.1.10) (2026-08-24)

Note : `commit-and-tag-version` a comparé par erreur contre `v0.1.2` au lieu de `v0.1.9` (les tags `v0.1.3`-`v0.1.9` ne sont plus des ancêtres de `master` depuis que `pin-release.sh` les déplace sur un commit jamais mergé) — cette section a été reconstruite manuellement avec les seuls commits réellement nouveaux depuis `v0.1.9`.

### Fonctionnalités

* **mail:** add Gandi DNS records for the VPS relay (A/MX/SPF/DKIM/DMARC) ([316eb91](https://github.com/Pavliin/MyOwn/commit/316eb916bf040a3138f6def82b07cd248171b541))
* **mail:** bootstrap dedicated WireGuard tunnel for VPS mail relay ([a075b83](https://github.com/Pavliin/MyOwn/commit/a075b835d93ad83c677cb59d4aae8c6476ec2181))
* **mail:** configure Postfix relay on the VPS façade ([9a894ad](https://github.com/Pavliin/MyOwn/commit/9a894ad3649f4eabbec078adc7b45bb054bf0245))
* **mail:** expose Mailu:25 to the VPS relay via a persistent port-forward ([38cbe8a](https://github.com/Pavliin/MyOwn/commit/38cbe8a0b17106dcb265de7cc550cfdd24287261))
* **mail:** route Mailu's outbound mail through the VPS relay ([43e4852](https://github.com/Pavliin/MyOwn/commit/43e48521c4cf7f00d55c4eeba3ac805f81b845b7))
* **mailu:** activate ForwardAuth SSO on the public Ingress ([5b38807](https://github.com/Pavliin/MyOwn/commit/5b388076e9b65bf12942e4e4dde377c9bb44ba7a))
* **mailu:** add base Mailu deployment ([8be8644](https://github.com/Pavliin/MyOwn/commit/8be8644ce1a3da629a332544a25290b5f8c895ec))
* **mailu:** add Restic backup CronJob ([eadaabe](https://github.com/Pavliin/MyOwn/commit/eadaabe6f699ada192e44e4540330c87dbefc3d1))
* **mailu:** make front's TLS cert and the SSO callback route reproducible ([4329b73](https://github.com/Pavliin/MyOwn/commit/4329b7366c14d81b155c8597bd8c8197ff0ba09d))
* **mailu:** prepare Authentik ForwardAuth SSO wiring ([ae81746](https://github.com/Pavliin/MyOwn/commit/ae817464dab24a02159ab7c6c9dcb4ab3ed0ddc6))

### Correctifs

* **mailu:** skip backend TLS verification for front's own certificate ([c3ee9d4](https://github.com/Pavliin/MyOwn/commit/c3ee9d45d1f9743ec1c470d335561f7e1c80e357))
* **mailu:** use Recreate strategy for postfix to avoid a rollout deadlock ([e301e7c](https://github.com/Pavliin/MyOwn/commit/e301e7c88f83070684d94c18087c3ba8edfb47f9))

### Documentation

* flag the myown-*.local hostname ambiguity between dev and mini PC ([ed163f2](https://github.com/Pavliin/MyOwn/commit/ed163f2e8793e9b365f5d6daa5934b2fb10327b3))
* pivot mail stack decision from Mailcow to Mailu ([48fda34](https://github.com/Pavliin/MyOwn/commit/48fda34410c5fb5dfdfdf3f114ebec5c074f568c))
* record Mailcow deployment research, refresh current state ([39fde74](https://github.com/Pavliin/MyOwn/commit/39fde746a2fbcc456bd38f769d34e336e3b18b50))
* record the full Mailu deployment and SSO validation ([89270e3](https://github.com/Pavliin/MyOwn/commit/89270e35cc1b3d056a4a556eb44f657f3febec9b))
* record the Mailu Restic backup validation and two ArgoCD gotchas ([e3bc759](https://github.com/Pavliin/MyOwn/commit/e3bc759908beaa7a0c84abc0b500c3cf3c20b183))
* record the VPS façade provisioning, done in an untracked session ([0da8913](https://github.com/Pavliin/MyOwn/commit/0da891300a0ca1d21989b54365f59088e0763f32))
* record the VPS mail relay chantier, validated end-to-end ([4583912](https://github.com/Pavliin/MyOwn/commit/4583912e74f5fb4ac5986dd3caf03307099b9786))
* record two pre-existing dev-cluster outages found and fixed ([b587e6f](https://github.com/Pavliin/MyOwn/commit/b587e6fd8d30caf90b07ed6e580c6863c0da2811))
## [0.1.9](https://github.com/Pavliin/MyOwn/compare/v0.1.8...v0.1.9) (2026-08-23)

### Fonctionnalités

* **tuwunel:** migrate server_name to offsystem.fr for real federation ([5f35e71](https://github.com/Pavliin/MyOwn/commit/5f35e71b90a044f1d2e1870f6ae4a59584bf67c2))

### Correctifs

* **tuwunel:** give the pod real IPv6 egress via hostNetwork ([0ad4356](https://github.com/Pavliin/MyOwn/commit/0ad43563e90061151b7c154d886c58a317c666d1))

### Documentation

* record the Tuwunel server_name migration and federation validation ([a147bb9](https://github.com/Pavliin/MyOwn/commit/a147bb905dffa5578f8170d3a84f82824aa4a929))

## [0.1.8](https://github.com/Pavliin/MyOwn/compare/v0.1.7...v0.1.8) (2026-08-23)

### Fonctionnalités

* **watchdog:** add host-level k3s auto-remediation watchdog ([4896a2c](https://github.com/Pavliin/MyOwn/commit/4896a2c1020821923b63f3b871b02cdc9d18db36))

### Correctifs

* **watchdog:** resolve sops's absolute path at install time ([6978c8e](https://github.com/Pavliin/MyOwn/commit/6978c8e49e46eca6d1269b4c47bcc7016fb83237))
* **watchdog:** resolve the real repo root at install time, not runtime ([20b38cd](https://github.com/Pavliin/MyOwn/commit/20b38cdfa54e77d75847b14d5b4ceb8e524a6e8b))
* **watchdog:** point sops at the real age key when running as root ([f345cf3](https://github.com/Pavliin/MyOwn/commit/f345cf35ff74dcceba83e9d104656524261ca9e0))

### Documentation

* record the watchdog's real forced-outage validation ([a3a7909](https://github.com/Pavliin/MyOwn/commit/a3a7909dc52e0ae31abf2b8fd44bdeb2c986efdb))

## [0.1.7](https://github.com/Pavliin/MyOwn/compare/v0.1.6...v0.1.7) (2026-08-22)

### Correctifs

* **livekit:** disable the chart's default TURN LoadBalancer Service ([e51daf6](https://github.com/Pavliin/MyOwn/commit/e51daf6462f0f37ab54be71fe1a5c85bf692ecb8))

## [0.1.6](https://github.com/Pavliin/MyOwn/compare/v0.1.5...v0.1.6) (2026-08-22)

### Fonctionnalités

* **authentik:** add account-recovery flow blueprint ([6db1511](https://github.com/Pavliin/MyOwn/commit/6db1511d3e81c994cec886294ce37721086b9319))
* **livekit:** sync LiveKit's TURN cert from Traefik's own ACME store ([05cb3c7](https://github.com/Pavliin/MyOwn/commit/05cb3c71646e22905043037ccd40fdd4c50a445c))

### Correctifs

* **livekit:** branch externally and add TURN ([270fedd](https://github.com/Pavliin/MyOwn/commit/270fedd9d022a95caeede1fdb53e52a854ce9e49))

### Documentation

* record LiveKit TURN/external branching and account recovery ([8ac45b6](https://github.com/Pavliin/MyOwn/commit/8ac45b65f6dd24da3c40b947c9890b0e2fe4c05c))

## [0.1.5](https://github.com/Pavliin/MyOwn/compare/v0.1.4...v0.1.5) (2026-08-22)

### Fonctionnalités

* **gitops:** generalize the domain/Let's Encrypt pattern to 8 more services ([f2c2018](https://github.com/Pavliin/MyOwn/commit/f2c201827d9c0c2687e64af5d250dfc144f37b1d))
* **sso:** migrate all 5 integrated services to the public hostnames ([d30f545](https://github.com/Pavliin/MyOwn/commit/d30f5458dea5ddec1bcf5a7ce555f08a811bd5e8))
* **traefik,dns:** real domain + Let's Encrypt via Gandi DNS-01, canary on Uptime Kuma ([6fc4081](https://github.com/Pavliin/MyOwn/commit/6fc4081405631b7b0b04f5991658f1a74bdadc95))

### Correctifs

* **authentik:** correct authentik-secrets YAML structure ([1f3cee6](https://github.com/Pavliin/MyOwn/commit/1f3cee659dd04274ba7bd21d7d3619f4233a94b8))
* **gandi-dyndns:** tighten schedule/TTL to cut IP-change exposure window ([0d7ebc4](https://github.com/Pavliin/MyOwn/commit/0d7ebc4913465c3c6a5a9ed06a76a46fdc9d90dd))
* **nextcloud:** backup CronJob referenced a PVC that no longer exists ([a9fec54](https://github.com/Pavliin/MyOwn/commit/a9fec54a1fa9180a67f88f4ef2e5e75e7ffbda65))

### Documentation

* record domain/Let's Encrypt canary validation, update current state ([335cc3c](https://github.com/Pavliin/MyOwn/commit/335cc3c92ccd36386f6fa0b2a4f880fee099624d))
* record the generalization pass and the Nextcloud permissions incident ([b0b7dff](https://github.com/Pavliin/MyOwn/commit/b0b7dff43b0648f17a4058538c75029f9c14845c))
* record the SSO migration and the ArgoCD selfHeal reversion incident ([d54a619](https://github.com/Pavliin/MyOwn/commit/d54a6199766fa4dc80fe44767a80831bd3d49021))

## [0.1.4](https://github.com/Pavliin/MyOwn/compare/v0.1.3...v0.1.4) (2026-08-20)

### Fonctionnalités

* **immich:** resize the library volume for real use (10Gi -> 300Gi) ([790bd70](https://github.com/Pavliin/MyOwn/commit/790bd70bcb55262bd4397ddd3ec14969a95ad64f))
* **nextcloud:** install groupfolders for shared family folders ([86213ef](https://github.com/Pavliin/MyOwn/commit/86213ef26baee700422d8d199905b7d62660854d))
* **ops:** complete first-boot account setup on the mini PC ([a776b21](https://github.com/Pavliin/MyOwn/commit/a776b21383e9ebcc8898258bce67f4adc8728a6f))
* **wireguard:** reinstall the admin VPN on the real mini PC ([4189403](https://github.com/Pavliin/MyOwn/commit/4189403a4f69e6ee7a1186a123f7b16824efc6c2))

### Correctifs

* **argocd:** pin a stable admin password ([0d2354b](https://github.com/Pavliin/MyOwn/commit/0d2354b4b54deb252e4bb056e6cee23921ea1581))
* **authentik:** pin a stable akadmin bootstrap password ([e271f1c](https://github.com/Pavliin/MyOwn/commit/e271f1c22ee02ee0cb03de61c20c7a3890ed1b4a))
* **jellyfin:** source media from the shared family folder, not admin ([bc2cbc0](https://github.com/Pavliin/MyOwn/commit/bc2cbc02903f876b1b9ca56c6f9356d13105df86))
* **monitoring:** pin a stable Grafana admin password ([1fa3029](https://github.com/Pavliin/MyOwn/commit/1fa3029fc3a2586c8944462f91de5443c074e5c0))

### Documentation

* correct the CronJob-Progressing root cause ([356bde9](https://github.com/Pavliin/MyOwn/commit/356bde93251d27472a103e20fe406cea3e129b6c))
* note the trailing-newline secret bug found fixing Grafana too ([797f111](https://github.com/Pavliin/MyOwn/commit/797f111b68b8ef0bf1d1f86bfd63ea8900976865))
* record the shared media folder migration and its real bugs ([945e628](https://github.com/Pavliin/MyOwn/commit/945e628b3919850d2792db7a408d62b3ac1d171e))

## [0.1.3](https://github.com/Pavliin/MyOwn/compare/v0.1.2...v0.1.3) (2026-08-20)

### Fonctionnalités

* **authentik:** add Restic backup pipeline ([008f79b](https://github.com/Pavliin/MyOwn/commit/008f79b83a24374052991c6fcd9cfa9e7ba662b0))
* **immich:** switch library storage to a fixed hostPath PV/PVC ([5dc85b8](https://github.com/Pavliin/MyOwn/commit/5dc85b8cf2f5847ce802d8d0edc772b0d6171b92))
* **jellyfin:** add Authentik OAuth2 blueprint ([d6f30d5](https://github.com/Pavliin/MyOwn/commit/d6f30d53db2233597790edffa7d6af78d14ed71f))
* **jellyfin:** add Restic backup for config and media PVCs ([c22cf36](https://github.com/Pavliin/MyOwn/commit/c22cf3635d26cbaea3e1db80655105098e5a34d2))
* **jellyfin:** add the Authentik login button to the login page ([c8c1437](https://github.com/Pavliin/MyOwn/commit/c8c1437a449a84a9c1ba78b0b1b63fee127cbe31))
* **jellyfin:** deploy bare via official jellyfin-helm chart ([19e0efc](https://github.com/Pavliin/MyOwn/commit/19e0efc07d185b7368ddaf2eb39672addc784e66))
* **jellyfin:** mount the Jellyfin Authentik blueprint secret ([9e3a3d4](https://github.com/Pavliin/MyOwn/commit/9e3a3d43e0a1bfa8e540a18810df50b0dd71e881))
* **jellyfin:** source media library from Nextcloud's own storage ([a256160](https://github.com/Pavliin/MyOwn/commit/a256160be6d2ae1806ddfc3b9f460bb3c886b7a1))
* **k3s:** expose Traefik on 8090/8453 for bare-metal deployments ([a0780e4](https://github.com/Pavliin/MyOwn/commit/a0780e44166441fff1e34323aae1a1001b29bf4e))
* **livekit:** deploy LiveKit SFU and lk-jwt-service for group calls ([9636f6a](https://github.com/Pavliin/MyOwn/commit/9636f6ae367769d4ca9e33c1a6e7b1a563e8f132))
* **monitoring:** alert Tuwunel room on service down/up via Uptime Kuma ([cee615f](https://github.com/Pavliin/MyOwn/commit/cee615f8122a365c36ff5034b4b0b00a081f1466)), references [#etat-du-systeme](https://github.com/Pavliin/MyOwn/issues/etat-du-systeme)
* **monitoring:** configure Uptime Kuma monitors and status page ([4ecca98](https://github.com/Pavliin/MyOwn/commit/4ecca98ec511f4cab055222abe537f933591673d))
* **nextcloud:** install Notes and Tasks apps ([17332bf](https://github.com/Pavliin/MyOwn/commit/17332bf53c52f698d7626c4af4b91b134027d759))
* **nextcloud:** switch file storage to a fixed hostPath ([995d2a2](https://github.com/Pavliin/MyOwn/commit/995d2a232d9b346b9407a04c9a19aec1c250b155))
* **ollama:** deploy Ollama and choose Qwen3 8B for mail triage ([10b0640](https://github.com/Pavliin/MyOwn/commit/10b064045af6d94751caa62bd817035d31654da0))
* **ops:** clarify ArgoCD sync philosophy, add announcement channel ([17ae44f](https://github.com/Pavliin/MyOwn/commit/17ae44f9ada030cbf52d11984cac55bca1c5a10a)), references [#etat-du-systeme](https://github.com/Pavliin/MyOwn/issues/etat-du-systeme)
* **tuwunel:** add Restic backup ([1ba65d4](https://github.com/Pavliin/MyOwn/commit/1ba65d4736a1873e6c4f9c26ba9193f9413a0bdb))
* **tuwunel:** advertise LiveKit SFU via well-known for MatrixRTC ([0b97d4c](https://github.com/Pavliin/MyOwn/commit/0b97d4cbe6815fc54a01a2e57299c61d99555753))
* **tuwunel:** deploy bare Tuwunel messaging server ([6d35b0e](https://github.com/Pavliin/MyOwn/commit/6d35b0ebb772dbd4682cbe5630f68d4d17516afc))
* **tuwunel:** wire up Authentik SSO ([7a41b9f](https://github.com/Pavliin/MyOwn/commit/7a41b9f75da0bbfcf0e5d6c9f1fa9d0d6a744ecb)), references [matrix-construct/tuwunel#340](https://github.com/Pavliin/MyOwn/issues/340) [matrix-construct/tuwunel#249](https://github.com/Pavliin/MyOwn/issues/249)
* **wireguard:** add host-level admin VPN bootstrap script ([7898111](https://github.com/Pavliin/MyOwn/commit/7898111fc7d61b2abe5971f4e60c0e45779e33f5))

### Correctifs

* **argocd:** add health check for Prometheus Operator CRDs ([d237cce](https://github.com/Pavliin/MyOwn/commit/d237cce0c53ab9538757c82f89a8852d899b4acb))
* **bootstrap:** route new services and mirror port 443 for federation ([3469df5](https://github.com/Pavliin/MyOwn/commit/3469df545dda8e29e54ccd619ece161254953979))
* **install:** correct namespace for the livekit-jwt mkcert secret ([bd51578](https://github.com/Pavliin/MyOwn/commit/bd51578675d4b3241ba555a6ab10bbd233b4c114))
* **installer:** wait for repo-server rollout after KSOPS patch ([7be392e](https://github.com/Pavliin/MyOwn/commit/7be392e04868f2c8d8bbd0ec701e7a367f456fd9))
* **jellyfin:** pin image tag to match the Authentik SSO plugin's ABI ([c9833d6](https://github.com/Pavliin/MyOwn/commit/c9833d61854c347b8d1bf1e449761c0f3a9a3325))
* **jellyfin:** work around host inotify limit with polling watcher ([33091cb](https://github.com/Pavliin/MyOwn/commit/33091cba63a7fa6dda4d787107652155c4dc6880))
* **nextcloud:** skip before-starting hook until Nextcloud is installed ([e8ff2cf](https://github.com/Pavliin/MyOwn/commit/e8ff2cf3890198e38b95034c4f641399e15f1670))
* **tuwunel:** move to HTTPS to fix SSO login ([560019f](https://github.com/Pavliin/MyOwn/commit/560019fa3a773931bd4d71d7469d028fd0496b29))
* **vision:** add blank lines around lists for markdownlint ([d0e2afb](https://github.com/Pavliin/MyOwn/commit/d0e2afb098c76f9f415a974136975a19e5f940a4))

### Documentation

* add mini PC sizing research and decisions ([b7c8f2a](https://github.com/Pavliin/MyOwn/commit/b7c8f2ac3bfea2143c728b1e837e1162ca880af5))
* capture Tuwunel deployment plan for session handoff ([f9c54e2](https://github.com/Pavliin/MyOwn/commit/f9c54e20bb692ba7c509f297e445987dc40db000))
* confirm Tuwunel SSO validated end-to-end ([b292059](https://github.com/Pavliin/MyOwn/commit/b292059f1d6924a1007f28ecd24f466dd902d2f2))
* design Phase 6 installer and admin-account model ([0491a54](https://github.com/Pavliin/MyOwn/commit/0491a54665fb5e2b0ae4c4913785c06c8eaf786c))
* document Authentik Restic backup and update current state ([a1bf052](https://github.com/Pavliin/MyOwn/commit/a1bf052a20ea9537c2e48f6719c84ce5add278e9))
* document LiveKit deployment and the two cluster recreations ([440e87d](https://github.com/Pavliin/MyOwn/commit/440e87db87a2247114ae8d85d9451a05d0dd1c82))
* document the mini PC's k3s bare-metal bootstrap ([08de7ea](https://github.com/Pavliin/MyOwn/commit/08de7eae8f129bd5436569e8586c0c51695816f1))
* fix calendar event landing on the wrong Nextcloud account ([68352bf](https://github.com/Pavliin/MyOwn/commit/68352bf9678a3b2ad6c4dc2b65e435016f38f700))
* fix floating-time CalDAV event invisible in Nextcloud UI ([dac8ed3](https://github.com/Pavliin/MyOwn/commit/dac8ed395a9a6dc76ca5c2f375ad0f1548490d0c))
* fix stale release process, add GitHub Release step ([1af644e](https://github.com/Pavliin/MyOwn/commit/1af644e73786103a3cea8bb568d98225cb0d3d9b))
* **installer:** trace secrets-push integration gap and sequencing risk ([db8ccd9](https://github.com/Pavliin/MyOwn/commit/db8ccd9d4b077219b4d9466914a937036da92800))
* **jellyfin:** record media-from-Nextcloud migration, fix stale backup docs ([195da09](https://github.com/Pavliin/MyOwn/commit/195da093a9bc858dec22ca9778a9cd2b1d1df37f))
* **jellyfin:** record real backup/restore validation ([0f1660f](https://github.com/Pavliin/MyOwn/commit/0f1660f57fb3ba145152375745ef1f31178037dd))
* **jellyfin:** record real deployment, inotify fix, and current status ([4624b25](https://github.com/Pavliin/MyOwn/commit/4624b258c8de43d1e8a135e6a0796b867bdf6383))
* **jellyfin:** record SSO setup, add reproducible setup script ([acbe3cd](https://github.com/Pavliin/MyOwn/commit/acbe3cda77031147e19abc6e5bbb34d13483ec1f))
* **jellyfin:** record the Authentik admin-group setup step ([2a362c7](https://github.com/Pavliin/MyOwn/commit/2a362c77a3f904455b8f75071fbe9b6ba1e86377))
* **materiel:** record OptiPlex purchase, note the rejected gaming PC ([8da40b6](https://github.com/Pavliin/MyOwn/commit/8da40b691d6ded252d134005b1a7e3877761eebf))
* note Element Web's room-join-by-alias UX gap ([f7e2eae](https://github.com/Pavliin/MyOwn/commit/f7e2eaebb8289748012821766a03206afe1725e8))
* record cluster crash-loop incident, add resilience roadmap items ([063e153](https://github.com/Pavliin/MyOwn/commit/063e15355417b276c5ff07b3923ee2e0a3da4175))
* record the Nextcloud/Immich hostPath storage migration ([5d7ebe5](https://github.com/Pavliin/MyOwn/commit/5d7ebe5c8d571df1c2bbb606f25d0563394a5f9d))
* refine roadmap and architecture for IA scope, ops, and pointers ([24a05e8](https://github.com/Pavliin/MyOwn/commit/24a05e8313c739b648eea8d8ece66296db637596))
* replace Conduwuit with Tuwunel across the docs ([84d2af5](https://github.com/Pavliin/MyOwn/commit/84d2af5d43902e9160263531c800246acee15a60))
* **roadmap:** add Jellyfin to Phase 3.5/4 ([6450984](https://github.com/Pavliin/MyOwn/commit/6450984065c2ed6bfa4d11460d91bfa4d9b4c5d9))
* **roadmap:** add Pi-hole/AdGuard Home to Phase 4 ([af971cd](https://github.com/Pavliin/MyOwn/commit/af971cdb8d06a98933accecc8365e38577aa2b06))
* **roadmap:** refine package-delivery idea toward Tasks, not Calendar ([1e38b56](https://github.com/Pavliin/MyOwn/commit/1e38b568030e8d071a2808ca8a05573ad2d227e1))
* specify decentralized update checks and the auto/manual choice ([c37eb0c](https://github.com/Pavliin/MyOwn/commit/c37eb0c44e8b3bcec05426c8f1999f5e6a5fc742))
* validate the admin-account/Vaultwarden secrets model ([1a3caca](https://github.com/Pavliin/MyOwn/commit/1a3cacae246c38b8bf7c9b4625094f90dda156cb))
* validate the full mail-to-calendar pipeline end-to-end ([62880e2](https://github.com/Pavliin/MyOwn/commit/62880e28abfbc6744ed1d5011e47383e278546ad))
* **vision:** add location-aware AI assistant as long-term idea ([46c446a](https://github.com/Pavliin/MyOwn/commit/46c446af4db90bd44873b0dc618ffe51a4747ff8))
* **vision:** add two-stage public deployment strategy ([153c964](https://github.com/Pavliin/MyOwn/commit/153c9647bcea4a13a7a815e70ff0f8d29efae9f4))
* **vision:** compare Fediverse and Solid for the social network piste ([83763b2](https://github.com/Pavliin/MyOwn/commit/83763b259573a78f5ba6a284590b8d228be46e1c))
* **wireguard:** record real client handshake validation ([7a98119](https://github.com/Pavliin/MyOwn/commit/7a9811995a6e1ea45105a6d133cbdfd5d05b1115))
* **wireguard:** record real validation, commit encrypted server config ([6ac9d15](https://github.com/Pavliin/MyOwn/commit/6ac9d154b5f1f33c338792b8aa66dcd21398c0e4))
## [0.1.2](https://github.com/Pavliin/MyOwn/compare/v0.1.1...v0.1.2) (2026-08-09)

### Fonctionnalités

* **immich:** deploy bare Immich (Phase 2) ([25b4264](https://github.com/Pavliin/MyOwn/commit/25b4264ace5be32acf0380c1720c3f8f0ab8b425))
* **immich:** extend Restic backup pipeline ([c9c857f](https://github.com/Pavliin/MyOwn/commit/c9c857f4fa846ba9a3a55db530058d2ffe6677a9))
* **immich:** integrate SSO with Authentik, zero manual config ([9fea77b](https://github.com/Pavliin/MyOwn/commit/9fea77bd672ee6125661bc63038f2e675ca062cc))
* **nextcloud:** deploy bare Nextcloud (Phase 2) ([c092200](https://github.com/Pavliin/MyOwn/commit/c0922003963d1bf9d6f5a52adda2383b39dc153d))
* **nextcloud:** disable native Photos app now that Immich exists ([924b205](https://github.com/Pavliin/MyOwn/commit/924b20583c64f5815a5624d0efe19bf45bb94dd0))
* **nextcloud:** extend Restic backup pipeline ([495f992](https://github.com/Pavliin/MyOwn/commit/495f99226d0b79654db51ad50317f3b28d6527da))
* **nextcloud:** install Calendar and Contacts apps ([8191736](https://github.com/Pavliin/MyOwn/commit/819173630a55fd5e2a35a0a20cfef3bc15099e7f))
* **nextcloud:** integrate SSO with Authentik ([a17a2ca](https://github.com/Pavliin/MyOwn/commit/a17a2cad4f6248a1d6af9ddb70a74a4e2a5d9a36))

### Correctifs

* **ci:** exclude generated CHANGELOG.md from markdownlint ([88119d7](https://github.com/Pavliin/MyOwn/commit/88119d7a17463b51354b1e705612e29d26e3cb88))
* **nextcloud:** allow OIDC discovery call, fix Redis session auth ([b0db8cc](https://github.com/Pavliin/MyOwn/commit/b0db8ccde4c3e7ad70d1cc06947859f3a87465e5))
* **nextcloud:** move to HTTPS — user_oidc refuses plain HTTP ([58f224a](https://github.com/Pavliin/MyOwn/commit/58f224ace3dd955fd6d59ec15c6702704a734577))
* **nextcloud:** run OIDC provider registration on every start, not just install ([7e456a5](https://github.com/Pavliin/MyOwn/commit/7e456a5d427deacd119f800d85c21e4958e5fefb))

### Documentation

* record Immich Restic backup as validated, Phase 2 complete ([ceda206](https://github.com/Pavliin/MyOwn/commit/ceda206d3d35c5ae6107973189d1e8901d88c163))
* record Immich SSO as validated end-to-end ([0edb9ff](https://github.com/Pavliin/MyOwn/commit/0edb9ff0f06cbe1bc75d0d90a74abf77cc3becb3))
* record Nextcloud Restic backup as validated end-to-end ([5b44f45](https://github.com/Pavliin/MyOwn/commit/5b44f45bc831713899b9e507544de0f4110ff60c))
* record Nextcloud SSO as validated end-to-end ([0a37e51](https://github.com/Pavliin/MyOwn/commit/0a37e5142111db31c14bc40adb83a53fb758f15c))
* **roadmap:** defer every mini-PC/domain-only item into Phase 4 ([0fa8403](https://github.com/Pavliin/MyOwn/commit/0fa8403d72525be5008c2aafd3ca540dc6c8867e))
## [0.1.1](https://github.com/Pavliin/MyOwn/compare/v0.1.0...v0.1.1) (2026-08-08)

### Fonctionnalités

* deploy Vaultwarden (Phase 1) ([28df072](https://github.com/Pavliin/MyOwn/commit/28df072c0b1ef65f1783df7b00e37fa38ec1cb96))
* enable TLS on Vaultwarden ingress ([aed6135](https://github.com/Pavliin/MyOwn/commit/aed6135f08f25bcfe373828d2696ba54d7d30bf6))
* integrate Vaultwarden SSO with Authentik ([2ed050c](https://github.com/Pavliin/MyOwn/commit/2ed050cfda0f52b0a35e260d3991f200bbdbb4ed))
* **vaultwarden:** add Restic backup pipeline ([f35b750](https://github.com/Pavliin/MyOwn/commit/f35b7501e99eb21ed60878d759b407d9f6551ccd))

### Correctifs

* add trailing slash to Vaultwarden SSO authority ([5734536](https://github.com/Pavliin/MyOwn/commit/5734536aa084298f60639d00526dd83587651a56))
* broaden StatefulSet ignoreDifferences, document Vaultwarden ([80745e8](https://github.com/Pavliin/MyOwn/commit/80745e8be17f9bb8bd940af39c710af33b012263))
* custom email scope mapping with email_verified true ([530c38b](https://github.com/Pavliin/MyOwn/commit/530c38b58b5afc04fc1141c4ea6c2dbdc9ede3ef))
* enable authorization_code grant type on Vaultwarden provider ([a25f996](https://github.com/Pavliin/MyOwn/commit/a25f996cda3dd4ba6b1e427a4b48c512a4ef6376))
* ignore email_verified claim for SSO, revert debug logging ([db986ab](https://github.com/Pavliin/MyOwn/commit/db986abb46ded9d89464cc42af295b5ee42b5270))
* ignore StatefulSet volumeClaimTemplates status drift ([492a33b](https://github.com/Pavliin/MyOwn/commit/492a33bd15aa1f3d6e88671a72c3a538786e6c3c))
* set Vaultwarden DOMAIN, correct real redirect_uri ([7ab14e2](https://github.com/Pavliin/MyOwn/commit/7ab14e29ed184b72aaa037c78cefaad52e9455f9))

### Documentation

* document the mkcert + snap browser + Chrome Root Store saga ([ef55e8a](https://github.com/Pavliin/MyOwn/commit/ef55e8a1a378543600e48d9e59c342a923ac601a))
* document TLS/secure-context requirement and sync quirk ([4095425](https://github.com/Pavliin/MyOwn/commit/40954258286f15f90e70de922fec1296671e6de4))
* document Vaultwarden/Authentik SSO integration ([a819477](https://github.com/Pavliin/MyOwn/commit/a819477b1749d1af2c990bca31f8078266f8eb6e))
* full writeup of the Vaultwarden/Authentik SSO debugging session ([2676f64](https://github.com/Pavliin/MyOwn/commit/2676f64a11234a88f5676c1e6499e06c3bde03bc))
* record Restic backup pipeline as-built and update project state ([8227a54](https://github.com/Pavliin/MyOwn/commit/8227a54ca885bab7b5ec09ca1d428d7c7cc07b70))
* turn CLAUDE.md's Current state into a session hand-off pointer ([d041571](https://github.com/Pavliin/MyOwn/commit/d041571860892fd37d987ee4994711d29fa664aa))
## 0.1.0 (2026-08-07)

### Fonctionnalités

* add monitoring stack (kube-prometheus-stack + Uptime Kuma) ([ece6f16](https://github.com/Pavliin/MyOwn/commit/ece6f168b4d20060f67af41d7f1f6a5ef38f8368))
* deploy Authentik with GitOps-native secret decryption (KSOPS) ([e3e6a77](https://github.com/Pavliin/MyOwn/commit/e3e6a7787b897e534c5b04e3edf6577ac9b680b7))
* expose ArgoCD via a fixed local hostname ([6c24bac](https://github.com/Pavliin/MyOwn/commit/6c24bac82f29d7bdabdc68c2482b311d9069de01))
* scaffold GitOps app-of-apps structure ([11d9c99](https://github.com/Pavliin/MyOwn/commit/11d9c997046ae4a0a106f8228b093fb8e7235db3))

### Correctifs

* add missing PostgreSQL connection fields to Authentik secret ([b0a507e](https://github.com/Pavliin/MyOwn/commit/b0a507e88d400748d3ebb46d38ac565acbc09402))
* **ci:** resolve commitlint action permissions and config path ([09d30cc](https://github.com/Pavliin/MyOwn/commit/09d30ccfb398dc2f0a9174bac761a9cf8a5cd2e8))
* stop monitoring Application fighting ArgoCD self-heal ([5c28f67](https://github.com/Pavliin/MyOwn/commit/5c28f67c81a0bfe49b53b3698a688bf9b4572395))

### Documentation

* add living technical notes, install manual, and user manual ([2e65f57](https://github.com/Pavliin/MyOwn/commit/2e65f57e0e95cfe48ecc57abab42999259c0b69f))
* correct merge method — rebase-merge rejected under signed commits ([04cfdad](https://github.com/Pavliin/MyOwn/commit/04cfdad22e1044b12a4d79e0556a0e047b62fce9))
* document branch protection and commit signing setup ([127d4c5](https://github.com/Pavliin/MyOwn/commit/127d4c540217c9535e81d53f98377fd69ec189ad))
* fix markdownlint formatting violations ([79a539e](https://github.com/Pavliin/MyOwn/commit/79a539ec99b6766acbf2c8845fcd41ef7ca404d7))
