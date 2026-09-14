# Sala de grabación OEV

Sistema de gestión de horarios y uso de la sala de grabación de la Oficina de
Educación Virtual, Facultad de Ciencias de la Ingeniería, UACh.

Equipo Vixus — Taller de Ingeniería de Software (INFO282), 2026-2.

## Estado

Repositorio recién creado. El código todavía no existe

## Stack

| Pieza | Decisión |
|---|---|
| Lenguaje y framework | Python, Django |
| Base de datos | PostgreSQL |
| Interfaz | Plantillas de Django servidas por el servidor, con HTMX y Alpine.js cargados como archivo estático |
| Estáticos | Sin empaquetador ni compilador: nada que construir antes de desplegar |
| Tareas programadas | Comando de Django llamado desde cron |
| Dependencias | `requirements.txt` con versiones fijas |
| Pruebas | pytest con pytest-django |

Las versiones exactas se fijan contra el Python que traiga el servidor, no
contra el de la máquina de cada uno.

## Módulos

Seis módulos de negocio (Configurables), que serán una app de Django cada uno:

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
│   └── management/commands/  solo en uso y notificaciones
├── templates/                base.html y parciales compartidos
└── static/
    ├── css/
    ├── js/vendor/            htmx y alpine, servidos por nosotros
    └── img/
```

Convenciones dentro de cada módulo, cuando aparezca el código:

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
- **Diagramas y documentos de entrega**: Drive del equipo.
- **Manuales de despliegue y de uso**: `docs/` de este repositorio.

## Reglas del repositorio

- Nada de credenciales, ni archivos `.env`, ni volcados de base de datos.
- Nada de datos personales reales de la contraparte ni de usuarios.
- Cómo se trabaja: `CONTRIBUTING.md`.

Despliegue "DEBUG=1 POSTGRES_DB=oev_formulario ./.venv/bin/python src/manage.py runserver" dentro del CD
