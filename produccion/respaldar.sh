#!/bin/sh
# Respalda la base y las fotos del check-out en respaldos/. Lo corre
# desplegar.sh antes de cada despliegue; también sirve para un cron.
set -eu
umask 077
cd "$(dirname "$0")/.."
c="docker compose -f docker-compose.yml -f docker-compose.produccion.yml"
mkdir -p respaldos
parcial="respaldos/.parcial-$$"
trap 'rm -f "$parcial"' EXIT

# Con `| gzip`, un pg_dump que falla deja un archivo vacío y salida 0: comprime
# pg_dump (-Z) y el archivo toma su nombre recién al terminar bien.
base="respaldos/oev-$(date +%Y%m%d-%H%M%S).sql.gz"
$c exec -T db pg_dump -U oev -Z6 oev > "$parcial"
mv "$parcial" "$base"
echo "respaldo: $base"
# Quedan los 30 más recientes.
ls -1t respaldos/oev-*.sql.gz | tail -n +31 | xargs -r rm --

# Las fotos no entran en el pg_dump. No cambian después de subidas, así que
# basta una copia. Sin contenedor web es la primera instalación: no hay fotos.
web="$($c ps -aq web)"
if [ -n "$web" ]; then
  docker cp "$web:/app/media" - > "$parcial"
  mv "$parcial" respaldos/fotos.tar
  echo "fotos: respaldos/fotos.tar"
fi
