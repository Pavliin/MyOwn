# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A personal self-hosted cloud project (files, photos, passwords, messaging, mail — replacing GAFAM services), starting as a solo POC for the author's family/friends. Full context lives in `docs/`, read it before making architectural decisions:

- [`docs/architecture.md`](docs/architecture.md) — chosen stack, infra, security, backup, known risks
- [`docs/roadmap.md`](docs/roadmap.md) — phased development plan with exit criteria per phase
- [`docs/pitch.md`](docs/pitch.md) — technical presentation of the project
- [`docs/vision-long-terme.md`](docs/vision-long-terme.md) — long-term directions to keep in mind, out of scope for the POC
- [`docs/notes-techniques.md`](docs/notes-techniques.md) — as-built reference: deployed versions, notable config choices, gotchas actually hit and how they were resolved
- [`docs/manuel-installation.md`](docs/manuel-installation.md) — reproducible steps for a first install
- [`docs/manuel-utilisateur.md`](docs/manuel-utilisateur.md) — how to use each deployed service (URL, credentials, basics)

**Keep the last three updated as you go, not retroactively**: whenever a service is added or changed in `gitops/apps/`, or a real bug/gotcha is hit and fixed (not a typo — an actual "this didn't work the way the docs/chart suggested" moment), add it to `notes-techniques.md` in the same PR. Same for `manuel-installation.md` (new bootstrap step) and `manuel-utilisateur.md` (new service reachable by a human) whenever they change. Retrofitting these later is much easier to get wrong or skip entirely.

## Current state

**Read this section first in any new conversation** — it's the single pointer to where the project actually stands, kept current at each natural completion point (end of a phase, end of an integration) rather than after every commit. For the full detail behind any of this, see `docs/notes-techniques.md` (as-built) and `docs/roadmap.md` (phase plan) — don't re-derive from `git log` unless this section seems stale.

Local k3d dev cluster (`myown-dev`) only — no mini PC or domain yet. Two access patterns: most services on `myown-<service>.local:8090` (HTTP); Vaultwarden and Nextcloud on `:8453` (HTTPS, mkcert) — each for a different reason: Vaultwarden needs the browser's Subtle Crypto API, Nextcloud's `user_oidc` SSO app flatly refuses to run over HTTP. ArgoCD (`gitops/apps/`, app-of-apps) manages everything except the bootstrap layer itself (`gitops/bootstrap/`: ArgoCD, KSOPS, internal DNS/Traefik-mirror — see `manuel-installation.md`).

- **Roadmap restructured (2026-08-08)**: everything that hard-requires the mini PC/domain (Android app validation across services, Matrix federation test) was pulled out of Phases 1-3 and merged into Phase 4, now "Bascule vers l'infra réelle & Mail" — Mail needed that infra from day one anyway, so it's a single hardware/domain cutover instead of one per phase. Phases 1-3 are now fully closable on the dev cluster alone. See `docs/roadmap.md` for the exact split.
- **Roadmap Phase 0 ("Socle")**: complete. k3s(dev)/ArgoCD/monitoring/Authentik/secrets(SOPS+KSOPS) all working.
- **Roadmap Phase 1 ("Vaultwarden")**: complete — Vaultwarden deployed and SSO-integrated with Authentik (via an Authentik blueprint, not the admin UI; took 4 real bugs to get a login to actually succeed, all in `notes-techniques.md`). Restic backup pipeline done and validated (daily CronJob, backup + full restore tested in the dev cluster — targets a local PVC as a stand-in for the real "nœud ami", which doesn't exist yet; see `notes-techniques.md`). Android app validation is no longer part of this phase's exit criteria — deferred to Phase 4.
- **Roadmap Phase 2 ("Nextcloud + Immich")**: both services deployed and working. Nextcloud: SSO-integrated with Authentik and validated end-to-end (official `user_oidc` app via `hooks.before-starting`; HTTPS on `:8453`; also fixed an SSRF guard and a Redis-session password encoding bug — see `notes-techniques.md`), Calendar/Contacts installed, Restic backup extended (files + `pg_dump` of Postgres) and validated with a real backup+restore test, native Photos app disabled now that Immich exists (one photo app per architecture.md §2). Immich: deployed (official `immich/immich` chart; Postgres is a hand-written StatefulSet on `ghcr.io/immich-app/postgres`, incompatible with the Bitnami postgresql chart used elsewhere) and validated end-to-end via the API (account creation, login, upload, confirmed on the library PVC). SSO integrated too and validated with a real browser login — Immich has native OAuth support (no third-party app like Nextcloud's `user_oidc`), configured via a partial `IMMICH_CONFIG_FILE` (merges with schema defaults, confirmed in the server source — only the `oauth` section is set, nothing else touched) rather than the Admin Settings UI, on the user's explicit ask that no one should ever have to click through manual config. Restic backup extended too and validated with a real backup+restore test (library PVC + `pg_dump` of Postgres, same shape as Nextcloud's — ML cache PVC deliberately excluded, fully reproducible). Still open for Immich: Android app (deferred to Phase 4 by roadmap design).
- **Roadmap Phase 3 ("Messagerie") — plan de démarrage arrêté (2026-08-09)**, pas encore implémenté : premier service à déployer sera **Tuwunel**, pas Conduwuit comme prévu dans `architecture.md` — **Conduwuit est archivé et n'est plus maintenu en amont**, pas viable pour stocker des messages privés sur la durée. Deux successeurs actifs identifiés : Continuwuity (continuation communautaire, pas de SSO natif confirmé) et Tuwunel (successeur officiel, adopté à l'échelle gouvernementale — Suisse —, staffé à temps plein, support OIDC natif déjà mergé — cohérent avec le "tout par Authentik" du projet) ; **Tuwunel retenu**. Approche prévue pour ce premier déploiement (nu, même déroulé incrémental que les autres services — pas de SSO/Restic/Android/LiveKit à ce stade) :
  - Pas de chart Helm à jour pour aucun des deux successeurs (le seul chart "conduwuit" trouvé pointe vers le projet archivé) → manifests bruts dans `gitops/manifests/tuwunel/` (`Deployment` + `Service` + `PVC`), `Application` ArgoCD dédiée `gitops/apps/tuwunel.yaml`.
  - Stockage RocksDB **embarqué** (pas de Postgres séparé, comme Vaultwarden) — une seule PVC pour `/var/lib/tuwunel`.
  - Config entièrement par variables d'env `TUWUNEL_*` (`TUWUNEL_SERVER_NAME`, `TUWUNEL_DATABASE_PATH`, `TUWUNEL_ALLOW_REGISTRATION`, `TUWUNEL_REGISTRATION_TOKEN` depuis un secret SOPS `gitops/secrets/tuwunel/`) — pas de fichier de config à monter.
  - Port client-serveur `8008` (HTTP) ; fédération (`8448`) différée en Phase 4. Ingress HTTP simple `myown-tuwunel.local:8090`.
  - Premier compte inscrit devient automatiquement admin (confirmé pour Tuwunel) — pas de commande d'init séparée à automatiser.
  - **Point technique resté incertain, à vérifier au déploiement réel** : la config par défaut lie le service à `127.0.0.1`/`::1` (`TUWUNEL_ADDRESS`) — potentiellement inutilisable depuis le Service Kubernetes ; à fixer explicitement et à valider par un `curl` réel depuis l'intérieur du cluster.
  - Validation prévue : inscription réelle + message envoyé via l'API client-serveur Matrix (`POST /_matrix/client/v3/register`), sans navigateur — même approche que les tests API faits pour Immich.
  - Docs à mettre à jour dans le cadre de ce déploiement (pas encore fait) : `docs/architecture.md` §5.5 (remplacer Conduwuit par Tuwunel, noter l'archivage), `docs/roadmap.md` Phase 3 (`Conduwuit` → `Tuwunel`), `docs/notes-techniques.md` (nouvelle section), `docs/manuel-utilisateur.md` (nouvelle entrée).
- **Not yet touched**: Mailcow, Ollama, LiveKit.

**Next step**: Phase 2 is fully done on the dev cluster. Phase 3 (messaging) plan is set (see bullet above) — implement the bare Tuwunel deployment described there: raw manifests, ArgoCD Application, SOPS secret for `REGISTRATION_TOKEN`, verify `TUWUNEL_ADDRESS` reachability, validate via a real registration + message over the client-server API, then update the architecture/roadmap/notes-techniques/manuel-utilisateur docs listed above.

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
- **Releases**: cut when a feature is implemented *and* validated in real use (matches the roadmap's exit-criteria philosophy — no release for a merge that only compiles/deploys but hasn't been used). Full process:
  1. Run `npm run release` (wraps `commit-and-tag-version`): bumps `package.json` version per the highest-impact commit type since the last tag, regenerates `CHANGELOG.md` from Conventional Commits (section mapping in `.versionrc.json`), creates a `chore(release): x.y.z` commit and a `vX.Y.Z` git tag.
  2. Push the tag directly (`git push origin vX.Y.Z`) — tags aren't covered by branch protection. The commit **can't** go through `git push --follow-tags` since `master` requires a PR; push it on a branch (e.g. `chore/release-x.y.z`) and merge normally like any other change.
  3. Create the GitHub Release (`gh release create vX.Y.Z --title "vX.Y.Z — Phase Name" --notes-file <file>`) — pushing the tag alone does **not** create one, they're separate GitHub objects. Title format `vX.Y.Z — <roadmap phase closed>`; body is a short French summary of what the release closes out, followed by that version's exact section from `CHANGELOG.md`. Do this for every tag going forward — `v0.1.1`/`v0.1.2` initially only existed as tags until this was noticed and backfilled.
- **Branch protection on `master`** is active (GitHub ruleset `master_protect`, repo Settings → Rules): PR required, `commitlint`+`markdown` checks required, no force-push, no branch deletion, **signed commits required**. Branch protection/rulesets need either a public repo or GitHub Pro on a personal (non-org) account — this repo is public specifically to get this for free.
- **Commit signing**: every commit on `master` must be SSH-signed. Anyone pushing to this repo (including on a new machine) needs their own signing key:
  1. `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_signing -C "commit-signing"`
  2. `gh ssh-key add ~/.ssh/id_ed25519_signing.pub --type signing` (or add it manually under GitHub Settings → SSH and GPG keys, as a *Signing Key*, not an *Authentication Key*)
  3. Locally, in the repo: `git config gpg.format ssh`, `git config user.signingkey ~/.ssh/id_ed25519_signing.pub`, `git config commit.gpgsign true` — the user should run these themselves, Claude must never modify git config.

## Design philosophy to respect when implementing

Assemble mature open-source components (Authentik, Vaultwarden, Nextcloud, Immich, Conduwuit/Element X/LiveKit, Mailcow, Ollama) rather than reimplementing them. Custom development is reserved for the integration layer (SSO wiring, automations, local AI glue) — see `docs/architecture.md` §3 and §5 for the full rationale and per-component choices before proposing a different tool.
