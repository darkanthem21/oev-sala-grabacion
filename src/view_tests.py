import csv
import os
from pathlib import Path

# Códigos ANSI para colores en consola
COLOR_RESET = "\033[0m"
COLOR_DESTACADO = "\033[1;36m" # Cyan (Última ejecución / Lecturas)
COLOR_ALERTA = "\033[1;31m"    # Rojo (Escrituras / Lento / Duplicados / Fugas)
COLOR_OK = "\033[1;32m"        # Verde (Call / Resto / Únicas / Liberada)
COLOR_GRIS = "\033[90m"        # Gris (Vacío / Contexto)
COLOR_AMARILLO = "\033[1;33m"  # Amarillo (Setup / Otras)
COLOR_MAGENTA = "\033[1;35m"   # Magenta (Teardown / Memoria Final)

def cargar_datos():
    ruta_csv = Path(__file__).parent / 'pruebas.csv'
    if not ruta_csv.exists():
        print(f"{COLOR_ALERTA}No se encontró el archivo {ruta_csv}. Ejecuta los tests primero.{COLOR_RESET}")
        return None

    filas = []
    with open(ruta_csv, mode='r', encoding='utf-8') as f:
        lector = csv.DictReader(f)
        for fila in lector:
            filas.append(fila)
            
    # Ordenar primero por nombre del test (agrupación) y luego por fecha (cronología)
    filas_ordenadas = sorted(filas, key=lambda x: (x['nombre_caso_prueba'], x['fecha_ejecucion']))
    return filas_ordenadas

def obtener_ultimas_ejecuciones(filas):
    """Mapea el nombre del test con su timestamp más reciente para destacarlo."""
    ultimas = {}
    for f in filas:
        ultimas[f['nombre_caso_prueba']] = f['fecha_ejecucion']
    return ultimas

def barra_proporcional_ascii(segmentos, max_total, ancho=30):
    """Genera una barra apilada proporcional recibiendo una lista de tuplas (valor, color)."""
    if max_total <= 0:
        return f"{COLOR_GRIS}" + ("░" * ancho) + f"{COLOR_RESET}"
        
    barra = ""
    pos_acumulada = 0
    acumulado_valor = 0
    
    for valor, color in segmentos:
        if valor <= 0:
            continue
        acumulado_valor += valor
        proporcion = min(acumulado_valor / max_total, 1.0)
        pos_actual = int(round(proporcion * ancho))
        longitud = pos_actual - pos_acumulada
        
        if longitud > 0:
            barra += f"{color}{'█' * longitud}"
        pos_acumulada = pos_actual
        
    len_empty = ancho - pos_acumulada
    if len_empty > 0:
        barra += f"{COLOR_GRIS}{'░' * len_empty}"
        
    return barra + COLOR_RESET

def imprimir_separador(test_anterior, test_actual):
    if test_anterior and test_anterior != test_actual:
        print(f"{COLOR_GRIS}{'-'*130}{COLOR_RESET}")

def imprimir_fila(fecha, test, ultimas, metricas_str, barra):
    es_ultima = (fecha == ultimas[test])
    color = COLOR_DESTACADO if es_ultima else COLOR_RESET
    marcador = "-> " if es_ultima else "   "
    identificador = f"{fecha} | {test.ljust(45)}"
    print(f"{color}{marcador}{identificador} | {metricas_str} | {barra}")

def representar_duracion(filas):
    print(f"\n{COLOR_DESTACADO}--- AUDITORÍA DE DURACIÓN TOTAL DE TESTS ---{COLOR_RESET}")
    print(f"Leyenda Fases: [ {COLOR_AMARILLO}█ Setup{COLOR_RESET} | {COLOR_OK}█ Call{COLOR_RESET} | {COLOR_MAGENTA}█ Teardown{COLOR_RESET} | {COLOR_GRIS}░ Escala{COLOR_RESET} ]\n")
    
    max_tiempo = max((float(f.get('duracion_total', 0)) for f in filas), default=1)
    ultimas = obtener_ultimas_ejecuciones(filas)
    test_anterior = None

    for f in filas:
        test, fecha = f['nombre_caso_prueba'], f['fecha_ejecucion']
        imprimir_separador(test_anterior, test)
        test_anterior = test

        tiempo = float(f.get('duracion_total', 0))
        setup = float(f.get('duracion_setup', 0))
        call = float(f.get('duracion_call', 0))
        teardown = float(f.get('duracion_teardown', 0))
        
        segmentos = [(setup, COLOR_AMARILLO), (call, COLOR_OK), (teardown, COLOR_MAGENTA)]
        barra = barra_proporcional_ascii(segmentos, max_tiempo)
        
        # Detalle exacto de cada valor
        detalle = f"Tot: {tiempo:5.2f}s [{COLOR_AMARILLO}S: {setup:4.2f}s{COLOR_RESET} | {COLOR_OK}C: {call:4.2f}s{COLOR_RESET} | {COLOR_MAGENTA}T: {teardown:4.2f}s{COLOR_RESET}]"
        imprimir_fila(fecha, test, ultimas, detalle, barra)

def representar_volumen_sql(filas):
    print(f"\n{COLOR_DESTACADO}--- AUDITORÍA DE VOLUMEN SQL (LECTURA VS ESCRITURA) ---{COLOR_RESET}")
    print(f"Leyenda SQL: [ {COLOR_DESTACADO}█ Lecturas{COLOR_RESET} | {COLOR_ALERTA}█ Escrituras{COLOR_RESET} | {COLOR_AMARILLO}█ Otras{COLOR_RESET} | {COLOR_GRIS}░ Escala{COLOR_RESET} ]\n")
    
    max_total = max((int(f.get('consultas_db', 0)) for f in filas), default=1)
    ultimas = obtener_ultimas_ejecuciones(filas)
    test_anterior = None

    for f in filas:
        test, fecha = f['nombre_caso_prueba'], f['fecha_ejecucion']
        imprimir_separador(test_anterior, test)
        test_anterior = test

        lecturas = int(f.get('consultas_lectura', 0))
        escrituras = int(f.get('consultas_escritura', 0))
        total = int(f.get('consultas_db', 0))
        otras = total - lecturas - escrituras
        
        segmentos = [(lecturas, COLOR_DESTACADO), (escrituras, COLOR_ALERTA), (otras, COLOR_AMARILLO)]
        barra = barra_proporcional_ascii(segmentos, max_total)
        
        # Detalle exacto de cada valor
        detalle = f"Tot: {total:4d} [{COLOR_DESTACADO}Lec: {lecturas:3d}{COLOR_RESET} | {COLOR_ALERTA}Esc: {escrituras:3d}{COLOR_RESET} | {COLOR_AMARILLO}Otr: {otras:3d}{COLOR_RESET}]"
        imprimir_fila(fecha, test, ultimas, detalle, barra)

def representar_rendimiento_db(filas):
    print(f"\n{COLOR_DESTACADO}--- AUDITORÍA DE RENDIMIENTO DE BASE DE DATOS ---{COLOR_RESET}")
    print(f"Leyenda Tiempos: [ {COLOR_ALERTA}█ Consulta Más Lenta{COLOR_RESET} | {COLOR_OK}█ Resto del Tiempo{COLOR_RESET} | {COLOR_GRIS}░ Escala{COLOR_RESET} ]\n")
    
    max_tiempo = max((float(f.get('tiempo_db_total_s', 0)) for f in filas), default=1)
    ultimas = obtener_ultimas_ejecuciones(filas)
    test_anterior = None

    for f in filas:
        test, fecha = f['nombre_caso_prueba'], f['fecha_ejecucion']
        imprimir_separador(test_anterior, test)
        test_anterior = test

        tiempo_total = float(f.get('tiempo_db_total_s', 0))
        lenta = float(f.get('consulta_mas_lenta_s', 0))
        resto = max(tiempo_total - lenta, 0) # Prevenir floats negativos mínimos
        
        segmentos = [(lenta, COLOR_ALERTA), (resto, COLOR_OK)]
        barra = barra_proporcional_ascii(segmentos, max_tiempo)
        
        # Detalle exacto de cada valor
        detalle = f"Tot: {tiempo_total:6.3f}s [{COLOR_ALERTA}Lenta: {lenta:5.3f}s{COLOR_RESET} | {COLOR_OK}Resto: {resto:5.3f}s{COLOR_RESET}]"
        imprimir_fila(fecha, test, ultimas, detalle, barra)

def representar_duplicadas(filas):
    print(f"\n{COLOR_DESTACADO}--- AUDITORÍA DE CONSULTAS DUPLICADAS (N+1) ---{COLOR_RESET}")
    print(f"Leyenda Salud: [ {COLOR_OK}█ Consultas Únicas{COLOR_RESET} | {COLOR_ALERTA}█ Consultas Duplicadas{COLOR_RESET} | {COLOR_GRIS}░ Escala{COLOR_RESET} ]\n")
    
    max_total = max((int(f.get('consultas_db', 0)) for f in filas), default=1)
    ultimas = obtener_ultimas_ejecuciones(filas)
    test_anterior = None

    for f in filas:
        test, fecha = f['nombre_caso_prueba'], f['fecha_ejecucion']
        imprimir_separador(test_anterior, test)
        test_anterior = test

        total = int(f.get('consultas_db', 0))
        duplicadas = int(f.get('consultas_duplicadas', 0))
        unicas = total - duplicadas
        
        segmentos = [(unicas, COLOR_OK), (duplicadas, COLOR_ALERTA)]
        barra = barra_proporcional_ascii(segmentos, max_total)
        
        color_dupl = COLOR_ALERTA if duplicadas > 0 else COLOR_OK
        # Detalle exacto de cada valor
        detalle = f"Tot: {total:4d} [{COLOR_OK}Únicas: {unicas:3d}{COLOR_RESET} | {color_dupl}Dupl: {duplicadas:3d}{COLOR_RESET}]"
        imprimir_fila(fecha, test, ultimas, detalle, barra)

def representar_memoria(filas):
    print(f"\n{COLOR_DESTACADO}--- AUDITORÍA DE CONSUMO DE MEMORIA RAM ---{COLOR_RESET}")
    print(f"Leyenda Memoria: [ {COLOR_MAGENTA}█ Retenida (Final){COLOR_RESET} | {COLOR_OK}█ Liberada{COLOR_RESET} | {COLOR_GRIS}░ Escala{COLOR_RESET} ]\n")
    
    max_peak = max((float(f.get('memoria_peak_mb', 0)) for f in filas), default=1)
    ultimas = obtener_ultimas_ejecuciones(filas)
    test_anterior = None

    for f in filas:
        test, fecha = f['nombre_caso_prueba'], f['fecha_ejecucion']
        imprimir_separador(test_anterior, test)
        test_anterior = test

        peak = float(f.get('memoria_peak_mb', 0))
        final = float(f.get('memoria_final_mb', 0))
        liberada = max(peak - final, 0)
        
        color_final = COLOR_ALERTA if (final > peak * 0.5 and peak > 0) else COLOR_MAGENTA
        segmentos = [(final, color_final), (liberada, COLOR_OK)]
        barra = barra_proporcional_ascii(segmentos, max_peak)
        
        # Detalle exacto de cada valor
        detalle = f"Peak: {peak:6.2f}MB [{color_final}Fin: {final:6.2f}MB{COLOR_RESET} | {COLOR_OK}Lib: {liberada:6.2f}MB{COLOR_RESET}]"
        imprimir_fila(fecha, test, ultimas, detalle, barra)

def menu():
    filas = cargar_datos()
    if not filas:
        return

    while True:
        print(f"\n{COLOR_GRIS}=========================================================================================================================={COLOR_RESET}")
        print("                                   AUDITORÍA DE MÉTRICAS DE TESTS (HISTÓRICO VS ACTUAL)")
        print(f"{COLOR_GRIS}=========================================================================================================================={COLOR_RESET}")
        print("1. Duración de los Tests (Rendimiento general y Fases)")
        print("2. Volumen SQL (Lecturas vs Escrituras)")
        print("3. Tiempos de Base de Datos (Cuellos de botella)")
        print("4. Consultas Duplicadas (Detección problema N+1)")
        print("5. Consumo de Memoria RAM (Posibles Memory Leaks)")
        print("6. Salir")
        
        opcion = input("\nElige una métrica a visualizar (1-6): ")
        
        if opcion == '1': representar_duracion(filas)
        elif opcion == '2': representar_volumen_sql(filas)
        elif opcion == '3': representar_rendimiento_db(filas)
        elif opcion == '4': representar_duplicadas(filas)
        elif opcion == '5': representar_memoria(filas)
        elif opcion == '6':
            print("Saliendo de la auditoría...")
            break
        else:
            print(f"{COLOR_ALERTA}Opción no válida. Intenta de nuevo.{COLOR_RESET}")

if __name__ == "__main__":
    os.system('color') # Habilita colores ANSI nativos si se ejecuta en terminales Windows
    menu()