import requests
from typing import Optional, Dict, Any, List

ZENODO_API_URL = "https://zenodo.org/api/records"

def get_zenodo_images(scientific_name: str) -> Optional[List[Dict[str, str]]]:
    """
    Searches Zenodo for images (figures, plates) associated with a species.
    This covers Plazi treatments and other scientific uploads.

    Args:
        scientific_name: The scientific name to search for.

    Returns:
        A list of dictionaries containing image URLs and captions.
    """
    try:
        # Search for the species name and ensure it has image files
        # We use strict quoting for the name to avoid partial matches
        query = f'"{scientific_name}" AND resource_type.type:image'
        
        params = {
            'q': query,
            'size': 20,  # Fetch more to allow filtering
            'sort': 'mostrecent'
        }
        
        response = requests.get(ZENODO_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        hits = data.get('hits', {}).get('hits', [])
        candidates = []
        
        # Keywords for scoring
        # Penalty: likely charts/graphs
        penalty_keywords = ['plot', 'graph', 'chart', 'histogram', 'absorbance', 'growth', 'concentration', 'spectrum', 'mean', 'deviation', 'data', 'curve']
        # Bonus: likely morphological/taxonomic images
        bonus_keywords = ['habitus', 'thallus', 'cell', 'micrograph', 'section', 'transverse', 'longitudinal', 'holotype', 'specimen', 'drawing', 'plate', 'morphology', 'anatomy']

        for hit in hits:
            title = hit.get('metadata', {}).get('title', 'Scientific Figure')
            description = hit.get('metadata', {}).get('description', '')
            full_text = (title + " " + description).lower()
            
            # Calculate Score
            score = 0
            if any(k in full_text for k in penalty_keywords):
                score -= 10
            if any(k in full_text for k in bonus_keywords):
                score += 5
            
            # If score is too low (likely a chart), skip unless we are desperate
            if score < -5:
                continue

            files = hit.get('files', [])
            
            # Find the image file in the record
            for file in files:
                file_type = file.get('type', '').lower()
                filename = file.get('key', '').lower()
                
                # Check if it's an image
                if file_type in ['png', 'jpg', 'jpeg', 'gif'] or \
                   filename.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    
                    # Zenodo file links are in 'links' -> 'self'
                    img_url = file.get('links', {}).get('self')
                    
                    if img_url:
                        candidates.append({
                            'url': img_url,
                            'caption': title,
                            'source': 'Zenodo',
                            'score': score
                        })
                        # Only take one image per record
                        break
        
        # Sort candidates by score (descending)
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Return top 5
        return candidates[:5] if candidates else None

    except requests.RequestException as e:
        print(f"Zenodo API error: {e}")
        return None
