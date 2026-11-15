#!/bin/sh
# Sauvegarde chiffrée de la base PostgreSQL et du dossier de données de Mealie.
#
#   backup.sh loop   une sauvegarde par jour à BACKUP_TIME (mode par défaut du conteneur)
#   backup.sh now    une sauvegarde immédiate (avant une mise à jour, par exemple)
#
# Chaque sauvegarde produit deux fichiers chiffrés en AES-256 dans /backups :
#   <horodatage>-db.dump.enc     base de données (pg_dump, format personnalisé)
#   <horodatage>-data.tar.gz.enc images, pièces jointes et fichiers de Mealie
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
DATA_DIR="${DATA_DIR:-/data}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"
BACKUP_TIME="${BACKUP_TIME:-03:30}"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }

prepare() {
    [ -r "$BACKUP_PASSPHRASE_FILE" ] || { log "ERREUR : phrase secrète de sauvegarde illisible"; exit 1; }
    [ -s "$BACKUP_PASSPHRASE_FILE" ] || { log "ERREUR : phrase secrète de sauvegarde vide"; exit 1; }
    PGPASSWORD="$(cat "$PGPASSFILE_SOURCE")"
    export PGPASSWORD
    mkdir -p "$BACKUP_DIR"
}

encrypt() {
    openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass "file:$BACKUP_PASSPHRASE_FILE" -out "$1"
}

run_backup() {
    stamp="$(date '+%Y%m%d-%H%M%S')"
    db_file="$BACKUP_DIR/$stamp-db.dump.enc"
    data_file="$BACKUP_DIR/$stamp-data.tar.gz.enc"

    log "Sauvegarde de la base → $db_file"
    pg_dump --format=custom --no-owner | encrypt "$db_file.part"
    mv "$db_file.part" "$db_file"

    log "Sauvegarde des fichiers → $data_file"
    tar -C "$DATA_DIR" -czf - . | encrypt "$data_file.part"
    mv "$data_file.part" "$data_file"

    # Une sauvegarde illisible ne sert à rien : on vérifie que la base se déchiffre et se lit.
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass "file:$BACKUP_PASSPHRASE_FILE" -in "$db_file" \
        | pg_restore --list > /dev/null
    log "Sauvegarde vérifiée"

    find "$BACKUP_DIR" -maxdepth 1 -name '*.enc' -mtime "+$KEEP_DAYS" -print -delete | while read -r old; do
        log "Suppression de l'ancienne sauvegarde $old"
    done
}

seconds_until() {
    now=$(date +%s)
    target=$(date -d "$(date '+%Y-%m-%d') $1:00" +%s)
    [ "$target" -le "$now" ] && target=$((target + 86400))
    echo $((target - now))
}

prepare
case "${1:-loop}" in
    now)
        run_backup
        ;;
    loop)
        log "Sauvegarde quotidienne à $BACKUP_TIME, conservation $KEEP_DAYS jours"
        while true; do
            sleep "$(seconds_until "$BACKUP_TIME")"
            run_backup || log "ERREUR : la sauvegarde a échoué"
        done
        ;;
    *)
        echo "Usage : backup.sh [loop|now]" >&2
        exit 2
        ;;
esac
