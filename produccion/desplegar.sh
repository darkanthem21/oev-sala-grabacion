#!/bin/sh
# Despliega una versión en el servidor propio. Uso:
#
#   sh produccion/desplegar.sh <tag>      # SHA completo de un commit, o main
#
# Si la versión no levanta, vuelve sola a la última de desplegados.log. Las
# migraciones no se revierten: para eso está el respaldo que se hace antes.
set -eu
cd "$(dirname "$0")/.."

TAG="${1:?falta el tag: el SHA del commit o main}"
export TAG
c="docker compose -f docker-compose.yml -f docker-compose.produccion.yml"

# La base se levanta primero para respaldarla siempre, también si estaba
# detenida. Si el respaldo falla, no se despliega.
$c up -d --wait db
sh produccion/respaldar.sh

$c pull web tareas

# --wait espera el healthcheck de web: gunicorn respondiendo, con la
# configuración revisada y las migraciones aplicadas.
levantar() { $c up -d --remove-orphans --wait --wait-timeout 180; }

if levantar; then
  echo "$(date -Iseconds) $TAG" >> desplegados.log
  docker images ghcr.io/darkanthem21/oev-sala-grabacion -f dangling=true -q | xargs -r docker rmi >/dev/null 2>&1 || true
  echo "desplegado: $TAG"
  exit 0
fi

echo "web no quedó arriba; últimas líneas del log:" >&2
$c logs --tail 40 web >&2
anterior="$(tail -n 1 desplegados.log 2>/dev/null | cut -d' ' -f2)"
if [ -n "$anterior" ] && [ "$anterior" != "$TAG" ]; then
  echo "vuelvo a $anterior; las migraciones que alcanzó a aplicar $TAG no se revierten" >&2
  TAG="$anterior"
  levantar >&2 || echo "tampoco levantó $anterior" >&2
fi
exit 1
