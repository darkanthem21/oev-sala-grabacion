#!/bin/sh
# Despliega una versión en el servidor propio. Uso, desde la carpeta del stack:
#
#   produccion/desplegar.sh <tag>      # SHA completo de un commit, o main
#
# Volver atrás es lo mismo con el SHA anterior (ver desplegados.log), pero las
# migraciones no se revierten: para eso está el respaldo que se hace antes.
set -eu
cd "$(dirname "$0")/.."

TAG="${1:?falta el tag: el SHA del commit o main}"
export TAG
c="docker compose -f docker-compose.yml -f docker-compose.produccion.yml"

mkdir -p respaldos
if [ -n "$($c ps -q db 2>/dev/null)" ]; then
  archivo="respaldos/oev-$(date +%Y%m%d-%H%M%S).sql.gz"
  $c exec -T db pg_dump -U oev oev | gzip > "$archivo"
  echo "respaldo: $archivo"
  # Quedan los 20 más recientes.
  ls -1t respaldos/*.sql.gz | tail -n +21 | xargs -r rm --
fi

$c pull web tareas
$c up -d --remove-orphans

# Si la configuración es insegura o falla una migración, web se reinicia en
# bucle: se espera a que lleve 20 segundos arriba sin reinicios.
for _ in $(seq 30); do
  sleep 2
  id="$($c ps -q web)"
  estado="$(docker inspect -f '{{.State.Running}} {{.RestartCount}}' "$id")"
  inicio="$(docker inspect -f '{{.State.StartedAt}}' "$id")"
  if [ "$estado" = "true 0" ] && [ $(( $(date +%s) - $(date -d "$inicio" +%s) )) -ge 20 ]; then
    echo "$(date -Iseconds) $TAG" >> desplegados.log
    docker images ghcr.io/darkanthem21/oev-sala-grabacion -f dangling=true -q | xargs -r docker rmi >/dev/null 2>&1 || true
    echo "desplegado: $TAG"
    exit 0
  fi
done

echo "web no quedó arriba; últimas líneas del log:" >&2
$c logs --tail 40 web >&2
exit 1
