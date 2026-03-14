import sqlite3
conn = sqlite3.connect("smartclinic_geo.db")
cur = conn.cursor()
cur.execute("DELETE FROM hospitals WHERE district_name = 'Bengaluru' AND address = 'Bengaluru, Karnataka'")
deleted = cur.rowcount
conn.commit()
conn.close()
print(f"Deleted {deleted} fake Bengaluru hospitals. Real OSM data will now be fetched.")
