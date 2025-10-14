# -*- coding: utf-8 -*-
"""
Este script es una herramienta para determinar el API_DELAY óptimo para usar
en el script principal `worms_skeleton_builder.py`.

Realiza una serie de llamadas rápidas y consecutivas a un endpoint de la API de WoRMS
y mide el tiempo de respuesta y la tasa de éxito. Esto ayuda a encontrar el
retraso mínimo posible sin sobrecargar el servidor y recibir errores.
"""

import requests
import time
import sys

# --- PARÁMETROS DE LA PRUEBA (¡Puedes modificar estos!) ---

# El AphiaID de un taxón común para usar en las pruebas.
# 124379 -> Fucus (un género común de alga parda)
TEST_APHIA_ID = 124379

# Número total de peticiones a realizar en la prueba.
# Un número alto (ej. 100) dará una mejor idea del comportamiento del servidor.
TOTAL_REQUESTS = 50

# El retraso (en segundos) que quieres probar entre cada llamada.
# Empieza con un valor bajo y auméntalo si recibes muchos errores.
# Buenos valores para probar: 0.1, 0.2, 0.25, 0.3
API_DELAY_TO_TEST = 0.5

# --- SCRIPT DE PRUEBA ---

def run_test():
    """Ejecuta la prueba de latencia contra la API de WoRMS."""
    print("--- Iniciando Prueba de Latencia de la API de WoRMS ---")
    print(f"Parámetros: {TOTAL_REQUESTS} peticiones con un retraso de {API_DELAY_TO_TEST} segundos.")
    print("-" * 50)

    endpoint = f"https://www.marinespecies.org/rest/AphiaRecordByAphiaID/{TEST_APHIA_ID}"
    headers = {'User-Agent': 'AlgaeTaxonomyTool/APITester (Python/Requests)'}
    
    success_count = 0
    failed_count = 0
    response_times = []

    for i in range(TOTAL_REQUESTS):
        start_time = time.time()
        try:
            response = requests.get(endpoint, headers=headers, timeout=15)
            # raise_for_status() lanzará una excepción para errores 4xx o 5xx.
            response.raise_for_status() 
            
            end_time = time.time()
            
            # Verificar que la respuesta es un JSON válido
            response.json()

            duration = end_time - start_time
            response_times.append(duration)
            success_count += 1
            
            sys.stdout.write(f"\rPetición {i+1}/{TOTAL_REQUESTS}: ÉXITO ({duration:.3f}s)   ")
            
        except (requests.exceptions.RequestException, requests.exceptions.HTTPError, ValueError) as e:
            failed_count += 1
            sys.stdout.write(f"\rPetición {i+1}/{TOTAL_REQUESTS}: FALLO - {type(e).__name__}   ")
        
        sys.stdout.flush()
        time.sleep(API_DELAY_TO_TEST)

    print("\n" + "-" * 50)
    print("--- Resultados de la Prueba ---")

    if not response_times:
        avg_time = float('nan')
    else:
        avg_time = sum(response_times) / len(response_times)

    success_rate = (success_count / TOTAL_REQUESTS) * 100

    print(f"Tasa de Éxito: {success_rate:.1f}% ({success_count} exitosas, {failed_count} fallidas)")
    print(f"Tiempo de Respuesta Promedio (para exitosas): {avg_time:.3f} segundos")
    
    print("\n--- Recomendación ---")
    if success_rate > 98:
        print(f"¡Excelente! Un retraso de {API_DELAY_TO_TEST}s parece ser seguro y eficiente.")
    elif success_rate > 85:
        print(f"Aceptable, pero con algunos fallos. Considera aumentar el retraso a ~{API_DELAY_TO_TEST + 0.1:.2f}s para mayor estabilidad.")
    else:
        print(f"Demasiados fallos. Aumenta significativamente el retraso. Prueba con {API_DELAY_TO_TEST * 2:.2f}s o más.")

if __name__ == "__main__":
    run_test()
