# Manual de uso

Sistema de gestión de horarios y uso de la sala de grabación de la Facultad de Ciencias de la Ingeniería, UACh.

Este manual cubre lo que hoy está disponible en el sistema, ordenado por rol:

| Historia | Quién la usa | Sección |
|---|---|---|
| US-01 Inicio de sesión | Todos | [Iniciar sesión](#1-iniciar-sesión) |
| US-02 Solicitud de reserva | Solicitante | [Solicitar una reserva](#solicitar-una-reserva) |
| US-09 Historial de solicitudes | Solicitante | [Mis solicitudes](#mis-solicitudes) |
| US-03 Confirmar la asistencia | Solicitante | [Confirmar la asistencia](#confirmar-la-asistencia) |
| US-10 Historial de sanciones | Solicitante y administrador | [Mis sanciones](#mis-sanciones) y [Sanciones](#sanciones) |
| US-12 Historial de sanciones (administrador) | Administrador | [Sanciones](#sanciones) |
| US-07 Panel del validador | Validador y administrador | [Validador](#3-validador) |
| US-04 Panel de administrador | Administrador | [Jornada semanal](#jornada-semanal) y [Reglas](#reglas-los-parámetros-del-sistema) |
| US-17 Bloquear fechas de la sala | Administrador | [Bloquear fechas de la sala](#bloquear-fechas-de-la-sala) |
| US-05 Áreas académicas | Administrador | [Áreas](#áreas) |
| US-08 Gestión de roles y usuarios | Administrador | [Usuarios](#usuarios) |
| US-14 Bloques del personal de apoyo | Personal de apoyo | [Bloques del día](#bloques-del-día) |
| US-15 Checklist de cierre (prototipo anterior) | Personal de apoyo | [Referencia histórica](#checklist-de-cierre-de-la-sala-prototipo-anterior) |
| US-20 Listado configurable de check-out | Administrador y personal de apoyo | [Administrar el listado](#administrar-el-listado-de-check-out) y [Consultar las faltas de integridad](#consultar-las-faltas-de-integridad) |

## Puertas de acceso

Cada rol entra por su propia dirección. Solo la del solicitante está enlazada
desde el sitio; las otras tres las conoce quien las usa. Cada puerta se reconoce
por el panel de la izquierda, con el nombre, el ícono y el color del rol. Una vez
adentro, el mismo ícono y color aparecen junto al nombre, bajo la banda naranja.

| Rol | Dirección | Panel |
|---|---|---|
| Solicitante | `/solicitante/entrar/` | Naranjo, **Solicitantes** |
| Administrador | `/configuracion/entrar/` | Azul petróleo, **Administración** |
| Validador | `/validacion/entrar/` | Turquesa, **Validación** |
| Personal de apoyo | `/apoyo/entrar/` | Gris azulado, **Personal de apoyo** |

### Dar un rol a alguien

Los roles y las áreas de cada persona se asignan en la pestaña
[Usuarios](#usuarios) del administrador. Una persona puede tener más de un rol y
más de un área a la vez. Un solicitante necesita al menos un área activa; las
áreas se crean en la pestaña [Áreas](#áreas).

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
contraseña incorrectos.**, junto con cuántos intentos seguidos bloquean la cuenta
y por cuántos minutos. El correo queda escrito para que no tengas que repetirlo.
Las mayúsculas del correo no importan.

![Aviso de credenciales incorrectas](uso/us-01/ingreso-error.jpg)

El aviso es el mismo cuando el correo no existe, cuando la cuenta no tiene el rol
de esa puerta o cuando está bloqueada. Así nadie puede usar la pantalla para
averiguar qué cuentas existen.

Después de esos intentos fallidos seguidos, la cuenta se bloquea por esos
minutos: mientras dure, ni la contraseña correcta la abre. Cuántos intentos y
cuántos minutos lo decide el administrador (ver
[Reglas](#reglas-los-parámetros-del-sistema)).

### Recuperar la contraseña

1. En la pantalla de ingreso, pulsa **¿Olvidaste tu contraseña?**.
2. Escribe tu correo y pulsa **Enviar enlace**.
3. Abre el enlace que llega a tu correo, escribe la contraseña nueva dos veces y
   pulsa **Guardar**.
4. Con el mensaje **Listo**, vuelve a iniciar sesión con la contraseña nueva.

![Recuperar contraseña](uso/us-01/recuperar-clave.png)

El enlace sirve una sola vez y vence en unas horas. Si ya no funciona, la
pantalla ofrece **Pedir otro enlace**.

### Avisos

Lo que resulta de una acción, como guardar, bloquear o retirar, aparece como un
aviso abajo a la derecha. Se va solo después de unos segundos; la **×** lo
cierra antes.

---

## 2. Solicitante

### Solicitar una reserva

Aquí se pide una reserva de la sala de grabación. Se entra por
`/solicitante/entrar/` y el formulario está en `/solicitar/`. Son tres pasos:
**Horario y disponibilidad**, **Datos de la actividad** y **Confirmación**.
Enviar la solicitud no la confirma: queda **en revisión** hasta que la acepte un
validador.

Tu cuenta necesita el rol **Solicitante** y al menos un área académica activa
(ver [Dar un rol a alguien](#dar-un-rol-a-alguien)). Si no perteneces a ninguna,
en vez del formulario aparece el aviso **No puedes solicitar todavía**, que te
pide pedirle al administrador que te asocie a tu área.

**Elegir el área académica**

Si perteneces a más de un área, lo primero es elegir para cuál es la grabación.
Selecciónala y pulsa **Continuar al calendario**. Si perteneces a una sola, este
paso no aparece.

![Elegir el área académica](uso/us-02/elegir-area.png)

Para cambiarla después, pulsa **Cambiar área** en el paso 1. Cambiar de área
borra el día y los bloques que ya habías marcado.

**Paso 1: elegir el día y los bloques**

Si el área tiene una nota de la Oficina (por ejemplo, que no graba en horario
laboral), aparece arriba del calendario.

1. En el calendario, los días que se pueden pedir aparecen destacados y con un
   punto. Arriba se indica desde qué fecha se puede solicitar: entre la
   solicitud y la grabación tienen que pasar las semanas de desfase que fija el
   administrador (ver [Reglas](#reglas-los-parámetros-del-sistema)). Sábados y
   domingos no se pueden pedir.
2. Para moverte entre meses usa **Anterior** y **Siguiente**, o los selectores
   de mes y año. Solo se puede pedir con unos meses de anticipación.
3. Haz clic en un día. Abajo aparecen sus bloques horarios.
4. Marca uno o más bloques. Cada uno dice **Disponible** o, al marcarlo,
   **Seleccionado**. Los que ya están reservados o bloqueados no aparecen, y los
   que ya pediste tú aparecen como **Ya solicitaste este bloque · Pendiente** y
   no se pueden marcar de nuevo.
5. Pulsa **Continuar a datos de la actividad**.

![Paso 1: día y bloques](uso/us-02/paso1-horario.png)

**Paso 2: completar los datos de la actividad**

1. Arriba se ve el día y los bloques elegidos. **Cambiar horario** vuelve al
   paso 1.
2. **Solicitante.** Tu nombre, tu correo y el área elegida, tomados de tu
   cuenta. No se pueden cambiar aquí.
3. **Motivo de la solicitud** (obligatorio, hasta 300 caracteres). Para qué
   usarás la sala, por ejemplo *grabación de cápsula para el módulo de Bases de
   Datos*.
4. **Cantidad de personas en sala.** De 1 a 5, contándote a ti. Por cada
   persona adicional aparece un recuadro **Acompañante** para su nombre y
   correo, hasta 4 acompañantes.
5. Pulsa **Continuar a confirmación**. **Volver al calendario** regresa al paso
   1.

![Paso 2: datos de la actividad](uso/us-02/paso2-datos.png)

Si algo no cuadra, el paso 2 vuelve con lo que escribiste y el aviso
correspondiente. Por ejemplo, al declarar 3 personas con un solo acompañante
completo:

![Paso 2 con un aviso](uso/us-02/paso2-error.png)

**Paso 3: revisar y enviar**

1. Revisa el **Resumen de la reserva**: fecha, horario, solicitante, área,
   motivo, personas y acompañantes. **Modificar datos** vuelve al paso 2.
2. Lee los **Términos y condiciones** y marca **He leído y acepto los términos
   y condiciones de uso de la sala**. El botón no se activa hasta marcar la
   casilla.
3. Pulsa **Confirmar y enviar solicitud**.

![Paso 3: revisión y confirmación](uso/us-02/paso3-confirmacion.png)

Al enviarla aparece **Solicitud completa**, con el número de la solicitud, que
queda en revisión, y el resumen de lo enviado. **Hacer otra solicitud** empieza
de nuevo.

![Solicitud enviada](uso/us-02/solicitud-enviada.png)

Lo que eliges en cada paso queda guardado mientras completas el formulario. La
solicitud se registra recién al pulsar **Confirmar y enviar solicitud**.

| Paso | Situación | Aviso |
|---|---|---|
| Área | No se eligió un área | Por favor, selecciona un área académica para continuar. |
| 1 | No se eligió un día | Por favor, selecciona un día disponible en el calendario. |
| 1 | El día está fuera del período que se puede pedir | La fecha seleccionada no está dentro del período permitido. |
| 1 | No se marcó ningún bloque | Por favor, selecciona al menos un bloque de horario para continuar. |
| 1 | Alguien reservó un bloque mientras lo elegías | Uno o más de los bloques seleccionados ya no están disponibles. Por favor, selecciona otros. |
| 2 | Falta el motivo | El motivo es obligatorio. |
| 2 | Más de 5 personas en sala | Como máximo 5 personas en sala. |
| 2 | Menos de 1 persona en sala | Al menos tienes que entrar tú. |
| 2 | Faltan datos de acompañantes, por ejemplo 3 personas con 1 acompañante completo | Declaraste 3 personas en sala, así que faltan los datos de 2 acompañante(s); tienes 1 completo(s). |
| 2 | Un acompañante tiene nombre pero no correo, o al revés | Falta el correo de esta persona. / Falta el nombre de esta persona. |
| 2 | Dos acompañantes tienen el mismo correo | Hay un correo repetido entre los acompañantes. |
| 2 | Se incluyó tu propio correo como acompañante | Tu propio correo ya está incluido: eres parte de la cuenta de personas. |
| 3 | No se aceptaron los términos | Tienes que aceptar los términos y condiciones para enviar la solicitud. |

### Mis solicitudes

La pestaña **Mis solicitudes**, arriba junto a **Solicitar reserva**, muestra
todas tus solicitudes, de cualquiera de tus áreas, con su estado actual. Está en
`/solicitar/mis-solicitudes/`.

Se separan en dos pestañas, cada una con cuántas tiene:

- **Próximas**: las de hoy en adelante, la más cercana primero. Una de hoy sigue
  aquí aunque su hora ya haya pasado.
- **Anteriores**: las de días que ya pasaron, la más reciente primero.

Cada fila dice el número de la solicitud, el área, la fecha, los bloques y el
estado. Se muestran de a 20; si hay más, abajo aparecen **Anterior** y
**Siguiente**.

![Mis solicitudes: próximas](uso/us-09/mis-solicitudes-proximas.png)

![Mis solicitudes: anteriores](uso/us-09/mis-solicitudes-anteriores.png)

| Estado | Qué significa |
|---|---|
| **En revisión por la Oficina** | La Oficina todavía no la revisa. Se puede **Retirar** |
| **Aceptada** | La Oficina la aceptó. Falta confirmar la asistencia: aparece **Confirmar asistencia** |
| **Pendiente de confirmación** | Ya te llegó el recordatorio. Aparecen la fecha límite, **Confirmar asistencia** y **Cancelar reserva** |
| **Confirmada** | Confirmaste que vas a usar la sala. Todavía se puede **Cancelar reserva** |
| **Rechazada** | La Oficina la rechazó. Debajo va el motivo que escribió |
| **Cancelada** | Se canceló después de aceptada: la cancelaste tú o la Oficina le quitó el horario, con un correo que dice por qué. Si la cancelaste en la semana de la reserva, dice que cuenta como inasistencia |
| **No confirmada (inasistencia)** | Llegó su día sin confirmar: el horario se liberó y queda como inasistencia |
| **Retirada** | La retiraste antes de que la Oficina la revisara |

**Retirar una solicitud**

Solo se puede retirar una solicitud **En revisión por la Oficina**. Una vez
aceptada o rechazada, el botón ya no aparece.

1. Pulsa **Retirar** en la fila de la solicitud.
2. Se abre un recuadro que pide confirmarlo. **Retirar solicitud** la retira;
   **Cancelar**, Esc o un clic fuera del recuadro lo cierran sin cambiar nada.

![Confirmar el retiro](uso/us-09/retirar-confirmar.png)

La solicitud queda **Retirada** en la misma pestaña, y el aviso dice **Retiraste
la solicitud #… Su horario queda libre.** No se borra: sigue en el historial. Si
la Oficina la revisó justo antes, el aviso dice que ya no está en revisión y no
cambia nada.

![Solicitud retirada](uso/us-09/solicitud-retirada.png)

### Confirmar la asistencia

Cuando la Oficina acepta una reserva llega un correo con un enlace para
confirmarla. El mismo enlace está en **Mis solicitudes**, como **Confirmar
asistencia** bajo el estado de cada reserva aceptada.

| Paso | Qué pasa |
|---|---|
| Abrir el enlace | Sin sesión iniciada, pide entrar y después vuelve a la reserva |
| Ver la reserva | Muestra la fecha, el horario, el área y el motivo. Abrirla no confirma nada |
| **Confirmar asistencia** | La reserva queda **Confirmada** y vuelve a Mis solicitudes con el aviso |

![Confirmar asistencia](uso/us-03/confirmar-asistencia.png)

Al confirmar, vuelves a **Mis solicitudes** con el aviso **Confirmaste tu
asistencia a la reserva #…** y la fila queda **Confirmada**.

![Asistencia confirmada](uso/us-03/asistencia-confirmada.png)

Se puede confirmar hasta el día anterior a la reserva. Si ya está confirmada,
cancelada o es el mismo día, la página lo dice y no muestra el botón.

![Reserva que ya no se puede confirmar](uso/us-03/confirmacion-no-disponible.png)

**El recordatorio**

Cuando falta el plazo de confirmación que fija la Oficina (hoy, dos días), llega
un segundo correo con el resumen de la reserva y dos enlaces: uno para confirmar
y otro para cancelar. Llega una sola vez, y no llega si ya confirmaste.

Desde ese momento, al entrar al sistema aparece una franja bajo el encabezado:
**Tienes N reservas por confirmar**, con un enlace a Mis solicitudes. En la
fila, la reserva queda **Pendiente de confirmación** con la fecha límite.

![Reserva por confirmar](uso/us-03/por-confirmar.png)

Si llega el día de la reserva sin confirmar, su horario se libera y queda
**No confirmada (inasistencia)**.

**Cancelar una reserva**

Una reserva aceptada, confirmada o no, se puede cancelar hasta que empiece su
primer bloque.

| Paso | Qué pasa |
|---|---|
| **Cancelar reserva** | En la fila de Mis solicitudes o desde el enlace del recordatorio. Abre una página con la reserva; abrirla no cancela nada |
| **Sí, cancelar la reserva** | La reserva queda **Cancelada**, su horario vuelve a ofrecerse y la Oficina recibe un correo |

Cancelar antes de la semana de la reserva no tiene consecuencias. Desde el lunes
de esa semana, la página avisa que cancelar cuenta como **inasistencia**.

![Cancelar una reserva en la semana de la reserva](uso/us-03/cancelar-reserva.png)

Al cancelar, vuelves a **Mis solicitudes** con el aviso **Cancelaste la reserva
#…** y la fila queda **Cancelada**.

![Reserva cancelada](uso/us-03/reserva-cancelada.png)

### Mis sanciones

Una sanción suspende por un tiempo la posibilidad de enviar solicitudes nuevas.
La pone la Oficina, por ejemplo tras inasistencias, con un motivo y un periodo.
Rige desde su primer día hasta las **23:59 de su último día**, en hora de Chile;
al día siguiente se puede volver a pedir sin hacer nada. Cuando la Oficina la
pone desde su panel, llega un correo con el motivo, el periodo y desde qué día
se puede volver a pedir.

Mientras hay una sanción vigente:

- En todas las pantallas del solicitante aparece, bajo el encabezado, una franja
  que dice hasta cuándo rige y desde qué día se puede volver a solicitar.
- **Solicitar reserva** no muestra el formulario: aparece **No puedes solicitar
  por ahora**, con el motivo, el periodo y la fecha desde la que se puede pedir de
  nuevo.
- Las reservas ya **aceptadas** no cambian: se pueden confirmar y usar como
  siempre. Las que estaban **en revisión** también siguen: la Oficina las
  resuelve igual que antes.

La pestaña **Mis sanciones**, arriba junto a **Mis solicitudes**, muestra primero
la sanción vigente y debajo las anteriores, cada una con su motivo y su periodo.
Si la Oficina levantó una antes de tiempo, dice cuándo y por qué. Está en
`/solicitar/mis-sanciones/` y solo muestra las sanciones propias.

---

## 3. Validador

Aquí se revisan las solicitudes pendientes y se aprueba o rechaza cada solicitud
entera. Se entra por `/validacion/entrar/` y el panel está en `/validador/`. El
administrador tiene el mismo panel en la pestaña **Validación** de
`/configuracion/`.

| Al resolver | Qué pasa |
|---|---|
| Aprobar | La solicitud queda **Aceptada** y su bloque deja de ofrecerse en el calendario |
| Rechazar | La solicitud queda **Rechazada** con el motivo |
| En ambos casos | Queda guardado quién resolvió y a qué hora. El solicitante recibe un correo y ve el resultado en **Mis solicitudes** |

### Leer el panel

El panel es la jornada semanal, la misma que configura el administrador, con
quién pide cada bloque escrito adentro. Abre en la primera semana que tiene algo
por resolver; **←**, **Hoy** y **→** cambian de semana.

![Panel del validador](uso/us-07/panel-con-tope.png)

| Bloque | Qué indica |
|---|---|
| Con un nombre | Una solicitud pendiente lo pide |
| Borde color vino, con dos nombres o más | Tope: varias solicitudes piden ese bloque |
| Filete celeste, con el nombre en gris | Reservado: ya está aprobado para esa persona |
| Rayado | Bloqueado por el administrador: no se puede aprobar |
| Borde punteado | Quitado de la jornada, pero con pedidos de antes |

A la derecha, **Por resolver** lista los topes y las solicitudes sin tope de la
semana. Un clic en un bloque o en un elemento de la lista abre su detalle en ese
mismo panel; **Volver a la lista** regresa.

### Sin tope

Una solicitud que nadie más disputa se abre en su ficha: solicitante, área y su
prioridad, motivo, personas y acompañantes, cuándo se envió, la fecha y el
bloque.

![Ficha de una solicitud sin tope](uso/us-07/panel-sin-tope.png)

- **Aprobar**: se aprueba de inmediato.
- **Rechazar**: abre el campo **Motivo del rechazo** (mínimo 10 caracteres) y
  luego **Confirmar rechazo**. **Cancelar** lo cierra.

Si la solicitud choca con otra en algún bloque, la ficha lo dice y ofrece **Ver
el tope**: se resuelve ahí.

### Con tope

El tope lista las solicitudes que piden el mismo bloque en la misma fecha,
ordenadas por la prioridad de su área, con una sugerencia según esa prioridad.
De cada una se ve el solicitante, el área, el motivo y, si pide otros bloques,
cuáles. La elegida es la de mayor prioridad; marca otra para cambiarla.

![Tope con dos solicitudes](uso/us-07/tope.png)

1. Pulsa **Aprobar a …** para darle el bloque a la elegida, o **Rechazar a …**
   para rechazar solo esa.
2. El panel dice quién obtiene el bloque y quién queda rechazada. Aprobar una
   rechaza enteras a las que chocan con ella.
3. Escribe el **Motivo del rechazo** (mínimo 10 caracteres). Les llega por
   correo a quienes pierden.
4. Pulsa **Confirmar**. **Volver** regresa al tope sin resolver.

Si confirmas sin motivo, el panel lo avisa y deja el cursor en el campo.

![Aviso de motivo faltante](uso/us-07/tope-falta-motivo.png)

![Motivo escrito antes de confirmar](uso/us-07/tope-motivo-escrito.png)

Al confirmar, el bloque queda reservado y el aviso resume lo que pasó, por
ejemplo **Aprobaste la solicitud de Sofía Solicitante. La de Marcela Rivas quedó
rechazada.**

![Tope resuelto](uso/us-07/tope-aprobado.png)

Si rechazas una en un tope de dos, la que queda se abre sola en su ficha.

### Resueltas hoy

**Resueltas (…)**, arriba, abre lo resuelto hoy por cualquier validador:
solicitud, resolución, motivo, quién y a qué hora. Una que perdió un tope dice a
quién se le asignó el bloque. Queda guardado: recargar la página no lo borra.

![Resueltas hoy](uso/us-07/resueltas.png)

### Historial

**Historial**, arriba del panel, abre todo lo resuelto hasta hoy en
`/validacion/historial/`, de lo más reciente a lo más antiguo: la solicitud,
sus bloques, la decisión, el motivo, quién la resolvió y cuándo. Una que perdió
un tope dice **asignada a #N**, con el número de la que se quedó con el bloque.
Una aprobada sin tope no lleva motivo y muestra **—**. El administrador lo abre
desde su pestaña **Validación** y lo ve con las pestañas de su panel.

Para acotar la lista:

1. Elige cualquiera de los filtros: **Resuelta desde**, **Hasta**, **Área**,
   **Decisión** y **Validador**. **Validador** ofrece solo a quienes han resuelto
   algo.
2. Pulsa **Filtrar**. La dirección de la página queda con los filtros: se puede
   guardar o enviar a otra persona que valide.
3. **Quitar filtros** vuelve a la lista completa.

![Historial filtrado por rechazadas](uso/us-11/historial.png)

Si **Hasta** es anterior a **Resuelta desde**, el campo lo avisa y esa fecha no
se aplica. Un clic en **#N** abre la solicitud como se envió (solicitante, área,
fecha, bloques, motivo, observaciones, personas, acompañantes y cuándo se envió)
junto con su resolución. **Volver al historial** regresa a la misma página con
los mismos filtros.

![Detalle de una solicitud resuelta](uso/us-11/detalle.png)

El historial es solo para consultar: desde ahí no se cambia nada, y en `/admin/`
una solicitud resuelta tampoco se puede editar ni borrar.

| Aviso | Cuándo |
|---|---|
| Escribe el motivo del rechazo (mínimo 10 caracteres). | Se rechaza, o se aprueba en un tope, sin motivo o con uno muy corto |
| La sala está bloqueada …: no se puede aprobar. Recházala con ese motivo. | Hay un bloqueo en ese horario |
| El bloque de las … ya no está en la jornada: no se puede aprobar. Recházala. | El administrador quitó el bloque después de que se pidiera |
| Esta solicitud ya fue resuelta o retirada. Recarga la página para ver lo último. | Otro validador la resolvió, o el solicitante la retiró, mientras tenías la página abierta |
| Uno de sus bloques ya está aprobado para otra solicitud ese día. | El bloque se aprobó para otra solicitud |
| No se pudo guardar. Recarga la página e inténtalo de nuevo. | La sesión venció o se perdió la conexión |

---

## 4. Administrador

El panel del administrador tiene siete pestañas: **Check-out**, **Bloques**,
**Áreas**, **Usuarios**, **Reglas**, **Validación** y **Sanciones**. Se entra por
`/configuracion/entrar/`.

![Puerta de la administración](uso/us-04/puerta-administracion.png)

**Validación** es el panel del validador (ver [Validador](#3-validador)): el
administrador también aprueba y rechaza, y la resolución queda a su nombre.

### Jornada semanal

Un bloque es un tramo horario de un día de la semana, por ejemplo *lunes de
08:10 a 09:40*. La jornada se define una vez y se repite todas las semanas. Se
edita en la pestaña **Bloques**, vista **Semanal**.

![Jornada semanal](uso/us-04/bloques-semana.png)

La vista semanal dice qué semana es y cada columna muestra su fecha, porque
desde ahí también se bloquea un bloque en una fecha. Para cambiar de semana usa
**←**, **Hoy** y **→**, o haz clic en un día del mini calendario de la izquierda.

**Agregar un bloque**

1. Pulsa **+** junto al nombre del día, o haz clic en un hueco de su columna.
2. En el recuadro, ajusta **Inicio** y **Término**, o la **Duración**, que se
   calcula sola.
3. Pulsa **Agregar el bloque**.

**Cambiar o quitar un bloque**

1. Haz clic sobre el bloque. Se abre un recuadro junto a él.
2. Cambia las horas y pulsa **Guardar el bloque**, o pulsa **Quitar de la
   jornada**. **Cancelar** o Esc lo cierran sin cambios.

![Cambiar un bloque](uso/us-04/bloques-editar.png)

El recuadro recuerda que el horario vale para todas las semanas, y un bloqueo,
solo para su fecha. Si el bloque se cruza con otro del mismo día, no se guarda:
el error aparece en el recuadro y el otro bloque queda marcado. Quitar un bloque
no pide confirmación; el aviso trae **Reponerlo**, por si fue un error. Un
bloque quitado nunca se borra, así que las solicitudes que ya lo apuntan siguen
siendo válidas.

**Vista mensual**

La vista **Mensual** es la que abre por defecto. Muestra el mes completo y, en
la cabecera, cuántos bloques y horas tiene cada día de la semana. Sirve para
revisar la jornada y para bloquear fechas; no para editar bloques.

![Vista mensual](uso/us-04/bloques-mes.png)

### Bloquear fechas de la sala

El administrador puede dejar la sala fuera de servicio por una **mantención**,
un **feriado** o un **evento**. El bloqueo vale para fechas concretas: la
jornada semanal sigue igual. Mientras está vigente, esos horarios no se pueden
solicitar ni aprobar, y quien solicita ve el motivo.

**Crear un bloqueo**

1. En la vista mensual, haz clic en el día que quieres bloquear.
2. En **Qué bloquear**, elige una opción:
   - **Todo el día**.
   - **Un bloque**, por ejemplo de 08:10 a 09:40.
   - **Varios días**: bloquea los días completos entre la fecha elegida y la
     que marques como término. Puedes marcarla con otro clic en el calendario.
3. Elige el **Motivo**: Mantención, Feriado o Evento. Si quieres, agrega un
   **Detalle**, como *Taller de profesores*. El solicitante lo ve.
4. Pulsa **Bloquear**.

![Recuadro para bloquear la sala](uso/us-17/crear-bloqueo.png)

El día queda rayado y el aviso confirma lo bloqueado, por ejemplo **Bloqueaste
la sala el miércoles 21 de octubre, todo el día (Evento: Taller de
profesores).**

![Bloqueo creado](uso/us-17/bloqueo-creado.png)

No se puede bloquear un día que ya pasó, una fecha sin jornada ni algo que ya
está bloqueado entero. Si el bloqueo le quita la sala a reservas aprobadas que
todavía no empiezan, el sistema no lo guarda a la primera: muestra esas
reservas en el recuadro para que revises a quién afecta, y el botón pasa a ser
**Bloquear y avisar**. Al pulsarlo, guarda el bloqueo y avisa por correo a cada
persona afectada.

**Bloquear un bloque desde la vista semanal**

Haz clic en el bloque, pulsa **Bloquear una fecha**, elige la fecha (viene
elegida la de la semana que estás mirando) y el motivo, y pulsa **Bloquear esa
fecha**. Los bloques bloqueados en esa semana aparecen rayados.

![Semana con un bloque bloqueado](uso/us-17/semana-con-bloqueo.png)

**Ver y levantar un bloqueo**

Haz clic en el bloqueo, dentro de su día en la vista mensual. El recuadro dice
el motivo, las fechas y quién lo registró. Para devolver el horario, escribe el
**Motivo para levantarlo** y pulsa **Levantar el bloqueo**.

![Ver y levantar un bloqueo](uso/us-17/levantar-bloqueo.png)

El horario vuelve a estar disponible y queda anotado quién levantó el bloqueo,
cuándo y por qué. Un bloqueo que ya pasó no se puede levantar.

**Registro (…)**, arriba de la vista mensual, abre las últimas acciones,
bloqueos y levantamientos, con fecha, qué se bloqueó, motivo y responsable.

![Registro de bloqueos](uso/us-17/bloqueo-levantado.png)

> **Estado actual.** Las reservas que un bloqueo afecta son las solicitudes
> aceptadas y no canceladas de esas fechas. En desarrollo, los correos de aviso
> se escriben en el log del contenedor en vez de enviarse.

### Áreas

Cada solicitud queda ligada a un área académica o unidad, y un solicitante solo
puede pedir la sala con un área activa. La pestaña **Áreas** lista cada una con
su nota, cuántas personas tiene y si está activa.

![Áreas](uso/us-05/areas.png)

| Acción | Qué pasa |
|---|---|
| **Nueva área** | Pide el nombre y, si hace falta, una nota. No puede haber dos áreas con el mismo nombre, aunque cambien las mayúsculas |
| **Editar** | Cambia el nombre o la nota. Las solicitudes que ya usan el área muestran el nombre nuevo |
| **Desactivar** | El área deja de ofrecerse al pedir. Las solicitudes que ya la usan no cambian, y las pendientes se resuelven como siempre |
| **Reactivar** | Vuelve a ofrecerse al pedir |

![Nueva área](uso/us-05/nueva-area.png)

Las áreas no se borran: una desactivada sigue en la lista, atenuada. La **nota**
es lo que hay que tener en cuenta de esa área, por ejemplo que Educación Continua
no graba en horario laboral. La ve quien pide con esa área, arriba del calendario,
y el validador en la ficha de cada solicitud, como **Nota del área**.

![Nota del área en el panel del validador](uso/us-05/nota-validador.png)

**Últimos cambios (…)**, al pie, abre los últimos 15: qué área cambió, qué
campo, de qué valor a cuál, quién y cuándo. Lo que se cambie desde `/admin`
también queda ahí.

Las personas se asignan a un área desde la pestaña [Usuarios](#usuarios).

### Usuarios

La pestaña **Usuarios** lista cada cuenta con su nombre, correo, roles, áreas y
estado. Se busca por nombre, apellido o correo, y se filtra por rol, área y
estado. Cada rol aparece con el ícono y el color de su puerta.

![Usuarios](uso/us-08/usuarios.png)

| Acción | Qué pasa |
|---|---|
| **Nueva cuenta** | Pide nombre, apellido, correo, al menos un rol y, si es solicitante, sus áreas. El correo no se puede repetir. A la persona le llega un correo para crear su contraseña; nadie más la conoce |
| **Editar** | Cambia los datos, los roles y las áreas. Validadores y personal de apoyo no tienen área |
| **Reenviar el correo de la contraseña** | Aparece mientras la persona no haya entrado nunca, por ejemplo si el enlace venció |
| **Desactivar cuenta** | La persona ya no entra por ninguna puerta y pierde la sesión abierta. Su historial se conserva. Si tiene solicitudes pendientes o reservas aceptadas de hoy en adelante, el sistema las cuenta y pide confirmar: desactivar no las cancela |
| **Reactivar cuenta** | Vuelve a entrar con su contraseña |

![Ficha de una cuenta](uso/us-08/cuenta.png)

Las cuentas no se borran, ni siquiera desde `/admin`. Siempre queda al menos un
administrador activo, y nadie se quita a sí mismo el rol ni desactiva su propia
cuenta.

El rol **Administrador** lo da y lo quita solo el **superusuario**, la cuenta de
soporte de la Oficina que se crea al instalar el sistema (ver
[despliegue](despliegue.md)). Un administrador que no es superusuario no ve esa
casilla, y la cuenta de otro administrador le aparece de solo lectura.

#### Cargar una planilla

**Cargar planilla** crea o actualiza muchas cuentas a la vez, por ejemplo los
docentes de una unidad.

1. **Descargar plantilla** baja un CSV con las columnas `correo`, `nombre`,
   `apellido`, `roles` y `areas`. Se completa una fila por persona. Varios roles
   o áreas van en la misma celda, separados por coma.
2. Se guarda como CSV (en Excel: *Guardar como → CSV*) y se sube con **Revisar**.
3. La vista previa dice, fila por fila, si la cuenta **se crea**, **se le suma**
   algo, queda **sin cambios** o tiene un **error**. Todavía no se guarda nada.
4. Si ninguna fila tiene errores, **Confirmar la carga** guarda todo. Si alguna
   tiene, no se puede confirmar: se corrige la planilla y se vuelve a subir.

![Vista previa de la carga](uso/us-08/carga.png)

A una cuenta que ya existe solo se le suman los roles y las áreas de la planilla;
nunca se le quita nada, y su nombre no cambia. Las cuentas nuevas reciben el
correo para crear su contraseña.

**Últimos cambios (…)**, al pie de la lista, abre los últimos 15: qué cuenta
cambió, qué campo, de qué valor a cuál, quién y cuándo. Lo que se cambie desde
`/admin` y lo que entre por planilla también queda ahí.

### Reglas: los parámetros del sistema

Aquí se ajustan los umbrales con los que opera el sistema, sin reinstalar nada.
Cada fila explica qué hace el sistema con ese valor.

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

El aviso dice cuántos cambios quedaron guardados. Los cambios rigen para las
solicitudes nuevas; las que ya se enviaron no cambian. Si un valor está fuera de
su rango permitido, la fila se marca y no se guarda nada.

![Parámetros del sistema](uso/us-04/reglas.png)

**Últimos cambios (…)**, al pie, abre los últimos 15: quién cambió cada
parámetro, cuándo y de qué valor a cuál.

### Sanciones

Una sanción impide a un solicitante enviar solicitudes nuevas desde su fecha de
inicio hasta las 23:59 de su fecha de término. **No cancela sus reservas ya
aceptadas ni sus solicitudes en revisión** (decisión del 20/10 sobre AC6 de
US-10).

#### El listado

La pestaña **Sanciones** muestra una fila por solicitante, con:

| Columna | Qué cuenta |
|---|---|
| Incidentes | Cada pregunta del check-out respondida **No**, en todos sus bloques |
| Inasistencias | Reservas aceptadas que llegaron a su día sin confirmar, y las canceladas desde el lunes de su semana |
| Sanción | **Vigente** (hasta qué día y por qué), **Levantada**, **Terminada** o **Sin sanción**, según la vigente o, si no hay, la última |
| Levantar | Solo si tiene una vigente: el motivo y el botón, como en el detalle |

Primero van quienes tienen más incidentes. Arriba se filtra por nombre o
correo, por área y por estado de la sanción, y **Quitar filtros** vuelve a
mostrar a todos. La dirección guarda los filtros, así que se puede compartir.
Hay 25 personas por página.

Si una persona llega a las **Inasistencias para sancionar** de
[Reglas](#reglas-los-parámetros-del-sistema) desde su última sanción, la fila
lo marca con **Llega al umbral de N**. El sistema **no la sanciona solo**:
decide el administrador.

#### El detalle de una persona

Un clic en el nombre abre su historial, del más antiguo al más reciente:

- **Incidente**: el día y el bloque, la sección y la pregunta del check-out tal
  como se preguntó ese día, la observación de quien lo registró y la foto.
- **Inasistencia**: el día, los bloques y si llegó su día sin confirmar o se
  canceló tarde.
- **Sanción**: el periodo, el motivo, quién la puso y cuándo y, si se levantó,
  quién, cuándo y por qué.

**Volver al listado** regresa a la misma página y filtros.

#### Aplicar una sanción

En el detalle, **Aplicar una sanción**:

1. Escribe el motivo. Es obligatorio y le llega a la persona por correo.
2. Revisa las fechas. Vienen propuestas: desde hoy y por la **Duración de la
   sanción** de Reglas, contando el primer día. Con 30 días desde el 3 de
   noviembre, **Hasta** dice 2 de diciembre: la sanción rige hasta las 23:59 de
   ese día y la persona vuelve a pedir el 3.
3. Pulsa **Sancionar**.

No se puede empezar en una fecha futura, terminar antes de empezar ni cruzarse
con otra sanción de la misma persona que no se haya levantado, aunque solo
compartan un día. Si pasa, el formulario lo dice y no se guarda nada. Si otro
administrador la sancionó justo antes, el segundo ve el cruce.

La persona recibe un correo con el motivo, el periodo y desde qué día puede
volver a pedir, y desde ese momento ve **No puedes solicitar por ahora**.

El superusuario puede además crear y acortar sanciones en `/admin`, en
**Personas › Sanciones**, con las mismas reglas. Las sanciones no se borran.

#### Levantar una sanción

Antes de que termine, en la fila del listado o en el detalle:

1. Escribe el motivo del levantamiento. Es obligatorio.
2. Pulsa **Levantar**.

El aviso dice **Levantaste la sanción de …**. Si la persona no tiene otra
vigente, agrega **Ya puede solicitar la sala** y puede pedir de inmediato. Si
tiene otra, dice hasta cuándo sigue sin poder pedir. La sanción no se borra:
queda en su historial con quién la levantó, cuándo y por qué. Si otra persona
la levantó justo antes, o ya terminó, el aviso lo dice y no cambia nada.

---

## 5. Personal de apoyo

Se entra por `/apoyo/entrar/`.

![Puerta del personal de apoyo](uso/us-14/puerta-apoyo.png)

### Bloques del día

La vista muestra las reservas de la sala para un día. Al entrar se ven las de
hoy, ordenadas por hora de inicio.

![Bloques del día](uso/us-14/bloques-del-dia.png)

| Columna | Qué indica |
|---|---|
| Hora | Inicio y término del bloque |
| Solicitante | Quién pidió la sala |
| Área | El área académica de la reserva |
| Personas | Cuántas personas declaró el solicitante |
| Estado | **Aprobada** o **Confirmada**. Una **Cancelada** o **No confirmada** aparece tachada: ya no hay que esperar a nadie |
| Check-out | **Completado** si ya se registró, **Hacer check-out** si el bloque terminó y falta, o **—** si el bloque aún no termina, se canceló o no se confirmó |

Las reservas pendientes de aprobación no aparecen, porque todavía pueden
rechazarse. Todo el personal de apoyo ve todos los bloques; no se asignan a una
persona en particular.

Usa **‹** y **›** para ir al día anterior o al siguiente, **Hoy** para volver al
día actual, o el selector de fecha para saltar a cualquier día.

### Hacer el check-out

El botón **Hacer check-out** aparece recién cuando termina el bloque.

1. Pulsa **Hacer check-out** en la fila del bloque.
2. En **Registro de asistencia**, indica si el solicitante asistió al bloque.
3. Si marcas **No, no asistió**, pulsa **Registrar inasistencia**. El registro queda completado sin exigir preguntas, observaciones, fotos ni hora de salida. No se registra una revisión de integridad de la sala.
4. Si marcas **Sí, asistió**, pulsa **Continuar al listado**. Responde las preguntas e indica la hora efectiva de salida. La asistencia positiva se guarda junto con el check-out al completar el formulario.
5. Cada respuesta **No** exige una **Observación del incumplimiento** de al menos 10 caracteres y una foto JPEG, PNG o WebP de hasta 5 MB.
6. En **Fundamento y evidencia final**, completa las observaciones finales (mínimo 10 caracteres) y adjunta una fotografía del estado general de la sala. Las recomendaciones finales son opcionales.
7. Pulsa **Finalizar y enviar reporte**. Si faltan antecedentes, corrige lo indicado y vuelve a seleccionar las fotos. El bloque aparece como **Completado**.

![Check-out pendiente](uso/us-14/checkout-pendiente.png)

Un check-out completado no se puede enviar de nuevo. Al pulsar **Completado**
se ve la asistencia, quién lo registró y cuándo. Las correcciones se realizan
mediante **Modificar check-out**, dentro del plazo descrito más abajo.

![Check-out completado](uso/us-14/checkout-completado.png)

El registro queda en la base de datos y lo ve todo el personal de apoyo. Al abrirlo
se muestran sus preguntas originales, respuestas y evidencias. Las fotos solo se
descargan con una sesión de apoyo o administración. Las capturas de US-14 de arriba
corresponden al simulador anterior.

Si una respuesta de un registro antiguo no está disponible, el formulario
completo y su PDF muestran **Sin respuesta registrada**, sin inventar una
respuesta de cumplimiento o incumplimiento.

### Administrar el listado de check-out

La pestaña **Check-out** aparece después de **Validación** en Configuración.
Inicia sesión como administrador y entra en `/configuracion/checkout/`.
Dentro encontrarás dos pestañas: **Formulario**, para editar el listado, e
**Historial**, para consultar los check-outs registrados.
Cada sección tiene sus controles de orden en la cabecera y un botón
**Añadir pregunta a esta sección** en su interior. Para crear un grupo distinto,
usa **Añadir nueva sección** en el bloque separado al final del editor.

Edita los títulos y las preguntas, y usa **Subir**, **Bajar** o **Eliminar**
en el elemento correspondiente. Debe conservarse al menos una sección con una
pregunta. Todas las preguntas son de **Sí / No** y obligatorias.

En **Revisar y publicar**, pulsa **Vista previa / Probar listado** para abrir
el borrador en otra pestaña. Allí puedes responder y pulsar **Probar respuestas**:
se ejecutan las mismas validaciones del check-out, sin guardar respuestas,
fotografías ni publicar cambios. Regresa a la pestaña del editor para seguir
editando y usa **Publicar listado** cuando esté listo. El sistema mostrará una
alerta de confirmación dentro de la página, compacta, con esquinas redondeadas,
borde fino naranja y celeste en la acción secundaria, antes
de guardar y publicar los cambios. Pulsa **Guardar y publicar** para continuar o
**Seguir editando** para conservar el borrador. También puedes cerrar la ventana
con **Escape**. Mientras esté abierta, el foco permanece dentro de la ventana.
La ventana comienza con el foco en **Seguir editando**. Cancelar no envía datos
al servidor: el borrador permanece en la pestaña actual, sin publicarse. No se
guarda automáticamente al salir o recargar. **Vista previa / Probar listado**
abre la prueba directamente, sin pedir esta confirmación.

La vista previa también comienza por asistencia. Permite probar una inasistencia
sin pedir el listado ni guardar un registro real. Para revisar las preguntas,
marca asistencia y continúa; **Cambiar asistencia** vuelve al paso anterior.

Los botones de edición preparan el borrador; confirmar **Guardar y publicar** guarda los
cambios para los check-outs pendientes. La regla de observación y foto ante un
**No** también se aplica a las preguntas nuevas. No se muestra un número de
versión publicada en la interfaz.

Los reportes completados conservan una copia del listado que se respondió.
Si el listado cambia mientras alguien responde o edita, el sistema solicita
recargar antes de continuar. Un envío con errores no registra el check-out;
hay que corregirlo y volver a seleccionar las fotos antes de enviarlo.

### Fotografías y observaciones del incumplimiento

Al responder **No**, registra lo sucedido en **Observación del incumplimiento**
y adjunta la fotografía de respaldo. Estos son los antecedentes que se
recopilan para el informe; no hay un campo de recomendaciones por pregunta.

**Recomendaciones para la fotografía** despliega consejos de iluminación,
encuadre y enfoque. Es una ayuda para tomar la foto. Al seleccionar una imagen,
aparece una vista previa para comprobar que fundamenta la observación.
Usa JPEG, PNG o WebP de hasta 5 MB.

La sección **Fundamento y evidencia final** reúne la observación y fotografía
general de cierre. Allí se mantiene la opción de recomendaciones finales,
separada de las observaciones específicas de los incumplimientos.

### Consultar las faltas de integridad

Después de registrar, abre el check-out completado y pulsa **Ver reporte de
faltas de integridad**. El reporte reúne únicamente las preguntas respondidas
**No**, agrupando cada pregunta y su sección original con la observación y la
fotografía correspondiente. Incluye los antecedentes generales del cierre
cuando existen incumplimientos.

Las preguntas respondidas **Sí** permanecen en el check-out completo y no se
incluyen como faltas. Si todas cumplen, el reporte indica que no hay faltas de
integridad. Las fotografías se descargan con una sesión autorizada de apoyo o
administración. La inasistencia se informa como tal, sin afirmar que se revisó
la integridad de una sala que no se utilizó. El reporte muestra las observaciones
y fotos de la última corrección válida.

### Modificar un check-out durante los primeros 10 minutos

1. Como el mismo usuario de apoyo que registró el check-out, abre **Completado**.
2. Pulsa **Modificar check-out**. La pantalla indica la hora límite para guardar.
3. Corrige asistencia, respuestas u observaciones. Las fotos registradas se
   conservan si no seleccionas reemplazos. Se utilizan las preguntas originales,
   aunque el administrador haya cambiado el listado desde entonces.
4. Pulsa **Guardar cambios**. El registro y su reporte muestran **Editado**, el
   autor de la corrección y su fecha y hora.

El plazo termina 10 minutos después del registro original; editar no lo amplía.
Solo el autor puede modificar y el servidor comprueba el plazo al guardar,
incluso si el formulario se abrió antes. Una vez vencido, el registro queda
disponible para consulta y ya no muestra la acción de modificación.

Al corregir asistencia a inasistencia, se retiran las respuestas y fotos del
reporte vigente y se conserva el estado anterior en el historial técnico. Al
corregir inasistencia a asistencia, se exige completar el listado y la evidencia
de cierre. Registrar inasistencia no aplica sanciones automáticas en este flujo.

### Historial administrativo y formulario en PDF

1. Entra como administrador a **Configuración → Check-out → Historial**.
2. Selecciona una semana. **Esta semana** y las semanas anteriores aparecen de
   la más reciente a la más antigua; los registros se agrupan por día en el mismo
   orden. Una semana sin registros muestra un aviso.
3. Revisa el usuario solicitante, la fecha de registro, la fecha y horario del
   bloque reservado, quién registró el check-out y su estado de reporte. **Sí ·
   Con reporte** indica al menos un incumplimiento de integridad; **No · Sin
   incumplimientos** indica que todas las preguntas cumplieron, y **No ·
   Inasistencia** indica que no hubo revisión de la sala. Las correcciones se
   identifican con **Editado**.
4. Pulsa el icono de documento **PDF** situado a la derecha de la fila. Se abre
   el formulario completo en otra pestaña, desde donde puedes guardarlo o imprimirlo.

El historial abarca los últimos **dos meses calendario**, según la fecha de
registro. Por ejemplo, el 2 de noviembre permite consultar desde el 2 de septiembre.
Los registros anteriores se conservan fuera de esta vista. Si hay más de 30
registros en una semana, usa **Anterior** y **Siguiente** para cambiar de página.

El PDF incluye las preguntas y respuestas originales, las observaciones y
fotografías, el cierre y la marca de edición cuando corresponde. Para una
inasistencia muestra sus datos y aclara que no se realizó revisión. El PDF
contiene el formulario completo; **Ver reporte de faltas de integridad** sigue
siendo la consulta que reúne exclusivamente los incumplimientos.

### Checklist de cierre de la sala: prototipo anterior

> **Referencia histórica.** La descripción y capturas siguientes corresponden
> al prototipo de US-15, con reserva de ejemplo y almacenamiento en el navegador.
> No describen el flujo actual ni constituyen instrucciones para sus pruebas.
> Para usar el check-out integrado, sigue las secciones anteriores de este manual.

Al terminar el uso de la sala, el personal de apoyo la revisa y deja constancia
de su estado. Son cuatro pasos; la barra de arriba dice en cuál vas y cuánto
falta.

| Paso | Qué se revisa |
|---|---|
| 1. Estado e integridad | Paredes y paneles acústicos sin daños; puerta y sellos acústicos funcionando |
| 2. Orden y limpieza | Sala sin basura ni objetos personales; mobiliario en su posición original |
| 3. Equipamiento técnico | Micrófonos y cables enrollados; consola y periféricos apagados; si algún equipo o cable presenta daños |
| 4. Cumplimiento y cierre | Si el ingreso y la desocupación fueron a la hora prevista, y la hora efectiva de salida |

![Paso 1 del checklist](uso/us-15/checklist-paso1.png)

**Responder un paso**

1. Marca **Sí** o **No** en cada pregunta.
2. Si marcas **No**, aparecen dos campos obligatorios: una **Observación** de al
   menos 10 caracteres que explique el problema y una **Foto de integridad** de
   respaldo. **Quitar foto** la saca para adjuntar otra.
3. Pulsa **Siguiente**. **Anterior** vuelve al paso previo sin perder lo
   respondido.

![Una respuesta No con su observación y su foto](uso/us-15/checklist-respuesta-no.png)

Si falta algo, el paso no avanza y el aviso aparece bajo los botones.

![Aviso por preguntas sin responder](uso/us-15/checklist-falta-respuesta.png)

| Situación | Aviso |
|---|---|
| Una pregunta sin responder | Responde todas las preguntas antes de continuar. |
| Un No con una observación corta | Agrega una observación de al menos 10 caracteres para cada respuesta No. |
| Un No sin foto | Adjunta una foto de integridad para cada respuesta marcada como No. |
| El paso 4 sin hora de salida | Indica la hora efectiva de salida. |

**Cerrar la revisión**

En el paso 4, además de las dos preguntas:

1. Escribe la **Hora efectiva de salida** (obligatoria).
2. Agrega **Observaciones finales** si hace falta (opcional).
3. Adjunta la **Foto de fidelidad / entrega**, con el estado general de la sala
   al terminar (opcional).
4. Pulsa **Finalizar y enviar reporte**.

![Paso 4: cumplimiento y cierre](uso/us-15/checklist-cierre.png)

Aparece **Revisión finalizada** con el resumen: la sala, la hora de salida,
cuántas fotos de integridad se adjuntaron, si hay foto final y la fecha y hora
del registro. **Volver al inicio** empieza un checklist nuevo.

![Revisión finalizada](uso/us-15/checklist-finalizado.png)
