import requests
from bs4 import BeautifulSoup
from googlesearch import search
from typing import Optional, Dict, Any, List

def get_algaebase_image(scientific_name: str) -> Optional[Dict[str, str]]:
    """
    Fetches an image from AlgaeBase by resolving the species ID via WoRMS.
    This bypasses the need for internal search or Google scraping.
    
    Args:
        scientific_name: The scientific name to search for.
        
    Returns:
        A dictionary with image URL and source, or None.
    """
    try:
        # 1. Resolve AlgaeBase ID via WoRMS
        # First get AphiaID
        worms_url = f"https://www.marinespecies.org/rest/AphiaRecordsByMatchNames?scientificnames[]={scientific_name}&marine_only=false"
        response = requests.get(worms_url)
        if response.status_code != 200:
            return None
            
        data = response.json()
        if not data or not data[0]:
            return None
            
        aphia_id = data[0][0]['AphiaID']
        
        # Now get AlgaeBase ID
        ext_url = f"https://www.marinespecies.org/rest/AphiaExternalIDByAphiaID/{aphia_id}?type=algaebase"
        ext_response = requests.get(ext_url)
        
        if ext_response.status_code != 200:
            return None
            
        ext_ids = ext_response.json()
        if not ext_ids:
            return None
            
        # AlgaeBase ID found (e.g., "39")
        algaebase_id = ext_ids[0]
        
        # 2. Construct Direct URL
        target_url = f"https://www.algaebase.org/search/species/detail/?species_id={algaebase_id}"
        
        # 3. Scrape the page for the image
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        
        page_response = requests.get(target_url, headers=headers, timeout=10)
        page_response.raise_for_status()
        
        soup = BeautifulSoup(page_response.text, 'html.parser')
        
        # Strategy: Use Open Graph image if available (most robust)
        og_image = soup.find("meta", property="og:image")
        candidate_url = None
        
        if og_image and og_image.get("content"):
            candidate_url = og_image.get("content")
        
        # Fallback: Look for specific image classes if og:image fails
        if not candidate_url:
            images = soup.find_all('img')
            for img in images:
                src = img.get('src', '')
                if 'skindata/images' in src or 'upload/images' in src:
                    if src.startswith('/'):
                        candidate_url = f"https://www.algaebase.org{src}"
                    elif src.startswith('http'):
                        candidate_url = src
                    if candidate_url:
                        break
        
        if candidate_url:
            return {
                'url': candidate_url,
                'caption': f"Image of {scientific_name} from AlgaeBase (ID: {algaebase_id})",
                'source': 'AlgaeBase'
            }
            
        return None

    except Exception as e:
        print(f"AlgaeBase tool error: {e}")
        return None
