# Changelog

All notable changes to this project will be documented in this file. See [commit-and-tag-version](https://github.com/absolute-version/commit-and-tag-version) for commit guidelines.

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
