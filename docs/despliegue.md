# Manual de despliegue

La aplicación se despliega en el servidor del curso desde la imagen que publica
GitHub Actions en GHCR (`ghcr.io/darkanthem21/oev-sala-grabacion`). En el
servidor no se clona el repositorio ni se construye nada: solo se necesitan dos
archivos de compose y un `.env`.

Al arrancar, el contenedor aplica las migraciones y crea el superusuario si no
existe. No hay pasos manuales de base de datos.

El check-out configurable añade la migración `uso/0001_initial` y requiere Pillow
(incluido en `requirements.txt`). Fuera de Docker, instalar las dependencias y
ejecutar `python src/manage.py migrate` antes de iniciar la aplicación.
Las fotos se guardan en `MEDIA_ROOT` (por defecto `src/media`); Docker monta el
volumen `checkoutmedia` en `/app/media` para conservarlas al recrear el contenedor.
Respaldar ese volumen junto con la base. No se necesita publicar una ruta de medios:
Django entrega las evidencias mediante una vista con control de acceso.

## Servidor del curso

| Dato | Valor |
|---|---|
| Máquina | `146.83.216.166`, usuario `grupo6` por SSH |
| URL pública | <http://grupo6.146.83.216.166.nip.io> |
| Carpeta de despliegue | `~/oev` |
| Contenedor de la aplicación | `grupo6_frontend`, puerto interno `3006` |
| Contenedor de la base | `grupo6_db` |
| Volumen de datos | `grupo6_pgdata` |
| Red | `red_taller_software`, compartida por todos los grupos |

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
| `TAG` | Qué imagen desplegar: `main`, una rama con `/` cambiado por `-` (`feat-us-14-bloques-apoyo`) o el SHA completo de un commit |
| `PUERTO` | `3006`. Tiene que coincidir con la regla del Caddy |
| `ALLOWED_HOSTS` | `grupo6.146.83.216.166.nip.io` |
| `POSTGRES_PASSWORD` | Clave de la base. PostgreSQL la lee solo al crear el volumen: cambiarla después no cambia la de la base |
| `SECRET_KEY` | Aleatoria y larga: `python3 -c 'import secrets; print(secrets.token_urlsafe(50))'` |
| `DJANGO_SUPERUSER_EMAIL` | Correo del administrador inicial |
| `DJANGO_SUPERUSER_PASSWORD` | Su clave. Si el usuario ya existe, no se modifica |
| `EMAIL_BACKEND` | Opcional. Sin él, los correos (recuperar clave) se escriben en el log del contenedor |
| `DEFAULT_FROM_EMAIL` | Opcional. Remitente de los correos; por defecto `no-responder@uach.cl` |
| `CSRF_ORIGINS` | Solo si el sitio pasa a servirse por HTTPS: `https://<dominio>` |

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

## Desplegar una versión

### 1. Esperar la imagen

Después del push, esperar a que termine el workflow `imagen` en la pestaña
*Actions* de GitHub. Hasta que termine, la imagen nueva no existe.

Si el push cambió `docker-compose.yml` o `docker-compose.servidor.yml`, repetir
antes el `scp` del paso 1 de la primera instalación, sin el `.env`.

### 2. Bajar la imagen y reiniciar

En el servidor, poner en `TAG` la versión que se quiere desplegar y ejecutar:

```sh
cd ~/oev
dc pull web
dc down
dc up -d
```

**Siempre `down` y después `up -d`, nunca `up -d` directamente.** El
`docker-compose` 1.29.2 falla al recrear un contenedor con
`KeyError: 'ContainerConfig'`, porque lee un campo que las imágenes construidas
por el workflow ya no traen. Crear los contenedores de cero no pasa por ese
código. El `down` sin `-v` no borra el volumen: los datos se conservan.
**Nunca `dc down -v`**: borra la base.

### 3. Verificar

```sh
docker ps --filter name=grupo6
docker logs --tail 50 grupo6_frontend
```

El log tiene que mostrar las migraciones aplicadas y terminar en
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
```

Para restaurar, sobre una base vacía:

```sh
docker exec -i grupo6_db psql -U oev oev < respaldo-AAAA-MM-DD.sql
```

## Solicitudes y panel del validador (US-02 y US-07)

### Antes de desplegar

Esta versión trae la migración de `solicitudes`, que crea las tablas de la
solicitud, sus bloques y sus acompañantes. Hacer el respaldo de la base (ver
[Respaldo de la base](#respaldo-de-la-base)) antes de bajar la imagen.

No hay variables nuevas en el `.env`. El texto de los términos y condiciones se
edita en el panel de administración, en **Reglas**, y no por entorno.

### Rutas nuevas

| Ruta | Quién entra |
|---|---|
| `/solicitar/` | Formulario de solicitud. Cuentas del grupo **Solicitante** con al menos un área activa |
| `/validacion/entrar/` | Puerta de los validadores |
| `/validador/` | Panel del validador. Cuentas del grupo **Validador** |

El grupo y las áreas de cada cuenta se asignan en `/admin/` > **Usuarios**.

### Verificar después de desplegar

- Entrar por `/solicitante/entrar/` con una cuenta que tenga área y ver el paso
  1 del formulario en `/solicitar/`.
- Entrar por `/validacion/entrar/` con una cuenta validadora y ver en
  `/validador/` las solicitudes pendientes reales.

## Validación conectada a la base (US-07)

### Antes de desplegar

Esta versión trae la migración `solicitudes.0004_solicitud_resolucion`, que
agrega a la solicitud quién la resolvió, cuándo y con qué motivo. Hacer el
respaldo de la base (ver [Respaldo de la base](#respaldo-de-la-base)) antes de
bajar la imagen.

No hay variables nuevas en el `.env`. Los correos de resolución salen por el
`EMAIL_BACKEND` configurado, igual que los avisos de bloqueo.

### Rutas nuevas

| Ruta | Quién entra |
|---|---|
| `/configuracion/validacion/` | Pestaña **Validación** del administrador. Cuentas con `is_staff` |
| `/validador/resolver/` | Lo llama el panel al aprobar o rechazar. Validadores y cuentas con `is_staff` |

### Verificar después de desplegar

- Aprobar o rechazar una solicitud en `/validador/`, recargar y ver que quedó
  resuelta.
- Entrar como el solicitante y ver el estado y el motivo en **Mis solicitudes**.
- `docker logs grupo6_frontend` muestra el correo de la resolución si el
  backend de correo es la consola.

## Problemas conocidos

| Síntoma | Causa | Solución |
|---|---|---|
| `KeyError: 'ContainerConfig'` al hacer `up -d` | Compose 1.29.2 intentó recrear un contenedor | `dc down` y después `dc up -d` |
| Error 500 sin detalle en el navegador | Con `DEBUG=0` el traceback no se muestra | `docker logs grupo6_frontend` |
| 500 al enviar el login, pero la página de login carga | Falló la base: la página no la consulta, autenticar sí | Revisar que `grupo6_db` esté *healthy* y que `POSTGRES_PASSWORD` sea la del volumen |
| 400 *Bad Request* | El dominio no está en `ALLOWED_HOSTS` | Corregir `.env` y redesplegar |
| 502 desde el Caddy | El contenedor está caído o no coincide con la regla | `docker ps`; revisar `container_name` y `PUERTO` |
| `manifest unknown` al hacer `pull` | El workflow no terminó o el `TAG` está mal escrito | Revisar *Actions* y el nombre de la etiqueta |
| `unauthorized` al hacer `pull` | El paquete de GHCR es privado | Hacerlo público en GitHub, o `docker login ghcr.io` con un token con permiso `read:packages` |
| SSH responde `Connection timed out` | Pasó en septiembre sin explicación, con el sitio funcionando | Preguntar en el Discord del curso si a otros grupos les responde el puerto 22 |
