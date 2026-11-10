#!/bin/sh
# Respalda la base en respaldos/. Lo corre desplegar.sh antes de cada despliegue.
set -eu
umask 077
cd "$(dirname "$0")/.."
c="docker compose -f docker-compose.yml -f docker-compose.produccion.yml"
mkdir -p respaldos
parcial="respaldos/.parcial-$$"
trap 'rm -f "$parcial"' EXIT

# pg_dump comprime solo (-Z): con `| gzip`, un pg_dump que falla deja un archivo
# vacío y salida 0. Se escribe aparte y se renombra al final, para que un
# respaldo a medias no cuente como bueno.
base="respaldos/oev-$(date +%Y%m%d-%H%M%S).sql.gz"
$c exec -T db pg_dump -U oev -Z6 oev > "$parcial"
mv "$parcial" "$base"
echo "respaldo: $base"
# Quedan los 20 más recientes.
ls -1t respaldos/oev-*.sql.gz | tail -n +21 | xargs -r rm --
