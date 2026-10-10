import csv
import pytest
import tracemalloc
from datetime import datetime
from pathlib import Path
from django.db import connection
from django.test.utils import CaptureQueriesContext

# Política de reemplazo: Cantidad máxima de filas (tests) a conservar en el historial
MAX_RESULTADOS = 1000

# Diccionario para ir consolidando los resultados por cada test a través de sus fases
resultados_pruebas = {}

@pytest.fixture(autouse=True)
def recolectar_metricas(request):
    """
    Fixture invisible que envuelve cada test. Inicia el rastreo de memoria 
    y captura las consultas SQL efectuadas durante la prueba.
    """
    tracemalloc.start()
    with CaptureQueriesContext(connection) as ctx:
        yield  # Aquí se ejecuta el test real
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    queries = ctx.captured_queries
    total_queries = len(queries)
    
    # Cálculos de rendimiento de DB
    tiempo_db_total = sum(float(q.get('time', 0)) for q in queries)
    consulta_mas_lenta = max((float(q.get('time', 0)) for q in queries), default=0.0)
    tiempo_db_promedio = (tiempo_db_total / total_queries) if total_queries > 0 else 0.0
    
    # Detección simple de N+1 (consultas SQL exactamente idénticas)
    sql_unicos = set(q.get('sql') for q in queries)
    consultas_duplicadas = total_queries - len(sql_unicos)

    # Conteo por tipo de operación SQL (Lectura vs Escritura)
    consultas_lectura = sum(1 for q in queries if q.get('sql', '').strip().upper().startswith('SELECT'))
    consultas_escritura = sum(1 for q in queries if q.get('sql', '').strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')))

    # Inyectamos las métricas en el nodo del test
    request.node.metricas_rendimiento = {
        'consultas_db': total_queries,
        'consultas_lectura': consultas_lectura,
        'consultas_escritura': consultas_escritura,
        'tiempo_db_total_s': round(tiempo_db_total, 4),
        'tiempo_db_promedio_s': round(tiempo_db_promedio, 4),
        'consulta_mas_lenta_s': round(consulta_mas_lenta, 4),
        'consultas_duplicadas': consultas_duplicadas,
        'memoria_peak_mb': round(peak / (1024 * 1024), 3),
        'memoria_final_mb': round(current / (1024 * 1024), 3)
    }

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Atrapa el resultado de la prueba.
    """
    outcome = yield
    reporte = outcome.get_result()
    
    nodeid = item.nodeid

    if nodeid not in resultados_pruebas:
        marcadores = [m.name for m in item.iter_markers() if not m.name.startswith('_')]
        
        resultados_pruebas[nodeid] = {
            'fecha_ejecucion': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'modulo_archivo': item.fspath.basename,
            'ruta_completa': nodeid,
            'nombre_caso_prueba': item.name,
            'marcadores': ", ".join(marcadores),
            'resultado_final': 'PASSED',
            'mensaje_error': '',
            'duracion_setup': 0.0,
            'duracion_call': 0.0,
            'duracion_teardown': 0.0,
            'duracion_total': 0.0,
            'consultas_db': 0,
            'consultas_lectura': 0,
            'consultas_escritura': 0,
            'tiempo_db_total_s': 0.0,       
            'tiempo_db_promedio_s': 0.0,
            'consulta_mas_lenta_s': 0.0,    
            'consultas_duplicadas': 0,      
            'memoria_peak_mb': 0.0,
            'memoria_final_mb': 0.0
        }

    registro = resultados_pruebas[nodeid]

    if reporte.when == 'setup':
        registro['duracion_setup'] = round(reporte.duration, 4)
    elif reporte.when == 'call':
        registro['duracion_call'] = round(reporte.duration, 4)
    elif reporte.when == 'teardown':
        registro['duracion_teardown'] = round(reporte.duration, 4)
        
        metricas = getattr(item, 'metricas_rendimiento', {})
        registro['consultas_db'] = metricas.get('consultas_db', 0)
        registro['consultas_lectura'] = metricas.get('consultas_lectura', 0)
        registro['consultas_escritura'] = metricas.get('consultas_escritura', 0)
        registro['tiempo_db_total_s'] = metricas.get('tiempo_db_total_s', 0.0)
        registro['tiempo_db_promedio_s'] = metricas.get('tiempo_db_promedio_s', 0.0)
        registro['consulta_mas_lenta_s'] = metricas.get('consulta_mas_lenta_s', 0.0)
        registro['consultas_duplicadas'] = metricas.get('consultas_duplicadas', 0)
        registro['memoria_peak_mb'] = metricas.get('memoria_peak_mb', 0.0)
        registro['memoria_final_mb'] = metricas.get('memoria_final_mb', 0.0)

    registro['duracion_total'] = round(
        registro['duracion_setup'] + registro['duracion_call'] + registro['duracion_teardown'], 4
    )

    if reporte.outcome != 'passed':
        if registro['resultado_final'] != 'FAILED':
            registro['resultado_final'] = reporte.outcome.upper()
        
        if reporte.outcome == 'failed' and call.excinfo:
            error_str = str(call.excinfo.value).split('\n')[0]
            registro['mensaje_error'] = f"{call.excinfo.type.__name__}: {error_str}"

def pytest_sessionfinish(session, exitstatus):
    """
    Genera el archivo CSV consolidado aplicando la política de retención de N líneas.
    """
    if not resultados_pruebas:
        return

    directorio_actual = Path(__file__).parent
    csv_path = directorio_actual / 'pruebas.csv'
    
    campos = [
        'fecha_ejecucion', 
        'modulo_archivo', 
        'nombre_caso_prueba', 
        'resultado_final', 
        'mensaje_error', 
        'duracion_total',
        'duracion_setup', 
        'duracion_call', 
        'duracion_teardown', 
        'consultas_db',
        'consultas_lectura',
        'consultas_escritura',
        'tiempo_db_total_s',    
        'tiempo_db_promedio_s',
        'consulta_mas_lenta_s',
        'consultas_duplicadas',
        'memoria_peak_mb',
        'memoria_final_mb',
        'marcadores',
        'ruta_completa'
    ]

    historial = []

    if csv_path.exists():
        with open(csv_path, mode='r', encoding='utf-8') as archivo_csv:
            lector = csv.DictReader(archivo_csv)
            historial = list(lector)

    historial.extend(resultados_pruebas.values())
    historial = historial[-MAX_RESULTADOS:]

    with open(csv_path, mode='w', newline='', encoding='utf-8') as archivo_csv:
        escritor = csv.DictWriter(archivo_csv, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(historial)