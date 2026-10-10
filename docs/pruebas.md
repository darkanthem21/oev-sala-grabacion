# Índice de Pruebas

Este documento sirve como índice centralizado para los casos de prueba y criterios de aceptación del sistema de gestión de horarios y uso de la sala de grabación de la Facultad de Ciencias de la Ingeniería, UACh.

El detalle técnico, precondiciones y el paso a paso de cada prueba se encuentran documentados en sus respectivos archivos dentro de la carpeta `tests/`.

## Historias de Usuario

| Historia | Quién la usa | Documento de pruebas |
|---|---|---|
| US-01 Inicio de sesión | Todos | [1-us-01.md](tests/1-us-01.md) |
| US-02 Solicitud de reserva | Solicitante | [1-us-02.md](tests/1-us-02.md) |
| US-04 Panel de administrador | Administrador | [1-us-04.md](tests/1-us-04.md) |
| US-07 Panel del validador | Validador | [1-us-07.md](tests/1-us-07.md) |
| US-09 Historial y retiro de solicitudes | Solicitante | [1-us-09.md](tests/1-us-09.md) |
| US-14 Bloques del personal de apoyo | Personal de apoyo | [1-us-14.md](tests/1-us-14.md) |
| US-17 Bloquear fechas de la sala | Administrador | [1-us-17.md](tests/1-us-17.md) |

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

## Visualización y Auditoría de Métricas (`view_tests.py`)

Para complementar la ejecución automatizada con `pytest` y `pytest-django`, el proyecto incluye una herramienta interactiva en consola para auditar el rendimiento y la salud del código a lo largo del tiempo.

### Almacenamiento Local de Datos

Cada vez que ejecutas la batería de pruebas desde la raíz del repositorio, un interceptor oculto captura métricas de rendimiento (tiempos de ejecución por fases, volumen SQL, consultas duplicadas y consumo de memoria RAM) y las anota en el archivo `src/pruebas.csv`.

Este archivo tiene un carácter estrictamente **local e individual para cada desarrollador**. No se sube al repositorio (Git). Esto se decide por tres razones fundamentales:

* **Contexto de hardware:** Los tiempos de ejecución varían drásticamente entre el equipo de un desarrollador y otro, por lo que cruzar estas métricas invalidaría la base de comparación.
* **Estado del entorno:** El volumen de datos locales y la concurrencia de la máquina afectan la latencia de las consultas SQL, haciendo que la métrica de rendimiento de la base de datos sea relativa al entorno.
* **Aislamiento de experimentación:** El objetivo principal es que el desarrollador compare su propio código base histórico contra el código en el que está trabajando actualmente (antes de hacer un *commit*). Si un desarrollador introduce accidentalmente un problema N+1, su métrica individual lo alertará de inmediato.

### Uso de la Herramienta

Para abrir la interfaz de auditoría, sitúate en la raíz del proyecto y ejecuta:

```sh
python src/view_tests.py

```

El script procesará el histórico del archivo `.csv` y presentará un menú interactivo. Al seleccionar una métrica, la consola desplegará una línea de tiempo para cada caso de prueba.

La herramienta está diseñada para no requerir esfuerzo cognitivo al auditar:

* **Ordenamiento estructurado:** Los datos se agrupan por nombre del caso de prueba y se ordenan cronológicamente en bloques delimitados.
* **Destacado automático:** La ejecución más reciente de cada prueba se identifica con una flecha (`->`) y texto cyan. Tu mirada siempre sabrá cuál es el estado actual frente a los registros anteriores en gris.
* **Precisión y visualización combinadas:** Cada línea muestra los valores numéricos exactos seguidos de una barra de proporción ASCII.
* **Semántica de colores:** Las barras apiladas utilizan colores para segmentar datos (ej. amarillo para *Setup*, verde para *Call*, magenta para *Teardown*) y alertan en rojo cuando existen problemas graves (como consultas duplicadas o alta retención de memoria que indique fugas).