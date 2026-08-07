# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A personal self-hosted cloud project (files, photos, passwords, messaging, mail — replacing GAFAM services), starting as a solo POC for the author's family/friends. Full context lives in `docs/`, read it before making architectural decisions:

- [`docs/architecture.md`](docs/architecture.md) — chosen stack, infra, security, backup, known risks
- [`docs/roadmap.md`](docs/roadmap.md) — phased development plan with exit criteria per phase
- [`docs/pitch.md`](docs/pitch.md) — technical presentation of the project
- [`docs/vision-long-terme.md`](docs/vision-long-terme.md) — long-term directions to keep in mind, out of scope for the POC

## Current state

Roadmap Phase 0 ("Socle") is underway, on a local k3d dev cluster (`myown-dev`) — no mini PC or domain yet, everything is reachable at `myown-<service>.local:8090` (add the host to `/etc/hosts`, HTTP not HTTPS, dev-only). ArgoCD is bootstrapped and watches `gitops/apps/` (app-of-apps pattern). Deployed so far: monitoring (kube-prometheus-stack + Uptime Kuma), Authentik (SSO) in progress. See `gitops/README.md` for the directory layout and `git log` for what's actually landed — don't assume a service exists in `gitops/apps/` until you've checked.

## Repository conventions (decided, not yet all implemented)

- **Structure**: monorepo — docs, GitOps manifests (once they exist, ArgoCD will watch this repo directly), and any custom integration code all live here. No plan to split repos at this stage.
- **License**: AGPL-3.0 (`LICENSE`) — network-copyleft, chosen deliberately so a third party can't wrap this project into a closed SaaS.
- **Git platform**: GitHub.
- **Secrets**: SOPS + age, decrypted automatically at ArgoCD sync time via KSOPS (chosen over manual `sops -d | kubectl apply` to keep disaster recovery fully automatic once the age key is restored — see `docs/vision-long-terme.md`-style reasoning: worth the extra setup cost for a project meant to be reproducible by others). `.sops.yaml` holds the real public key — never commit an unencrypted secret or the age private key.
  - Private key lives at `~/.config/sops/age/keys.txt` (sops' default lookup path, no env var needed) — **back this up somewhere durable**. Losing it is only harmless while zero secrets are encrypted; past that point it means every encrypted secret in the repo becomes permanently unrecoverable and has to be rotated.
  - New secret files: name them `*.sops.yaml` (matches `.sops.yaml`'s `path_regex`), write plaintext under `stringData`, then `sops --encrypt --in-place path/to/name.sops.yaml`. Never hand-edit an already-encrypted file.
  - Each secret lives in `gitops/secrets/<name>/` as a small kustomize app (`kustomization.yaml` + `secret-generator.yaml` ksops generator + the `*.sops.yaml`), wired into the owning service's Application as a second `sources` entry (multi-source Application) — see `gitops/apps/authentik.yaml` for the pattern to copy.
  - KSOPS itself is bootstrapped onto `argocd-repo-server` the same way ArgoCD is bootstrapped: not GitOps-managed. On a fresh cluster, after installing ArgoCD:
    1. `kubectl create secret generic sops-age -n argocd --from-file=keys.txt=$HOME/.config/sops/age/keys.txt`
    2. `kubectl patch configmap argocd-cm -n argocd --type merge -p '{"data":{"kustomize.buildOptions":"--enable-alpha-plugins --enable-exec"}}'`
    3. `kubectl patch deployment argocd-repo-server -n argocd --type strategic --patch-file gitops/bootstrap/argocd-repo-server-ksops-patch.yaml`
- **CI**: `.github/workflows/lint.yml` lints Markdown and lints every commit in a PR (commitlint). Expect this to grow (Helm lint, Trivy CVE scan) once Phase 0 introduces actual manifests — don't pre-build CI stages for infra that doesn't exist yet.
- **Language**: project docs and communication are in French.
- **`package.json` / `node_modules`**: not a JS project — this Node tooling exists solely to run commit-and-tag-version, husky and commitlint. Don't treat its presence as an invitation to scaffold a JS/TS app here.
- **Test locally before pushing, not after**: run `npm run lint:md` before opening/updating a PR — don't rely on CI to discover a lint error that a 5-second local command would have caught. Commit message format is already covered by the local `commit-msg` hook. No self-hosted runner: this repo is public, and GitHub explicitly warns against self-hosted runners on public repos (a fork's PR could run arbitrary code on the runner's host) — public repos get free/unlimited Actions minutes on hosted runners anyway, so there's no capacity reason to reach for one.

## Git workflow & releases

Trunk-based, single long-lived branch (`master`), no `develop`/`release` branches.

- **Dev branches**: short-lived, one per feature/fix. Before merging, clean up history with interactive rebase (`git rebase -i`) so every commit that lands on `master` is itself a valid, atomic Conventional Commit — commits are preserved through the merge, not squashed. Merge PRs with **"Create a merge commit"**, not "Rebase and merge": GitHub can only auto-sign commits it authors itself (a merge/squash commit), and rejects rebase-merge outright once signed commits are required (`gh pr merge --merge`).
- **Commit format**: [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `ci:`, …). Enforced by a local `commit-msg` hook (husky + commitlint, `commitlint.config.mjs` — `.mjs` is required, the commitlint GitHub Action rejects `.js`) and again in CI (`wagoid/commitlint-github-action`, checks every commit in the PR range) since local hooks can be bypassed or skipped.
- **Versioning**: SemVer (`major.minor.patch`). Stay in `0.x.y` through the POC phases (0–3 in the roadmap); reserve `1.0.0` for the MVP milestone (end of roadmap phase 3 — passwords + files/photos + messaging in real use).
- **Releases**: cut when a feature is implemented *and* validated in real use (matches the roadmap's exit-criteria philosophy — no release for a merge that only compiles/deploys but hasn't been used). Run `npm run release` (wraps `commit-and-tag-version`): bumps `package.json` version per the highest-impact commit type since the last tag, regenerates `CHANGELOG.md` from Conventional Commits (section mapping in `.versionrc.json`), creates a `chore(release): x.y.z` commit and a `vX.Y.Z` git tag. Push both the commit and the tag (`git push --follow-tags`).
- **Branch protection on `master`** is active (GitHub ruleset `master_protect`, repo Settings → Rules): PR required, `commitlint`+`markdown` checks required, no force-push, no branch deletion, **signed commits required**. Branch protection/rulesets need either a public repo or GitHub Pro on a personal (non-org) account — this repo is public specifically to get this for free.
- **Commit signing**: every commit on `master` must be SSH-signed. Anyone pushing to this repo (including on a new machine) needs their own signing key:
  1. `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_signing -C "commit-signing"`
  2. `gh ssh-key add ~/.ssh/id_ed25519_signing.pub --type signing` (or add it manually under GitHub Settings → SSH and GPG keys, as a *Signing Key*, not an *Authentication Key*)
  3. Locally, in the repo: `git config gpg.format ssh`, `git config user.signingkey ~/.ssh/id_ed25519_signing.pub`, `git config commit.gpgsign true` — the user should run these themselves, Claude must never modify git config.

## Design philosophy to respect when implementing

Assemble mature open-source components (Authentik, Vaultwarden, Nextcloud, Immich, Conduwuit/Element X/LiveKit, Mailcow, Ollama) rather than reimplementing them. Custom development is reserved for the integration layer (SSO wiring, automations, local AI glue) — see `docs/architecture.md` §3 and §5 for the full rationale and per-component choices before proposing a different tool.
