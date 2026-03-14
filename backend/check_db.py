import sqlite3
import os

db_path = 'smartclinic_geo.db'
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('SELECT hospital_name, district_name FROM hospitals WHERE district_name LIKE "%Bangalore%" LIMIT 20')
rows = cursor.fetchall()
print(f"Showing {len(rows)} records for Bangalore:")
for r in rows:
    print(f"- {r[0]} ({r[1]})")
conn.close()
