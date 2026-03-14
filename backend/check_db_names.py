import sqlite3
conn = sqlite3.connect("smartclinic_geo.db")
cur = conn.cursor()
cur.execute("SELECT district_id, district_name FROM districts WHERE district_name LIKE '%shiv%' OR district_name LIKE '%bang%' OR district_name LIKE '%mang%' OR district_name LIKE '%mys%' OR district_name LIKE '%hosp%'")
print("Districts in DB:")
for r in cur.fetchall():
    print(r)
conn.close()
