#!/usr/bin/env bash
# Generates the family-facing browser bookmarks file (Netscape Bookmark
# format — importable into Chrome/Firefox/Edge/Safari) from the domain a
# MyOwn install actually runs on, instead of hand-maintaining a static
# HTML file that would silently drift from docs/manuel-utilisateur.md.
#
# Deliberately limited to the family-facing services (same list as
# docs/manuel-utilisateur.md) — admin-only services (ArgoCD, Grafana,
# Ollama) are never included, matching the project's own no-admin-tools-
# in-front-of-the-family principle.
#
# Usage:
#   scripts/generate-bookmarks.sh [DOMAIN] [OUTPUT_FILE]
#
#   DOMAIN       defaults to offsystem.fr
#   OUTPUT_FILE  defaults to myown-favoris.html ; use "-" for stdout

set -euo pipefail

DOMAIN="${1:-offsystem.fr}"
OUTPUT_FILE="${2:-myown-favoris.html}"
ADD_DATE="$(date +%s)"

render() {
  cat <<HTML
<!DOCTYPE NETSCAPE-Bookmark-file-1>
<!-- This is an automatically generated file.
     It will be read and overwritten.
     DO NOT EDIT! -->
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Favoris</TITLE>
<H1>Favoris</H1>
<DL><p>
    <DT><H3 ADD_DATE="${ADD_DATE}" LAST_MODIFIED="${ADD_DATE}">MyOwn</H3>
    <DL><p>
        <DT><A HREF="https://nextcloud.${DOMAIN}" ADD_DATE="${ADD_DATE}">Nextcloud — Fichiers, agenda, contacts</A>
        <DT><A HREF="https://vaultwarden.${DOMAIN}" ADD_DATE="${ADD_DATE}">Vaultwarden — Mots de passe</A>
        <DT><A HREF="https://immich.${DOMAIN}" ADD_DATE="${ADD_DATE}">Immich — Photos et vidéos</A>
        <DT><A HREF="https://mailu.${DOMAIN}" ADD_DATE="${ADD_DATE}">Mailu — Courrier électronique</A>
        <DT><A HREF="https://app.element.io" ADD_DATE="${ADD_DATE}">Element — Messagerie (serveur : ${DOMAIN})</A>
        <DT><A HREF="https://jellyfin.${DOMAIN}" ADD_DATE="${ADD_DATE}">Jellyfin — Films et musique</A>
        <DT><A HREF="https://status.${DOMAIN}" ADD_DATE="${ADD_DATE}">État du système</A>
        <DT><A HREF="https://authentik.${DOMAIN}" ADD_DATE="${ADD_DATE}">Mon compte MyOwn (Authentik)</A>
        <DT><A HREF="https://aide.${DOMAIN}" ADD_DATE="${ADD_DATE}">Aide — manuel d'utilisation</A>
    </DL><p>
</DL><p>
HTML
}

if [[ "${OUTPUT_FILE}" == "-" ]]; then
  render
else
  render > "${OUTPUT_FILE}"
  echo "Favoris générés : ${OUTPUT_FILE}"
fi
