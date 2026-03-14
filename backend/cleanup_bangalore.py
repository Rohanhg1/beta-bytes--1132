import sqlite3
import os

db_path = 'smartclinic_geo.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("DELETE FROM hospitals WHERE district_name = 'Bangalore Urban'")
conn.commit()
print(f"Deleted {cursor.rowcount} stale Bangalore facilities.")
conn.close()
