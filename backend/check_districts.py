import sqlite3
conn = sqlite3.connect("smartclinic_geo.db")
cur = conn.cursor()
cur.execute("SELECT district_id, district_name, latitude, longitude FROM districts WHERE district_name LIKE '%mangal%' OR district_name LIKE '%udupi%'")
rows = cur.fetchall()
print("District Table Search Results:")
for r in rows:
    print(r)
conn.close()
