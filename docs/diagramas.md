# Diagramas

## Comportamiento

Cada línea de vida es una parte del código con el nombre que tiene ahí
(`<app>.views` en presentación, la app en dominio, la base o los datos de prueba
en persistencia) y el archivo que la implementa debajo; el color es su capa. Las
flechas son las llamadas del código, escritas como en la línea donde ocurren:
entre partes, la función con sus argumentos, abreviados cuando no cambian lo que
pasa (dentro de un formulario, `self.instance` es el modelo que se le pasó);
hacia la base, solo la operación SQL y la tabla que toca. Cada llamada abre una
barra de activación en quien la recibe, también cuando es de la misma parte. El
retorno lleva el nombre de la variable donde queda lo que vuelve, y lo que
vuelve de la base se rotula `fila` o `filas` aunque venga vacío: los casos
alternativos van en la guarda del `alt`, no en la flecha. Cuando lo que vuelve
decide un `alt`, cada rama lleva su propia vuelta, primero la que corta
(`False`, o `ValidationError` si una validación falla) y después la que sigue
(`True`). Lo que no devuelve nada (`save()`, un `UPDATE`) cierra su barra sin
flecha de vuelta. Una salida anticipada (un `400`, un `404`) va en un `break`.
La respuesta lleva el código HTTP y la plantilla o la dirección; `render()` y
`redirect()` no se dibujan aparte. Lo que una parte hace por dentro va como
mensaje a sí misma con la línea de código, y el porqué, en nota. Las condiciones
de `alt`, `opt`, `loop` y `break` van en español. El control de acceso por rol
(`staff_member_required`, `user_passes_test`) corre antes de cada vista y no se
repite en cada diagrama.

Cada escenario es un archivo `docs/diagramas/us-XX/<escenario>.puml`. Parte con
`@startuml <escenario>`, que le da el nombre al PNG, e incluye `../estilo.iuml`,
donde están los colores y las fuentes. La capa de cada línea de vida va como
estereotipo: `<<presentación>>`, `<<dominio>>` o `<<persistencia>>`. Para una
historia nueva conviene copiar el diagrama más parecido y adaptarlo. Se dibuja
con `plantuml -tpng docs/diagramas/us-XX/*.puml` y se suben el `.puml` y el
`.png`, con el PNG enlazado acá en una sección de su historia. Las fuentes son
Noto Sans y JetBrainsMono NF; sin ellas PlantUML usa otras y el diagrama sale
igual, con otra letra.

### Inicio de sesión (US-01)

Las cuatro puertas, `/solicitante/entrar/`, `/configuracion/entrar/`,
`/validacion/entrar/` y `/apoyo/entrar/`, son la misma vista `entrar` con otros
argumentos: cada una dice qué rol deja pasar, a qué panel lleva (`destino`) y
qué título muestra. La plantilla, la autenticación y el bloqueo son los mismos
para todas. `/login/` solo redirige a la del solicitante, para no romper enlaces
viejos. Los diagramas siguen al solicitante, que es el rol de US-01, y van
separados por cómo termina el intento: con la clave correcta, con la clave
incorrecta o con la cuenta bloqueada.

![Clave correcta](diagramas/us-01/ingreso.png)

`_puede_pasar` se revisa después de autenticar y antes de `login()`. Sin el rol
de la puerta responde el mismo error que una clave mala, sin abrir sesión y sin
sumar un intento, porque la clave era correcta (AC4).

`django.contrib.auth` busca la cuenta y revisa la clave a través de
`personas`, porque `Usuario` es el modelo de usuario del proyecto.

![Clave incorrecta y bloqueo](diagramas/us-01/intento-fallido.png)

![Cuenta bloqueada](diagramas/us-01/cuenta-bloqueada.png)

Cuando la respuesta es 200, htmx reemplaza solo el formulario y conserva el
correo escrito.

La recuperación de clave (AC6) no tiene diagrama propio: son las cuatro vistas
que trae Django (`PasswordReset`, `Done`, `Confirm` y `Complete`), con enlace
firmado y sin tabla nuestra. El proyecto solo pone las plantillas.

### Guardar los parámetros del sistema (US-04)

La bitácora de quién cambió qué es el AC4, y es lo que obliga a que el guardado
sea una transacción: unos parámetros cambiados sin su fila de bitácora son justo
lo que el criterio pide evitar.

![Guardar los parámetros](diagramas/us-04/parametros.png)

El rango se escribe una sola vez, en los validadores del modelo, y lo revisa el
servidor. La vuelta por redirección es para que recargar no reenvíe el
formulario y duplique filas en la bitácora. `changed_data` deja fuera lo que no
cambió, así que guardar sin tocar nada no ensucia el historial.

### Editar la plantilla semanal de bloques (US-04)

Un bloque es un tramo de la semana, no una fecha: el cambio vale para ese día
todas las semanas, y por eso solo se edita en la vista semanal. Agregar,
cambiar, quitar y reponer comparten vista porque las cuatro devuelven la misma
rejilla. Quitar y reponer llegan con su `accion`; agregar y cambiar son el
mismo botón, y los distingue si viene o no el `pk` del bloque. Un alta con un
día fuera de lunes a viernes no llega al formulario: la vista contesta 400.

![Agregar o cambiar un bloque](diagramas/us-04/bloque-guardar.png)

Cada respuesta es la rejilla completa: htmx reemplaza `#calendario` entero y
Alpine arranca de nuevo sobre el fragmento. Sin htmx el formulario se envía
normal y `_responder` contesta con una redirección a
`/configuracion/bloques/?vista=semana&desde=…`. Ese camino no lleva el aviso ni
el bloque elegido.

![Quitar y reponer un bloque](diagramas/us-04/bloque-quitar.png)

Quitar no pide confirmación: desactiva y ofrece deshacer después, que es más
rápido y no se pierde nada.

### Ver los bloques del día (US-14)

Los tickets todavía no existen en la base, así que `services._tickets()` los lee
de un JSON de prueba con fechas relativas a hoy. Es el único punto que sabe de
dónde vienen: cuando existan Solicitud y Ticket se cambia esa función, y ni
`bloques_del_dia()` ni `buscar()` ni las vistas se enteran. Todos los del
personal de apoyo ven todos los bloques (AC7), porque el modelo no tiene a quién
asignarlos.

![Ver los bloques del día](diagramas/us-14/bloques-del-dia.png)

Las canceladas se listan marcadas en vez de desaparecer (AC5), para que nadie se
quede esperando a alguien que ya avisó. Una fecha mal escrita en la dirección no
es un error: se muestra hoy.

### Check-out de un bloque terminado (US-14)

El botón solo aparece cuando el bloque terminó y no se canceló, y la vista
repite esa revisión. El formulario es US-15; mientras tanto, el envío se simula
y queda en la sesión.

![Entrar al check-out](diagramas/us-14/checkout-entrar.png)

![Registrar el check-out](diagramas/us-14/checkout-registrar.png)

Si registra, la vuelta es por redirección, a la lista del día del bloque.
