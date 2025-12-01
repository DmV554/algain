import requests
from typing import Optional, Dict, Any

WORMS_API_URL = "https://www.marinespecies.org/rest/AphiaRecordsByMatchNames"

def search_worms_taxonomy(scientific_name: str) -> Optional[Dict[str, Any]]:
    """
    Queries the WoRMS API for taxonomic information of a species.

    Args:
        scientific_name: The scientific name to search for.

    Returns:
        A dictionary with taxonomic details if found, else None.
    """
    try:
        params = {
            'scientificnames[]': scientific_name,
            'marine_only': 'false'
        }
        response = requests.get(WORMS_API_URL, params=params)
        
        if response.status_code == 204: # No content found
            return None
            
        response.raise_for_status()
        data = response.json()

        # The API returns a list of lists (one list per input name)
        if data and len(data) > 0 and data[0]:
            # We take the first match for the first name
            match = data[0][0]
            aphia_id = match.get('AphiaID')
            
            result = {
                'aphia_id': aphia_id,
                'scientific_name': match.get('scientificname'),
                'authority': match.get('authority'),
                'status': match.get('status'),
                'rank': match.get('rank'),
                'valid_name': match.get('valid_name'),
                'valid_aphia_id': match.get('valid_AphiaID'),
                'kingdom': match.get('kingdom'),
                'phylum': match.get('phylum'),
                'class': match.get('class'),
                'order': match.get('order'),
                'family': match.get('family'),
                'genus': match.get('genus'),
                'url': match.get('url'),
                'synonyms': []
            }

            # Fetch synonyms if we have an AphiaID
            if aphia_id:
                try:
                    synonyms_url = f"https://www.marinespecies.org/rest/AphiaSynonymsByAphiaID/{aphia_id}"
                    syn_response = requests.get(synonyms_url)
                    if syn_response.status_code == 200:
                        syn_data = syn_response.json()
                        # Extract just the scientific names and authorities
                        result['synonyms'] = [
                            f"{item.get('scientificname')} {item.get('authority', '')}".strip()
                            for item in syn_data
                        ]
                except Exception as e:
                    print(f"Error fetching synonyms: {e}")
            
            return result
            
        return None

    except requests.RequestException as e:
        print(f"WoRMS API error: {e}")
        return None
