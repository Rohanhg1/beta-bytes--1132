import sqlite3
import urllib.request
import json
import ssl

def check_overpass_direct(district):
    print(f"Testing direct Overpass fetch for {district}...")
    
    # Generic approx bounding box for testing
    if district.lower() == "mangaluru":
        query = "[out:json][timeout:25];(node[\"amenity\"=\"hospital\"](12.8,74.8,12.9,74.9););out body;"
    else:
        query = "[out:json][timeout:25];(node[\"amenity\"=\"hospital\"](13.3,74.7,13.4,74.8););out body;"
        
    url = "https://overpass-api.de/api/interpreter"
    data = {"data": query}
    encoded_data = urllib.parse.urlencode(data).encode('utf-8')
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    req = urllib.request.Request(url, data=encoded_data)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
            res = json.loads(response.read().decode())
            print(f"Success! Found {len(res.get('elements', []))} elements.")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == '__main__':
    conn = sqlite3.connect('smartclinic_geo.db')
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM hospitals WHERE district_name LIKE '%udupi%'")
    print("Udupi count in DB:", cur.fetchone()[0])
    
    cur.execute("SELECT COUNT(*) FROM hospitals WHERE district_name LIKE '%mangal%'")
    print("Mangaluru count in DB:", cur.fetchone()[0])
    
    print("-" * 30)
    check_overpass_direct("Mangaluru")
