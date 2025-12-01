import requests
from typing import Optional, Dict, Any, List

GBIF_API_BASE = "https://api.gbif.org/v1"

def validate_image_url(url: str) -> bool:
    """Checks if a URL is accessible (status 200)."""
    try:
        # Many servers block requests without a User-Agent
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; AlgaInfoBot/1.0)'}
        response = requests.head(url, headers=headers, timeout=3)
        return response.status_code == 200
    except requests.RequestException:
        return False

def get_gbif_info(scientific_name: str) -> Optional[Dict[str, Any]]:
    """
    Queries GBIF for species information, including backbone match and media.

    Args:
        scientific_name: The scientific name to search for.

    Returns:
        A dictionary with GBIF info and images if found, else None.
    """
    try:
        # 1. Match species name to get usageKey
        match_url = f"{GBIF_API_BASE}/species/match"
        params = {'name': scientific_name, 'kingdom': 'Plantae'} # Assuming algae are often Plantae or Chromista, but let's be broad or check response
        # Actually, algae can be in different kingdoms. Let's not restrict kingdom too much unless needed.
        params = {'name': scientific_name}
        
        response = requests.get(match_url, params=params)
        response.raise_for_status()
        match_data = response.json()

        if match_data.get('matchType') == 'NONE':
            return None

        usage_key = match_data.get('usageKey')
        if not usage_key:
            return None

        result = {
            'gbif_key': usage_key,
            'scientific_name': match_data.get('scientificName'),
            'rank': match_data.get('rank'),
            'status': match_data.get('status'),
            'images': [],
            'top_countries': []
        }

        # 2. Get Media (Images)
        media_url = f"{GBIF_API_BASE}/species/{usage_key}/media"
        media_response = requests.get(media_url)
        if media_response.status_code == 200:
            media_data = media_response.json()
            results = media_data.get('results', [])
            for item in results:
                if item.get('type') == 'StillImage':
                    img_url = item.get('identifier')
                    # Validate URL before adding
                    if img_url and validate_image_url(img_url):
                        result['images'].append({
                            'url': img_url,
                            'rights': item.get('rightsHolder') or item.get('creator'),
                            'license': item.get('license')
                        })
                        if len(result['images']) >= 5: # Limit to 5 images
                            break
        
        # 3. Get Distribution (Top Countries by Occurrence)
        occurrence_url = f"{GBIF_API_BASE}/occurrence/search"
        params = {
            'taxonKey': usage_key,
            'facet': 'country',
            'limit': 0  # We only want facets, not records
        }
        occ_response = requests.get(occurrence_url, params=params)
        if occ_response.status_code == 200:
            occ_data = occ_response.json()
            facets = occ_data.get('facets', [])
            for facet in facets:
                if facet.get('field') == 'COUNTRY':
                    # Get top 10 countries
                    counts = facet.get('counts', [])[:10]
                    for count in counts:
                        # GBIF returns country codes (e.g., 'ES'), we might want to map them to names if possible,
                        # but for now code + count is better than nothing.
                        # Note: Ideally we would use a library like pycountry or GBIF's node API to map codes.
                        result['top_countries'].append({
                            'country_code': count.get('name'),
                            'record_count': count.get('count')
                        })
        
        return result

    except requests.RequestException as e:
        print(f"GBIF API error: {e}")
        return None
