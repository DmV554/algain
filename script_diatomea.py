# -*- coding: utf-8 -*-
"""
Este script construye una lista maestra de especies de diatomeas consultando
la API pública de DiatomBase, que comparte la arquitectura Aphia con WoRMS.

Versión 1.0: "El Especialista en Diatomeas"
- Adaptado del constructor de WoRMS (v0.4) para funcionar con DiatomBase.
- Utiliza un único punto de partida ("Bacillariophyceae") para mapear todo el árbol.
- Sistema de Caché y Reanudación de Proceso para robustez.
- Nombres de archivo y directorios específicos para evitar conflictos.
- Configurado para incluir especies no marinas.
"""

import requests
import pandas as pd
import time
import sys
import os
import json
from collections import deque

# --- CONFIGURACIÓN ---
# URL base para la API de DiatomBase
API_BASE_URL = "https://www.diatombase.org/aphia.php?p=rest&__route__"

# Punto de partida para todas las diatomeas.
STARTING_GROUP_NAMES = ["Bacillariophyceae"]

# Archivos y directorios específicos para DiatomBase
OUTPUT_CSV_FILE = "diatombase_species.csv"
CACHE_DIR = "diatombase_cache"
STATE_QUEUE_FILE = "diatombase_state_queue.json"
STATE_RECORDS_FILE = "diatombase_state_records.json"

# Parámetros de ejecución
API_DELAY = 0.3 # Un buen punto de partida, ajústalo si es necesario
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
    cache_filename = "".join(c for c in endpoint if c.isalnum() or c in ('-', '_')).rstrip()
    cache_filepath = os.path.join(CACHE_DIR, f"{cache_filename}.json")

    cached_data = load_json(cache_filepath)
    if cached_data is not None:
        return cached_data

    headers = {'User-Agent': 'DiatomTaxonomyTool/1.0 (Python/Requests)'}
    for attempt in range(retries):
        try:
            response = requests.get(endpoint, headers=headers, timeout=45)
            response.raise_for_status()
            
            data = None
            if response.status_code == 204:
                data = []
            elif "/AphiaIDByName/" in endpoint:
                if response.text.isdigit() or (response.text.startswith('-') and response.text[1:].isdigit()):
                    data = {"id": int(response.text)}
                else:
                    data = {"id": -1}
            else:
                data = response.json()

            save_json(cache_filepath, data)
            return data
            
        except (requests.exceptions.RequestException, requests.exceptions.HTTPError, json.JSONDecodeError) as e:
            print(f"\nAdvertencia: Intento {attempt + 1}/{retries} falló para {endpoint}. Error: {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(backoff_factor * (2 ** attempt))

    print(f"\nError: Fallaron todos los intentos para {endpoint}. Saltando.", file=sys.stderr)
    return None

# --- FUNCIONES DE LA API ---

def get_aphia_id_by_name(name):
    """Obtiene el AphiaID para un nombre científico, usando el caché."""
    print(f"Buscando AphiaID para '{name}'...")
    # marine_only=false es importante para DiatomBase
    endpoint = f"{API_BASE_URL}/AphiaIDByName/{name}?marine_only=false"
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
    endpoint = f"{API_BASE_URL}/AphiaRecordByAphiaID/{aphia_id}"
    return get_cached_api_data(endpoint)

def get_aphia_children(aphia_id):
    """Obtiene los taxones hijos directos para un AphiaID."""
    endpoint = f"{API_BASE_URL}/AphiaChildrenByAphiaID/{aphia_id}?marine_only=false"
    return get_cached_api_data(endpoint)

# --- LÓGICA PRINCIPAL ---

def main():
    """Función principal del script."""
    setup_environment()
    
    queue_data = load_json(STATE_QUEUE_FILE)
    records_data = load_json(STATE_RECORDS_FILE)
    
    if queue_data is not None and records_data is not None:
        print("Reanudando sesión anterior de DiatomBase...")
        queue = deque(queue_data)
        all_taxa_records = records_data
        processed_ids = {record['AphiaID'] for record in all_taxa_records if 'AphiaID' in record and record['AphiaID']}
    else:
        print("Iniciando una nueva sesión de DiatomBase...")
        queue = deque()
        all_taxa_records = []
        processed_ids = set()
        
        for name in STARTING_GROUP_NAMES:
            aphia_id = get_aphia_id_by_name(name)
            if aphia_id:
                queue.append(aphia_id)
            time.sleep(API_DELAY)

    taxa_processed_since_save = 0
    try:
        while queue:
            current_id = queue.popleft()
            
            if current_id in processed_ids:
                continue

            record = get_aphia_record(current_id)
            if not record or not isinstance(record, dict) or 'AphiaID' not in record:
                continue
            
            all_taxa_records.append(record)
            processed_ids.add(current_id)
            taxa_processed_since_save += 1
            
            rank = record.get('rank', 'N/A')
            name = record.get('scientificname', 'N/A')
            sys.stdout.write(f"\rProcesando ({len(all_taxa_records)}): {rank} - {name} | Cola: {len(queue)}   ")
            sys.stdout.flush()

            if record.get('rank') != "Species":
                children = get_aphia_children(current_id)
                if children:
                    for child in children:
                        if child and child.get('AphiaID') and child.get('AphiaID') not in processed_ids:
                            queue.append(child['AphiaID'])
            
            time.sleep(API_DELAY)
            
            if taxa_processed_since_save >= SAVE_STATE_INTERVAL:
                print("\n--- Guardando progreso... ---")
                save_json(STATE_QUEUE_FILE, list(queue))
                save_json(STATE_RECORDS_FILE, all_taxa_records)
                taxa_processed_since_save = 0
                
    except KeyboardInterrupt:
        print("\n\nProceso interrumpido. Guardando estado final antes de salir...")
    finally:
        print("\nGuardando estado final...")
        save_json(STATE_QUEUE_FILE, list(queue))
        save_json(STATE_RECORDS_FILE, all_taxa_records)
        print("Estado guardado. Puede reanudar la ejecución más tarde.")

    if not queue:
        print("\n\n¡Búsqueda en DiatomBase completada! Procesando resultados finales...")
        
        df = pd.DataFrame(all_taxa_records)
        df.dropna(subset=['AphiaID'], inplace=True)
        print(f"Se encontraron un total de {len(df)} registros taxonómicos.")
        
        species_df = df[df['rank'] == 'Species'].drop_duplicates(subset=['AphiaID']).copy()
        species_df = species_df[species_df['status'] == 'accepted']
        
        print(f"Se identificaron {len(species_df)} especies únicas y aceptadas de diatomeas.")
        
        try:
            species_df.to_csv(OUTPUT_CSV_FILE, index=False, encoding='utf-8-sig')
            print(f"\n¡Éxito! El esqueleto de DiatomBase ha sido guardado en: {OUTPUT_CSV_FILE}")
            
            if os.path.exists(STATE_QUEUE_FILE): os.remove(STATE_QUEUE_FILE)
            if os.path.exists(STATE_RECORDS_FILE): os.remove(STATE_RECORDS_FILE)
            print("Archivos de estado temporales eliminados.")
            
        except IOError as e:
            print(f"\nError al guardar el archivo CSV: {e}")

if __name__ == "__main__":
    main()
