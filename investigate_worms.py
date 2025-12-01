import requests

def check_worms_external_ids(scientific_name):
    print(f"Checking WoRMS for {scientific_name}...")
    
    # 1. Get AphiaID
    url = f"https://www.marinespecies.org/rest/AphiaRecordsByMatchNames?scientificnames[]={scientific_name}&marine_only=false"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print("Error fetching species.")
            return

        data = response.json()
        if not data or not data[0]:
            print("No species found.")
            return

        record = data[0][0]
        aphia_id = record['AphiaID']
        print(f"Found AphiaID: {aphia_id}")

        # 2. Get External IDs
        ext_url = f"https://www.marinespecies.org/rest/AphiaExternalIDByAphiaID/{aphia_id}?type=algaebase"
        print(f"Querying external IDs: {ext_url}")
        
        ext_response = requests.get(ext_url)
        if ext_response.status_code == 200:
            ext_ids = ext_response.json()
            print("External IDs found:", ext_ids)
        elif ext_response.status_code == 204:
             print("No external IDs found (204).")
        else:
            print(f"Error fetching external IDs: {ext_response.status_code}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_worms_external_ids("Ulva lactuca")
    check_worms_external_ids("Padina pavonica")
