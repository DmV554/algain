# -*- coding: utf-8 -*-
"""
Este script construye una lista maestra de especies de algas marinas consultando
la API pública de WoRMS (World Register of Marine Species).

Versión 0.4: "El Resiliente"
- Sistema de Caché: Guarda los resultados de la API en la carpeta `worms_cache`
  para acelerar ejecuciones futuras y reducir la carga en la API.
- Reanudación de Proceso: Guarda el estado (cola de IDs por procesar y
  registros encontrados) en archivos `state_*.json`. Se puede interrumpir
  (Ctrl+C) y reanudar sin perder el progreso.
- Búsqueda Iterativa: Se reemplazó la recursión por un bucle iterativo con
  una cola explícita, lo que permite guardar y cargar el estado.
"""

import requests
import pandas as pd
import time
import sys
import os
import json
from collections import deque

# --- CONFIGURACIÓN ---
# URL base para la API de WoRMS
WORMS_API_BASE_URL = "https://www.marinespecies.org/rest"

# Nombres de los grupos para una máxima cobertura de algas marinas y cianobacterias.
STARTING_GROUP_NAMES = [
    "Cyanobacteria",   # El grupo más importante después de las diatomeas en agua dulce
    "Chlorophyta",     # Algas Verdes, extremadamente comunes
    "Dinoflagellata"           # Para capturar los dinoflagelados de agua dulce
]

# Archivos y directorios
OUTPUT_CSV_FILE = "worms_marine_algae_species.csv"
CACHE_DIR = "worms_cache"
STATE_QUEUE_FILE = "worms_state_queue.json"
STATE_RECORDS_FILE = "worms_state_records.json"

# Parámetros de ejecución
API_DELAY = 0.5
SAVE_STATE_INTERVAL = 100 # Guardar progreso cada 100 taxones procesados

# --- FUNCIONES DE INFRAESTRUCTURA ---

def setup_environment():
    """Crea los directorios necesarios si no existen."""
    os.makedirs(CACHE_DIR, exist_ok=True)

def save_json(filepath, data):
    """Guarda datos en un archivo JSON."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def load_json(filepath):
    """Carga datos desde un archivo JSON."""
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def get_cached_api_data(endpoint, retries=3, backoff_factor=0.5):
    """Obtiene datos de la API, usando un caché para evitar llamadas repetidas."""
    # Crear un nombre de archivo seguro para el caché a partir del endpoint
    cache_filename = "".join(c for c in endpoint if c.isalnum() or c in ('-', '_')).rstrip()
    cache_filepath = os.path.join(CACHE_DIR, f"{cache_filename}.json")

    # 1. Intentar leer desde el caché
    cached_data = load_json(cache_filepath)
    if cached_data is not None:
        return cached_data

    # 2. Si no está en caché, llamar a la API
    headers = {'User-Agent': 'AlgaeTaxonomyTool/0.4 (Python/Requests)'}
    for attempt in range(retries):
        try:
            response = requests.get(endpoint, headers=headers, timeout=45)
            response.raise_for_status()
            
            data = None
            if response.status_code == 204:
                data = [] # Respuesta válida sin contenido
            elif "/AphiaIDByName/" in endpoint:
                if response.text.isdigit() or (response.text.startswith('-') and response.text[1:].isdigit()):
                    data = {"id": int(response.text)} # Guardar como JSON para consistencia
                else: # Nombre no encontrado, respuesta inválida
                    data = {"id": -1}
            else:
                data = response.json()

            # 3. Guardar el resultado exitoso en el caché
            save_json(cache_filepath, data)
            return data
            
        except (requests.exceptions.RequestException, requests.exceptions.HTTPError, json.JSONDecodeError) as e:
            print(f"\nAdvertencia: Intento {attempt + 1}/{retries} falló para {endpoint}. Error: {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(backoff_factor * (2 ** attempt))

    print(f"\nError: Fallaron todos los intentos para {endpoint}. Saltando.", file=sys.stderr)
    return None # Fallo después de todos los reintentos

# --- FUNCIONES DE LA API DE WORMS ---

def get_aphia_id_by_name(name):
    """Obtiene el AphiaID para un nombre científico, usando el caché."""
    print(f"Buscando AphiaID para '{name}'...")
    endpoint = f"{WORMS_API_BASE_URL}/AphiaIDByName/{name}?marine_only=false"
    result = get_cached_api_data(endpoint)
    if result and result.get("id", -1) > 0:
        aphia_id = result["id"]
        print(f"ID encontrado para '{name}': {aphia_id}")
        return aphia_id
    else:
        print(f"No se pudo encontrar un AphiaID para '{name}'.", file=sys.stderr)
        return None

def get_aphia_record(aphia_id):
    """Obtiene el registro completo para un AphiaID."""
    endpoint = f"{WORMS_API_BASE_URL}/AphiaRecordByAphiaID/{aphia_id}"
    return get_cached_api_data(endpoint)

def get_aphia_children(aphia_id):
    """Obtiene los taxones hijos directos para un AphiaID."""
    endpoint = f"{WORMS_API_BASE_URL}/AphiaChildrenByAphiaID/{aphia_id}?marine_only=false"
    return get_cached_api_data(endpoint)

# --- LÓGICA PRINCIPAL ---

def main():
    """Función principal del script."""
    setup_environment()
    
    # Cargar estado o inicializar
    queue_data = load_json(STATE_QUEUE_FILE)
    records_data = load_json(STATE_RECORDS_FILE)
    
    if queue_data is not None and records_data is not None:
        print("Reanudando sesión anterior...")
        queue = deque(queue_data)
        all_taxa_records = records_data
        processed_ids = {record['AphiaID'] for record in all_taxa_records}
    else:
        print("Iniciando una nueva sesión...")
        queue = deque()
        all_taxa_records = []
        processed_ids = set()
        
        # Llenar la cola inicial con los AphiaIDs de los grupos de partida
        for name in STARTING_GROUP_NAMES:
            aphia_id = get_aphia_id_by_name(name)
            if aphia_id:
                queue.append(aphia_id)
            time.sleep(API_DELAY)

    # Procesar la cola
    taxa_processed_since_save = 0
    try:
        while queue:
            current_id = queue.popleft()
            
            if current_id in processed_ids:
                continue

            record = get_aphia_record(current_id)
            if not record:
                continue
            
            all_taxa_records.append(record)
            processed_ids.add(current_id)
            taxa_processed_since_save += 1
            
            # Imprimir progreso
            rank = record.get('rank', 'N/A')
            name = record.get('scientificname', 'N/A')
            sys.stdout.write(f"\rProcesando ({len(all_taxa_records)}): {rank} - {name} | Cola: {len(queue)}   ")
            sys.stdout.flush()

            # Si no es una especie, buscar a sus hijos
            if record.get('rank') != "Species":
                children = get_aphia_children(current_id)
                if children:
                    for child in children:
                        if child.get('AphiaID') not in processed_ids:
                            queue.append(child['AphiaID'])
            
            time.sleep(API_DELAY)
            
            # Guardar estado periódicamente
            if taxa_processed_since_save >= SAVE_STATE_INTERVAL:
                print("\n--- Guardando progreso... ---")
                save_json(STATE_QUEUE_FILE, list(queue))
                save_json(STATE_RECORDS_FILE, all_taxa_records)
                taxa_processed_since_save = 0
                
    except KeyboardInterrupt:
        print("\n\nProceso interrumpido por el usuario. Guardando estado final antes de salir...")
    finally:
        # Guardado final al terminar o ser interrumpido
        print("\nGuardando estado final...")
        save_json(STATE_QUEUE_FILE, list(queue))
        save_json(STATE_RECORDS_FILE, all_taxa_records)
        print("Estado guardado. Puede reanudar la ejecución más tarde.")

    # --- POST-PROCESAMIENTO FINAL ---
    if not queue:
        print("\n\n¡Búsqueda taxonómica completada! Procesando resultados finales...")
        
        df = pd.DataFrame(all_taxa_records)
        print(f"Se encontraron un total de {len(df)} registros taxonómicos.")
        
        # Filtrado final
        species_df = df[df['rank'] == 'Species'].drop_duplicates(subset=['AphiaID']).copy()
        species_df = species_df[species_df['status'] == 'accepted']
        
        print(f"Se identificaron {len(species_df)} especies únicas y aceptadas.")
        
        # Guardar CSV y limpiar
        try:
            species_df.to_csv(OUTPUT_CSV_FILE, index=False, encoding='utf-8-sig')
            print(f"\n¡Éxito! El esqueleto taxonómico ha sido guardado en: {OUTPUT_CSV_FILE}")
            
            # Limpiar archivos de estado si el proceso terminó exitosamente
            if os.path.exists(STATE_QUEUE_FILE): os.remove(STATE_QUEUE_FILE)
            if os.path.exists(STATE_RECORDS_FILE): os.remove(STATE_RECORDS_FILE)
            print("Archivos de estado temporales eliminados.")
            
        except IOError as e:
            print(f"\nError al guardar el archivo CSV: {e}")

if __name__ == "__main__":
    main()

