{{/*
Scope mapping « email vérifié », partagé par tous les fournisseurs OIDC.
Déclaré dans CHAQUE blueprint qui s'en sert (Authentik l'identifie par son
nom : une seule entrée en base, quel que soit le nombre de déclarations) —
les blueprints s'appliquent dans un ordre quelconque, et un `!Find` vers un
mapping que seul Vaultwarden créait échouait quand Tuwunel passait avant lui
(installation neuve en VM, 2026-10-29). Nom historique conservé : c'est
l'identifiant de l'objet déjà en place sur les installations existantes.
*/}}
{{- define "myown.emailVerifiedMapping" -}}
- model: authentik_providers_oauth2.scopemapping
  id: email-verified-mapping
  identifiers:
    name: "Vaultwarden: email (verified)"
    scope_name: email
  attrs:
    description: "Comme le mapping email par défaut d'Authentik, mais avec email_verified forcé à true — ce projet est le seul opérateur/IdP, pas un tiers non fiable, donc pas de flux de vérification d'email séparé à faire porter aux comptes."
    expression: |
      return {
          "email": request.user.email,
          "email_verified": True,
      }
{{- end }}
