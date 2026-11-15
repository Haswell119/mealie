# Installer Mealie Personal Edition sur un NAS UGREEN

Cette pile Docker Compose est isolée : son propre projet (`mealie-pe`), son propre réseau, ses
propres volumes. Elle ne modifie aucune autre application du NAS.

| Service | Rôle | Port publié |
|---|---|---|
| `mealie` | l'application | un seul, choisi après l'audit, sur une seule interface |
| `postgres` | la base de données | aucun |
| `backup` | sauvegarde chiffrée quotidienne | aucun |
| `price-bridge` | prix des magasins (facultatif, éteint par défaut) | aucun |

## En bref : déployer depuis son poste

Dans le dépôt, sur le poste de développement (Git Bash sous Windows) :

```bash
NAS_SSH=utilisateur@nas sh deploy/nas/deploy-from-pc.sh
```

Le script construit l'image à partir du dernier commit, l'envoie au NAS par SSH sans passer par un
registre, copie ce dossier dans `/volume2/docker/mealie-pe` et y lance `install.sh`.

- **Premier passage** : `install.sh` crée les deux secrets et un fichier `.env`, puis s'arrête.
  Compléter `.env` sur le NAS (étapes 1 et 2), puis relancer la même commande : la pile démarre.
- **Passages suivants** : la même commande met à jour, avec une sauvegarde vérifiée avant.

Pour ne pas retaper l'adresse, l'écrire dans `deploy/nas/.deploy.env` (non suivi par git) :
`NAS_SSH=utilisateur@nas`. Les autres réglages sont décrits en tête du script.

Les étapes ci-dessous détaillent ce que fait le script et permettent de tout faire à la main.

## 1. Auditer le NAS (lecture seule)

Copier le dossier `deploy/nas` sur le NAS, puis :

```bash
sh ./audit-nas.sh
```

Le script ne crée, ne modifie et ne supprime rien. Il liste les conteneurs, les ports en écoute, les
projets Compose, les réseaux et l'état de Tailscale, puis propose un port libre. Pour vérifier un
port précis :

```bash
sh ./audit-nas.sh 9925
```

Ne pas continuer tant qu'une ligne marquée `[!!]` reste inexpliquée.

## 2. Préparer la configuration

```bash
cp .env.example .env
```

Dans `.env`, renseigner `MEALIE_PORT` (le port confirmé par l'audit), `BASE_URL`, `BACKUP_DIR`,
`PUID` et `PGID`.

Créer les deux secrets. Ils ne vont ni dans `.env` ni dans le dépôt :

```bash
openssl rand -base64 36 > secrets/postgres_password.txt
```

```bash
openssl rand -base64 48 > secrets/backup_passphrase.txt
```

```bash
chmod 600 secrets/*.txt
```

**Conserver une copie de `backup_passphrase.txt` ailleurs que sur le NAS** (gestionnaire de mots de
passe). Sans elle, les sauvegardes sont illisibles.

## 3. Obtenir l'image

**Sans registre** : `deploy-from-pc.sh` construit l'image sur le poste et la charge sur le NAS sous
le nom `mealie-pe:<version>-pe.<commit>`. Rien d'autre à faire.

**Avec un registre** : l'image se construit par GitHub Actions (onglet *Actions* du dépôt → *Personal Edition Image* →
*Run workflow*, étiquette `3.31.0-pe.1`). Le workflow lance d'abord tous les tests et ne publie
l'image que s'ils passent. L'image arrive dans `ghcr.io/<votre compte>/mealie-pe`.

Si le dépôt est privé, connecter le NAS au registre une fois :

```bash
docker login ghcr.io
```

Variante : construire sur le NAS, en décommentant le bloc `build` de `docker-compose.yml` (prévoir
environ 4 Go de mémoire et plusieurs minutes).

## 4. Démarrer

```bash
docker compose up -d
```

```bash
docker compose ps
```

`mealie` doit passer à l'état `healthy`. Le premier démarrage crée les tables de Mealie puis celles
du fork.

Se connecter avec `changeme@example.com` / `MyPassword`, puis **changer immédiatement l'adresse et
le mot de passe**.

## 5. Accès privé en HTTPS par Tailscale

L'application n'écoute que sur `127.0.0.1` (réglage `MEALIE_BIND_IP`). Deux façons de l'ouvrir :

**Tailscale Serve** (recommandé : certificat HTTPS automatique, visible seulement depuis votre
réseau Tailscale, aucun autre conteneur) :

```bash
tailscale serve --bg --https=443 http://127.0.0.1:9925
```

Vérifier d'abord avec `tailscale serve status` (affiché par l'audit) qu'aucun service n'occupe déjà
le port 443 de Tailscale ; sinon choisir un autre port HTTPS, par exemple `--https=8443`.
`BASE_URL` vaut alors `https://<nom-du-nas>.<votre-tailnet>.ts.net` (avec `:8443` le cas échéant).

**Tailscale dans un conteneur** (le NAS n'a pas la commande `tailscale`) : brancher un conteneur
Tailscale sur le réseau `mealie-pe_internal` et lui faire relayer `http://mealie:9000`. Le port de
l'hôte ne sert alors pas. `BASE_URL` vaut `https://<nom du conteneur Tailscale>.<votre-tailnet>.ts.net`.

**Reverse proxy déjà présent sur le NAS** : y ajouter un hôte qui pointe vers
`http://127.0.0.1:<MEALIE_PORT>`. Ne pas modifier les hôtes existants. Le proxy doit transmettre les
en-têtes `Host`, `X-Forwarded-For` et `X-Forwarded-Proto`.

## 6. Premiers réglages dans l'application

1. **Personnes** → créer votre fiche (« C'est moi ») avec vos restrictions. Pour une maladie
   cœliaque : Gluten, sévérité stricte, portée « Toute la préparation », « S'applique quand cette
   personne cuisine ».
2. **Vérifications** → marquer « vérifié » les aliments dont vous avez lu l'étiquette.
3. **Stocks** → saisir le stock, les tailles de paquets et, dans l'onglet **Prix**, ce que vous
   payez pour les aliments que vous achetez souvent. Chaque plan de courses compare alors les
   magasins sur le **panier entier**, et la page **Idées** donne le coût par portion.
4. **Budget** → après les courses, « J'ai fait ces courses » dans le plan enregistre le montant
   payé. La page **Budget** montre les dépenses par mois et par magasin, l'objectif du mois, et
   le coût des repas planifiés et des recettes.
5. **Assistant IA** (facultatif) → voir `docs/personal-edition/infomaniak.md`.

## Prix des magasins (facultatif)

Sans rien activer, les prix se saisissent à la main dans **Stocks → Prix**, et le budget fonctionne.

Le service `price-bridge` ajoute la recherche des prix du jour chez Coop, Migros, Aldi et Lidl, et
la mise à jour des prix déjà gardés. Il est **éteint par défaut**. Avant de l'allumer, savoir que :

- il installe, à la construction de son image, le paquet npm
  [`@nicktcode/swissgroceries-mcp`](https://www.npmjs.com/package/@nicktcode/swissgroceries-mcp),
  un programme tiers qui lit les sites publics des enseignes. Ce dépôt n'en contient pas le code.
  Sa licence (PolyForm Shield 1.0.0) autorise l'usage personnel ; la lire avant de construire ;
- ce programme n'est ni écrit ni vérifié par ce projet. Il tourne donc à l'écart : aucun secret,
  aucun volume, aucun port publié, système de fichiers en lecture seule, et un réseau (`prices`)
  qu'il ne partage qu'avec `mealie` — il ne voit pas la base de données ;
- Mealie ne lui envoie que le texte recherché et le nom des enseignes ; jamais rien sur une
  personne. Les enseignes voient l'adresse IP du NAS, comme pour une visite de leur site ;
- les enseignes peuvent changer leur site : une enseigne peut cesser de répondre sans prévenir
  (Lidl ne publie qu'une partie de son assortiment). L'application le signale et continue.

Pour l'allumer, écrire dans `.env` :

```bash
COMPOSE_PROFILES=prices
PE_PRICE_SOURCE_URL=http://price-bridge:8080
```

```bash
docker compose up -d --build
```

Vérifier que le service répond, puis chercher un produit dans **Stocks → Prix** :

```bash
docker compose exec price-bridge wget -q -O - http://127.0.0.1:8080/health
```

Dans un plan de courses, le bouton **Chercher les produits en magasin** propose alors, pour
chaque article et chaque enseigne, les produits qui correspondent. Vous choisissez ; rien n'est
gardé avant. À savoir :

- les enseignes nomment leurs produits en allemand : l'application traduit l'aliment (liste
  `mealie/services/personal/data/store_terms.json`) et vous pouvez chercher avec un autre texte ;
- un produit n'est présélectionné que si son nom désigne bien l'aliment. Pour un aliment « sans
  gluten », un produit qui ne porte pas cette mention n'est jamais proposé ;
- **un prix ne vérifie rien** : le produit proposé n'est pas contrôlé pour vos restrictions.
  Lisez l'étiquette ;
- les montants sont approximatifs : un article compté à la pièce est estimé avec un poids
  usuel, et un article sans prix dans un magasin y est compté au prix moyen des autres. Un
  magasin qui a un prix pour moins de la moitié des articles n'est pas comparé.

Pour l'éteindre : retirer les deux lignes de `.env`, puis

```bash
docker compose --profile prices rm --stop --force price-bridge
```

```bash
docker compose up -d
```

Les prix déjà gardés restent ; ils ne sont simplement plus mis à jour.

La version du programme tiers est fixée dans `price-bridge/Dockerfile` (`PRICE_SERVICE_VERSION`).
La changer est une décision : relire son journal des modifications avant.

## Sauvegardes

Chaque nuit à `BACKUP_TIME`, le service `backup` écrit dans `BACKUP_DIR` deux fichiers chiffrés en
AES-256 : la base (`…-db.dump.enc`) et les fichiers (`…-data.tar.gz.enc`). Il vérifie que la base se
déchiffre et se lit, puis supprime les sauvegardes de plus de `BACKUP_KEEP_DAYS` jours.

Sauvegarde immédiate :

```bash
docker compose run --rm backup now
```

Copier régulièrement `BACKUP_DIR` hors du NAS.

### Restaurer

```bash
docker compose stop mealie
```

```bash
docker compose run --rm --entrypoint restore.sh backup /backups/<horodatage>-db.dump.enc
```

Restaurer les fichiers (images, pièces jointes) :

```bash
docker compose run --rm --entrypoint sh -v mealie-pe_mealie-data:/restore backup -c 'openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass file:/run/secrets/backup_passphrase -in /backups/<horodatage>-data.tar.gz.enc | tar -C /restore -xzf -'
```

```bash
docker compose up -d mealie
```

**Tester une restauration une fois, juste après l'installation.** Une sauvegarde jamais restaurée
n'est pas une sauvegarde.

## Mettre à jour

```bash
sh ./upgrade.sh ghcr.io/<votre compte>/mealie-pe:3.32.0-pe.1
```

Depuis le poste, `deploy-from-pc.sh` construit la nouvelle image puis appelle ce même script.

Le script fait une sauvegarde vérifiée, change l'image, redémarre et contrôle l'état de santé. Les
migrations de Mealie et du fork s'appliquent au démarrage.

## Retour arrière

Trois niveaux, du plus léger au plus radical.

**1. Revenir à l'image précédente** (la mise à jour a échoué) : restaurer la sauvegarde faite par
`upgrade.sh` (procédure ci-dessus), remettre l'ancienne valeur de `MEALIE_IMAGE` (conservée dans
`.env.before-upgrade`), puis `docker compose up -d`. Ne jamais démarrer une ancienne image sur une
base déjà migrée sans restaurer la sauvegarde.

**2. Retirer le fork et garder ses recettes** (revenir à Mealie d'origine) :

```bash
docker compose exec mealie python -c "from mealie.db import personal_migrations as m; m.downgrade()"
```

Cette commande supprime toutes les tables du fork (personnes, événements, plans, stocks,
inspirations). Les recettes, le planning et les listes de courses restent. Remplacer ensuite
`MEALIE_IMAGE` par l'image officielle de la **même version** (`ghcr.io/mealie-recipes/mealie:v3.31.0`).

**3. Tout supprimer** :

```bash
docker compose down
```

Les volumes `mealie-pe_mealie-data` et `mealie-pe_postgres-data` restent en place tant qu'on ne les
supprime pas explicitement. Aucune autre application du NAS n'est concernée.

## Ce que cette pile ne fait pas

- Elle ne publie rien sur Internet et n'ouvre aucun port sur le routeur.
- Elle ne publie pas le port de PostgreSQL.
- Elle ne touche ni aux réseaux, ni aux volumes, ni aux conteneurs des autres projets.
