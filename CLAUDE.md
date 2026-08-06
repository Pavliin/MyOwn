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
- **Secrets**: SOPS + age. `.sops.yaml` holds the encryption rule but the placeholder public key must be replaced with a real one before any secret is committed — never commit an unencrypted secret or the age private key.
- **CI**: `.github/workflows/lint.yml` currently only lints Markdown (`.markdownlint.yaml` relaxes line-length/inline-HTML/first-heading/fenced-code-language rules to fit prose docs). Expect this to grow (Helm lint, Trivy CVE scan) once Phase 0 introduces actual manifests — don't pre-build CI stages for infra that doesn't exist yet.
- **Language**: project docs and communication are in French.

## Design philosophy to respect when implementing

Assemble mature open-source components (Authentik, Vaultwarden, Nextcloud, Immich, Conduwuit/Element X/LiveKit, Mailcow, Ollama) rather than reimplementing them. Custom development is reserved for the integration layer (SSO wiring, automations, local AI glue) — see `docs/architecture.md` §3 and §5 for the full rationale and per-component choices before proposing a different tool.
