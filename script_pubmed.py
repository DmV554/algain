# -*- coding: utf-8 -*-
"""
Este script recolecta literatura científica relevante (artículos en PDF)
desde PubMed Central (PMC) para cada especie en nuestros esqueletos taxonómicos.

Versión 1.7: "El Contador de Resultados"
- Añadido log dentro de `search_pmc` para mostrar el recuento total ('count')
  devuelto por la API de PubMed ESearch. Esto nos ayudará a diagnosticar
  si la API realmente devuelve 0 resultados o si hay un problema al
  extraer la lista de IDs.

Versión 1.6: "Corrección del Parser XML"
- Eliminado argumento `resolve_entities=False`.

Versión 1.5: "El Verificador de Descargas"
- Mejorada `download_pdf`.

Versión 1.4: "El Detective XML"
- Añadidos logs detallados en `get_pmc_pdf_url`.
- Corregida búsqueda Prioridad 1.

Versión 1.3: "El Constructor de URLs"
- Añadida lógica para nombres de archivo PDF relativos.

Versión 1.2: "El Analizador XML Inteligente"
- Mejorada lógica `get_pmc_pdf_url`.
- Añadido log a `download_pdf`.

Versión 1.1:
- Corregido FileNotFoundError.

Versión 1.0:
- Versión inicial.
"""

import requests
import pandas as pd
import time
import sys
import os
import json
import xml.etree.ElementTree as ET
import hashlib # Para nombres de caché cortos
from urllib.parse import quote # Para codificar URL de forma estándar

# --- CONFIGURACIÓN ---
INPUT_SKELETON_FILES = [
    "worms_marine_algae_species.csv",
    "diatombase_species.csv"
]
PDF_OUTPUT_DIR = "literature_pdfs"
CACHE_DIR = "pmc_cache"
STATE_FILE = "pmc_state.json"
NCBI_API_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
API_DELAY = 0.35
SAVE_STATE_INTERVAL = 10
MAX_PAPERS_PER_SPECIES = 10
VERBOSE_XML_LOGGING = True
VERBOSE_SEARCH_LOGGING = True # <-- Nuevo log para search_pmc

# Palabras clave ampliadas
SEARCH_KEYWORDS = [
    "ecology", "morphology", "freshwater", "distribution", "taxonomy",
    "ultrastructure", "phylogeny", "bloom", "toxin", "habitat", "bioindicator"
]

# --- FUNCIONES DE INFRAESTRUCTURA ---

def setup_environment():
    """Crea los directorios necesarios."""
    os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

def save_json(filepath, data):
    data_str_keys = {str(k): v for k, v in data.items()}
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data_str_keys, f, indent=4)

def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print(f"Advertencia: Archivo JSON corrupto {filepath}", file=sys.stderr)
                return None
    return None

def get_cached_api_data(endpoint, retries=3, backoff_factor=0.5, is_xml=False):
    """Obtiene datos de la API (JSON o XML), usando un caché con hash."""
    hashed_endpoint = hashlib.md5(endpoint.encode('utf-8')).hexdigest()
    cache_filepath = os.path.join(CACHE_DIR, f"{hashed_endpoint}.{'xml' if is_xml else 'json'}")

    if os.path.exists(cache_filepath):
        with open(cache_filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content:
                 if VERBOSE_SEARCH_LOGGING or VERBOSE_XML_LOGGING: print(f"    > [LOG] Archivo de caché vacío: {cache_filepath}")
                 return None
            if is_xml:
                return content
            else:
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                     if VERBOSE_SEARCH_LOGGING or VERBOSE_XML_LOGGING: print(f"    > [LOG] Error decodificando JSON de caché: {cache_filepath}")
                     return None # Cache corrupto

    headers = {'User-Agent': 'AlgaeTaxonomyTool/LitCollector/1.7'}
    for attempt in range(retries):
        try:
            response = requests.get(endpoint, headers=headers, timeout=60)
            response.raise_for_status()
            content = response.text
            if not content:
                 if VERBOSE_SEARCH_LOGGING or VERBOSE_XML_LOGGING: print(f"    > [LOG] Respuesta vacía de API para {endpoint}. No se guarda en caché.")
                 return None
            with open(cache_filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            if is_xml:
                return content
            else:
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                     if VERBOSE_SEARCH_LOGGING or VERBOSE_XML_LOGGING: print(f"    > [LOG] Error decodificando JSON de API para {endpoint}")
                     return None # Respuesta invalida
        except requests.exceptions.HTTPError as e:
             if VERBOSE_SEARCH_LOGGING or VERBOSE_XML_LOGGING: print(f"    > [LOG] Error HTTP {e.response.status_code} para {endpoint}")
             if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                  break
             if attempt < retries - 1:
                wait_time = backoff_factor * (2 ** attempt)
                if VERBOSE_SEARCH_LOGGING or VERBOSE_XML_LOGGING: print(f"    > [LOG] Reintentando en {wait_time:.2f} segundos...")
                time.sleep(wait_time)
        except requests.exceptions.RequestException as e:
             if VERBOSE_SEARCH_LOGGING or VERBOSE_XML_LOGGING: print(f"    > [LOG] Error de red para {endpoint}: {e}")
             if attempt < retries - 1:
                wait_time = backoff_factor * (2 ** attempt)
                if VERBOSE_SEARCH_LOGGING or VERBOSE_XML_LOGGING: print(f"    > [LOG] Reintentando en {wait_time:.2f} segundos...")
                time.sleep(wait_time)

    if VERBOSE_SEARCH_LOGGING or VERBOSE_XML_LOGGING: print(f"    > [LOG] Fallaron todos los intentos para {endpoint}")
    return None


def download_pdf(url, filepath, aphia_id, pmcid):
    """Descarga un archivo PDF de forma más robusta."""
    if os.path.exists(filepath):
        try:
            existing_size = os.path.getsize(filepath)
            if existing_size > 0:
                 if VERBOSE_XML_LOGGING: print(f"    > [LOG] PDF ya existe: {filepath}")
                 return True
            else:
                 if VERBOSE_XML_LOGGING: print(f"    > [LOG] PDF existente tiene tamaño 0, reintentando descarga: {filepath}")
                 os.remove(filepath)
        except OSError as e:
             print(f"    > [LOG] Error al verificar PDF existente {filepath}: {e}", file=sys.stderr)

    downloaded_bytes = 0
    expected_bytes = None
    success = False

    try:
        if VERBOSE_XML_LOGGING: print(f"    > [LOG] Intentando descargar: {url}")
        headers = {'User-Agent': 'AlgaeTaxonomyTool/LitCollector/1.7'}
        with requests.get(url, headers=headers, stream=True, timeout=180) as response:
            response.raise_for_status()

            content_type = response.headers.get('content-type', '').lower()
            if 'pdf' not in content_type and 'octet-stream' not in content_type:
                 print(f"\n    > Advertencia: El contenido de {url} no parece ser PDF (Tipo: {content_type}). Omitiendo descarga.", file=sys.stderr)
                 return False

            content_length = response.headers.get('content-length')
            if content_length:
                try:
                    expected_bytes = int(content_length)
                    if VERBOSE_XML_LOGGING: print(f"    > [LOG] Tamaño esperado: {expected_bytes} bytes.")
                except ValueError:
                    if VERBOSE_XML_LOGGING: print(f"    > [LOG] Advertencia: Cabecera Content-Length inválida ('{content_length}').")

            temp_filepath = filepath + ".part"
            try:
                 with open(temp_filepath, 'wb') as f:
                     for chunk in response.iter_content(chunk_size=8192*2):
                         if chunk:
                             f.write(chunk)
                             downloaded_bytes += len(chunk)

                 actual_size = os.path.getsize(temp_filepath)
                 if expected_bytes is not None and actual_size != expected_bytes:
                     print(f"\n    > Error: Descarga incompleta para PMCID {pmcid}. Esperado: {expected_bytes}, Descargado: {actual_size}", file=sys.stderr)
                     os.remove(temp_filepath)
                     success = False
                 elif actual_size == 0:
                     print(f"\n    > Error: Archivo descargado para PMCID {pmcid} tiene tamaño 0.", file=sys.stderr)
                     os.remove(temp_filepath)
                     success = False
                 else:
                     os.rename(temp_filepath, filepath)
                     if VERBOSE_XML_LOGGING: print(f"    > [LOG] Archivo guardado con éxito: {filepath} ({actual_size} bytes)")
                     success = True
            except IOError as e:
                 print(f"\n    > Error de E/S al escribir archivo temporal {temp_filepath}: {e}", file=sys.stderr)
                 success = False
                 if os.path.exists(temp_filepath):
                     try: os.remove(temp_filepath)
                     except OSError: pass

    except requests.exceptions.Timeout:
         print(f"\n    > Error: Timeout durante la descarga de PMCID {pmcid} desde {url}", file=sys.stderr)
         success = False
    except requests.exceptions.HTTPError as e:
         print(f"\n    > Error HTTP {e.response.status_code} al descargar PDF PMCID {pmcid} desde {url}", file=sys.stderr)
         success = False
    except requests.exceptions.RequestException as e:
        print(f"\n    > Error general de red al descargar PDF PMCID {pmcid}: {e}", file=sys.stderr)
        success = False
    except Exception as e:
         print(f"\n    > Error inesperado durante descarga de PMCID {pmcid}: {e}", file=sys.stderr)
         success = False
    finally:
         temp_filepath = filepath + ".part"
         if not success and os.path.exists(temp_filepath):
             try: os.remove(temp_filepath)
             except OSError: pass

    return success

# --- FUNCIONES DE LA API DE PUBMED ---

def search_pmc(query):
    """Busca en PubMed Central y devuelve una lista de PMCIDs."""
    # Usar quote_plus para manejar espacios y caracteres especiales de forma estándar
    query_formatted = quote(query, safe='()[]') # No codificar paréntesis ni corchetes
    query_formatted += "+AND+pmc+open+access[filter]"
    endpoint = f"{NCBI_API_BASE_URL}esearch.fcgi?db=pmc&term={query_formatted}&retmax={MAX_PAPERS_PER_SPECIES}&retmode=json"

    if VERBOSE_SEARCH_LOGGING: print(f"    > [SEARCH_LOG] Query URL: {endpoint}")

    data = get_cached_api_data(endpoint)
    id_list = []
    count = 0

    if data and isinstance(data, dict) and 'esearchresult' in data and isinstance(data['esearchresult'], dict):
        id_list = data['esearchresult'].get('idlist', [])
        count = int(data['esearchresult'].get('count', 0)) # Obtener el recuento total
    elif data is None:
         if VERBOSE_SEARCH_LOGGING: print(f"    > [SEARCH_LOG] get_cached_api_data devolvió None.")
    else:
         if VERBOSE_SEARCH_LOGGING: print(f"    > [SEARCH_LOG] Datos inesperados recibidos: {type(data)}")

    # <<<--- NUEVO LOG --- >>>
    if VERBOSE_SEARCH_LOGGING:
        print(f"    > [SEARCH_LOG] API ESearch devolvió: Count={count}, IDs encontrados={len(id_list)}")

    return id_list


def get_pmc_pdf_url(pmcid):
    """
    Obtiene la URL de descarga del PDF para un PMCID usando un
    análisis XML más robusto (v1.6).
    """
    endpoint = f"{NCBI_API_BASE_URL}efetch.fcgi?db=pmc&id={pmcid}&rettype=OA_XML"
    xml_data = get_cached_api_data(endpoint, is_xml=True)
    if not xml_data:
        if VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] PMCID {pmcid}: No se pudo obtener el XML.")
        return None

    final_url = None
    try:
        # Usar el parser estándar
        root = ET.fromstring(xml_data)

        namespaces = {'xlink': 'http://www.w3.org/1999/xlink'}
        if VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] PMCID {pmcid}: Analizando XML...")

        # --- LÓGICA DE BÚSQUEDA MEJORADA (v1.6) ---

        # Prioridad 1: Buscar <self-uri content-type="pmc-pdf" xlink:href="..."/>
        direct_link = root.find(".//self-uri[@content-type='pmc-pdf']", namespaces)
        if direct_link is not None:
             url_part = direct_link.attrib.get('{http://www.w3.org/1999/xlink}href')
             if VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] Prioridad 1: Encontró self-uri, href='{url_part}'")
             if url_part:
                if url_part.startswith('/'): # Relativo al servidor NCBI
                    final_url = "https://www.ncbi.nlm.nih.gov" + url_part
                elif url_part.startswith('http://') or url_part.startswith('https://'): # URL Completa
                    final_url = url_part
                elif '/' not in url_part and ':' not in url_part and url_part.lower().endswith('.pdf'): # Solo nombre de archivo
                    try:
                        pmcid_num = int(pmcid)
                        final_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid_num}/pdf/{url_part}"
                    except ValueError:
                         if VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] Error: PMCID '{pmcid}' no es un número válido para construir URL.")
                         final_url = None
                else:
                    if VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] Prioridad 1: href no reconocido como URL válida: '{url_part}'")
        else:
             if VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] Prioridad 1: No se encontró <self-uri content-type='pmc-pdf'>.")

        # Prioridad 2: Si P1 falló, buscar <uri content-type="pdf" xlink:href="..."> (Formato alternativo)
        if final_url is None:
             alternative_link = root.find(".//uri[@content-type='pdf']", namespaces)
             if alternative_link is not None:
                 url_part = alternative_link.attrib.get('{http://www.w3.org/1999/xlink}href')
                 if VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] Prioridad 1.5 (uri): Encontró uri, href='{url_part}'")
                 if url_part:
                    if url_part.startswith('/'):
                        final_url = "https://www.ncbi.nlm.nih.gov" + url_part
                    elif url_part.startswith('http://') or url_part.startswith('https://'):
                        final_url = url_part
                    elif '/' not in url_part and ':' not in url_part and url_part.lower().endswith('.pdf'):
                        try:
                            pmcid_num = int(pmcid)
                            final_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid_num}/pdf/{url_part}"
                        except ValueError:
                             if VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] Error: PMCID '{pmcid}' no es un número válido para construir URL.")
                             final_url = None
                    else:
                         if VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] Prioridad 1.5: href no reconocido como URL válida: '{url_part}'")
             else:
                 if VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] Prioridad 1.5: No se encontró <uri content-type='pdf'>.")


        # Prioridad 3: Si P1 y P1.5 fallaron, buscar cualquier xlink:href ABSOLUTO que termine en .pdf
        if final_url is None:
            if VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] Iniciando Prioridad 2: Búsqueda de enlaces absolutos .pdf")
            all_links = root.findall(".//*[@xlink:href]", namespaces)
            found_links_p2 = []
            for link in all_links:
                url = link.attrib.get('{http://www.w3.org/1999/xlink}href')
                if url and url.lower().endswith('.pdf') and (url.startswith('http://') or url.startswith('https://')):
                    found_links_p2.append(url)

            if VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] Prioridad 2: Encontró {len(found_links_p2)} URLs absolutas .pdf.")
            if found_links_p2:
                final_url = found_links_p2[0] # Tomar el primero
                if VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] Prioridad 2: Seleccionada URL: {final_url}")
            elif VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] Prioridad 2: No se encontró URL absoluta .pdf válida.")


        # Prioridad 4: Si todo lo anterior falló, buscar xlink:href RELATIVO (/) que termine en .pdf
        if final_url is None:
            if VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] Iniciando Prioridad 3: Búsqueda de enlaces relativos .pdf")
            all_links = root.findall(".//*[@xlink:href]", namespaces)
            found_links_p3 = []
            for link in all_links:
                url = link.attrib.get('{http://www.w3.org/1999/xlink}href')
                if url and url.lower().endswith('.pdf') and url.startswith('/'):
                     found_links_p3.append(url)

            if VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] Prioridad 3: Encontró {len(found_links_p3)} URLs relativas .pdf.")
            if found_links_p3:
                 final_url = "https://www.ncbi.nlm.nih.gov" + found_links_p3[0] # Tomar el primero
                 if VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] Prioridad 3: Seleccionada y construida URL: {final_url}")
            elif VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] Prioridad 3: No se encontró URL relativa .pdf válida.")


    except ET.ParseError as e:
        print(f"\n    > Error analizando XML para PMCID {pmcid}: {e}", file=sys.stderr)
        return None
    except Exception as e:
         print(f"\n    > Error inesperado analizando XML para PMCID {pmcid}: {e}", file=sys.stderr)
         return None


    if VERBOSE_XML_LOGGING: print(f"    > [XML_LOG] PMCID {pmcid}: URL final devuelta: {final_url}")
    return final_url

# --- LÓGICA PRINCIPAL ---

def main():
    """Función principal del script."""
    setup_environment()

    all_species_df = pd.DataFrame()
    for file in INPUT_SKELETON_FILES:
        if os.path.exists(file):
            try:
                df = pd.read_csv(file)
                if 'AphiaID' in df.columns:
                     df['AphiaID'] = pd.to_numeric(df['AphiaID'], errors='coerce')
                     df = df.dropna(subset=['AphiaID'])
                     df['AphiaID'] = df['AphiaID'].astype('Int64')
                all_species_df = pd.concat([all_species_df, df], ignore_index=True)
            except pd.errors.EmptyDataError:
                print(f"Advertencia: Archivo {file} está vacío o corrupto. Se omitirá.", file=sys.stderr)
            except Exception as e:
                print(f"Error cargando {file}: {e}", file=sys.stderr)

    if all_species_df.empty:
        print("Error: No se pudieron cargar datos válidos de los esqueletos. Saliendo.", file=sys.stderr)
        return

    all_species_df.drop_duplicates(subset=['AphiaID'], inplace=True)
    species_to_process = all_species_df[all_species_df['AphiaID'].notna()][['AphiaID', 'scientificname']].to_dict('records')
    total_species = len(species_to_process)
    print(f"Se encontraron {total_species} especies únicas y válidas para buscar literatura.")

    state = load_json(STATE_FILE) or {'processed_aphia_ids': [], 'downloaded_pmcids': {}}
    processed_aphia_ids = set(map(int, state.get('processed_aphia_ids', [])))
    downloaded_pmcids = state.get('downloaded_pmcids', {})

    species_processed_since_save = 0

    try:
        for i, species in enumerate(species_to_process):
            try:
                aphia_id = int(species['AphiaID'])
                name = str(species['scientificname'])
                if pd.isna(name) or name.strip() == "":
                    print(f"\n({i+1}/{total_species}) Omitiendo registro con AphiaID {aphia_id} por nombre inválido.")
                    processed_aphia_ids.add(aphia_id)
                    continue
            except (ValueError, TypeError, KeyError):
                print(f"\n({i+1}/{total_species}) Omitiendo registro con formato inválido: {species}")
                try: processed_aphia_ids.add(int(species.get('AphiaID', -1)))
                except: pass
                continue

            if aphia_id in processed_aphia_ids:
                continue

            progress = f"({i+1}/{total_species})"
            print(f"\n{progress} Buscando literatura para: {name} (AphiaID: {aphia_id})")

            keyword_query = " OR ".join(f'"{k}"[Title/Abstract]' for k in SEARCH_KEYWORDS)
            # Asegurarse que el nombre no contenga caracteres que rompan la query
            safe_name = name.replace('"', '') # Quitar comillas del nombre
            specific_query = f'"{safe_name}"[Title/Abstract] AND ({keyword_query})'
            general_query = f'"{safe_name}"[Title/Abstract]'

            try:
                pmcids = search_pmc(specific_query)
                time.sleep(API_DELAY)

                if not pmcids:
                    print(f"  > Búsqueda específica sin resultados. Probando búsqueda general...")
                    pmcids = search_pmc(general_query)
                    time.sleep(API_DELAY)

                # El log de search_pmc ya imprime el count y los IDs
                # print(f"  > Se encontraron {len(pmcids)} artículos potenciales.")

                papers_downloaded_for_species = 0
                for pmcid in pmcids:
                    pmcid_str = str(pmcid)

                    if pmcid_str in downloaded_pmcids:
                        if VERBOSE_XML_LOGGING: print(f"    > [LOG] PMCID {pmcid_str} ya procesado anteriormente (Estado: {downloaded_pmcids[pmcid_str]}).")
                        if downloaded_pmcids[pmcid_str] is not None:
                             papers_downloaded_for_species += 1
                        continue


                    pdf_url = get_pmc_pdf_url(pmcid_str)
                    time.sleep(API_DELAY)

                    if pdf_url:
                        if not (pdf_url.startswith('http://') or pdf_url.startswith('https://')):
                            print(f"    > URL inválida omitida: {pdf_url}")
                            downloaded_pmcids[pmcid_str] = None
                            continue

                        filepath = os.path.join(PDF_OUTPUT_DIR, f"{aphia_id}_{pmcid_str}.pdf")
                        if download_pdf(pdf_url, filepath, aphia_id, pmcid_str):
                            downloaded_pmcids[pmcid_str] = filepath
                            papers_downloaded_for_species += 1
                        else:
                             downloaded_pmcids[pmcid_str] = None
                    else:
                        print(f"    > No se encontró URL de PDF válida en el XML para PMCID {pmcid_str}.")
                        downloaded_pmcids[pmcid_str] = None

                    if papers_downloaded_for_species >= MAX_PAPERS_PER_SPECIES:
                        print(f"  > Límite de {MAX_PAPERS_PER_SPECIES} artículos descargados alcanzado para esta especie.")
                        break
            except Exception as e:
                 print(f"\nError inesperado procesando {name} (AphiaID: {aphia_id}): {e}", file=sys.stderr)
                 state['processed_aphia_ids'] = list(map(str, processed_aphia_ids))
                 state['downloaded_pmcids'] = downloaded_pmcids
                 save_json(STATE_FILE, state)

            processed_aphia_ids.add(aphia_id)
            species_processed_since_save += 1

            if species_processed_since_save >= SAVE_STATE_INTERVAL:
                state['processed_aphia_ids'] = list(map(str, processed_aphia_ids))
                state['downloaded_pmcids'] = downloaded_pmcids
                save_json(STATE_FILE, state)
                species_processed_since_save = 0
                print("--- Progreso guardado ---")

    except KeyboardInterrupt:
        print("\n\nProceso interrumpido.")
    finally:
        print("\nGuardando estado final...")
        state['processed_aphia_ids'] = list(map(str, processed_aphia_ids))
        state['downloaded_pmcids'] = downloaded_pmcids
        save_json(STATE_FILE, state)
        print("Estado guardado. Puede reanudar la ejecución más tarde.")

    if len(processed_aphia_ids) >= total_species:
         print("\n\n¡Recolección de literatura completada!")
         successful_downloads = {k:v for k,v in downloaded_pmcids.items() if v is not None and isinstance(v, str) and os.path.exists(v)}
         final_log = {"downloaded_pdfs_log": successful_downloads}
         save_json("literature_download_log.json", final_log)
         if os.path.exists(STATE_FILE):
             try:
                 os.remove(STATE_FILE)
                 print("Archivo de estado eliminado.")
             except OSError as e:
                 print(f"Error al eliminar el archivo de estado: {e}", file=sys.stderr)
         print(f"Registro de {len(successful_downloads)} descargas exitosas guardado en literature_download_log.json.")

if __name__ == "__main__":
    main()

