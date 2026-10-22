{{/*
Domaine de l'installation (valeur `domain`, configuration d'installation —
docs/installation-utilisateur.md). Obligatoire : sans lui, le rendu échoue
explicitement plutôt que de produire des noms d'hôte vides.
*/}}
{{- define "myown.domain" -}}
{{- required "la valeur `domain` est obligatoire (configuration d'installation de root)" .Values.domain -}}
{{- end -}}

{{/*
Source « accès admin » d'une Application : filtre par adresse + Ingress
<prefix>.<domain> vers service:port, via le chart gitops/manifests/admin-access.
Rien n'est créé si `adminSourceRanges` est vide (outil non exposé).
Usage : {{ include "myown.adminAccessSource" (dict "root" . "prefix" "grafana" "service" "monitoring-grafana" "port" 80) | nindent 4 }}
*/}}
{{- define "myown.adminAccessSource" -}}
- repoURL: {{ .root.Values.repoURL }}
  targetRevision: {{ .root.Values.revision }}
  path: gitops/manifests/admin-access
  helm:
    valuesObject:
      domain: {{ include "myown.domain" .root }}
      sourceRanges: {{ toJson .root.Values.adminSourceRanges }}
      hostPrefix: {{ .prefix }}
      service: {{ .service }}
      port: {{ .port }}
{{- end -}}
