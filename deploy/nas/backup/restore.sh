#!/bin/sh
# Restaure une sauvegarde de la base. À lancer avec le conteneur mealie ARRÊTÉ.
#
#   restore.sh /backups/20261115-033000-db.dump.enc
#
# Les fichiers (images, pièces jointes) se restaurent à part : voir README.md.
set -eu

[ $# -eq 1 ] || { echo "Usage : restore.sh <fichier -db.dump.enc>" >&2; exit 2; }
[ -r "$1" ] || { echo "Fichier introuvable : $1" >&2; exit 1; }

PGPASSWORD="$(cat "$PGPASSFILE_SOURCE")"
export PGPASSWORD

echo "Cette opération REMPLACE toute la base « $PGDATABASE ». Tapez OUI pour continuer :"
read -r answer
[ "$answer" = "OUI" ] || { echo "Abandon."; exit 1; }

openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass "file:$BACKUP_PASSPHRASE_FILE" -in "$1" \
    | pg_restore --clean --if-exists --no-owner --dbname "$PGDATABASE"
echo "Base restaurée. Redémarrez mealie : docker compose up -d mealie"
