#!/usr/bin/env bash
# Escribe relaciones-bd.puml desde la base de desarrollo: una entidad por tabla,
# agrupadas por app, y una línea por clave foránea. El PNG se compila aparte,
# como el de los demás diagramas (ver docs/diagramas.md, "Cómo se dibujan").
#
# Requiere el stack de desarrollo con las migraciones aplicadas:
#   docker compose -f docker-compose.yml -f docker-compose.desarrollo.yml up -d db
#   docker compose -f docker-compose.yml -f docker-compose.desarrollo.yml run --rm web python manage.py migrate
set -euo pipefail

raiz="$(cd "$(dirname "$0")/../../.." && pwd)"
salida="$raiz/docs/diagramas/estructura/relaciones-bd.puml"
compose=(docker compose -f "$raiz/docker-compose.yml" -f "$raiz/docker-compose.desarrollo.yml")

psql_db() {
  "${compose[@]}" exec -T db psql -U oev -d oev -At -F '|' -c "$1"
}

# tabla | columna | tipo | NOT NULL | es PK
columnas="$(psql_db "
  SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull,
         EXISTS (SELECT 1 FROM pg_index i
                 WHERE i.indrelid = c.oid AND i.indisprimary AND a.attnum = ANY(i.indkey))
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
  WHERE n.nspname = 'public' AND c.relkind = 'r'
  ORDER BY c.relname, a.attnum;")"

# tabla de origen | columna | tabla referenciada | NOT NULL | columna única (uno a uno)
llaves="$(psql_db "
  SELECT c.conrelid::regclass::text, a.attname, c.confrelid::regclass::text, a.attnotnull,
         EXISTS (SELECT 1 FROM pg_index i
                 WHERE i.indrelid = c.conrelid AND i.indisunique AND i.indnatts = 1
                   AND i.indkey[0] = a.attnum)
  FROM pg_constraint c
  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
  WHERE c.contype = 'f'
  ORDER BY 1, 2;")"

COLUMNAS="$columnas" LLAVES="$llaves" SALIDA="$salida" python3 - <<'PY'
import os
import re

# El prefijo de la tabla es la app de Django que la crea.
APPS = [
    ("personas", "personas"),
    ("agenda", "agenda"),
    ("solicitudes", "solicitudes"),
    ("uso", "uso"),
    ("configuracion", "configuracion"),
    ("Django (auth, admin, sesiones)", "auth|django"),
]

TIPOS = [
    (r"^character varying\((\d+)\)$", r"varchar(\1)"),
    (r"^timestamp with time zone$", "timestamptz"),
    (r"^time without time zone$", "time"),
]


def tipo(texto):
    for patron, corto in TIPOS:
        texto = re.sub(patron, corto, texto)
    return texto


tablas = {}
for linea in os.environ["COLUMNAS"].splitlines():
    tabla, columna, ty, no_nulo, pk = linea.split("|")
    tablas.setdefault(tabla, []).append((columna, tipo(ty), no_nulo == "t", pk == "t"))

llaves = []
destino_de = {}
for linea in os.environ["LLAVES"].splitlines():
    origen, columna, destino, no_nulo, unica = linea.split("|")
    llaves.append((origen, columna, destino, no_nulo == "t", unica == "t"))
    destino_de[(origen, columna)] = destino


def app_de(tabla):
    for nombre, prefijos in APPS:
        if re.match(rf"^({prefijos})_", tabla):
            return nombre
    return "otras"


def entidad(tabla):
    lineas = [f'  entity "{tabla}" as {tabla} {{']
    cols = tablas[tabla]
    for columna, ty, no_nulo, pk in cols:
        if pk:
            lineas.append(f"    * <b>{columna}</b> : {ty}")
    lineas.append("    --")
    for columna, ty, no_nulo, pk in cols:
        if pk:
            continue
        marca = "* " if no_nulo else ""
        destino = destino_de.get((tabla, columna))
        flecha = f" → {destino}" if destino else ""
        lineas.append(f"    {marca}{columna} : {ty}{flecha}")
    lineas.append("  }")
    return lineas


out = [
    "@startuml relaciones-bd",
    "!include ../estilo.iuml",
    "' Generado por generar_relaciones.sh desde la base de desarrollo: no editar a mano.",
    "hide circle",
    "hide empty members",
    "left to right direction",
    "title Relaciones de la base de datos",
    "",
]
grupos = {}
for tabla in tablas:
    grupos.setdefault(app_de(tabla), []).append(tabla)
for nombre, _ in APPS + [("otras", "")]:
    if nombre not in grupos:
        continue
    out.append(f'package "{nombre}" {{')
    for tabla in grupos[nombre]:
        out.extend(entidad(tabla))
    out.append("}")
    out.append("")

for origen, columna, destino, no_nulo, unica in llaves:
    # Lado de la tabla referenciada: exactamente uno si la FK es obligatoria, cero o uno si no.
    izquierda = "||" if no_nulo else "|o"
    # Lado de la que referencia: a lo más uno si la columna es única (uno a uno), si no, muchos.
    derecha = "o|" if unica else "o{"
    out.append(f"{destino} {izquierda}--{derecha} {origen} : {columna}")

out += [
    "",
    "legend right",
    "  <b>negrita</b>: clave primaria · <b>*</b>: NOT NULL · <b>→</b>: clave foránea",
    "endlegend",
    "@enduml",
]

with open(os.environ["SALIDA"], "w") as f:
    f.write("\n".join(out) + "\n")

print(f"{len(tablas)} tablas, {len(llaves)} claves foráneas -> {os.environ['SALIDA']}")
PY
