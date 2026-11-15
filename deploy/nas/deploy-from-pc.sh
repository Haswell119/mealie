#!/bin/sh
# Construit l'image de Mealie Personal Edition et l'installe sur le NAS par SSH, sans registre.
# À lancer sur le poste de développement (Linux, macOS, ou Git Bash sous Windows) :
#
#   NAS_SSH=utilisateur@nas sh deploy/nas/deploy-from-pc.sh
#
# L'image part du dernier commit, pas des modifications en cours. Elle rejoint le NAS par
# `docker save | docker load`. Le dossier deploy/nas y est copié, puis ./install.sh fait la
# première installation ou la mise à jour (avec sauvegarde préalable).
#
# Réglages, en variables d'environnement ou dans deploy/nas/.deploy.env (non suivi par git) :
#   NAS_SSH    utilisateur@hôte du NAS (obligatoire)
#   NAS_PORT   port SSH (22)
#   NAS_DIR    dossier de la pile sur le NAS (/volume2/docker/mealie-pe)
#   BUILD_ON   local ou nas : où construire l'image (local si Docker tourne ici, sinon nas)
#   IMAGE_TAG  étiquette de l'image (<version de Mealie>-pe.<commit>)
set -eu

here="$(cd "$(dirname "$0")" && pwd)"
cd "$here/../.."
if [ -f "$here/.deploy.env" ]; then . "$here/.deploy.env"; fi

: "${NAS_SSH:?Définir NAS_SSH=utilisateur@hôte, ici ou dans deploy/nas/.deploy.env}"
NAS_PORT="${NAS_PORT:-22}"
NAS_DIR="${NAS_DIR:-/volume2/docker/mealie-pe}"

nas() { ssh -p "$NAS_PORT" "$NAS_SSH" "$@"; }

commit="$(git rev-parse HEAD)"
version="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)"
image="mealie-pe:${IMAGE_TAG:-$version-pe.$(git rev-parse --short HEAD)}"

if [ -n "$(git status --porcelain -- . ':(exclude)deploy')" ]; then
    echo "Attention : les modifications non validées ne seront pas dans l'image (commit $commit)."
fi

case "$(nas uname -m)" in
    x86_64 | amd64) platform=linux/amd64 ;;
    aarch64 | arm64) platform=linux/arm64 ;;
    *) echo "Architecture du NAS non prévue." >&2; exit 1 ;;
esac

if [ -z "${BUILD_ON:-}" ]; then
    if docker info > /dev/null 2>&1; then BUILD_ON=local; else BUILD_ON=nas; fi
fi

# core.autocrlf=false : sous Windows, `git archive` écrirait sinon les scripts de l'image en CRLF.
source_tar() { git -c core.autocrlf=false archive --format=tar "$commit"; }
build_args="--file docker/Dockerfile --target production --build-arg COMMIT=$commit --tag $image"

echo "1/3 Construction de $image ($BUILD_ON, $platform)…"
# L'étiquette porte le commit : une image déjà chargée sur le NAS est donc la bonne.
if nas "docker image inspect '$image' > /dev/null 2>&1"; then
    echo "    Image déjà présente sur le NAS : construction sautée."
    BUILD_ON=skip
fi
case "$BUILD_ON" in
    skip) ;;
    local)
        # shellcheck disable=SC2086
        source_tar | docker build --platform "$platform" $build_args -
        echo "    Envoi de l'image au NAS…"
        docker save "$image" | gzip -1 | nas docker load
        ;;
    nas)
        # La construction du frontend demande environ 4 Go de mémoire sur le NAS.
        source_tar | nas "docker build $build_args -"
        ;;
    *)
        echo "BUILD_ON doit valoir local ou nas." >&2
        exit 2
        ;;
esac

echo "2/3 Copie de deploy/nas vers $NAS_SSH:$NAS_DIR…"
# Le `sed` retire les CR d'une copie de travail Windows. Ni .env ni secrets/ ne sont envoyés.
tar -C "$here" -cf - docker-compose.yml .env.example README.md audit-nas.sh install.sh upgrade.sh backup \
    | nas "mkdir -p '$NAS_DIR' && cd '$NAS_DIR' && tar -xof - && sed -i 's/\r\$//' *.sh *.yml .env.example backup/*"

echo "3/3 Installation sur le NAS…"
nas "cd '$NAS_DIR' && sh ./install.sh '$image'"
