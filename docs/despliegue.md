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
| `EMAIL_BACKEND` | Opcional. Sin él, los correos (recuperar clave) se escriben en el log del contenedor. Para enviarlos: `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Solo con el backend SMTP: servidor, usuario y clave de la cuenta que envía |
| `EMAIL_PORT`, `EMAIL_USE_TLS` | Opcionales; por defecto `587` y `1` (STARTTLS), lo que usan Gmail, Brevo y Ethereal |
| `DEFAULT_FROM_EMAIL` | Opcional. Remitente de los correos; por defecto `no-responder@uach.cl`. Con una cuenta externa tiene que ser la dirección de esa cuenta, o el correo cae en spam |
| `CSRF_ORIGINS` | Solo si el sitio pasa a servirse por HTTPS: `https://<dominio>` |
| `URL_BASE` | Dominio de los enlaces del recordatorio de US-03: `https://oev.inf.uach.cl`. Por defecto `http://localhost:8000` |

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

## Recordatorio y cancelación (US-03)

### Antes de desplegar

Esta versión trae la migración `solicitudes.0006_solicitud_recordatorio_y_cancelacion`,
que agrega a la solicitud cuándo salió su recordatorio y cuándo se canceló. Hacer el
respaldo de la base antes de bajar la imagen.

Agregar `URL_BASE` al `.env`. Sin ella, los enlaces del recordatorio apuntan a
`localhost`.

El stack suma un contenedor, `grupo6_tareas`: la misma imagen que
`grupo6_frontend`, con un bucle que manda los recordatorios cada hora. `dc pull web`
baja la imagen de los dos.

### Rutas nuevas

| Ruta | Quién entra |
|---|---|
| `/solicitar/mis-solicitudes/<id>/cancelar/` | El solicitante de esa reserva. El enlace llega en el recordatorio y en **Mis solicitudes** |

### Verificar después de desplegar

- `docker ps --filter name=grupo6` muestra `grupo6_tareas` corriendo.
- Un minuto después de levantar, `docker logs grupo6_tareas` muestra
  `recordatorios enviados: N`, y luego una línea por hora.
- Correr una vuelta a mano: `docker exec grupo6_tareas python manage.py recordar_confirmaciones`.
  Repetirla no manda nada nuevo.

## Sanciones (US-10)

### Antes de desplegar

Esta versión trae la migración `personas.0003_sancion`, que crea la tabla de
sanciones con sus tres claves foráneas a la persona: a quién se sanciona, quién
la puso y quién la levantó. Hacer el respaldo de la base antes de bajar la
imagen. No hay variables nuevas en el `.env` ni tareas programadas: la sanción
deja de regir sola al día siguiente de su término.

### Rutas nuevas

| Ruta | Quién entra |
|---|---|
| `/solicitar/mis-sanciones/` | Pestaña **Mis sanciones** del solicitante. Cuentas del grupo **Solicitante** |
| `/configuracion/sanciones/` | Pestaña **Sanciones** del administrador, para levantarlas. Rol **Administrador** (antes de US-08, `is_staff`) |
| `/admin/personas/sancion/` | Crear y acortar sanciones. Solo el superusuario |

### Verificar después de desplegar

- En `/admin/` > **Personas › Sanciones**, crear una sanción de un día para una
  cuenta de prueba.
- Entrar con esa cuenta por `/solicitante/entrar/`: en vez del formulario sale
  **No puedes solicitar por ahora**, y la franja de aviso aparece en **Mis
  solicitudes**.
- Levantarla en `/configuracion/sanciones/` con un motivo y ver que la cuenta
  vuelve a ver el formulario.

## Historial de sanciones del administrador (US-12)

### Antes de desplegar

Esta versión **no trae migraciones**: la sanción ya tenía todo lo que hace falta
(`creada_por` y `creada_en` son quién la aplicó y cuándo), y los incidentes y
las inasistencias se calculan de las tablas del check-out y de la solicitud. No
hay variables nuevas en el `.env` ni tareas programadas.

Los correos de sanción salen por el `EMAIL_BACKEND` configurado, igual que los
de resolución.

### Rutas nuevas

| Ruta | Quién entra |
|---|---|
| `/configuracion/sanciones/` | La misma de US-10, ahora con el listado de solicitantes, sus incidentes, inasistencias y sanción. Rol **Administrador** |
| `/configuracion/sanciones/<id>/` | Historial de una persona, y desde ahí aplicar y levantar. Rol **Administrador** |

### Verificar después de desplegar

- Entrar a `/configuracion/sanciones/` y ver a los solicitantes, con sus
  incidentes y la sanción vigente de quien tenga una.
- Abrir a una cuenta de prueba, sancionarla por un día y ver en
  `docker logs grupo6_frontend` el correo, si el backend es la consola.
- Entrar con esa cuenta por `/solicitante/entrar/`: sale **No puedes solicitar
  por ahora**. Levantar la sanción desde el detalle y ver que vuelve el
  formulario.

### Decisión abierta: una restricción en la base contra sanciones pisadas

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

## Áreas académicas (US-05)

### Antes de desplegar

Esta versión trae la migración `personas.0004_area_nota_y_cambios`, que agrega
la nota del área y su registro de cambios. Hacer el respaldo de la base antes de
bajar la imagen. No hay variables nuevas en el `.env`.

### Rutas nuevas

| Ruta | Quién entra |
|---|---|
| `/configuracion/areas/` | Pestaña **Áreas** del administrador. Rol **Administrador** (antes de US-08, `is_staff`) |

### Después de desplegar

Las áreas no vienen cargadas. En la pestaña **Áreas**, crear **Educación
Continua Online** y **Decanatura** (minuta del 27/10) y desactivar las que ya no
correspondan. Un solicitante sin un área activa no puede pedir la sala.

## Usuarios (US-08)

### Antes de desplegar

Esta versión trae la migración `personas.0005_cuentas_y_su_registro`, que crea el
registro de cambios de cuentas. Hacer el respaldo de la base antes de bajar la
imagen. No hay variables nuevas en el `.env`, pero las cuentas nuevas reciben su
contraseña por correo: sin SMTP configurado, el enlace queda solo en
`docker logs grupo6_frontend`.

Desde esta versión el panel del administrador lo abre el rol **Administrador**,
no solo `is_staff`. El superusuario que crea el arranque
(`DJANGO_SUPERUSER_EMAIL`) es la cuenta de soporte de la Oficina: es la única
que da y quita el rol **Administrador**.

### Rutas nuevas

| Ruta | Quién entra |
|---|---|
| `/configuracion/usuarios/` | Pestaña **Usuarios**: lista, búsqueda y filtros. Rol **Administrador** |
| `/configuracion/usuarios/nueva/`, `/configuracion/usuarios/<id>/` | Crear y editar una cuenta. Rol **Administrador** |
| `/configuracion/usuarios/cargar/` | Carga en lote desde un CSV. Rol **Administrador** |
| `/configuracion/usuarios/plantilla.csv` | Plantilla de la carga. Rol **Administrador** |

### Verificar después de desplegar

- Entrar con el superusuario por `/configuracion/entrar/` y abrir **Usuarios**.
- Crear una cuenta de prueba con el rol **Validador** y ver que le llega el
  correo (o que el enlace aparece en el log) y que entra por
  `/validacion/entrar/` después de crear su contraseña.
- Desactivarla y ver que ya no entra.

## Diagramas de la documentación

`docs/` no viaja en la imagen (`.dockerignore`), así que los diagramas no se
despliegan: se compilan en la máquina de quien los cambia y se commitean con su
fuente. Todos incluyen `docs/diagramas/estilo.iuml`, que fija la resolución, las
fuentes y el color de cada capa. Para compilarlos hacen falta PlantUML y las
fuentes **Noto Sans** y **JetBrainsMono NF** instaladas. El detalle está en
`docs/diagramas.md`, en
[Cómo se dibujan y se compilan](diagramas.md#cómo-se-dibujan-y-se-compilan).

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
