# Índice de Pruebas

Este documento sirve como índice centralizado para los casos de prueba y criterios de aceptación del sistema de gestión de horarios y uso de la sala de grabación de la Facultad de Ciencias de la Ingeniería, UACh.

El detalle técnico, precondiciones y el paso a paso de cada prueba se encuentran documentados en sus respectivos archivos dentro de la carpeta `tests/`.

## Historias de Usuario

| Historia | Quién la usa | Documento de pruebas |
|---|---|---|
| US-01 Inicio de sesión | Todos | [1-us-01.md](tests/1-us-01.md) |
| US-02 Solicitud de reserva | Solicitante | [1-us-02.md](tests/2-us-02.md) |
| US-03 Confirmar la asistencia | Solicitante | [1-us-03.md](tests/3-us-03.md) |
| US-04 Panel de administrador | Administrador | [1-us-04.md](tests/4-us-04.md) |
| US-07 Panel del validador | Validador | [1-us-07.md](tests/7-us-07.md) |
| US-09 Historial y retiro de solicitudes | Solicitante | [1-us-09.md](tests/9-us-09.md) |
| US-14 Bloques del personal de apoyo | Personal de apoyo | [1-us-14.md](tests/14-us-14.md) |
| US-17 Bloquear fechas de la sala | Administrador | [1-us-17.md](tests/17-us-17.md) |

## Estructura de los documentos

Cada documento enlazado en este índice sigue un formato estándar para asegurar la trazabilidad de la calidad del software:

1. **Historia de Usuario y Criterios de Aceptación (AC):** Definición del requerimiento formal.
2. **Enfoque de Pruebas:** Resumen de la estrategia aplicada a los criterios (UI, Happy Path, Casos Negativos, Seguridad).
3. **Casos de Prueba (Test Cases):**
   * **Setup (Precondiciones):** Estado necesario del sistema antes de ejecutar.
   * **Ejecución:** Pasos exactos que debe seguir el evaluador.
   * **Verificación (Oráculo):** Resultados esperados observables por el usuario o en el servidor.
   * **Teardown:** Limpieza posterior a la prueba.

> **Nota para evaluadores:** Para la correcta ejecución de los casos documentados aquí, se asume que el sistema está desplegado en un entorno local de desarrollo o pruebas controlado, tal como se especifica en el manual de despliegue.

# Estrategia y Métricas de Pruebas

Este documento define la estructura general de pruebas automatizadas y el sistema de recolección de métricas para el sistema **Sala de grabación OEV**.

## Stack de Pruebas
Las pruebas están construidas utilizando **`pytest`** y **`pytest-django`**.
- Las pruebas de cada módulo viven en su respectivo directorio `tests/` dentro de la aplicación de Django (ej. `src/solicitudes/tests/`, `src/personas/tests/`).
- La configuración base de las pruebas está definida en el archivo `pytest.ini` en la raíz del proyecto.

## Ejecución
Para ejecutar toda la batería de pruebas del proyecto, sitúate en la raíz del repositorio (donde vive `pytest.ini`) y ejecuta:

```sh
pytest
```