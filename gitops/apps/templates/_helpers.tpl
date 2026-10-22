{{/*
Domaine de l'installation (valeur `domain`, configuration d'installation —
docs/installation-utilisateur.md). Obligatoire : sans lui, le rendu échoue
explicitement plutôt que de produire des noms d'hôte vides.
*/}}
{{- define "myown.domain" -}}
{{- required "la valeur `domain` est obligatoire (configuration d'installation de root)" .Values.domain -}}
{{- end -}}
