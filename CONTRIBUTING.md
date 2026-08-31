# Cómo se trabaja en este repositorio

## Ramas

`main` siempre desplegable. Una rama por carta de Trello, sacada de `main`:

```
feat/us-02-solicitud-reserva
fix/us-07-doble-aprobacion
docs/manual-despliegue
```

Nada se integra por commit directo a `main`: todo entra por pull request.

## Commits

Conventional Commits, en inglés, con el módulo como scope:

```
feat(solicitudes): add block selection to request form
fix(agenda): prevent booking a blocked slot
docs(despliegue): document cron entry for reminders
test(uso): cover check-out with missing items
```

Tipos: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.

## Pull requests

La plantilla se llena sola al abrir el PR. Un PR necesita:

1. La historia que cierra y los criterios de aceptación que cubre.
2. Una revisión aprobada de otro integrante (columna *Pair Review* del tablero).
3. El DOD marcado completo.

La carta pasa a *PO Review* cuando el PR está aprobado, y a *Done* cuando la
Product Owner valida contra los criterios de aceptación.

## Definition of Done

Una tarea está terminada cuando:

- [ ] Documentación actualizada: instrucciones de despliegue, manuales, y el documento de backlog si la historia cambió.
- [ ] Diagramas de comportamiento (secuencia) y de estructura (paquetes o componentes).
- [ ] Casos de prueba y resultados.
- [ ] Software versionado.
- [ ] Software desplegado.

## Qué no entra al repositorio

Credenciales, archivos `.env`, volcados de base de datos, datos personales
reales y documentos que ya viven en el Drive del equipo.
