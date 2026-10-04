# Manual de uso

Sistema de gestión de horarios y uso de la sala de grabación de la Facultad de Ciencias de la Ingeniería, UACh.

Este manual cubre lo que hoy está disponible en el sistema:

| Historia | Quién la usa | Sección |
|---|---|---|
| US-01 Inicio de sesión | Todos | [Iniciar sesión](#1-iniciar-sesión) |
| US-04 Panel de administrador | Administrador | [Configurar la sala](#2-configurar-la-sala) |
| US-14 Bloques del personal de apoyo | Personal de apoyo | [Bloques del día](#3-bloques-del-día) |
| US-07 Panel del validador | Validador | [Panel del validador](#5-panel-del-validador) |

## Puertas de acceso

Cada rol entra por su propia dirección. Solo la del solicitante está enlazada
desde el sitio; las otras dos las conoce quien las usa.

| Rol | Dirección |
|---|---|
| Solicitante | `/solicitante/entrar/` |
| Administrador | `/configuracion/entrar/` |
| Validador | `/validacion/entrar/` |
| Personal de apoyo | `/apoyo/entrar/` |

---

## 1. Iniciar sesión

### Entrar

1. Abre la dirección de tu rol.
2. Escribe tu correo institucional y tu contraseña. Marca **Ver contraseña** si
   quieres revisar lo que escribiste.
3. Pulsa **Iniciar sesión**. El sistema te lleva al panel de esa puerta. Si
   tienes más de un rol, la puerta por la que entras decide a qué panel llegas.

![Pantalla de inicio de sesión](uso/us-01/ingreso.jpg)

### Si no puedes entrar

Si el correo o la contraseña no coinciden, aparece el aviso **Correo o
contraseña incorrectos.** y el correo queda escrito para que no tengas que
repetirlo.

![Aviso de credenciales incorrectas](uso/us-01/ingreso-error.jpg)

El aviso es el mismo cuando el correo no existe o cuando la cuenta no tiene el
rol de esa puerta. Así nadie puede usar la pantalla para averiguar qué cuentas
existen.

Después de varios intentos fallidos seguidos, la cuenta se bloquea por unos
minutos y la pantalla indica cuánto falta. Cuántos intentos y cuántos minutos lo
decide el administrador (ver [Reglas](#reglas-los-parámetros-del-sistema)).

### Recuperar la contraseña

1. En la pantalla de ingreso, pulsa **¿Olvidaste tu contraseña?**.
2. Escribe tu correo y pulsa **Enviar enlace**.
3. Abre el enlace que llega a tu correo, escribe la contraseña nueva dos veces y
   pulsa **Guardar**.
4. Con el mensaje **Listo**, vuelve a iniciar sesión con la contraseña nueva.

![Recuperar contraseña](uso/us-01/recuperar-clave.png)

El enlace sirve una sola vez y vence en unas horas. Si ya no funciona, la
pantalla ofrece **Pedir otro enlace**.

---

## 2. Configurar la sala

El panel del administrador tiene tres pestañas: **Bloques**, **Áreas** y
**Reglas**. Se entra por `/configuracion/entrar/`.

![Puerta de la administración](uso/us-04/puerta-administracion.png)

### Bloques: la jornada semanal

Un bloque es un tramo horario de un día de la semana, por ejemplo *lunes de
08:10 a 09:40*. La jornada se define una vez y se repite todas las semanas.

![Jornada semanal](uso/us-04/bloques-semana.png)

**Agregar un bloque**

1. En la vista **Semanal**, haz clic en un hueco de la columna del día o pulsa
   **+** junto al nombre del día.
2. Ajusta **Inicio** y **Término** en el editor de abajo. La **Duración** se
   calcula sola.
3. Pulsa **Agregar el bloque**.

**Editar o quitar un bloque**

1. Haz clic sobre el bloque. Queda marcado y se abre el editor.
2. Cambia las horas y pulsa **Guardar el bloque**, o pulsa **Quitar de la
   jornada**. **Cancelar** cierra el editor sin cambios.

![Editar un bloque](uso/us-04/bloques-editar.png)

Si el bloque se cruza con otro del mismo día, no se guarda: aparece un aviso y
el otro bloque queda marcado. Quitar un bloque no pide confirmación; en su lugar
aparece **Reponerlo**, por si fue un error. Un bloque quitado nunca se borra,
así que las solicitudes que ya lo apuntan siguen siendo válidas.

**Vista mensual**

La vista **Mensual** muestra el mes completo, con cuántos bloques y horas tiene
cada día de la semana. Sirve para revisar, no para editar. Con **←**, **Hoy** y
**→** te mueves entre meses.

![Vista mensual](uso/us-04/bloques-mes.png)

### Áreas

La pestaña **Áreas** todavía no tiene contenido. Llega con US-05.

### Reglas: los parámetros del sistema

Aquí se ajustan los umbrales con los que opera el sistema, sin reinstalar nada.
Cada fila explica qué hace el sistema con ese valor.

![Parámetros del sistema](uso/us-04/reglas.png)

| Grupo | Parámetros |
|---|---|
| Recepción de solicitudes | Día y hora límite para pedir la semana siguiente, desfase mínimo en semanas |
| Reserva | Días de anticipación para confirmar, tope mensual por persona, bloques por solicitud |
| Cierre y sanciones | Inasistencias para sancionar, duración de la sanción |
| Acceso | Intentos antes de bloquear una cuenta, duración del bloqueo |
| Términos y condiciones | El texto que acepta el solicitante al enviar una solicitud |

Para cambiar valores:

1. Modifica los que necesites.
2. Pulsa **Guardar cambios**.

Si un valor está fuera de su rango permitido, la fila se marca y no se guarda
nada. Los cambios rigen para las solicitudes nuevas; las que ya se enviaron no
cambian.

Al final de la página, **Últimos cambios** muestra quién cambió cada parámetro,
cuándo y de qué valor a cuál.

---

## 3. Bloques del día

La vista del personal de apoyo muestra las reservas de la sala para un día. Se
entra por `/apoyo/entrar/`.

![Puerta del personal de apoyo](uso/us-14/puerta-apoyo.png)

### Dar el rol a alguien

El rol se asigna desde `/admin` con la cuenta de administrador: en **Usuarios**,
abre la cuenta de la persona, agrégale el grupo **Personal de apoyo** y guarda.
Una persona puede tener más de un rol a la vez.

### Leer la lista

Al entrar se ven las reservas de hoy, ordenadas por hora de inicio.

![Bloques del día](uso/us-14/bloques-del-dia.png)

| Columna | Qué indica |
|---|---|
| Hora | Inicio y término del bloque |
| Solicitante | Quién pidió la sala |
| Área | El área académica de la reserva |
| Personas | Cuántas personas declaró el solicitante |
| Estado | **Aprobada** o **Confirmada**. Una **Cancelada** aparece tachada: ya no hay que esperar a nadie |
| Check-out | **Completado** si ya se registró, **Hacer check-out** si el bloque terminó y falta, o **—** si el bloque aún no termina o se canceló |

Las reservas pendientes de aprobación no aparecen, porque todavía pueden
rechazarse. Todo el personal de apoyo ve todos los bloques; no se asignan a una
persona en particular.

### Cambiar de día

Usa **‹** y **›** para ir al día anterior o al siguiente, **Hoy** para volver al
día actual, o el selector de fecha para saltar a cualquier día.

### Hacer el check-out

El botón **Hacer check-out** aparece recién cuando termina el bloque.

1. Pulsa **Hacer check-out** en la fila del bloque.
2. Revisa los datos del bloque y pulsa **Registrar check-out (simulado)**.
3. El sistema vuelve a la lista y el bloque aparece como **Completado**.

![Check-out pendiente](uso/us-14/checkout-pendiente.png)

Un check-out completado no se puede enviar de nuevo. Al pulsar **Completado**
se ve quién lo registró y cuándo.

![Check-out completado](uso/us-14/checkout-completado.png)

> **Estado actual.** Mientras no existan las solicitudes en la base de datos,
> esta vista muestra reservas de prueba y lo avisa con una franja arriba de la
> tabla. El formulario de check-out con el checklist de la sala llega con US-15;
> hasta entonces el registro es simulado y solo lo ve quien lo envió.

---

## 5. Panel del validador

Aquí el validador revisa las solicitudes pendientes y aprueba o rechaza cada
bloque pedido. Se entra por `/validacion/entrar/` y el panel está en
`/validador/`.

> **Estado actual.** El panel funciona con datos de prueba: los lee de
> `src/solicitudes/datos_prueba/panel_validador.json`, no de la base de datos.
> Aprobar y rechazar solo cambian lo que se ve en pantalla: no se guarda nada, y
> al recargar todo vuelve a pendiente. Un recuadro naranja arriba del panel lo
> recuerda.

### Dar el rol a alguien

El rol se asigna desde `/admin` con la cuenta de administrador: en **Usuarios**,
abre la cuenta de la persona, agrégale el grupo **Validador** y guarda.

### Leer el panel

![Panel del validador](uso/us-07/panel-con-tope.png)

**Bloques de la semana**, en la columna izquierda, es un calendario de lunes a
viernes con los bloques de la jornada:

| Casilla | Qué indica |
|---|---|
| Vacía | Libre |
| Borde gris con un número | Una solicitud pendiente |
| Borde rojo con un número | Tope: varias solicitudes piden ese bloque. El número dice cuántas |
| Verde | Aprobado, con el número de la solicitud |

Al hacer clic en una casilla, el panel baja a la solicitud o al tope
correspondiente.

Arriba a la derecha, el resumen dice cuántos bloques quedan **pendientes**,
cuántos tienen **tope** y cuántos están **resueltos**.

Cada tarjeta tiene además un mini calendario con sus bloques: borde azul es un
pedido pendiente, borde rojo con número es un tope, verde es aprobado y rayado
es rechazado.

### Con tope

Agrupa los bloques que piden dos o más solicitudes en la misma fecha y hora.
Esos bloques se resuelven solo aquí.

Cada tarjeta muestra el bloque, las solicitudes que lo piden, ordenadas por
prioridad del área (P1 primero), y una sugerencia según esa prioridad. De cada
solicitud se ve el encargado, el área, el motivo y las personas, y si pide otros
bloques también se indica.

Para resolver un tope:

1. Escribe el **Motivo de la resolución** (mínimo 10 caracteres). Es el motivo
   que recibe quien no obtiene el bloque.
2. Pulsa **Aprobar esta** en la solicitud elegida. Las demás quedan rechazadas
   solo en ese bloque; sus otros bloques siguen pendientes.
3. También puedes **Rechazar** una solicitud en particular, con el mismo
   motivo. Si en el bloque queda una sola, pasa a **Sin tope**.

Si pulsas **Aprobar esta** o **Rechazar** sin motivo, la tarjeta lo avisa y
deja el cursor en el campo.

![Aviso de motivo faltante](uso/us-07/tope-falta-motivo.png)

![Motivo escrito antes de aprobar](uso/us-07/tope-motivo-escrito.png)

Al aprobar, la casilla del calendario queda verde con el número de la solicitud
y el tope sale de la lista.

![Tope resuelto](uso/us-07/tope-aprobado.png)

### Sin tope

Muestra una tarjeta por solicitud con bloques que nadie más pide: encargado,
área, motivo, observaciones, personas y acompañantes, fecha de envío y su mini
calendario.

![Solicitudes sin tope](uso/us-07/panel-sin-tope.png)

Cada bloque se resuelve por separado:

- **Aprobar**: se aprueba de inmediato.
- **Rechazar**: pide escribir el motivo (mínimo 10 caracteres) y luego
  **Confirmar**.

Si la solicitud también tiene un bloque con tope, ese bloque aparece como
**Tope con #…** junto a **Ir al tope**, y no se resuelve aquí. Según cómo se
resuelvan sus bloques, la solicitud queda **Aprobada**, **Rechazada** o
**Aprobada en parte**.

### Resueltas

Un registro de cada resolución: bloque, solicitud, resultado, motivo, validador
y hora.

![Registro de resoluciones](uso/us-07/resueltas.png)
