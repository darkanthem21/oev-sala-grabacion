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

- Plantillas: `src/uso/templates/uso/checkout/` (`editor.html` y `reporte.html`).
- CSS y JavaScript: `src/uso/static/uso/checkout/`.
- Diagrama: `docs/diagramas/us-20/editar-checkout.puml`.

El paquete sigue perteneciendo a la aplicación Django `uso`. Sus migraciones
permanecen en `src/uso/migrations/`. `src/uso/models.py` expone los modelos para
que Django los descubra y conserva `listado_inicial`, usado por la migración
inicial. La reorganización no requiere cambios en las tablas ni nuevas migraciones.

Las rutas siguen siendo `/configuracion/checkout/`,
`/apoyo/checkout/<codigo>/` y `/apoyo/evidencia/<pk>/`.
El panel diario de bloques continúa en `src/uso/views.py` y `src/uso/services.py`.

Para ejecutar las pruebas desde la raíz del repositorio:

```powershell
$env:DB_ENGINE = 'sqlite3'
python src/manage.py test uso.checkout.tests
```
