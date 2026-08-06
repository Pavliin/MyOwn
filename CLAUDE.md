# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A personal self-hosted cloud project (files, photos, passwords, messaging, mail — replacing GAFAM services), starting as a solo POC for the author's family/friends. Full context lives in `docs/`, read it before making architectural decisions:

- [`docs/architecture.md`](docs/architecture.md) — chosen stack, infra, security, backup, known risks
- [`docs/roadmap.md`](docs/roadmap.md) — phased development plan with exit criteria per phase
- [`docs/pitch.md`](docs/pitch.md) — technical presentation of the project
- [`docs/vision-long-terme.md`](docs/vision-long-terme.md) — long-term directions to keep in mind, out of scope for the POC

## Current state

Docs-only. No infrastructure code, manifests, or application code exist yet — the repo currently holds only documentation and scaffolding (license, CI lint, secrets config). Do not assume any `gitops/`, `helm/`, or app code directories exist until they're actually created. The roadmap's "Phase 0 — Socle" (k3s, ArgoCD, Traefik, Authentik, monitoring) has not started.

## Repository conventions (decided, not yet all implemented)

- **Structure**: monorepo — docs, GitOps manifests (once they exist, ArgoCD will watch this repo directly), and any custom integration code all live here. No plan to split repos at this stage.
- **License**: AGPL-3.0 (`LICENSE`) — network-copyleft, chosen deliberately so a third party can't wrap this project into a closed SaaS.
- **Git platform**: GitHub.
- **Secrets**: SOPS + age. `.sops.yaml` holds the real public key — never commit an unencrypted secret or the age private key.
- **CI**: `.github/workflows/lint.yml` lints Markdown and lints every commit in a PR (commitlint). Expect this to grow (Helm lint, Trivy CVE scan) once Phase 0 introduces actual manifests — don't pre-build CI stages for infra that doesn't exist yet.
- **Language**: project docs and communication are in French.
- **`package.json` / `node_modules`**: not a JS project — this Node tooling exists solely to run commit-and-tag-version, husky and commitlint. Don't treat its presence as an invitation to scaffold a JS/TS app here.

## Git workflow & releases

Trunk-based, single long-lived branch (`master`), no `develop`/`release` branches.

- **Dev branches**: short-lived, one per feature/fix. Before merging, clean up history with interactive rebase (`git rebase -i`) so every commit that lands on `master` is itself a valid, atomic Conventional Commit — commits are preserved through the merge, not squashed.
- **Commit format**: [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `ci:`, …). Enforced by a local `commit-msg` hook (husky + commitlint, `commitlint.config.js`) and again in CI (`wagoid/commitlint-github-action`, checks every commit in the PR range) since local hooks can be bypassed or skipped.
- **Versioning**: SemVer (`major.minor.patch`). Stay in `0.x.y` through the POC phases (0–3 in the roadmap); reserve `1.0.0` for the MVP milestone (end of roadmap phase 3 — passwords + files/photos + messaging in real use).
- **Releases**: cut when a feature is implemented *and* validated in real use (matches the roadmap's exit-criteria philosophy — no release for a merge that only compiles/deploys but hasn't been used). Run `npm run release` (wraps `commit-and-tag-version`): bumps `package.json` version per the highest-impact commit type since the last tag, regenerates `CHANGELOG.md` from Conventional Commits (section mapping in `.versionrc.json`), creates a `chore(release): x.y.z` commit and a `vX.Y.Z` git tag. Push both the commit and the tag (`git push --follow-tags`).
- **Branch protection on `master`** (PR required, CI green before merge) is a manual GitHub setting — not something configured from this repo's files, ask the user to set it up rather than assuming it's on.

## Design philosophy to respect when implementing

Assemble mature open-source components (Authentik, Vaultwarden, Nextcloud, Immich, Conduwuit/Element X/LiveKit, Mailcow, Ollama) rather than reimplementing them. Custom development is reserved for the integration layer (SSO wiring, automations, local AI glue) — see `docs/architecture.md` §3 and §5 for the full rationale and per-component choices before proposing a different tool.
