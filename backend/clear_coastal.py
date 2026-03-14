import sqlite3

conn = sqlite3.connect("smartclinic_geo.db")
cur = conn.cursor()

# We will delete ALL hospitals in Mangaluru/Mangalore so that a fresh
# accurate OSM fetch occurs without any fake generated markers in the sea.
# We also delete Udupi just in case they clicked that too.
cur.execute("DELETE FROM hospitals WHERE district_name LIKE '%mangal%' OR district_name LIKE '%udupi%'")
deleted = cur.rowcount
conn.commit()
conn.close()

print(f"Deleted {deleted} hospitals from coastal districts. Overpass will re-fetch real ones.")
