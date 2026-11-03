# Sala de grabación OEV

Sistema de gestión de horarios y uso de la sala de grabación de la Oficina de
Educación Virtual, Facultad de Ciencias de la Ingeniería, UACh.

Equipo VirtuNexo — Taller de Ingeniería de Software (INFO282), 2026-2.

En producción en <https://oev.inf.uach.cl>.

## Stack

| Pieza | Decisión |
|---|---|
| Lenguaje y framework | Python 3.13, Django 5.2 |
| Base de datos | PostgreSQL 17 |
| Interfaz | Plantillas de Django servidas por el servidor, con HTMX y Alpine.js |
| Estáticos | Sin empaquetador ni compilador: nada que construir antes de desplegar |
| Tareas programadas | Comando de Django en un bucle, en el contenedor `tareas`: el servidor no tiene cron |
| Despliegue | Imagen de Docker publicada en GHCR por GitHub Actions ([`docs/despliegue.md`](docs/despliegue.md)) |
| Dependencias | `requirements.txt` (lo que va en la imagen) y `requirements-dev.txt` (más las pruebas) |
| Pruebas | pytest con pytest-django ([`docs/pruebas.md`](docs/pruebas.md)) |

## Módulos

Seis módulos de negocio, una app de Django cada uno:

| Módulo | Responsabilidad |
|---|---|
| `personas` | Usuario, rol, área, pertenencia usuario–área y sanción. Único módulo con datos personales |
| `agenda` | Bloques, bloqueos puntuales, disponibilidad y calendario |
| `solicitudes` | Solicitud, ticket, impedimentos, agrupación y resolución |
| `uso` | Confirmación, marcaje, check-out, incidentes y propuesta de sanción |
| `configuracion` | Umbrales, plazos, topes y textos editables, con bitácora de cambios |
| `notificaciones` | Plantillas de aviso, bandeja de salida e integracion con correo electronico|

## Estructura

```
src/
├── oev/                      paquete del proyecto: settings, urls, wsgi
├── <modulo>/                 una app de Django por módulo de negocio
│   ├── migrations/
│   ├── templates/<modulo>/   plantillas propias del módulo
│   ├── tests/                pruebas del módulo
│   └── management/commands/  comandos de las tareas programadas
├── templates/                base.html y parciales compartidos
└── static/                   css, js e img compartidos
```

Convenciones dentro de cada módulo:

- `models.py` guarda el estado; `services.py`, las reglas de negocio. Una vista
  no decide: llama a un servicio.
- Las dependencias entre módulos van en una sola dirección:
  `uso` → `solicitudes` → `agenda` → `personas`. `configuracion` y
  `notificaciones` las usa cualquiera y no dependen de nadie. Si necesitas una
  dependencia que cierre un ciclo, la responsabilidad quedó en el módulo
  equivocado.
- Las plantillas de un módulo viven en `<modulo>/templates/<modulo>/`, no en la
  carpeta compartida. La compartida es solo para lo que usan todos.

## Dónde está cada cosa

- **Tareas del sprint**: Trello.
- **Backlog, historias y criterios de aceptación**: planilla `UserStorys - Backlog` del Drive del equipo.
- **Documentos de entrega**: Drive del equipo.
- **Manuales, diagramas y casos de prueba**: `docs/` de este repositorio.

## Reglas del repositorio

- Nada de credenciales, ni archivos `.env`, ni volcados de base de datos.
- Nada de datos personales reales de la contraparte ni de usuarios.
- Cómo se trabaja: `CONTRIBUTING.md`.
