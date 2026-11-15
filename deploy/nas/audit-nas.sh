#!/bin/sh
# Audit en LECTURE SEULE du NAS avant l'installation de Mealie Personal Edition.
#
# Ce script ne crée, ne modifie et ne supprime rien. Il liste ce qui tourne déjà, puis indique
# si le nom de projet, les volumes et le port voulus sont libres.
#
#   ./audit-nas.sh            propose un port libre
#   ./audit-nas.sh 9925       vérifie ce port précis
set -u

PROJECT=mealie-pe
WANTED_PORT="${1:-}"
CANDIDATES="9925 9926 9927 9930 9940 19925 29925"
problems=0

section() { printf '\n=== %s ===\n' "$1"; }
ok() { printf '  [OK] %s\n' "$1"; }
warn() { printf '  [!!] %s\n' "$1"; problems=$((problems + 1)); }

listening_ports() {
    if command -v ss >/dev/null 2>&1; then
        ss -H -tln 2>/dev/null | awk '{print $4}' | sed 's/.*://' | sort -un
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tln 2>/dev/null | awk 'NR>2 {print $4}' | sed 's/.*://' | sort -un
    else
        # Ni ss ni netstat : lecture directe de la table du noyau (état 0A = en écoute).
        cat /proc/net/tcp /proc/net/tcp6 2>/dev/null | awk '$4 == "0A" {n = split($2, a, ":"); print a[n]}' \
            | while read -r hex; do printf '%d\n' "0x$hex"; done | sort -un
    fi
}

port_in_use() {
    listening_ports | grep -qx "$1" && return 0
    docker ps --format '{{.Ports}}' 2>/dev/null | grep -Eq "[:>]$1->|:$1->" && return 0
    return 1
}

section "Système"
echo "  Architecture : $(uname -m)"
echo "  Noyau        : $(uname -sr)"
case "$(uname -m)" in
    x86_64|amd64) echo "  Image à utiliser : linux/amd64" ;;
    aarch64|arm64) echo "  Image à utiliser : linux/arm64" ;;
    *) warn "Architecture non prévue : vérifier qu'une image existe pour elle" ;;
esac
free -m 2>/dev/null | awk '/^Mem:/ {printf "  Mémoire      : %s Mo au total, %s Mo disponibles\n", $2, $7}'

section "Docker"
if ! command -v docker >/dev/null 2>&1; then
    warn "Docker est introuvable dans le PATH"
else
    echo "  $(docker --version 2>/dev/null)"
    if docker compose version >/dev/null 2>&1; then
        echo "  $(docker compose version 2>/dev/null)"
    else
        warn "Le greffon « docker compose » est absent"
    fi

    section "Conteneurs en cours (nom, image, ports)"
    docker ps --format '  {{.Names}}\t{{.Image}}\t{{.Ports}}' 2>/dev/null

    section "Projets Compose existants"
    docker compose ls --all 2>/dev/null | sed 's/^/  /'
    if docker compose ls --all --format json 2>/dev/null | grep -q "\"Name\":\"$PROJECT\""; then
        warn "Un projet Compose « $PROJECT » existe déjà"
    else
        ok "Le nom de projet « $PROJECT » est libre"
    fi

    section "Collisions de noms"
    for volume in "${PROJECT}_mealie-data" "${PROJECT}_postgres-data"; do
        if docker volume inspect "$volume" >/dev/null 2>&1; then
            warn "Le volume « $volume » existe déjà (normal seulement lors d'une réinstallation)"
        else
            ok "Volume « $volume » libre"
        fi
    done
    if docker network inspect "${PROJECT}_internal" >/dev/null 2>&1; then
        warn "Le réseau « ${PROJECT}_internal » existe déjà"
    else
        ok "Réseau « ${PROJECT}_internal » libre"
    fi

    section "Sous-réseaux Docker utilisés"
    for network in $(docker network ls --format '{{.Name}}' 2>/dev/null); do
        subnet=$(docker network inspect "$network" --format '{{range .IPAM.Config}}{{.Subnet}} {{end}}' 2>/dev/null)
        [ -n "$subnet" ] && echo "  $network : $subnet"
    done
fi

section "Ports en écoute sur l'hôte"
listening_ports | tr '\n' ' ' | sed 's/^/  /'
echo

section "Port de Mealie"
if [ -n "$WANTED_PORT" ]; then
    if port_in_use "$WANTED_PORT"; then
        warn "Le port $WANTED_PORT est déjà utilisé"
    else
        ok "Le port $WANTED_PORT est libre → MEALIE_PORT=$WANTED_PORT"
    fi
else
    suggestion=""
    for port in $CANDIDATES; do
        if ! port_in_use "$port"; then suggestion="$port"; break; fi
    done
    if [ -n "$suggestion" ]; then
        ok "Port libre proposé → MEALIE_PORT=$suggestion"
    else
        warn "Aucun des ports candidats n'est libre : en choisir un autre et relancer ./audit-nas.sh <port>"
    fi
fi

section "Tailscale"
if command -v tailscale >/dev/null 2>&1; then
    echo "  Adresse IPv4 : $(tailscale ip -4 2>/dev/null | head -1)"
    tailscale status --peers=false 2>/dev/null | sed 's/^/  /'
    echo "  Services déjà publiés par « tailscale serve » :"
    tailscale serve status 2>/dev/null | sed 's/^/    /'
elif docker ps --format '{{.Names}} {{.Image}}' 2>/dev/null | grep -qi tailscale; then
    echo "  Tailscale tourne dans un conteneur :"
    docker ps --format '  {{.Names}}\t{{.Image}}' 2>/dev/null | grep -i tailscale
else
    warn "Tailscale est introuvable : l'accès privé devra passer par un autre moyen"
fi

section "Espace disque"
df -h 2>/dev/null | awk 'NR==1 || /volume|\/mnt|\/data|\/$/' | sed 's/^/  /'

section "Résultat"
if [ "$problems" -eq 0 ]; then
    echo "  Rien ne s'oppose à l'installation. Reporter le port proposé dans .env."
else
    echo "  $problems point(s) à régler avant l'installation (lignes marquées [!!])."
fi
exit 0
