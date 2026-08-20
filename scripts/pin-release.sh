#!/usr/bin/env bash
# Pins every gitops/apps/*.yaml source that points back at this repo
# (secrets, extra manifests — the sources alongside each app's real chart)
# from "targetRevision: master" to an immutable tag. Without this, a
# production install whose root Application tracks a release tag would
# still have every child Application quietly re-resolving its own secrets/
# manifests source against master's current tip at every sync — root being
# pinned to a tag says nothing about what its children's own sources track,
# each one is an independent git reference.
#
# Deliberately NOT part of the release commit itself (`npm run release`):
# that commit lands on master, and master must keep these self-references
# floating on "master" forever — dev's ArgoCD root tracks master and
# expects its own secrets sources to track master too, not freeze onto
# whatever tag was last cut. So this script creates one extra commit on
# top of the already-merged release commit, and moves the tag there —
# master itself is never touched, this commit is never merged into it.
#
# Usage (after the release PR from `npm run release` is merged):
#   scripts/pin-release.sh vX.Y.Z

set -euo pipefail

VERSION="${1:?Usage: scripts/pin-release.sh vX.Y.Z}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

git diff --quiet --exit-code || { echo "Arbre de travail non propre — committez ou stashez avant de lancer ce script." >&2; exit 1; }

git fetch origin --tags -q

BRANCH="pin-${VERSION}"
git checkout -B "$BRANCH" "origin/master"

for f in gitops/apps/*.yaml; do
  grep -q "repoURL: https://github.com/Pavliin/MyOwn.git" "$f" || continue
  awk -v ver="$VERSION" '
    /repoURL: https:\/\/github\.com\/Pavliin\/MyOwn\.git/ { print; pin=1; next }
    pin && /targetRevision: /{ sub(/targetRevision: .*/, "targetRevision: " ver); pin=0; print; next }
    { pin=0; print }
  ' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done

if git diff --quiet; then
  echo "Rien à épingler (déjà à jour, ou tag inconnu de ces fichiers)."
  git checkout - >/dev/null
  git branch -D "$BRANCH" >/dev/null
  exit 0
fi

git add gitops/apps/*.yaml
git commit -m "chore(release): pin ${VERSION} self-references

Rewrites each gitops/apps/*.yaml's own repoURL: .../MyOwn.git sources
(secrets, extra manifests) from targetRevision: master to this exact
tag, so a production install tracking ${VERSION} via root's own
targetRevision doesn't quietly keep floating on master for its
secrets/manifests. Deliberately not part of master's history — see
this script's own header, or notes-techniques.md."

git tag -f "$VERSION" HEAD

echo
echo "Commit créé sur la branche locale '${BRANCH}' — jamais destinée à être mergée dans master."
echo "Vérifiez le diff (git show ${VERSION}), puis publiez :"
echo "  git push --force origin ${VERSION}"
echo
echo "La prod peut alors suivre ce tag exact :"
echo "  kubectl patch application root -n argocd --type merge -p '{\"spec\":{\"source\":{\"targetRevision\":\"${VERSION}\"}}}'"
