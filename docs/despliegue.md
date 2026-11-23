# Manual de despliegue

La aplicación se despliega desde la imagen que publica GitHub Actions en GHCR
(`ghcr.io/darkanthem21/oev-sala-grabacion`) en dos lugares. En el servidor del
curso se despliega a mano y en el [servidor propio](#servidor-propio) la puede
desplegar el CI. En ninguno se clona el repositorio ni se construye nada, basta
con los archivos de compose y un `.env`.

Al arrancar, el contenedor:

1. Corre `check --deploy` y **no levanta** si la configuración es insegura, por
   ejemplo con una `SECRET_KEY` corta o de ejemplo, `DEBUG=1` o cookies sin
   `Secure`. El motivo queda en el log.
2. Aplica las migraciones y crea el superusuario si no existe. No hay pasos
   manuales de base de datos.
3. Levanta gunicorn con `WEB_CONCURRENCY` workers (2 por defecto) de 4 hilos
   cada uno, para que una subida lenta de fotos no deje a un worker sin
   responder. Los estáticos los sirve whitenoise, comprimidos y con un hash en
   el nombre.

El contenedor corre con el usuario `oev` (UID 1000) en vez de root, y solo
puede escribir en `/app/media`, donde van las fotos del check-out.

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

No necesita sudo, basta con estar en el grupo `docker`. Un volumen nuevo ya
nace con el dueño correcto.

## Imágenes publicadas

| Cuándo | Etiquetas |
|---|---|
| Cada push a `main`, si pasan las pruebas | `main` y el SHA del commit |
| A mano, desde *Actions* > **imagen** > *Run workflow* sobre una rama | La rama con `/` cambiado por `-` (`feat-us-14-bloques-apoyo`) y el SHA |

El mismo workflow borra las imágenes antiguas y deja `main` y las 15 versiones
más recientes.

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
| `POSTGRES_PASSWORD` | Clave de la base. PostgreSQL la lee solo al crear el volumen; si se cambia después, la base sigue con la anterior |
| `SECRET_KEY` | Aleatoria y larga: `python3 -c 'import secrets; print(secrets.token_urlsafe(50))'`. Con una corta el contenedor no levanta |
| `DJANGO_SUPERUSER_EMAIL` | Correo de la cuenta técnica, un superusuario sin rol que entra solo a `/admin/`. Puede ser el mismo de la cuenta de soporte ([Puesta en marcha](#puesta-en-marcha)) |
| `DJANGO_SUPERUSER_PASSWORD` | Su clave. Si el usuario ya existe, no se modifica |
| `EMAIL_BACKEND` | Opcional. Sin él, los correos se escriben en el log del contenedor, también el enlace con que una cuenta nueva crea su contraseña. Para enviarlos: `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Solo con el backend SMTP. Servidor, usuario y clave de la cuenta que envía |
| `EMAIL_PORT`, `EMAIL_USE_TLS` | Opcionales; por defecto `587` y `1` (STARTTLS), lo que usan Gmail, Brevo y Ethereal |
| `DEFAULT_FROM_EMAIL` | Opcional. Remitente de los correos; por defecto `no-responder@uach.cl`. Con una cuenta externa tiene que ser la dirección de esa cuenta, o el correo cae en spam |

Compose usa el `.env` para elegir la imagen (`TAG`, `PUERTO`) y para pasarles
las variables a los contenedores.

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
código. El `down` sin `-v` conserva el volumen y sus datos.
**Nunca `dc down -v`**: borra la base.

La última línea borra la imagen que quedó sin etiqueta al bajar la nueva. Solo
toca las de este repositorio, porque el servidor es compartido y
`docker image prune` borraría también las de los otros grupos.

### 3. Verificar

```sh
docker ps --filter name=grupo6
docker logs --tail 50 grupo6_frontend
```

Tienen que estar arriba `grupo6_frontend`, `grupo6_tareas` y `grupo6_db`. El log
tiene que mostrar las migraciones aplicadas y terminar en `Booting worker with
pid`, una línea por worker. Después se entra a la URL pública y se inicia
sesión.

## Volver a una versión anterior

Se pone en `TAG` el SHA completo del commit que funcionaba y se repite el paso 2
de "Desplegar una versión". Volver a una imagen anterior **no revierte las
migraciones**. Si la versión nueva cambió la base, hay que restaurar el respaldo.

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

Es el servidor que asignó la profesora en noviembre. A diferencia del servidor
del curso, lo administramos nosotros. No hay red compartida ni proxy de otro
grupo, y el stack trae el suyo.

| Dato | Valor |
|---|---|
| Máquina | `45.79.193.250`, con Ubuntu 24.04 |
| URL | La de `DOMINIO`. Mientras `oev.inf.uach.cl` apunte al servidor del curso, `45-79-193-250.sslip.io` |
| Acceso | Usuario `despliegue` por SSH, solo con clave. Ni `root` ni las contraseñas entran |
| Carpeta de despliegue | `~/oev` de ese usuario |
| Compose | v2 (`docker compose`), proyecto `oev` fijado en `docker-compose.produccion.yml` |
| Volúmenes | `oev_pgdata`, `oev_checkoutmedia` y `oev_caddy_data` (certificados) |
| Puertos públicos | 80 y 443, de Caddy. La aplicación y la base no publican puertos |
| Memoria | Tope de 400 MB para `web` y 200 MB para `tareas`; la base y Caddy, sin tope |

Caddy (`produccion/Caddyfile`) saca y renueva el certificado de Let's Encrypt,
redirige http a https, agrega HSTS y comprime. gunicorn queda detrás, sin
recibir conexiones directas de internet. Para que Caddy obtenga el certificado,
`DOMINIO` tiene que resolver a la IP del servidor y los puertos 80 y 443 tienen
que estar abiertos. Un cambio en el `Caddyfile` se aplica en el despliegue
siguiente, porque el script recarga Caddy. Si el archivo es inválido, el script
avisa y Caddy sigue con el anterior.

### Preparación del servidor

Una máquina con Ubuntu recién instalado necesita esto antes de la primera
instalación. El servidor propio quedó así, y otra máquina se prepara con los
mismos pasos.

| Qué | Cómo quedó |
|---|---|
| Usuario | `despliegue`, con `sudo` (pide su contraseña) y en el grupo `docker` |
| SSH | Solo con clave y solo `despliegue`, en `/etc/ssh/sshd_config.d/00-oev.conf` |
| Firewall | `ufw`: lo entrante cerrado salvo `22/tcp`, `80/tcp`, `443/tcp` y `443/udp` |
| Docker | Engine y plugin de compose del repositorio oficial de Docker, no los de Ubuntu |
| Actualizaciones | Las de seguridad se instalan solas, como trae Ubuntu. El reinicio no es automático |

Primero, como `root`, se crea el usuario. Después se copia su clave pública
desde la máquina propia:

```sh
adduser despliegue && usermod -aG sudo despliegue
ssh-copy-id -i ~/.ssh/id_ed25519.pub despliegue@45.79.193.250    # en la máquina propia
```

Con la entrada por clave ya probada, como `despliegue`:

```sh
printf '%s\n' 'PermitRootLogin no' 'PasswordAuthentication no' \
  'KbdInteractiveAuthentication no' 'AllowUsers despliegue' \
  | sudo tee /etc/ssh/sshd_config.d/00-oev.conf
sudo sshd -t && sudo systemctl restart ssh

sudo ufw default deny incoming && sudo ufw default allow outgoing
sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw allow 443/udp
sudo ufw enable
```

Docker se instala con los pasos de
<https://docs.docker.com/engine/install/ubuntu/> (`docker-ce`, `docker-ce-cli`,
`containerd.io` y `docker-compose-plugin`), y después
`sudo usermod -aG docker despliegue`.

- El archivo de sshd empieza con `00-` porque sshd se queda con el primer valor
  que lee de cada opción. Después de cambiarlo, y antes de cerrar la sesión
  abierta, se prueba desde otra terminal que se sigue entrando.
- Los puertos que publica Docker no pasan por `ufw`. Lo que deja a la base y a
  gunicorn fuera de internet es que el compose no les publica puertos.
- El grupo `docker` equivale a `root` en la máquina. Vale recién desde la
  sesión siguiente, y en la que ya estaba abierta `docker` responde
  `permission denied`.
- Cuando una actualización pide reiniciar existe `/var/run/reboot-required`. Se
  reinicia con `sudo reboot` y los contenedores vuelven solos
  (`restart: unless-stopped`).

**La clave autorizada es una sola, la del grupo.** Es un par creado para este
servidor, que comparten los integrantes en vez de usar cada uno su clave
personal. Para quitarle el acceso a alguien hay que cambiarla para todos. Se
autoriza una nueva y se borra la anterior de `~/.ssh/authorized_keys`. Otra
clave, por ejemplo la de quien reciba el sistema, se agrega así:

```sh
ssh despliegue@45.79.193.250 'cat >> ~/.ssh/authorized_keys' < clave-nueva.pub
```

Para desplegar basta la clave. La contraseña de `despliegue` solo la pide
`sudo`, en tareas de administración de la máquina.

### Primera instalación

Requiere el servidor preparado como arriba. Desde la raíz del repositorio:

```sh
ssh despliegue@45.79.193.250 'mkdir -p ~/oev/produccion'
scp docker-compose.yml docker-compose.produccion.yml despliegue@45.79.193.250:~/oev/
scp produccion/* despliegue@45.79.193.250:~/oev/produccion/
scp .env.ejemplo despliegue@45.79.193.250:~/oev/.env
```

En el servidor, `chmod 600 ~/oev/.env` y completar las mismas variables de
[Completar el `.env`](#2-completar-el-env), más `DOMINIO`, el nombre sin
`https://`. `ALLOWED_HOSTS`, `CSRF_ORIGINS` y `URL_BASE` llevan ese mismo
dominio. `PUERTO` queda igual, porque es interno. Compose v2 interpreta el `$`
dentro del `.env`. Por eso `POSTGRES_PASSWORD` se genera con el mismo comando
que `SECRET_KEY`, que no produce ese carácter.

Después, el primer [despliegue](#desplegar) y la
[puesta en marcha](#puesta-en-marcha).

### Puesta en marcha

Después del primer despliegue hay una sola cuenta, la **cuenta técnica**, que
el contenedor crea al arrancar con `DJANGO_SUPERUSER_EMAIL` y
`DJANGO_SUPERUSER_PASSWORD` del `.env`. Es un superusuario sin rol y no ve el
panel del sistema.

1. Crear la **cuenta de soporte** de la Oficina, un superusuario con el rol
   Administrador:

   ```sh
   docker compose -f docker-compose.yml -f docker-compose.produccion.yml exec web python manage.py crear_administrador CORREO
   ```

   Si el correo es nuevo, crea la cuenta y le manda el enlace para crear la
   contraseña. Si la cuenta ya existe, por ejemplo la técnica, le agrega el rol
   y deja la contraseña como estaba. Se puede correr más de una vez.
2. Entrar con la cuenta de soporte por `/configuracion/entrar/`.
3. Crear las áreas, como en [Cargar las áreas](#5-cargar-las-áreas).
4. Crear las cuentas en la pestaña **Usuarios**, partiendo por los
   administradores, porque ese rol solo lo da la cuenta de soporte.
5. Cada cuenta nueva crea su contraseña con el enlace que le llega por correo.
   Sin correo configurado el enlace no llega: ver [Correo](#correo).

El resto (jornada, reglas, listado de check-out) viene con valores por defecto
y se ajusta desde el panel; el detalle está en el
[manual de uso](uso.md#primeros-pasos-en-un-sistema-recién-instalado).

Sobre la cuenta técnica:

- Las dos variables del `.env` se leen solo si la cuenta no existe. Cambiarlas
  después no cambia el correo ni la contraseña de la cuenta.
- Su contraseña se cambia con **¿Olvidaste tu contraseña?**, o sin correo:

  ```sh
  docker compose -f docker-compose.yml -f docker-compose.produccion.yml exec web python manage.py changepassword CORREO
  ```

- Entra solo al panel de Django, por `/soporte/entrar/`. Esa puerta deja pasar
  a las cuentas `is_staff` y bloquea por intentos fallidos como las demás.
  `/admin/` no tiene formulario de ingreso propio y manda ahí. Para qué sirve
  ese panel está en el [manual de uso](uso.md#superusuario-y-panel-de-django).

### Correo

Sin `EMAIL_BACKEND` en el `.env` no sale ningún correo. La bienvenida con el
enlace para crear la contraseña, la recuperación de contraseña y los
recordatorios de confirmación se escriben en el log del contenedor que los
genera (`web` o `tareas`).

Mientras tanto, el enlace de cada cuenta se saca del log, en `~/oev`:

```sh
alias dc='docker compose -f docker-compose.yml -f docker-compose.produccion.yml'
dc logs --no-log-prefix web | grep -E '^To: |/clave/'
```

Sale el destinatario y, debajo, su enlace. El enlace sirve tres días y una sola
vez. Si una cuenta aparece más de una vez, vale el último. Con el enlace
cualquiera puede crear la contraseña de esa cuenta, y por eso no se pega en
canales abiertos. Si venció, el botón **Reenviar el correo de la contraseña**
de la ficha de la cuenta escribe otro en el log.

Para enviar de verdad se agregan al `.env` las variables `EMAIL_*` de
[Completar el `.env`](#2-completar-el-env) y se recrean los contenedores:

```sh
dc up -d
dc exec web python manage.py sendtestemail CORREO_PROPIO
```

La segunda línea manda un correo de prueba. Si el envío falla, el error sale en
la terminal.

### Operación

En el servidor, en `~/oev`:

```sh
alias dc='docker compose -f docker-compose.yml -f docker-compose.produccion.yml'
dc ps                         # web y db tienen que decir (healthy)
dc logs --tail 100 web        # accesos y errores de la aplicación
dc logs --tail 20 tareas      # una línea por hora: recordatorios enviados
dc logs --tail 50 caddy       # certificado y proxy
docker stats --no-stream      # memoria de cada contenedor contra su tope
dc restart web                # reiniciar sin cambiar de versión
dc exec web python manage.py shell
```

Cada acceso del log de `web` trae la dirección de Caddy, que es quien se
conecta, y la del navegador, que Caddy le informa. **Nunca `dc down -v`**: borra
la base, las fotos y los certificados.

### Cambiar de dominio

Cuando `oev.inf.uach.cl` apunte a esta máquina, se cambian en el `.env` las
cuatro variables que llevan el dominio (`DOMINIO`, `ALLOWED_HOSTS`,
`CSRF_ORIGINS` y `URL_BASE`) y se corre `dc up -d`. Caddy pide el certificado
del dominio nuevo al arrancar, y para obtenerlo el DNS ya tiene que resolver a
`45.79.193.250`.

### Probar el check-out en una instalación nueva

El check-out de un bloque se habilita cuando el bloque ya terminó, y la fecha
más cercana que se puede pedir es un lunes futuro. En una instalación nueva no
hay, entonces, nada que cerrar. Para probarlo sin esperar se pide una reserva,
se acepta como validador y se mueve a la misma hora de una semana pasada:

```sh
dc exec -T web python manage.py shell -c '
from datetime import timedelta
from django.utils import timezone
from solicitudes.models import Solicitud
s = Solicitud.objects.filter(estado_validacion="ACEPTADA").latest("pk")
f = s.fecha
while f >= timezone.localdate(): f -= timedelta(weeks=1)
Solicitud.objects.filter(pk=s.pk).update(fecha=f, estado_confirmacion="CONFIRMADA")
print("solicitud", s.pk, "movida al", f)
'
```

El bloque aparece en `/apoyo/?fecha=AAAA-MM-DD` con el check-out pendiente.
**Solo con datos de prueba.** Cambia la última solicitud aceptada sin pasar por
las reglas del sistema.

### Desplegar

```sh
sh ~/oev/produccion/desplegar.sh <SHA completo del commit>
```

El script hace primero el [respaldo](#respaldos) de la base y las fotos.
Después baja la imagen, levanta el stack y espera a que `web` esté sano. Su
healthcheck pide la página de ingreso, que solo responde si la configuración
pasó la revisión, las migraciones se aplicaron y gunicorn arrancó. Cada
despliegue que funcionó queda anotado en `~/oev/desplegados.log` y en el `TAG`
del `.env`, para que un `docker compose up -d` a mano levante esa misma versión.
Con compose v2, `up -d` recrea los contenedores sin el `KeyError` del servidor
del curso y no hace falta el `down`.

Si la versión no levanta, el script muestra el log, **vuelve solo a la última
versión de `desplegados.log`** y termina con error. Las migraciones que haya
alcanzado a aplicar la versión fallida no se revierten.

### Respaldos

`produccion/respaldar.sh` deja en `~/oev/respaldos/`, legible solo para el
usuario que despliega:

- `oev-AAAAMMDD-HHMMSS.sql.gz`: la base. Quedan los 30 más recientes.
- `fotos.tar`: las fotos del check-out, que no entran en el respaldo de la
  base. Una sola copia, porque una foto no cambia después de subida.

Lo corre `desplegar.sh` antes de cada despliegue. Para que corra también todos
los días, se agrega al cron del usuario que despliega (`crontab -e`):

```
15 3 * * * sh $HOME/oev/produccion/respaldar.sh >> $HOME/oev/respaldos/cron.log 2>&1
```

Esos respaldos están en el mismo disco que los datos. Sirven si una migración
sale mal o se borra un volumen, pero se pierden con el servidor. Por eso hay que
copiarlos cada cierto tiempo a otra máquina:

```sh
rsync -a despliegue@45.79.193.250:oev/respaldos/ respaldos-oev/
```

### Volver atrás

Si la versión nueva no aplicó migraciones, basta desplegar la anterior con su
SHA, que está en `~/oev/desplegados.log`:

```sh
sh ~/oev/produccion/desplegar.sh <SHA anterior>
```

El servidor guarda las 5 imágenes más recientes, y esas se pueden desplegar
aunque GHCR ya las haya borrado.

Si entre las dos versiones cambiaron los `docker-compose*.yml` o `produccion/`,
antes se copian los del commit al que se vuelve, con `git switch --detach <SHA>`
en la máquina propia y el `scp` de la primera instalación, sin el `.env`.

Si la versión nueva aplicó migraciones, la imagen anterior no conoce esa base.
Hay que restaurar también el respaldo que el script hizo justo antes de
desplegarla. **Se pierde lo ingresado desde ese respaldo.**

```sh
cd ~/oev
alias dc='docker compose -f docker-compose.yml -f docker-compose.produccion.yml'
dc stop web tareas
dc exec -T db dropdb -U oev oev
dc exec -T db createdb -U oev oev
gunzip -c respaldos/oev-AAAAMMDD-HHMMSS.sql.gz | dc exec -T db psql -U oev -q -v ON_ERROR_STOP=1 oev
sh produccion/desplegar.sh <SHA anterior>
```

Las fotos no hace falta restaurarlas para volver atrás, porque las migraciones
no tocan los archivos. Si se perdió el volumen, se recuperan de `fotos.tar` con
el stack arriba:

```sh
docker cp -a - "$(dc ps -aq web)":/app < respaldos/fotos.tar
```

### Despliegue automático

El job `desplegar` de `.github/workflows/imagen.yml` corre después de publicar
la imagen de cada push a `main`. Copia los compose y `produccion/` al servidor y
ejecuta `desplegar.sh` con el SHA del commit. Los cambios en esos archivos
también llegan solos. Está apagado hasta configurar en GitHub, en *Settings*:

| Dónde | Nombre | Valor |
|---|---|---|
| *Environments* > `produccion` > *Secrets* | `SSH_HOST` | `45.79.193.250` |
| | `SSH_USUARIO` | El usuario que despliega |
| | `SSH_CLAVE` | La clave privada de un par **solo para el CI** (`ssh-keygen -t ed25519 -N ''`), cuya pública está en `~/.ssh/authorized_keys` del servidor |
| | `SSH_HUELLA` | La salida de `ssh-keyscan -t ed25519 45.79.193.250`, revisada contra la huella que muestra el servidor. Sin ella el CI no confía en el servidor |
| *Secrets and variables* > *Actions* > *Variables* | `DESPLIEGUE_AUTOMATICO` | `true` |

En el environment `produccion`, en *Deployment branches and tags*, se elige
*Selected branches and tags* y se deja solo `main`. Sin eso, cualquiera con
permiso de escritura puede subir una rama cuyo workflow use ese environment y
leer la clave. Ahí mismo se puede exigir una aprobación manual antes de cada
despliegue (*Required reviewers*).

## Diagramas de la documentación

`docs/` no viaja en la imagen (`.dockerignore`). Los diagramas se compilan en
la máquina de quien los cambia y se commitean junto a su fuente. Todos incluyen
`docs/diagramas/estilo.iuml`, que fija la resolución, las fuentes y el color de
cada capa. Para compilarlos hacen falta PlantUML y las fuentes **Noto Sans** y
**JetBrainsMono NF** instaladas. El detalle está en `docs/diagramas.md`, en
[Cómo se dibujan y se compilan](diagramas.md#cómo-se-dibujan-y-se-compilan).

## Decisión abierta: una restricción en la base contra sanciones pisadas

Hoy la regla de que dos sanciones no levantadas no se pisen la revisan
`Sancion.clean()` y `personas.services.aplicar`, que bloquea la fila de la
persona mientras revisa. Lo que no pasa por ahí (el shell, un `UPDATE` a mano)
no la cumple. PostgreSQL podría exigirla siempre con una `ExclusionConstraint`
sobre `daterange(inicio, termino, '[]')` y `usuario_id`, con
`levantada_en IS NULL`. No se agregó porque:

- Necesita la extensión `btree_gist`, que la migración crearía con
  `CreateExtension`. Desde PostgreSQL 13 es una extensión *trusted*, que puede
  crear el dueño de la base. En este servidor alcanzaría, porque el usuario
  `oev` es el `POSTGRES_USER` de la imagen y es superusuario. En otro servidor,
  con un usuario sin privilegio `CREATE` sobre la base, la migración falla y
  alguien con permisos tiene que correr antes `CREATE EXTENSION btree_gist;`.
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
| `web` se reinicia en bucle y el log muestra `SystemCheckError` | `check --deploy` encontró la configuración insegura. El log dice qué falló (`security.W009` es la `SECRET_KEY`) | Corregir `.env` y redesplegar |
| `PermissionError` al guardar una foto del check-out | El volumen de fotos es de root, de antes de la imagen sin root | El `chown` de [Usuario del contenedor](#usuario-del-contenedor) |
| Caddy no obtiene el certificado | `DOMINIO` no resuelve a la IP del servidor, o el 80 o el 443 están cerrados | `docker compose ... logs caddy`; revisar el DNS y el firewall |
| 413 al enviar un check-out | El formulario pasa de los 50 MB que acepta Caddy en el servidor propio | Subir fotos más livianas, o subir `max_size` en `produccion/Caddyfile` |
| Error 500 sin detalle en el navegador | Con `DEBUG=0` el traceback no se muestra | `docker logs grupo6_frontend`; en el servidor propio, `dc logs web` |
| Una cuenta nueva no recibe el correo para crear su contraseña | No hay SMTP configurado y el correo se escribió en el log | [Correo](#correo) |
| `permission denied` al conectar con `docker.sock` en el servidor propio | La sesión se abrió antes de agregar el usuario al grupo `docker` | Salir y volver a entrar |
| 500 al enviar el login, pero la página de login carga | Falló la base. La página de login no la consulta, pero autenticar sí | Revisar que `grupo6_db` esté *healthy* y que `POSTGRES_PASSWORD` sea la del volumen |
| 400 *Bad Request* | El dominio no está en `ALLOWED_HOSTS` | Corregir `.env` y redesplegar |
| 403 *CSRF verification failed* al enviar un formulario | Falta el dominio con `https://` en `CSRF_ORIGINS` | Corregir `.env` y redesplegar |
| 502 desde el Caddy | El contenedor está caído o no coincide con la regla | `docker ps`; revisar `container_name` y `PUERTO` |
| `manifest unknown` al hacer `pull` | El workflow no terminó, el `TAG` está mal escrito o la versión ya no está entre las 15 que se conservan | Revisar *Actions* y el nombre de la etiqueta |
| `unauthorized` al hacer `pull` | El paquete de GHCR es privado | Hacerlo público en GitHub, o `docker login ghcr.io` con un token con permiso `read:packages` |
| SSH responde `Connection timed out` | Pasó en septiembre sin explicación, con el sitio funcionando | Preguntar en el Discord del curso si a otros grupos les responde el puerto 22 |
