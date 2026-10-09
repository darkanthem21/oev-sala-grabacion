import csv
import pytest
from datetime import datetime
from pathlib import Path

# Política de reemplazo: Cantidad máxima de filas (tests) a conservar en el historial
MAX_RESULTADOS = 500

# Diccionario para ir consolidando los resultados por cada test a través de sus fases
resultados_pruebas = {}

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Atrapa el resultado de la prueba. 
    Pytest llama a este hook 3 veces por test (setup, call, teardown).
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
            'duracion_total': 0.0
        }

    registro = resultados_pruebas[nodeid]

    if reporte.when == 'setup':
        registro['duracion_setup'] = round(reporte.duration, 4)
    elif reporte.when == 'call':
        registro['duracion_call'] = round(reporte.duration, 4)
    elif reporte.when == 'teardown':
        registro['duracion_teardown'] = round(reporte.duration, 4)

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