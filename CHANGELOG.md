# Changelog

All notable changes to this project will be documented in this file. See [commit-and-tag-version](https://github.com/absolute-version/commit-and-tag-version) for commit guidelines.

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
