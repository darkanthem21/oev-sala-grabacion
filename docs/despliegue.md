# Manual de despliegue

La aplicación se despliega en el servidor del curso desde la imagen que publica
GitHub Actions en GHCR (`ghcr.io/darkanthem21/oev-sala-grabacion`). En el
servidor no se clona el repositorio ni se construye nada: solo se necesitan dos
archivos de compose y un `.env`.

Al arrancar, el contenedor aplica las migraciones y crea el superusuario si no
existe. No hay pasos manuales de base de datos.

## Servidor del curso

| Dato | Valor |
|---|---|
| Máquina | `146.83.216.166`, usuario `grupo6` por SSH |
| URL pública | <https://oev.inf.uach.cl> |
| Carpeta de despliegue | `~/oev` |
| Contenedor de la aplicación | `grupo6_frontend`, puerto interno `3006` |
| Contenedor de los recordatorios | `grupo6_tareas`, la misma imagen con un bucle que corre cada hora |
| Contenedor de la base | `grupo6_db` |
| Volúmenes | `grupo6_pgdata` (base) y `grupo6_checkoutmedia` (fotos del check-out) |
| Red | `red_taller_software`, compartida por todos los grupos |

## Imágenes publicadas

| Cuándo | Etiquetas |
|---|---|
| Cada push a `main` | `main` y el SHA del commit |
| A mano, desde *Actions* > **imagen** > *Run workflow* sobre una rama | La rama con `/` cambiado por `-` (`feat-us-14-bloques-apoyo`) y el SHA |

El mismo workflow borra lo antiguo: quedan `main` y las 15 versiones más
recientes.

## Primera instalación

### 1. Copiar los archivos al servidor

Desde la raíz del repositorio en tu máquina, con `main` actualizado:

```sh
git switch main && git pull
ssh grupo6@146.83.216.166 'mkdir -p ~/oev'
scp docker-compose.yml docker-compose.servidor.yml grupo6@146.83.216.166:~/oev/
scp .env.ejemplo grupo6@146.83.216.166:~/oev/.env
```

### 2. Completar el `.env`

En el servidor:

```sh
cd ~/oev
chmod 600 .env
nano .env
```

Ese archivo vive solo en el servidor y nunca entra a git.

| Variable | Valor |
|---|---|
| `TAG` | Qué imagen desplegar: `main`, el SHA completo de un commit o una rama publicada a mano |
| `PUERTO` | `3006`. Tiene que coincidir con la regla del Caddy |
| `ALLOWED_HOSTS` | `oev.inf.uach.cl` |
| `CSRF_ORIGINS` | `https://oev.inf.uach.cl`. Caddy sirve el dominio por HTTPS |
| `URL_BASE` | `https://oev.inf.uach.cl`. Dominio de los enlaces del recordatorio; por defecto `http://localhost:8000` |
| `POSTGRES_PASSWORD` | Clave de la base. PostgreSQL la lee solo al crear el volumen: cambiarla después no cambia la de la base |
| `SECRET_KEY` | Aleatoria y larga: `python3 -c 'import secrets; print(secrets.token_urlsafe(50))'` |
| `DJANGO_SUPERUSER_EMAIL` | Correo del superusuario: la cuenta de soporte de la Oficina, la única que da y quita el rol **Administrador** |
| `DJANGO_SUPERUSER_PASSWORD` | Su clave. Si el usuario ya existe, no se modifica |
| `EMAIL_BACKEND` | Opcional. Sin él, los correos se escriben en el log del contenedor, también el enlace con que una cuenta nueva crea su contraseña. Para enviarlos: `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Solo con el backend SMTP: servidor, usuario y clave de la cuenta que envía |
| `EMAIL_PORT`, `EMAIL_USE_TLS` | Opcionales; por defecto `587` y `1` (STARTTLS), lo que usan Gmail, Brevo y Ethereal |
| `DEFAULT_FROM_EMAIL` | Opcional. Remitente de los correos; por defecto `no-responder@uach.cl`. Con una cuenta externa tiene que ser la dirección de esa cuenta, o el correo cae en spam |

Compose lee el mismo `.env` dos veces: para elegir la imagen (`TAG`, `PUERTO`) y
para pasarle las variables a los contenedores.

### 3. Definir el atajo

Todos los comandos siguientes se ejecutan en `~/oev`, con este atajo:

```sh
alias dc='docker-compose -p grupo6 -f docker-compose.yml -f docker-compose.servidor.yml'
```

Para no repetirlo en cada sesión, se agrega esa línea a `~/.bashrc`.

El `-p grupo6` fija el nombre del proyecto, y de ahí sale el del volumen. Sin
él, compose usa el nombre de la carpeta y crearía otra base vacía.

### 4. Levantar

Se sigue con el paso 2 de la sección siguiente.

### 5. Cargar las áreas

Las áreas no vienen cargadas y un solicitante sin un área activa no puede pedir
la sala. En la pestaña **Áreas**, crear **Educación Continua Online** y
**Decanatura** (minuta del 27/10).

## Desplegar una versión

### 1. Esperar la imagen

Después del merge a `main`, esperar a que termine el workflow `imagen` en la
pestaña *Actions* de GitHub. Hasta que termine, la imagen nueva no existe.

Si el cambio tocó `docker-compose.yml` o `docker-compose.servidor.yml`, repetir
antes el `scp` del paso 1 de la primera instalación, sin el `.env`. Si la versión
trae migraciones, hacer antes el [respaldo](#respaldo-de-la-base).

### 2. Bajar la imagen y reiniciar

En el servidor, poner en `TAG` la versión que se quiere desplegar y ejecutar:

```sh
cd ~/oev
dc pull web
dc down
dc up -d
docker images ghcr.io/darkanthem21/oev-sala-grabacion -f dangling=true -q | xargs -r docker rmi
```

**Siempre `down` y después `up -d`, nunca `up -d` directamente.** El
`docker-compose` 1.29.2 falla al recrear un contenedor con
`KeyError: 'ContainerConfig'`, porque lee un campo que las imágenes construidas
por el workflow ya no traen. Crear los contenedores de cero no pasa por ese
código. El `down` sin `-v` no borra el volumen: los datos se conservan.
**Nunca `dc down -v`**: borra la base.

La última línea borra la imagen que quedó sin etiqueta al bajar la nueva. Solo
toca las de este repositorio: el servidor es compartido, así que nunca
`docker image prune`.

### 3. Verificar

```sh
docker ps --filter name=grupo6
docker logs --tail 50 grupo6_frontend
```

Tienen que estar arriba `grupo6_frontend`, `grupo6_tareas` y `grupo6_db`. El log
tiene que mostrar las migraciones aplicadas y terminar en
`Starting development server at http://0.0.0.0:3006/`. Después se entra a la URL
pública y se inicia sesión.

## Volver a una versión anterior

Se pone en `TAG` el SHA completo del commit que funcionaba y se repite el paso 2
de "Desplegar una versión". Volver a una imagen anterior **no revierte las
migraciones**: si la versión nueva cambió la base, hay que restaurar el respaldo.

## Respaldo de la base

Antes de desplegar una versión que traiga migraciones:

```sh
docker exec grupo6_db pg_dump -U oev oev > respaldo-$(date +%F).sql
docker cp grupo6_frontend:/app/media media-$(date +%F)
```

La segunda línea copia las fotos del check-out, que viven en el volumen
`grupo6_checkoutmedia` y no en la base.

Para restaurar, sobre una base vacía:

```sh
docker exec -i grupo6_db psql -U oev oev < respaldo-AAAA-MM-DD.sql
```

### Exportar la estructura

Para revisar las tablas, índices, restricciones y claves foráneas sin los datos,
`pg_dump -s` exporta solo la estructura. `--no-owner --no-privileges` deja fuera
los dueños y permisos, para que el archivo sirva en otra máquina.

En el servidor:

```sh
docker exec grupo6_db pg_dump -U oev -s --no-owner --no-privileges oev > estructura-$(date +%F).sql
```

En desarrollo, con la base levantada y las migraciones aplicadas:

```sh
docker compose -f docker-compose.yml -f docker-compose.desarrollo.yml exec -T db pg_dump -U oev -s --no-owner --no-privileges oev > estructura.sql
```

Ni el respaldo ni la estructura entran al repositorio (`CONTRIBUTING.md`). Las
relaciones entre tablas también están dibujadas en `docs/diagramas.md`, en
**Relaciones de la base de datos**.

## Diagramas de la documentación

`docs/` no viaja en la imagen (`.dockerignore`), así que los diagramas no se
despliegan: se compilan en la máquina de quien los cambia y se commitean con su
fuente. Todos incluyen `docs/diagramas/estilo.iuml`, que fija la resolución, las
fuentes y el color de cada capa. Para compilarlos hacen falta PlantUML y las
fuentes **Noto Sans** y **JetBrainsMono NF** instaladas. El detalle está en
`docs/diagramas.md`, en
[Cómo se dibujan y se compilan](diagramas.md#cómo-se-dibujan-y-se-compilan).

## Decisión abierta: una restricción en la base contra sanciones pisadas

Hoy la regla de que dos sanciones no levantadas no se pisen la revisan
`Sancion.clean()` y `personas.services.aplicar`, que bloquea la fila de la
persona mientras revisa. Lo que no pasa por ahí (el shell, un `UPDATE` a mano)
no la cumple. PostgreSQL podría exigirla siempre con una `ExclusionConstraint`
sobre `daterange(inicio, termino, '[]')` y `usuario_id`, con
`levantada_en IS NULL`. No se agregó porque:

- Necesita la extensión `btree_gist`, que la migración crearía con
  `CreateExtension`. Desde PostgreSQL 13 es una extensión *trusted*: la puede
  crear el dueño de la base. En este servidor el usuario `oev` es el
  `POSTGRES_USER` de la imagen, que es superusuario, así que alcanzaría; en
  otro servidor con un usuario sin privilegio `CREATE` sobre la base, la
  migración falla y alguien con permisos tiene que correr antes
  `CREATE EXTENSION btree_gist;`.
- El contenedor aplica las migraciones solo al arrancar. Si la base ya tiene
  sanciones pisadas, que US-10 permitía, la migración falla y el sitio no
  levanta hasta limpiarlas. Antes hay que decidir qué hacer con ellas.

Para revisar si hay sanciones pisadas antes de decidir:

```sh
docker exec grupo6_db psql -U oev oev -c "
  SELECT a.usuario_id, a.id, b.id FROM personas_sancion a JOIN personas_sancion b
    ON a.usuario_id = b.usuario_id AND a.id < b.id
   AND a.levantada_en IS NULL AND b.levantada_en IS NULL
   AND a.inicio <= b.termino AND b.inicio <= a.termino;"
```

## Problemas conocidos

| Síntoma | Causa | Solución |
|---|---|---|
| `KeyError: 'ContainerConfig'` al hacer `up -d` | Compose 1.29.2 intentó recrear un contenedor | `dc down` y después `dc up -d` |
| Error 500 sin detalle en el navegador | Con `DEBUG=0` el traceback no se muestra | `docker logs grupo6_frontend` |
| 500 al enviar el login, pero la página de login carga | Falló la base: la página no la consulta, autenticar sí | Revisar que `grupo6_db` esté *healthy* y que `POSTGRES_PASSWORD` sea la del volumen |
| 400 *Bad Request* | El dominio no está en `ALLOWED_HOSTS` | Corregir `.env` y redesplegar |
| 403 *CSRF verification failed* al enviar un formulario | Falta el dominio con `https://` en `CSRF_ORIGINS` | Corregir `.env` y redesplegar |
| 502 desde el Caddy | El contenedor está caído o no coincide con la regla | `docker ps`; revisar `container_name` y `PUERTO` |
| `manifest unknown` al hacer `pull` | El workflow no terminó, el `TAG` está mal escrito o la versión ya no está entre las 15 que se conservan | Revisar *Actions* y el nombre de la etiqueta |
| `unauthorized` al hacer `pull` | El paquete de GHCR es privado | Hacerlo público en GitHub, o `docker login ghcr.io` con un token con permiso `read:packages` |
| SSH responde `Connection timed out` | Pasó en septiembre sin explicación, con el sitio funcionando | Preguntar en el Discord del curso si a otros grupos les responde el puerto 22 |
