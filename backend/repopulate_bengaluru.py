"""
One-shot script: clears ALL existing Bengaluru/Bangalore hospital entries and
inserts a fresh set of 250 realistic hospital records spread across the city.
Run once, then restart the server.
"""
import sqlite3
import random

DB_PATH = "smartclinic_geo.db"

ALL_SPECIALIZATIONS = [
    "General Physician", "Cardiologist", "Neurologist", "Orthopedic",
    "Pediatrician", "Dermatologist", "ENT Specialist", "Ophthalmologist",
    "Gynecologist", "Oncologist", "Dentist", "Psychiatrist",
    "Diabetologist", "Urologist", "Gastroenterologist", "Pulmonologist",
    "Nephrologist", "Physiotherapist", "Homeopath", "Ayurvedic", "General Surgeon",
]

PREFIXES = [
    "Sri", "Shri", "Apollo", "Fortis", "Manipal", "Aster", "Columbia",
    "Narayana", "KIMS", "Sakra", "Medanta", "City", "General", "Government",
    "St. John's", "St. Martha's", "Seva", "Arogya", "Jeevan", "Vikram",
    "Lotus", "Sunrise", "Lifeline", "Sanjeevani", "Sparsh", "Ramanashree",
    "Sagar", "BGS", "Baptist", "Bowring", "Victoria", "Nimhans", "People Tree",
    "Jayadeva", "Malya", "Wockhardt", "HCG", "Cloudnine", "Motherhood",
    "Rainbow", "Indira", "MVJ", "BMS", "MS Ramaiah", "Vydehi", "RV", "PES",
]

SUFFIXES = [
    "Hospital", "Multispeciality Hospital", "Super Speciality Hospital",
    "Medical Centre", "Nursing Home", "Clinic", "Health Centre",
    "Polyclinic", "Eye Hospital", "Dental Clinic", "Skin Clinic",
    "Orthopaedic Centre", "Care Centre", "Maternity Home", "Heart Clinic",
    "Cancer Centre", "Children's Hospital", "Women & Children Hospital",
]

# Bengaluru city centre coordinates  
CENTER_LAT = 12.9716
CENTER_LON = 77.5946
SPREAD = 0.25  # ~28km radius for the metro

def random_specs(rng, n=5):
    pool = ALL_SPECIALIZATIONS[:]
    rng.shuffle(pool)
    return ", ".join(pool[:n])

def random_rating(rng):
    return round(rng.uniform(3.2, 4.9), 1)

def generate_hospitals(count=250):
    rng = random.Random(42)  # deterministic
    hospitals = []
    seen = set()
    attempts = 0
    while len(hospitals) < count and attempts < count * 5:
        attempts += 1
        prefix = rng.choice(PREFIXES)
        suffix = rng.choice(SUFFIXES)
        use_city = rng.random() > 0.4
        name = (
            f"{prefix} Bengaluru {suffix}" if use_city
            else f"{prefix} {suffix}"
        )
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        lat = CENTER_LAT + rng.uniform(-SPREAD, SPREAD)
        lon = CENTER_LON + rng.uniform(-SPREAD, SPREAD)
        hospitals.append({
            "name": name,
            "specs": random_specs(rng, n=rng.randint(3, 7)),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "rating": random_rating(rng),
            "doctors": rng.randint(2, 80),
        })
    return hospitals

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Delete existing Bengaluru/Bangalore entries
cur.execute("DELETE FROM hospitals WHERE district_name LIKE '%engalur%' OR district_name LIKE '%angalore%'")
deleted = cur.rowcount
print(f"Deleted {deleted} old Bengaluru/Bangalore entries.")

# Get district_id and state_id for Bengaluru
cur.execute("SELECT district_id FROM districts WHERE district_name LIKE '%engalur%' LIMIT 1")
row = cur.fetchone()
district_id = row[0] if row else 1

cur.execute("SELECT state_id FROM states WHERE state_name LIKE '%Karnataka%' LIMIT 1")
row = cur.fetchone()
state_id = row[0] if row else 1

# Insert fresh records
hospitals = generate_hospitals(250)
inserted = 0
for h in hospitals:
    try:
        cur.execute("""
            INSERT INTO hospitals
              (hospital_name, specializations, district_name, state_name,
               district_id, state_id, latitude, longitude, rating, available_doctors, address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            h["name"], h["specs"], "Bengaluru", "Karnataka",
            district_id, state_id,
            h["lat"], h["lon"], h["rating"], h["doctors"],
            "Bengaluru, Karnataka"
        ))
        inserted += 1
    except Exception as e:
        print(f"  Skip: {e}")

conn.commit()
conn.close()
print(f"Inserted {inserted} fresh Bengaluru hospitals.")
print("Done! Please restart the backend server.")
