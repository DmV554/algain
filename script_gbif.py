# -*- coding: utf-8 -*-
"""
Este script enriquece los esqueletos taxonómicos (generados por los scripts de
WoRMS y DiatomBase) con datos de distribución geográfica de la API pública de GBIF
(Global Biodiversity Information Facility).

Versión 1.0: "El Cartógrafo de la Biodiversidad"
- Lee múltiples archivos CSV de entrada (esqueletos taxonómicos).
- Para cada especie, busca su 'taxonKey' en GBIF para asegurar precisión.
- Descarga registros de ocurrencia (latitud, longitud, fecha, etc.).
- Sistema de Caché: Guarda respuestas de la API en `gbif_cache`.
- Reanudación de Proceso: Guarda el progreso en `gbif_state.json` y los
  datos recolectados en `gbif_occurrences_temp.csv`. Se puede interrumpir y reanudar.
"""

import requests
import pandas as pd
import time
import sys
import os
import json

# --- CONFIGURACIÓN ---
# Archivos CSV de entrada generados por los scripts anteriores.
INPUT_SKELETON_FILES = [
    "worms_marine_algae_species.csv",
    "diatombase_species.csv"
]

# Archivos y directorios de salida y estado
OUTPUT_CSV_FILE = "gbif_occurrences.csv"
CACHE_DIR = "gbif_cache"
STATE_FILE = "gbif_state.json"
TEMP_DATA_FILE = "gbif_occurrences_temp.csv" # Guardado intermedio

# Parámetros de la API y del proceso
GBIF_API_BASE_URL = "https://api.gbif.org/v1"
API_DELAY = 0.2
SAVE_STATE_INTERVAL = 25 # Guardar progreso cada 25 especies procesadas
MAX_OCCURRENCES_PER_SPECIES = 1000 # Límite de registros a descargar por especie

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
    cache_filename = endpoint.replace(GBIF_API_BASE_URL, "").replace("/", "_").replace("?", "&")
    cache_filepath = os.path.join(CACHE_DIR, f"{cache_filename}.json")

    if os.path.exists(cache_filepath):
        return load_json(cache_filepath)

    headers = {'User-Agent': 'AlgaeTaxonomyTool/GBIF-Enricher/1.0'}
    for attempt in range(retries):
        try:
            response = requests.get(endpoint, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            save_json(cache_filepath, data)
            return data
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            print(f"\nAdvertencia: Intento {attempt + 1}/{retries} falló para {endpoint}. Error: {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(backoff_factor * (2 ** attempt))
    
    print(f"\nError: Fallaron todos los intentos para {endpoint}. Saltando.", file=sys.stderr)
    return None

# --- FUNCIONES DE LA API DE GBIF ---

def get_gbif_taxon_key(scientific_name):
    """Busca el taxonKey (usageKey) en GBIF para un nombre científico."""
    endpoint = f"{GBIF_API_BASE_URL}/species/match?name={scientific_name.replace(' ', '%20')}&rank=SPECIES"
    data = get_cached_api_data(endpoint)
    if data and data.get('matchType') != 'NONE' and 'usageKey' in data:
        return data['usageKey']
    return None

def get_gbif_occurrences(taxon_key):
    """Obtiene registros de ocurrencia para un taxonKey, manejando paginación."""
    occurrences = []
    endpoint = f"{GBIF_API_BASE_URL}/occurrence/search?taxonKey={taxon_key}&limit=300&hasCoordinate=true"
    offset = 0
    
    while len(occurrences) < MAX_OCCURRENCES_PER_SPECIES:
        paginated_endpoint = f"{endpoint}&offset={offset}"
        data = get_cached_api_data(paginated_endpoint)
        
        if not data or not data.get('results'):
            break # No hay más resultados

        results = data['results']
        occurrences.extend(results)
        
        if data.get('endOfRecords', True):
            break # GBIF indica que no hay más páginas
        
        offset += len(results)
        time.sleep(API_DELAY)

    return occurrences[:MAX_OCCURRENCES_PER_SPECIES]

# --- LÓGICA PRINCIPAL ---

def main():
    """Función principal del script."""
    setup_environment()

    # 1. Cargar y combinar los esqueletos taxonómicos
    all_species_df = pd.DataFrame()
    for file in INPUT_SKELETON_FILES:
        if os.path.exists(file):
            print(f"Cargando esqueleto: {file}")
            df = pd.read_csv(file)
            all_species_df = pd.concat([all_species_df, df], ignore_index=True)
        else:
            print(f"Advertencia: No se encontró el archivo de esqueleto {file}. Se omitirá.", file=sys.stderr)
    
    if all_species_df.empty:
        print("Error: No se encontraron datos en los archivos de esqueleto. Saliendo.", file=sys.stderr)
        return

    all_species_df.drop_duplicates(subset=['AphiaID'], inplace=True)
    species_to_process = all_species_df[['AphiaID', 'scientificname']].to_dict('records')
    total_species = len(species_to_process)
    print(f"Se encontraron {total_species} especies únicas para procesar.")

    # 2. Cargar estado o inicializar
    state = load_json(STATE_FILE)
    if state and 'processed_aphia_ids' in state:
        print("Reanudando sesión anterior...")
        processed_aphia_ids = set(state['processed_aphia_ids'])
    else:
        print("Iniciando una nueva sesión...")
        processed_aphia_ids = set()

    all_occurrences = []
    species_processed_since_save = 0
    
    # Cargar datos temporales si existen
    if os.path.exists(TEMP_DATA_FILE):
        print(f"Cargando datos de ocurrencias desde {TEMP_DATA_FILE}")
        all_occurrences = pd.read_csv(TEMP_DATA_FILE).to_dict('records')


    try:
        for i, species in enumerate(species_to_process):
            aphia_id = species['AphiaID']
            name = species['scientificname']

            if aphia_id in processed_aphia_ids:
                continue

            # --- Procesamiento por especie ---
            progress = f"({i+1}/{total_species})"
            sys.stdout.write(f"\r{progress} Procesando: {name}...")
            sys.stdout.flush()

            taxon_key = get_gbif_taxon_key(name)
            time.sleep(API_DELAY)

            if taxon_key:
                occurrences = get_gbif_occurrences(taxon_key)
                sys.stdout.write(f"\r{progress} Procesando: {name}... Encontradas {len(occurrences)} ocurrencias.      ")
                
                for occ in occurrences:
                    all_occurrences.append({
                        'AphiaID': aphia_id,
                        'scientificname': name,
                        'gbifID': occ.get('key'),
                        'decimalLatitude': occ.get('decimalLatitude'),
                        'decimalLongitude': occ.get('decimalLongitude'),
                        'eventDate': occ.get('eventDate'),
                        'countryCode': occ.get('countryCode'),
                        'gbifTaxonKey': taxon_key
                    })
            else:
                sys.stdout.write(f"\r{progress} Procesando: {name}... No se encontró en GBIF.      ")

            processed_aphia_ids.add(aphia_id)
            species_processed_since_save += 1

            # Guardar estado y datos temporales periódicamente
            if species_processed_since_save >= SAVE_STATE_INTERVAL:
                pd.DataFrame(all_occurrences).to_csv(TEMP_DATA_FILE, index=False)
                save_json(STATE_FILE, {'processed_aphia_ids': list(processed_aphia_ids)})
                species_processed_since_save = 0
                sys.stdout.write(f"\r{progress} Progreso guardado. Continuando...                                ")

    except KeyboardInterrupt:
        print("\n\nProceso interrumpido. Guardando estado final antes de salir...")
    finally:
        print("\nGuardando estado y datos finales...")
        if all_occurrences:
            pd.DataFrame(all_occurrences).to_csv(TEMP_DATA_FILE, index=False)
        save_json(STATE_FILE, {'processed_aphia_ids': list(processed_aphia_ids)})
        print("Estado guardado. Puede reanudar la ejecución más tarde.")

    # --- POST-PROCESAMIENTO FINAL ---
    if len(processed_aphia_ids) == total_species:
        print("\n\n¡Enriquecimiento geográfico completado! Generando archivo final...")
        
        final_df = pd.DataFrame(all_occurrences)
        print(f"Se recolectaron un total de {len(final_df)} registros de ocurrencia.")
        
        try:
            final_df.to_csv(OUTPUT_CSV_FILE, index=False, encoding='utf-8-sig')
            print(f"\n¡Éxito! Los datos de ocurrencia han sido guardados en: {OUTPUT_CSV_FILE}")
            
            # Limpiar archivos de estado y temporales
            if os.path.exists(STATE_FILE): os.remove(STATE_FILE)
            if os.path.exists(TEMP_DATA_FILE): os.remove(TEMP_DATA_FILE)
            print("Archivos de estado y temporales eliminados.")
            
        except IOError as e:
            print(f"\nError al guardar el archivo CSV final: {e}")

if __name__ == "__main__":
    main()
