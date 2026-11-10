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
repo=ghcr.io/darkanthem21/oev-sala-grabacion

# La base se levanta primero para respaldarla siempre, también si estaba
# detenida. Si el respaldo falla, no se despliega.
$c up -d --wait db
sh produccion/respaldar.sh

# GHCR conserva solo las últimas versiones: una más antigua se puede desplegar
# igual si la imagen sigue en este servidor.
$c pull web tareas || docker image inspect "$repo:$TAG" >/dev/null

# --wait espera el healthcheck de web: gunicorn respondiendo, con la
# configuración revisada y las migraciones aplicadas.
levantar() { $c up -d --remove-orphans --wait --wait-timeout 180; }

if levantar; then
  echo "$(date -Iseconds) $TAG" >> desplegados.log
  # Un `docker compose up` a mano tiene que levantar esta misma versión.
  if grep -q '^TAG=' .env; then sed -i "s|^TAG=.*|TAG=$TAG|" .env; else echo "TAG=$TAG" >> .env; fi
  # Quedan las 5 imágenes más recientes, para volver atrás sin depender de
  # GHCR. La que está en uso no se deja borrar.
  docker images "$repo" --format '{{.Repository}}:{{.Tag}}' | grep -v '<none>' | tail -n +6 | xargs -r docker rmi >/dev/null 2>&1 || true
  docker images "$repo" -f dangling=true -q | xargs -r docker rmi >/dev/null 2>&1 || true
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
