# Manual de despliegue

La aplicación se despliega desde la imagen que publica GitHub Actions en GHCR
(`ghcr.io/darkanthem21/oev-sala-grabacion`), en dos lugares: el servidor del
curso, a mano, y el [servidor propio](#servidor-propio), donde la puede desplegar
el CI. En ninguno se clona el repositorio ni se construye nada: solo se
necesitan los archivos de compose y un `.env`.

Al arrancar, el contenedor:

1. Corre `check --deploy` y **no levanta** si la configuración es insegura: una
   `SECRET_KEY` corta o de ejemplo, `DEBUG=1` o cookies sin `Secure`. El motivo
   queda en el log.
2. Aplica las migraciones y crea el superusuario si no existe. No hay pasos
   manuales de base de datos.
3. Levanta gunicorn con `WEB_CONCURRENCY` workers (2 por defecto) de 4 hilos
   cada uno, para que una subida lenta de fotos no deje a un worker sin
   responder. Los estáticos los sirve whitenoise, con nombre con hash y
   comprimidos.

El contenedor corre con el usuario `oev` (UID 1000), no como root. Solo puede
escribir en `/app/media`, las fotos del check-out.

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

### Usuario del contenedor

Hasta noviembre la imagen corría como root, y el volumen de fotos quedó de root.
Antes del primer despliegue con la imagen nueva hay que cambiarle el dueño una
vez, o las fotos nuevas del check-out fallan al guardarse:

```sh
docker run --rm -v grupo6_checkoutmedia:/m alpine chown -R 1000:1000 /m
```

No necesita sudo: alcanza con estar en el grupo `docker`. Un volumen nuevo ya
nace con el dueño correcto.

## Imágenes publicadas

| Cuándo | Etiquetas |
|---|---|
| Cada push a `main`, si pasan las pruebas | `main` y el SHA del commit |
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
| `WEB_CONCURRENCY` | Opcional. Workers de gunicorn; por defecto `2`. Cada uno ocupa unos 50 MB |
| `PUERTO` | `3006`. Tiene que coincidir con la regla del Caddy |
| `ALLOWED_HOSTS` | `oev.inf.uach.cl` |
| `CSRF_ORIGINS` | `https://oev.inf.uach.cl`. Caddy sirve el dominio por HTTPS |
| `URL_BASE` | `https://oev.inf.uach.cl`. Dominio de los enlaces del recordatorio; por defecto `http://localhost:8000` |
| `POSTGRES_PASSWORD` | Clave de la base. PostgreSQL la lee solo al crear el volumen: cambiarla después no cambia la de la base |
| `SECRET_KEY` | Aleatoria y larga: `python3 -c 'import secrets; print(secrets.token_urlsafe(50))'`. Con una corta el contenedor no levanta |
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
tiene que mostrar las migraciones aplicadas y terminar en `Booting worker with
pid`, una línea por worker. Después se entra a la URL
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

## Servidor propio

El servidor que asignó la profesora en noviembre. A diferencia del del curso,
somos sus administradores: no hay red compartida ni proxy de otro, así que el
stack trae el suyo.

| Dato | Valor |
|---|---|
| Máquina | `45.79.193.250` (VPS de Linode, Ubuntu 24.04, 1 CPU, 1 GB de RAM) |
| URL | La de `DOMINIO`. Mientras `oev.inf.uach.cl` apunte al servidor del curso, `45-79-193-250.sslip.io` |
| Carpeta de despliegue | `~/oev` del usuario que despliega |
| Compose | v2 (`docker compose`), proyecto `oev` fijado en `docker-compose.produccion.yml` |
| Volúmenes | `oev_pgdata`, `oev_checkoutmedia` y `oev_caddy_data` (certificados) |
| Puertos públicos | 80 y 443, de Caddy. La aplicación y la base no publican puertos |

Caddy (`produccion/Caddyfile`) saca y renueva el certificado de Let's Encrypt,
redirige http a https, agrega HSTS y comprime. gunicorn queda detrás, sin
recibir conexiones directas de internet. Para que Caddy obtenga el certificado,
`DOMINIO` tiene que resolver a la IP del servidor y los puertos 80 y 443 tienen
que estar abiertos.

### Primera instalación

Requiere Docker Engine con el plugin de compose v2 y un usuario en el grupo
`docker`. Desde la raíz del repositorio:

```sh
ssh USUARIO@45.79.193.250 'mkdir -p ~/oev/produccion'
scp docker-compose.yml docker-compose.produccion.yml USUARIO@45.79.193.250:~/oev/
scp produccion/Caddyfile produccion/desplegar.sh USUARIO@45.79.193.250:~/oev/produccion/
scp .env.ejemplo USUARIO@45.79.193.250:~/oev/.env
```

En el servidor, `chmod 600 ~/oev/.env` y completar las mismas variables de
[Completar el `.env`](#2-completar-el-env), más `DOMINIO`, el nombre sin
`https://`. `ALLOWED_HOSTS`, `CSRF_ORIGINS` y `URL_BASE` llevan ese mismo
dominio. `PUERTO` no se cambia: es interno.

Después, el primer despliegue y la [carga de las áreas](#5-cargar-las-áreas).

### Desplegar

```sh
sh ~/oev/produccion/desplegar.sh <SHA completo del commit>
```

El script respalda la base en `~/oev/respaldos/` (quedan los 20 más recientes),
baja la imagen, levanta el stack y espera a que `web` lleve 20 segundos arriba
sin reiniciarse. Si no lo logra, muestra el log y termina con error. Cada
despliegue que funcionó queda anotado en `~/oev/desplegados.log`. Con compose v2
`up -d` recrea los contenedores sin el `KeyError` del servidor del curso, así que
no hace falta el `down`.

**Volver atrás** es lo mismo con el SHA anterior de `desplegados.log`. Si la
versión nueva traía migraciones, antes se restaura el respaldo:

```sh
gunzip -c respaldos/oev-AAAAMMDD-HHMMSS.sql.gz | docker compose -f docker-compose.yml -f docker-compose.produccion.yml exec -T db psql -U oev oev
```

sobre una base vacía. Las fotos del check-out no entran en ese respaldo: se
copian con `docker cp` desde el contenedor `web`, como en el servidor del curso.

### Despliegue automático

El job `desplegar` de `.github/workflows/imagen.yml` corre después de publicar
la imagen de cada push a `main`. Copia los compose y `produccion/`, así que un
cambio en ellos llega solo, y ejecuta `desplegar.sh` con el SHA del commit. Está
apagado hasta configurar en GitHub, en *Settings*:

| Dónde | Nombre | Valor |
|---|---|---|
| *Environments* > `produccion` > *Secrets* | `SSH_HOST` | `45.79.193.250` |
| | `SSH_USUARIO` | El usuario que despliega |
| | `SSH_CLAVE` | La clave privada de un par **solo para el CI** (`ssh-keygen -t ed25519 -N ''`), cuya pública está en `~/.ssh/authorized_keys` del servidor |
| | `SSH_HUELLA` | La salida de `ssh-keyscan -t ed25519 45.79.193.250`, revisada contra la huella que muestra el servidor. Sin ella el CI no confía en el servidor |
| *Secrets and variables* > *Actions* > *Variables* | `DESPLIEGUE_AUTOMATICO` | `true` |

En el environment `produccion` se puede exigir una aprobación manual antes de
cada despliegue (*Required reviewers*).

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
| `web` se reinicia en bucle y el log muestra `SystemCheckError` | `check --deploy` encontró la configuración insegura: el log dice qué (`security.W009` es la `SECRET_KEY`) | Corregir `.env` y redesplegar |
| `PermissionError` al guardar una foto del check-out | El volumen de fotos es de root, de antes de la imagen sin root | El `chown` de [Usuario del contenedor](#usuario-del-contenedor) |
| Caddy no obtiene el certificado | `DOMINIO` no resuelve a la IP del servidor, o el 80 o el 443 están cerrados | `docker compose ... logs caddy`; revisar el DNS y el firewall |
| Error 500 sin detalle en el navegador | Con `DEBUG=0` el traceback no se muestra | `docker logs grupo6_frontend` |
| 500 al enviar el login, pero la página de login carga | Falló la base: la página no la consulta, autenticar sí | Revisar que `grupo6_db` esté *healthy* y que `POSTGRES_PASSWORD` sea la del volumen |
| 400 *Bad Request* | El dominio no está en `ALLOWED_HOSTS` | Corregir `.env` y redesplegar |
| 403 *CSRF verification failed* al enviar un formulario | Falta el dominio con `https://` en `CSRF_ORIGINS` | Corregir `.env` y redesplegar |
| 502 desde el Caddy | El contenedor está caído o no coincide con la regla | `docker ps`; revisar `container_name` y `PUERTO` |
| `manifest unknown` al hacer `pull` | El workflow no terminó, el `TAG` está mal escrito o la versión ya no está entre las 15 que se conservan | Revisar *Actions* y el nombre de la etiqueta |
| `unauthorized` al hacer `pull` | El paquete de GHCR es privado | Hacerlo público en GitHub, o `docker login ghcr.io` con un token con permiso `read:packages` |
| SSH responde `Connection timed out` | Pasó en septiembre sin explicación, con el sitio funcionando | Preguntar en el Discord del curso si a otros grupos les responde el puerto 22 |
