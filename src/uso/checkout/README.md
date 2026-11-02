# Check-out de la sala

Este paquete reúne la edición del listado, las validaciones de integridad,
el registro del reporte y el acceso a las evidencias.

| Archivo | Responsabilidad |
|---|---|
| `models.py` | Listado configurable, reporte y fotografías |
| `forms.py` | Validación del editor y de las respuestas y evidencias |
| `views.py` | Editor administrativo, formulario del personal de apoyo y descarga de fotos |
| `services.py` | Guardado del reporte con copia del listado original |
| `permissions.py` | Acceso según el rol del usuario |
| `tests/test_checkout.py` | Pruebas de integridad, permisos, versiones e historial |

Los recursos de la interfaz están agrupados siguiendo el descubrimiento de Django:

- Plantillas: `src/uso/templates/uso/checkout/` (`editor.html`, `preview.html`, `reporte.html`, `incidencias.html`, `_listado.html` y `_fotografia.html`).
- CSS y JavaScript: `src/uso/static/uso/checkout/`.
- Diagrama: `docs/diagramas/us-20/editar-checkout.puml`.

El paquete sigue perteneciendo a la aplicación Django `uso`. Sus migraciones
permanecen en `src/uso/migrations/`. `src/uso/models.py` expone los modelos para
que Django los descubra y conserva `listado_inicial`, usado por la migración
inicial. Las migraciones `0002` y `0003` incorporan la evidencia final, las
respuestas por pregunta y la conversión de los reportes anteriores.
La migración `0004_asistencia_y_edicion_checkout` añade asistencia, hora de salida
opcional para inasistencias, autor/fecha de edición e historial de correcciones.

Las rutas siguen siendo `/configuracion/checkout/`,
`/apoyo/checkout/<codigo>/` y `/apoyo/evidencia/<pk>/`.
El reporte filtrado está en `/apoyo/checkout/<codigo>/integridad/` y la foto
final se descarga desde `/apoyo/cierre/<pk>/foto/`, con control de acceso.
La vista previa administrativa está en `/configuracion/checkout/preview/`.
El botón **Vista previa / Probar listado** envía el borrador a una pestaña nueva
sin publicarlo. La prueba usa `CheckoutForm`, los mismos campos de la plantilla
`_listado.html` y las mismas reglas del formulario real. No crea reportes ni
guarda archivos de evidencia. El editor permanece abierto con sus cambios.
El panel diario de bloques continúa en `src/uso/views.py` y `src/uso/services.py`.
La edición se realiza en `/apoyo/checkout/<codigo>/editar/`.

## Historial administrativo y PDF

Dentro de Configuración → Check-out, las pestañas **Formulario** e **Historial**
separan el editor de los registros completados. El historial está en
`/configuracion/checkout/historial/` y solo admite usuarios de administración.

`historial.py` limita las consultas a los últimos dos meses calendario, desde
el inicio del día local de corte hasta la hora actual. Por ejemplo, el 2 de
noviembre incluye registros desde el 2 de septiembre. Si el mes de corte no
tiene ese día, se usa su último día. La ventana no borra registros ni archivos.
Se usa la fecha de registro del check-out, no la fecha de la reserva ni la de
su última edición.

Las semanas van de lunes a domingo y se muestran en orden descendente, incluyendo
las semanas vacías. Dentro de la elegida se agrupa por día, también descendente.
Cada página contiene hasta 30 registros y conserva la semana seleccionada.
La consulta usa un índice por `registrado_en` e `id` (migración `0005`) y calcula
`tiene_reporte` mediante `Exists` sobre las respuestas incumplidas. El solicitante
y el usuario que registró se muestran por separado. Las inasistencias se identifican
como tales y no se cuentan como reportes de integridad.

`pdf.py` genera el formulario completo en memoria mediante ReportLab. La ruta
`/configuracion/checkout/historial/<pk>/pdf/` exige administración y la misma
ventana de dos meses. No se guarda otra copia en disco ni se publica el archivo.
El documento contiene datos de reserva, asistencia, autor, fecha, marca de edición,
preguntas originales, respuestas, observaciones y fotos por incumplimiento, además
del cierre. En inasistencias se indica que no hubo revisión. El PDF es distinto
de la pantalla de incidencias, que incluye solo los incumplimientos.

Se incorporan las fuentes locales de `fonts/`, con sus licencias, y los colores
se leen de `marca.css`. No se necesitan descargas de fuentes al generar el PDF.
Los textos se escapan antes de componer el documento. Las imágenes se ajustan a
la página; si una evidencia antigua no está disponible se indica en el PDF sin
impedir consultar el resto del formulario.

## Almacenamiento y consulta de faltas

| Modelo | Información guardada |
|---|---|
| `Checkout` | Ticket, asistencia, copia del listado, respuestas, hora de salida si asistió, autor, cierre, foto final y datos de última edición |
| `RespuestaCheckout` | Pregunta y sección originales, cumplimiento y observación del incumplimiento |
| `FotoIntegridad` | Archivo de evidencia y vínculo al check-out y a su respuesta concreta |
| `EdicionCheckout` | Autor, fecha y estado anterior de cada corrección, con referencias a las fotografías anteriores |

Los textos y las rutas de los archivos quedan en la base de datos. Los archivos
de imagen se guardan en `MEDIA_ROOT/checkout/` (las fotos finales, en
`checkout/cierre/`). Docker conserva ese directorio en el volumen `checkoutmedia`.
Las fotografías no se guardan como base64 dentro del JSON ni se publican como
archivos estáticos. Las descargas exigen rol de apoyo o administración.

`casos_falta_integridad(checkout)` devuelve un QuerySet de respuestas con
`cumple=False`, incluyendo su fotografía y los datos del check-out. Sin argumento
permite consultar todos los incumplimientos para futuros reportes. La pantalla
de incidencias usa esta consulta y excluye las preguntas respondidas Sí. La
observación y foto de cierre son antecedentes del reporte completo, y no se
crean como una falta adicional.

La condición de incumplimiento se define en
`RespuestaCheckoutQuerySet.faltas_integridad()` e incluye asistencia. El historial
la usa mediante `Exists` y el PDF aprovecha esa anotación o la consulta del servicio.
`resumen_respuestas()` prepara las preguntas y evidencias originales para la
pantalla y el PDF, indicando las respuestas ausentes de un registro anterior en
vez de interpretarlas como incumplimientos.

Cuando hay asistencia, las observaciones finales (mínimo 10 caracteres) y la foto de cierre son
obligatorias. Las recomendaciones finales son opcionales;
el formulario no solicita recomendaciones por pregunta. La interfaz permite revisar la foto seleccionada antes
de enviar y muestra consejos de iluminación, encuadre y enfoque. No modifica
los píxeles de las fotografías.

Los reportes recopilan la observación del incumplimiento y la foto de cada
respuesta No. El campo histórico `RespuestaCheckout.recomendacion` se conserva
para no borrar datos de instalaciones previas, pero no se solicita, no se escribe
en nuevos reportes y no se muestra en el reporte de incidencias. Los parámetros
POST antiguos `recomendacion_<pregunta>` se ignoran. La copia JSON de nuevas
respuestas contiene `cumple` y `observacion`.

El número de revisión se conserva únicamente como control interno de concurrencia:
viaja en un campo oculto y permite detectar formularios desactualizados. No aparece
como versión publicada en el editor ni en la cabecera del reporte completado.
Ocultar la revisión y retirar recomendaciones por pregunta no requiere migraciones;
el registro de asistencia y las ediciones sí requieren la migración `0004`.

## Asistencia y correcciones

`AsistenciaForm` es el paso inicial, también en vista previa. Una inasistencia
crea un check-out con `asistio=False`, respuestas vacías y sin hora de salida ni
evidencias. La asistencia positiva habilita el listado y se guarda al finalizar
la revisión. No se aplican sanciones automáticas. Los registros anteriores a
`0004` se conservan con `asistio=True`.

`Checkout.puede_editar(usuario)` comprueba que el usuario sea el autor y que la
hora actual no supere `registrado_en + 10 minutos`. La vista y el servicio de
persistencia vuelven a comprobarlo en el servidor, con bloqueo de la fila.
El límite incluye exactamente el minuto 10 y no cambia tras una corrección.
Los envíos repetidos a la ruta de creación no modifican el reporte; es necesario
utilizar la acción de edición.

La edición usa el listado original (`formulario` y `revision` del registro),
precarga las respuestas y conserva las fotos cuando no se suben reemplazos.
Al guardar, actualiza las respuestas consultables, marca `editado_en` y
`editado_por`, y conserva un registro `EdicionCheckout.antes` con el estado
previo. Las imágenes anteriores se mantienen en almacenamiento para respaldar
esas referencias; no se eliminan físicamente al corregir una incidencia.

Si se cambia a inasistencia, el reporte vigente deja de incluir respuestas y
fotografías de integridad. Si se cambia a asistencia, se vuelven obligatorias
las preguntas y la evidencia final. Las dos operaciones están sujetas al mismo
plazo. Los errores de validación y los intentos fuera de plazo no crean ediciones.

La migración de datos conserva el texto y las fotos anteriores, y crea las
respuestas consultables a partir del listado que se respondió. Los reportes
anteriores sin foto final siguen disponibles; no se inventa evidencia faltante.

Para ejecutar las pruebas desde la raíz del repositorio:

```powershell
python -m pip install -r requirements-dev.txt
$env:DB_ENGINE = 'sqlite3'
python src/manage.py test uso.checkout.tests
```

`requirements-dev.txt` añade pypdf para comprobar el contenido real, las fuentes
y las páginas de los documentos de prueba. La aplicación solo necesita las
dependencias de `requirements.txt`.

El manual operativo está integrado en [docs/uso.md](../../../docs/uso.md),
el despliegue en [docs/despliegue.md](../../../docs/despliegue.md) y los casos
de prueba manuales en [docs/tests/1-us-20.md](../../../docs/tests/1-us-20.md).

La revisión de duplicaciones, referencias, compatibilidad y limpieza aplicada se
documenta en [docs/revision-us-20.md](../../../docs/revision-us-20.md).
