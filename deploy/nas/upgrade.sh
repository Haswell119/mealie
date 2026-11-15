#!/bin/sh
# Met à jour Mealie Personal Edition avec une sauvegarde préalable.
#
#   ./upgrade.sh ghcr.io/haswell119/mealie-pe:3.32.0-pe.1
#
# Étapes : sauvegarde immédiate et vérifiée, changement d'image, redémarrage, contrôle de santé.
# En cas d'échec, l'ancienne image et la commande de retour arrière sont affichées.
set -eu

cd "$(dirname "$0")"
[ $# -eq 1 ] || { echo "Usage : ./upgrade.sh <nouvelle image>" >&2; exit 2; }
[ -f .env ] || { echo "Fichier .env introuvable" >&2; exit 1; }

new_image="$1"
old_image="$(grep '^MEALIE_IMAGE=' .env | cut -d= -f2-)"
echo "Image actuelle : $old_image"
echo "Nouvelle image : $new_image"

echo "1/4 Sauvegarde avant mise à jour…"
docker compose run --rm backup now

echo "2/4 Téléchargement de la nouvelle image…"
MEALIE_IMAGE="$new_image" docker compose pull mealie

echo "3/4 Redémarrage…"
cp .env ".env.before-upgrade"
sed -i "s|^MEALIE_IMAGE=.*|MEALIE_IMAGE=$new_image|" .env
docker compose up -d mealie

echo "4/4 Contrôle de santé (jusqu'à 3 minutes)…"
i=0
while [ $i -lt 36 ]; do
    status="$(docker inspect --format '{{.State.Health.Status}}' "$(docker compose ps -q mealie)" 2>/dev/null || echo unknown)"
    [ "$status" = "healthy" ] && { echo "Mise à jour réussie."; exit 0; }
    i=$((i + 1))
    sleep 5
done

echo "ÉCHEC : l'application ne répond pas." >&2
echo "Journal : docker compose logs --tail 100 mealie" >&2
echo "Retour arrière : voir README.md, section « Retour arrière » (image précédente : $old_image)" >&2
exit 1
