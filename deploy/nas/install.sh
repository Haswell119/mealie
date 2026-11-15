#!/bin/sh
# Installe Mealie Personal Edition, ou la met à jour si elle est déjà installée.
# À lancer sur le NAS, dans ce dossier, une fois l'image présente (deploy-from-pc.sh le fait).
#
#   sh ./install.sh mealie-pe:3.31.0-pe.f48125b
#
# Premier lancement : crée les deux secrets et un fichier .env à compléter, puis s'arrête.
# Lancements suivants : démarre la pile, ou la met à jour par ./upgrade.sh (sauvegarde d'abord).
set -eu

cd "$(dirname "$0")"
[ $# -eq 1 ] || { echo "Usage : sh ./install.sh <image>" >&2; exit 2; }
image="$1"

# Les secrets ne sont créés qu'une fois : les régénérer rendrait la base et les sauvegardes illisibles.
# Les chmod sont explicites : sur un dossier à ACL par défaut (cas de /volume2/docker sous UGOS),
# umask ne suffit pas et les fichiers naîtraient lisibles par tous les comptes du NAS.
(
    umask 077
    mkdir -p secrets
    chmod 700 secrets
    [ -s secrets/postgres_password.txt ] || openssl rand -base64 36 > secrets/postgres_password.txt
    [ -s secrets/backup_passphrase.txt ] || openssl rand -base64 48 > secrets/backup_passphrase.txt
    chmod 600 secrets/*.txt
)

if [ ! -f .env ]; then
    sed -e "s|^MEALIE_IMAGE=.*|MEALIE_IMAGE=$image|" \
        -e "s|^PUID=.*|PUID=$(id -u)|" \
        -e "s|^PGID=.*|PGID=$(id -g)|" .env.example > .env
    echo "Fichier créé : $(pwd)/.env"
    echo "Y renseigner MEALIE_PORT (sh ./audit-nas.sh propose un port libre), BASE_URL et BACKUP_DIR, puis relancer."
    exit 3
fi

if ! docker compose config --quiet; then
    echo "Le fichier $(pwd)/.env est incomplet : corriger la variable citée ci-dessus, puis relancer." >&2
    exit 3
fi

# Créé ici pour qu'il appartienne à l'utilisateur du NAS : Docker le créerait au nom de root.
backup_dir="$(grep '^BACKUP_DIR=' .env | cut -d= -f2-)"
mkdir -p "$backup_dir"

if [ -n "$(docker compose ps --all --quiet mealie)" ]; then
    if [ "$(grep '^MEALIE_IMAGE=' .env | cut -d= -f2-)" = "$image" ]; then
        echo "L'image $image est déjà celle de .env."
    else
        sh ./upgrade.sh "$image"
    fi
    # Reconstruit le service de sauvegarde si ses scripts ont changé ; ne touche pas au reste.
    docker compose up --detach --build
    exit 0
fi

sed -i "s|^MEALIE_IMAGE=.*|MEALIE_IMAGE=$image|" .env
docker compose up --detach --build

echo "Premier démarrage : création des tables (jusqu'à 5 minutes)…"
i=0
while [ $i -lt 60 ]; do
    status="$(docker inspect --format '{{.State.Health.Status}}' "$(docker compose ps --quiet mealie)" 2>/dev/null || echo unknown)"
    if [ "$status" = "healthy" ]; then
        port="$(grep '^MEALIE_PORT=' .env | cut -d= -f2-)"
        echo "Mealie répond sur le port $port du NAS. Suite : README.md, sections 4 à 6."
        exit 0
    fi
    i=$((i + 1))
    sleep 5
done

echo "ÉCHEC : l'application ne répond pas." >&2
echo "Journal : docker compose logs --tail 100 mealie" >&2
exit 1
