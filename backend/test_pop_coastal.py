import sys
import os
import logging

# Add parent dir to path to import backend modules
sys.path.append(os.getcwd())

from sqlalchemy.orm import Session
from database import SessionLocal
from hospital_matcher import populate_dynamic_hospitals

logging.basicConfig(level=logging.INFO)

def test_populate(district):
    print(f"--- Populating for {district} ---")
    db = SessionLocal()
    try:
        populate_dynamic_hospitals(db, district)
        print("Population call finished.")
    finally:
        db.close()

if __name__ == '__main__':
    test_populate("Mangalore")
    test_populate("Udupi")
