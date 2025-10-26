# -*- coding: utf-8 -*-
"""
Este script realiza un "scraping quirúrgico" de AlgaeBase para extraer
información textual curada (descripciones, publicaciones).

Versión 1.5: "El Diagnóstico Final"
- Añadida una función de diagnóstico que guarda el HTML de las páginas
  donde el scraping falla. Si no encuentra el contenedor de resultados,
  guarda el archivo en la carpeta `debug_html` para inspección manual,
  permitiéndonos encontrar la estructura HTML correcta.

Versión 1.4: "El Depurador Transparente"
- Añadido modo de depuración (VERBOSE_LOGGING).
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import sys
import os
import json
import hashlib
import re
from difflib import SequenceMatcher

# --- CONFIGURACIÓN ---
INPUT_SKELETON_FILES = [
    "worms_marine_algae_species.csv",
    "diatombase_species.csv"
]
OUTPUT_JSON_FILE = "algaebase_text_data.json"
CACHE_DIR = "algaebase_cache"
STATE_FILE = "algaebase_state.json"
DEBUG_DIR = "debug_html" # <-- Nueva carpeta para depuración
ALGAEBASE_SEARCH_URL = "https://www.algaebase.org/search/species/"
API_DELAY = 1.0
SAVE_STATE_INTERVAL = 25
SIMILARITY_THRESHOLD = 0.85
VERBOSE_LOGGING = True

# --- FUNCIONES DE INFRAESTRUCTURA ---

def setup_environment():
    """Crea los directorios necesarios."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(DEBUG_DIR, exist_ok=True) # <-- Asegurarse de que exista

def save_json(filepath, data):
    """Guarda datos en un archivo JSON."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def load_json(filepath):
    """Carga datos desde un archivo JSON."""
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return None
    return None

def get_cached_html(url, retries=3, backoff_factor=1):
    """Obtiene el HTML de una URL, usando un caché."""
    hashed_url = hashlib.md5(url.encode('utf-8')).hexdigest()
    cache_filepath = os.path.join(CACHE_DIR, f"{hashed_url}.html")
    if os.path.exists(cache_filepath):
        if VERBOSE_LOGGING: print("    [LOG] Cargando HTML desde caché.")
        with open(cache_filepath, 'r', encoding='utf-8') as f:
            return f.read()
    if VERBOSE_LOGGING: print("    [LOG] Descargando HTML desde la web.")
    headers = {'User-Agent': 'AlgaeTaxonomyTool/AlgaeBase-Scraper/1.5 (Educational research project)'}
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            content = response.text
            with open(cache_filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return content
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                time.sleep(backoff_factor * (2 ** attempt))
    return None

# --- FUNCIONES DE SCRAPING MEJORADAS ---

def similarity(a, b):
    """Calcula la similitud entre dos cadenas de texto."""
    return SequenceMatcher(None, a, b).ratio()

def find_species_url_fuzzy(scientific_name):
    """
    Busca una especie y devuelve la URL del resultado más similar
    si supera el umbral de confianza, con guardado de HTML para depuración.
    """
    search_query = scientific_name.replace(' ', '+')
    search_url = f"{ALGAEBASE_SEARCH_URL}?name={search_query}"
    
    html = get_cached_html(search_url)
    if not html:
        if VERBOSE_LOGGING: print("    [LOG] ERROR: No se pudo obtener el HTML.")
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    best_match = {'url': None, 'score': 0.0, 'text': ''}
    
    results_container = soup.find('div', class_='searchResultsDivider')
    
    if not results_container:
        if VERBOSE_LOGGING:
            debug_filename = os.path.join(DEBUG_DIR, f"{scientific_name.replace(' ', '_')}.html")
            with open(debug_filename, 'w', encoding='utf-8') as f:
                f.write(soup.prettify())
            print(f"    [LOG] DEBUG: No se encontró 'searchResultsDivider'. HTML guardado en: {debug_filename}")
        return None
    
    if VERBOSE_LOGGING: print("    [LOG] DEBUG: Contenedor 'searchResultsDivider' encontrado.")
        
    possible_links = results_container.find_all('a', href=re.compile(r'detail/\?species_id=\d+'))
    if VERBOSE_LOGGING: print(f"    [LOG] DEBUG: Se encontraron {len(possible_links)} enlaces de especies potenciales.")
    
    for link in possible_links:
        link_text = link.get_text(strip=True)
        score = similarity(scientific_name.lower(), link_text.lower())
        if VERBOSE_LOGGING: print(f"      - Evaluando: '{link_text}' -> Puntuación: {score:.2f}")
        
        if score > best_match['score']:
            best_match['score'] = score
            best_match['url'] = f"https://www.algaebase.org{link['href']}"
            best_match['text'] = link_text
            
    if VERBOSE_LOGGING: 
        print(f"    [LOG] DEBUG: Mejor coincidencia encontrada: '{best_match['text']}' con puntuación {best_match['score']:.2f}")

    if best_match['score'] >= SIMILARITY_THRESHOLD:
        return best_match['url']
        
    return None

def extract_species_info(species_url):
    """Extrae la descripción y los detalles de publicación."""
    html = get_cached_html(species_url)
    if not html: return None
    soup = BeautifulSoup(html, 'html.parser')
    info = {}

    description_header = soup.find('h4', string='Description')
    if description_header:
        description_p = description_header.find_next_sibling('p')
        if description_p: info['description'] = description_p.get_text(strip=True)

    publication_header = soup.find('h4', string='Publication details')
    if publication_header:
        publication_p = publication_header.find_next_sibling('p')
        if publication_p: info['publication_details'] = publication_p.get_text(strip=True)
            
    return info if info else None

# --- LÓGICA PRINCIPAL ---

def main():
    """Función principal del script."""
    setup_environment()

    all_species_df = pd.DataFrame()
    for file in INPUT_SKELETON_FILES:
        if os.path.exists(file):
            df = pd.read_csv(file)
            all_species_df = pd.concat([all_species_df, df], ignore_index=True)
    
    all_species_df.drop_duplicates(subset=['AphiaID'], inplace=True)
    species_to_process = all_species_df[['AphiaID', 'scientificname']].to_dict('records')
    total_species = len(species_to_process)
    print(f"Se encontraron {total_species} especies únicas para buscar en AlgaeBase.")

    state = load_json(STATE_FILE) or {'processed_aphia_ids': []}
    processed_aphia_ids = set(state['processed_aphia_ids'])
    
    all_data = load_json(OUTPUT_JSON_FILE) or {}
    species_processed_since_save = 0
    
    try:
        for i, species in enumerate(species_to_process):
            aphia_id = int(species['AphiaID'])
            name = species['scientificname']

            if aphia_id in processed_aphia_ids:
                continue

            progress = f"({i+1}/{total_species})"
            print(f"\n{progress} Buscando en AlgaeBase: {name} (AphiaID: {aphia_id})")
            
            species_url = find_species_url_fuzzy(name)
            time.sleep(API_DELAY)

            if species_url:
                print(f"  > URL encontrada con alta similitud: {species_url}")
                extracted_info = extract_species_info(species_url)
                time.sleep(API_DELAY)
                
                if extracted_info:
                    print(f"  > Se extrajeron {len(extracted_info)} campos de información.")
                    all_data[str(aphia_id)] = {
                        "scientificname": name,
                        "algaebase_url": species_url,
                        **extracted_info
                    }
                else:
                    print("  > No se encontró información relevante en la página.")
            else:
                print("  > No se encontró URL con similitud suficiente.")

            processed_aphia_ids.add(aphia_id)
            species_processed_since_save += 1

            if species_processed_since_save >= SAVE_STATE_INTERVAL:
                state['processed_aphia_ids'] = list(processed_aphia_ids)
                save_json(STATE_FILE, state)
                save_json(OUTPUT_JSON_FILE, all_data)
                species_processed_since_save = 0
                print("--- Progreso guardado ---")

    except KeyboardInterrupt:
        print("\n\nProceso interrumpido.")
    finally:
        print("\nGuardando estado y datos finales...")
        state['processed_aphia_ids'] = list(processed_aphia_ids)
        save_json(STATE_FILE, state)
        save_json(OUTPUT_JSON_FILE, all_data)
        print("Estado y datos guardados. Puede reanudar la ejecución más tarde.")
        
    if len(processed_aphia_ids) == total_species:
        print("\n\n¡Scraping de AlgaeBase completado!")
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
            print("Archivo de estado eliminado.")

if __name__ == "__main__":
    main()

