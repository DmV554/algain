import sqlite3
import os
from typing import Optional, Dict, Any

# algae.db is now inside the alga_agent package (one level up from tools)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'algae.db')

def search_local_species(scientific_name: str) -> Optional[Dict[str, Any]]:
    """
    Searches for a species in the local database 'algae.db'.

    Args:
        scientific_name: The scientific name of the species to search for.

    Returns:
        A dictionary containing taxonomy and distribution summary if found, else None.
    """
    if not os.path.exists(DB_PATH):
        print(f"Warning: Database not found at {DB_PATH}")
        return None

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Search in taxonomy table
        cursor.execute(
            "SELECT * FROM taxonomy WHERE scientific_name LIKE ?", 
            (scientific_name,)
        )
        taxon = cursor.fetchone()

        if not taxon:
            conn.close()
            return None

        taxon_dict = dict(taxon)
        aphia_id = taxon_dict['aphia_id']

        # Get distribution count
        cursor.execute(
            "SELECT COUNT(*) as count FROM distributions WHERE aphia_id = ?", 
            (aphia_id,)
        )
        dist_count = cursor.fetchone()['count']
        taxon_dict['local_distribution_records'] = dist_count

        # Get traits
        cursor.execute(
            "SELECT measurement_type, measurement_value FROM traits WHERE aphia_id = ?",
            (aphia_id,)
        )
        traits = [dict(row) for row in cursor.fetchall()]
        taxon_dict['traits'] = traits

        conn.close()
        return taxon_dict

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
