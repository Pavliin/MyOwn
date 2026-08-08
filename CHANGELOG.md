# Changelog

All notable changes to this project will be documented in this file. See [commit-and-tag-version](https://github.com/absolute-version/commit-and-tag-version) for commit guidelines.

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
