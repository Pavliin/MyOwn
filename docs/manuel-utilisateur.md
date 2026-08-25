# Manuel utilisateur

Guide de prise en main des services MyOwn — un compte unique, une section par
service : à quoi il sert, comment démarrer.

Tous les services se rejoignent avec la même identité : un email et un mot de
passe, créés une fois pour toutes via **Authentik**, votre "compte MyOwn". Sur
chaque service, cherchez un bouton du type *« Se connecter via Authentik »* —
c'est toujours la même connexion.

## 👤 Mon compte (Authentik)

**À quoi ça sert** : le compte qui ouvre tous les autres services — vous ne
créez un compte séparé nulle part ailleurs.

- **Adresse** : <https://authentik.offsystem.fr>

### Pour commencer

1. Le premier accès se fait via un **lien envoyé par l'administrateur** — pas
   d'inscription libre.
2. Ce lien vous laisse choisir vous-même votre mot de passe ; personne
   d'autre, pas même l'administrateur, ne le voit passer.
3. Une fois connecté, vous pouvez retrouver vos informations de profil dans
   le menu en haut à droite.

### Ajouter un authentificateur (recommandé)

Un authentificateur permet de récupérer votre compte vous-même en cas de mot
de passe oublié, sans passer par l'administrateur — il ne vous sera **jamais**
demandé pour une connexion normale, uniquement pour cette récupération.

1. Depuis votre profil (menu en haut à droite), ouvrez la section
   **Authentificateurs**.
2. Ajoutez un authentificateur **TOTP** et scannez le QR code affiché avec
   une application comme Google Authenticator, Aegis ou Ente Auth.
3. Saisissez le code à 6 chiffres affiché pour confirmer.

!!! example "Capture à venir"
    Écran d'ajout d'un authentificateur TOTP.

!!! note "Mot de passe oublié"
    Depuis l'écran de connexion, **Mot de passe oublié ?** vous identifie
    (nom d'utilisateur ou email) puis vous demande un code de votre
    authentificateur avant de choisir un nouveau mot de passe — à condition
    d'en avoir configuré un comme ci-dessus. Sans authentificateur, demandez
    un lien à l'administrateur.

## 🗂️ Nextcloud — fichiers, agenda, contacts

**À quoi ça sert** : vos fichiers, votre calendrier, vos contacts, vos notes
et vos listes de tâches, accessibles depuis n'importe où — le remplaçant
maison de Google Drive.

- **Adresse** : <https://nextcloud.offsystem.fr>

### Pour commencer

1. Connectez-vous avec le bouton *« Se connecter via Authentik »*.
2. Glissez-déposez un fichier depuis votre ordinateur pour l'envoyer.
3. Dans le menu de gauche : **Calendrier**, **Contacts**, **Notes** (texte
   libre) et **Tâches** (listes à cocher partagées — une tâche avec une date
   apparaît aussi automatiquement dans le Calendrier).
4. Le dossier **Mediatheque** est partagé avec toute la famille : déposez-y
   un film ou un album pour qu'il apparaisse dans Jellyfin (voir plus bas).

!!! example "Capture à venir"
    Écran d'accueil Nextcloud après connexion — vue Fichiers.

### Agenda et contacts sur mobile

L'application Nextcloud ne synchronise pas l'agenda/les contacts elle-même :
elle renvoie vers une application tierce (par exemple **DAVx5** — payante
sur le Play Store, gratuite via F-Droid). Cette application ne propose pas
de connexion via Authentik, mais un **mot de passe d'application** scanné
par QR code :

1. Sur Nextcloud (navigateur) : **Réglages → Sécurité → « Appareils et
   sessions »**.
2. Donnez un nom à l'appareil, puis **« Créer un nouveau mot de passe
   d'application »**.
3. Un QR code s'affiche : scannez-le depuis l'application de synchronisation
   sur votre téléphone — serveur, identifiant et mot de passe se remplissent
   automatiquement.

!!! example "Capture à venir"
    QR code de mot de passe d'application dans Nextcloud.

## 🔑 Vaultwarden — mots de passe

**À quoi ça sert** : un coffre-fort qui retient tous vos mots de passe à
votre place, compatible avec l'application officielle Bitwarden (navigateur,
téléphone, ordinateur).

- **Adresse** : <https://vaultwarden.offsystem.fr>

### Pour commencer

1. Ouvrez l'adresse ci-dessus et cliquez sur *« Se connecter via
   Authentik »* — pas besoin de créer un compte séparé.
2. À cette première connexion, Vaultwarden vous demande de définir votre
   **mot de passe maître**. Le SSO prouve qui vous êtes, mais seul ce mot de
   passe peut déchiffrer votre coffre — d'où cette double étape :
   choisissez-le solide et dont vous vous souviendrez, personne ne peut vous
   le retrouver s'il est perdu, pas même l'administrateur du serveur.
3. Installez l'extension ou l'application Bitwarden, puis dans ses réglages
   changez le **serveur** pour l'adresse ci-dessus (Bitwarden pointe vers
   bitwarden.com par défaut) avant de vous connecter avec les mêmes
   identifiants.
4. Ajoutez votre premier mot de passe avec le bouton **+**.

!!! example "Capture à venir"
    Réglage « Serveur auto-hébergé » dans l'application Bitwarden.

!!! note "Sur mobile : bouton « Use single sign-on »"
    Une fois votre email saisi, ne cliquez pas sur *Continuer* (qui demande
    un mot de passe classique) : choisissez plutôt l'option distincte
    **« Use single sign-on »**. Un « identifiant SSO » est ensuite demandé —
    n'importe quelle valeur convient (tapez par exemple `offsystem`).

!!! warning "Avertissement Chrome « Dangerous site »"
    Un avertissement rouge plein écran peut apparaître pendant la
    redirection — faux positif connu de Chrome, sans rapport avec la
    sécurité réelle du site. Le bouton pour continuer est caché : cherchez
    un lien texte (souvent la phrase *« this unsafe site »*) plutôt qu'un
    vrai bouton, en dépliant les détails de l'avertissement si besoin.

## 📷 Immich — photos et vidéos

**À quoi ça sert** : le remplaçant maison de Google Photos — stockage,
albums, recherche parmi vos photos et vidéos, avec reconnaissance des
visages qui tourne localement (rien n'est envoyé à l'extérieur).

- **Adresse** : <https://immich.offsystem.fr>

### Pour commencer

1. Connectez-vous avec le bouton *« Se connecter via Authentik »*.
2. Glissez-déposez des photos ou vidéos depuis votre navigateur.
3. L'application mobile officielle Immich peut aussi être configurée pour
   pointer vers cette adresse, pour une sauvegarde automatique depuis votre
   téléphone.

!!! example "Capture à venir"
    Bibliothèque de photos après un premier import.

## 💬 Messagerie (Tuwunel)

**À quoi ça sert** : discussions texte et appels vidéo de groupe — pas
seulement avec la famille : ce serveur peut aussi discuter avec n'importe
qui possédant un compte sur un autre serveur Matrix (comme email, mais pour
la messagerie).

- **Sur ordinateur** : [Element Web](https://app.element.io) (aucune
  installation nécessaire)
- **Sur mobile** : **Element X**, disponible sur le Play Store et l'App
  Store

### Pour commencer

#### Sur ordinateur (Element Web)

1. Ouvrez [app.element.io](https://app.element.io).
2. Sur l'écran de connexion, cliquez sur **Modifier** en face du serveur
   proposé par défaut, et saisissez `offsystem.fr`.
3. Connectez-vous via Authentik. Votre identité est
   `@votre-prenom:offsystem.fr`.
4. Dans une conversation, un bouton d'appel démarre un appel vidéo de
   groupe.

#### Sur mobile (Element X)

1. Installez **Element X** depuis le Play Store ou l'App Store.
2. Au démarrage, choisissez l'option pour un **serveur personnalisé** et
   saisissez `offsystem.fr`.
3. Connectez-vous via Authentik.

!!! note "État du système du foyer"
    Le salon [#etat-du-systeme](https://matrix.to/#/#etat-du-systeme:offsystem.fr)
    prévient en cas de panne d'un service — cliquez sur le lien pour le
    rejoindre directement (la recherche de salon dans Element ne trouve pas
    toujours les alias existants).

!!! warning "Appels vidéo de groupe sur mobile"
    Les appels de groupe fonctionnent bien depuis un ordinateur. Sur mobile,
    un problème connu les empêche encore de démarrer — le chat texte, lui,
    fonctionne normalement partout.

## ✉️ Mailu — courrier électronique

**À quoi ça sert** : une boîte mail complète (webmail, anti-spam) sur le
domaine `offsystem.fr` — le remplaçant maison de Gmail/Outlook.

- **Adresse** : <https://mailu.offsystem.fr>

### Pour commencer

1. Connectez-vous via Authentik — pas de formulaire de connexion séparé, la
   page redirige directement.
2. Votre adresse mail est automatiquement créée à cette première connexion,
   à partir de l'email de votre compte MyOwn.

!!! warning "Adresse en @offsystem.fr requise"
    Si votre compte MyOwn utilise encore un email extérieur (Gmail...), la
    connexion à Mailu est refusée. Demandez à l'administrateur de mettre à
    jour votre email vers une adresse `@offsystem.fr` avant votre première
    connexion.

### Lier votre carnet d'adresses Nextcloud

Le webmail affiche vos contacts Nextcloud directement à la composition,
ajoutés en libre-service, comme l'authentificateur plus haut.

1. Dans le webmail, **Paramètres → CardDAV**, puis **+**.
2. Renseignez :
   - **URL** : `https://nextcloud.offsystem.fr/remote.php/dav/`
   - **Nom d'utilisateur** : votre identifiant Nextcloud interne — **pas**
     votre email. S'il n'est pas visible dans vos réglages Nextcloud,
     demandez-le à l'administrateur.
   - **Mot de passe** : un **mot de passe d'application** généré dans
     Nextcloud (**Paramètres → Sécurité → « Appareils et sessions »**), pas
     votre mot de passe MyOwn habituel.

!!! example "Capture à venir"
    Formulaire d'ajout CardDAV dans le webmail Mailu.

## 🎬 Jellyfin — films et musique

**À quoi ça sert** : votre bibliothèque de films, séries et musique, en
streaming sur tous vos écrans.

- **Adresse** : <https://jellyfin.offsystem.fr>

### Pour commencer

1. Connectez-vous via Authentik — votre compte Jellyfin est créé
   automatiquement à la première connexion.
2. Pour ajouter un film ou un album : déposez le fichier dans le dossier
   **Mediatheque** de Nextcloud (voir plus haut) — Jellyfin le détecte et
   l'affiche après une courte mise à jour automatique.

!!! example "Capture à venir"
    Écran d'accueil Jellyfin avec la bibliothèque de films.

## 🟢 État du système

**À quoi ça sert** : vérifier en un coup d'œil que tout fonctionne, sans
avoir à demander à l'administrateur.

- **Adresse** : <https://status.offsystem.fr>

Vert = tout va bien. En cas de panne, un message est aussi posté
automatiquement dans le salon
[#etat-du-systeme](https://matrix.to/#/#etat-du-systeme:offsystem.fr).
