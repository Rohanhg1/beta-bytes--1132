"""
SmartClinic GeoVoice Receptionist - FastAPI Backend
Main application with all API endpoints for India map + voice integration.
"""

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import re
from datetime import datetime, timedelta

from database import engine, get_db, Base
from models import State, District, Hospital, Appointment, Receptionist
from schemas import (
    StateOut, DistrictOut, 
    HospitalCreate, HospitalUpdate, HospitalOut, HospitalMapOut,
    AppointmentCreate, AppointmentOut,
    ReceptionistCreate, ReceptionistLogin, TokenOut, ReceptionistOut,
    VoiceTextInput, VoiceBookingResponse, ExtractedIntent,
)
from auth import (
    hash_password, verify_password, create_access_token,
    get_current_receptionist,
)
from intent_extractor import extract_intent
from hospital_matcher import get_best_hospital, find_matching_hospitals, suggest_time_for_appointment, populate_dynamic_hospitals, _POPULATED_DISTRICTS, resolve_canonical_district
import threading
from email_service import send_appointment_email, send_cancellation_email
from seed_data import seed_states_districts, seed_hospitals

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SmartClinic GeoVoice Receptionist",
    description="AI-powered map+voice receptionist for booking Indian hospital appointments",
    version="2.0.0",
)

# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
#  SEED DATA
# ============================================================

def seed_db(db: Session):
    """Seed map data, hospitals, and an admin user."""
    seed_states_districts(db, State, District)
    seed_hospitals(db, State, District, Hospital)

    if db.query(Receptionist).count() == 0:
        default_receptionist = Receptionist(
            name="Admin",
            email="admin@smartclinic.geo",
            hashed_password=hash_password("admin123"),
        )
        db.add(default_receptionist)
        db.commit()
        print("[SEED] Created default receptionist: admin@smartclinic.geo / admin123")


@app.on_event("startup")
def startup():
    db = next(get_db())
    seed_db(db)

    # Pre-warm the district populate cache so first booking is instant.
    # Any district already having >= 50 records is considered ready.
    from sqlalchemy import func
    rows = (
        db.query(Hospital.district_name, func.count(Hospital.hospital_id).label("cnt"))
        .group_by(Hospital.district_name)
        .having(func.count(Hospital.hospital_id) >= 50)
        .all()
    )
    for row in rows:
        _POPULATED_DISTRICTS.add(row.district_name.strip().lower())
    print(f"[STARTUP] Pre-warmed cache with {len(_POPULATED_DISTRICTS)} districts")

    db.close()


# ============================================================
#  SYSTEM
# ============================================================

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "SmartClinic GeoVoice Engine"}


# ============================================================
#  AUTH ROUTES
# ============================================================

@app.post("/api/auth/register", response_model=TokenOut)
def register(data: ReceptionistCreate, db: Session = Depends(get_db)):
    existing = db.query(Receptionist).filter(Receptionist.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    receptionist = Receptionist(
        name=data.name,
        email=data.email,
        hashed_password=hash_password(data.password),
    )
    db.add(receptionist)
    db.commit()
    db.refresh(receptionist)

    token = create_access_token({"sub": receptionist.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "receptionist": receptionist,
    }


@app.post("/api/auth/login", response_model=TokenOut)
def login(data: ReceptionistLogin, db: Session = Depends(get_db)):
    receptionist = db.query(Receptionist).filter(Receptionist.email == data.email).first()
    if not receptionist or not verify_password(data.password, receptionist.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": receptionist.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "receptionist": receptionist,
    }

@app.get("/api/auth/me", response_model=ReceptionistOut)
def get_me(receptionist=Depends(get_current_receptionist)):
    return receptionist


# ============================================================
#  MAP GEO DATA ROUTES
# ============================================================

@app.get("/api/states", response_model=List[StateOut])
def list_states(db: Session = Depends(get_db)):
    """Get all supported Indian states."""
    return db.query(State).order_by(State.state_name.asc()).all()


@app.get("/api/states/{state_id}/districts", response_model=List[DistrictOut])
def list_districts(state_id: int, db: Session = Depends(get_db)):
    """Get districts for a selected state."""
    return db.query(District).filter(District.state_id == state_id).order_by(District.district_name.asc()).all()


@app.get("/api/districts", response_model=List[DistrictOut])
def all_districts(db: Session = Depends(get_db)):
    """Get all districts."""
    return db.query(District).order_by(District.district_name.asc()).all()


# ============================================================
#  HOSPITAL ROUTES
# ============================================================

@app.get("/hospitals", response_model=List[HospitalMapOut])
def list_react_hospitals(
    state: Optional[str] = None,
    district: Optional[str] = None,
    specialization: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Exact Match API for the requested React app map interface.
    Returns: name, lat, lng, specialization, rating
    """
    query = db.query(Hospital)
    if state:
        query = query.filter(Hospital.state_name.ilike(state))
    if district:
        query = query.filter(Hospital.district_name.ilike(district))
    
    hospitals = query.all()
    
    # Filter specialization natively
    if specialization:
        filtered = []
        for h in hospitals:
            specs = [s.strip().lower() for s in h.specializations.split(",")]
            if specialization.lower() in specs:
                filtered.append(h)
        hospitals = filtered

    results = []
    for h in hospitals:
        # Provide the top specialization or the matching one
        display_spec = specialization.title() if specialization else h.specializations.split(",")[0].strip()
        results.append({
            "name": h.hospital_name,
            "lat": float(h.latitude) if h.latitude else 0.0,
            "lng": float(h.longitude) if h.longitude else 0.0,
            "specialization": display_spec,
            "rating": h.rating or 4.0
        })
    return results


@app.get("/api/hospitals", response_model=List[HospitalOut])
def list_hospitals(
    district_name: Optional[str] = None,
    state_name: Optional[str] = None,
    specialization: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Filter hospitals by district and/or specialization for ANY Indian district."""
    if district_name:
        # Resolve aliases: Manglor -> Mangalore, Udapi -> Udupi, Bengaluru -> Bangalore Urban, etc.
        district_name = resolve_canonical_district(district_name)
        # Always attempt to populate — populate_dynamic_hospitals handles
        # the threshold check internally (skips if already >= 200 records).
        populate_dynamic_hospitals(db, district_name, specialization, state_name)

    query = db.query(Hospital)
    if district_name:
        # Exact case-insensitive match — NOT fuzzy '%LIKE%' to prevent cross-district bleed
        query = query.filter(Hospital.district_name.ilike(district_name))
    if state_name:
        query = query.filter(Hospital.state_name.ilike(f"%{state_name}%"))
    
    # Auto-discovery for empty states
    if state_name and not district_name:
        h_count = query.count()
        if h_count == 0:
            # Pick a major district for this state to populate
            from seed_data import INDIA_STATES_DISTRICTS
            state_info = INDIA_STATES_DISTRICTS.get(state_name.title()) 
            if state_info and state_info["districts"]:
                major_dist = state_info["districts"][0]["name"]
                populate_dynamic_hospitals(db, major_dist, specialization, state_name)
                # Re-run query after population
                query = db.query(Hospital).filter(Hospital.state_name.ilike(f"%{state_name}%"))

    hospitals = query.all()

    # Filter by specialization (comma-separated field)
    if specialization:
        filtered = [
            h for h in hospitals
            if any(
                specialization.lower() in s.strip().lower()
                for s in h.specializations.split(",")
            )
        ]
        return filtered

    return hospitals


@app.post("/api/hospitals/refresh")
def refresh_hospitals(
    district_name: str = Query(...),
    state_name: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Force a fresh Overpass fetch for a district — useful when the
    frontend selects a new location and wants all hospitals + clinics.
    Deletes nothing; only adds new records that don't already exist.
    """
    populate_dynamic_hospitals(db, district_name, specialization=None, state=state_name)
    count = (
        db.query(Hospital)
        .filter(Hospital.district_name.ilike(f"%{district_name}%"))
        .count()
    )
    return {"district": district_name, "total_hospitals": count, "status": "refreshed"}


@app.post("/api/hospitals", response_model=HospitalOut)
def create_hospital(
    data: HospitalCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_receptionist),
):
    hospital = Hospital(**data.model_dump())
    db.add(hospital)
    db.commit()
    db.refresh(hospital)
    return hospital


@app.delete("/api/hospitals/{hospital_id}")
def delete_hospital(
    hospital_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_receptionist),
):
    hospital = db.query(Hospital).filter(Hospital.hospital_id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    db.delete(hospital)
    db.commit()
    return {"message": "Hospital deleted successfully"}


# ============================================================
#  APPOINTMENT ROUTES
# ============================================================

@app.get("/api/appointments", response_model=List[AppointmentOut])
def list_appointments(db: Session = Depends(get_db)):
    return db.query(Appointment).order_by(Appointment.created_at.desc()).all()


@app.post("/api/appointments", response_model=AppointmentOut)
def create_appointment(data: AppointmentCreate, db: Session = Depends(get_db)):
    hospital = db.query(Hospital).filter(Hospital.hospital_id == data.hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    appointment = Appointment(**data.model_dump(), status="confirmed")
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


@app.put("/api/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_receptionist),
):
    appointment = db.query(Appointment).filter(
        Appointment.appointment_id == appointment_id
    ).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appointment.status = "cancelled"
    db.commit()
    db.refresh(appointment)

    # Send cancellation email in background
    def _send_cancel_email_bg():
        try:
            hospital_name = appointment.hospital.hospital_name if appointment.hospital else "Unknown Hospital"
            district_name = appointment.hospital.district_name if appointment.hospital else "Unknown District"
            send_cancellation_email(
                to_email=appointment.patient_email or "unknown@email.com",
                hospital_name=hospital_name,
                date=appointment.date,
                time=appointment.time,
                district=district_name
            )
        except Exception as e:
            print(f"[EMAIL] Cancellation email setup failed: {e}")

    threading.Thread(target=_send_cancel_email_bg, daemon=True).start()

    return appointment


@app.delete("/api/appointments/{appointment_id}")
def delete_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_receptionist),
):
    appointment = db.query(Appointment).filter(
        Appointment.appointment_id == appointment_id
    ).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    db.delete(appointment)
    db.commit()
    return {"message": "Appointment deleted successfully"}


# ============================================================
#  VOICE / AI BOOKING ENGINE ROUTES
# ============================================================

@app.post("/api/voice/book", response_model=VoiceBookingResponse)
def voice_book_appointment(data: VoiceTextInput, db: Session = Depends(get_db)):
    """
    Core Voice Booking endpoint.
    Processes NLP Intent -> Disease Mapper -> Hospital Matcher -> Booking
    """
    # 1. Analyze intent (Pass frontend context to fill gaps)
    intent_data = extract_intent(data.text, current_district=data.district, current_state=data.state)
    intent = ExtractedIntent(**intent_data)

    # 2. Strict validation (booking branch only)
    if intent.command == "cancel":
        final_hospital_name = intent.hospital_name
        final_district = intent.district or data.district
        
        if not final_hospital_name or not final_district:
             return VoiceBookingResponse(
                success=False,
                message="To cancel, please mention the hospital name and district (e.g., 'Cancel Apollo in Bangalore').",
                intent=intent,
            )
            
        # Try to find the hospital first
        hospital, _ = get_best_hospital(db, specialization=None, district=final_district, hospital_name=final_hospital_name, state=intent.state)
        if not hospital:
             return VoiceBookingResponse(
                success=False,
                message=f"I couldn't find a hospital named {final_hospital_name} in {final_district} to cancel.",
                intent=intent,
            )

        # Look for the last active booking for this hospital
        # Note: We don't have user login here, so we look for 'Voice User' or matching by email if provided
        query = db.query(Appointment).filter(
            Appointment.hospital_id == hospital.hospital_id,
            Appointment.status == "confirmed"
        )
        if data.receptionist_email:
            # If logged in, maybe we can filter by who booked it? 
            # Actually, let's just find the latest confirmed one for this hospital.
            pass
            
        appointment = query.order_by(Appointment.created_at.desc()).first()
        
        if not appointment:
            return VoiceBookingResponse(
                success=False,
                message=f"No active bookings found for {hospital.hospital_name} in {hospital.district_name}.",
                intent=intent,
            )

        # Execute cancellation
        appointment.status = "cancelled"
        db.commit()
        
        # Trigger background email
        if data.receptionist_email:
            threading.Thread(
                target=send_cancellation_email,
                args=(data.receptionist_email, appointment.patient_name, hospital.hospital_name)
            ).start()

        return VoiceBookingResponse(
            success=True,
            message=f"Success! Your appointment at {hospital.hospital_name} has been cancelled.",
            intent=intent,
            matched_hospital=HospitalOut.from_orm(hospital),
        )

    # 3. Booking Branch (Original validation)
    missing_fields = []
    final_district = intent.district or data.district
    final_state = intent.state or data.state or "Karnataka"
    final_specialty = intent.specialization or intent.hospital_name
    final_time = intent.time_preference or data.time_slot

    if not final_district:
        missing_fields.append("the location (district)")
    if not final_specialty:
        missing_fields.append("the disease or specialization")
    if not final_time:
        missing_fields.append("a time slot")

    if missing_fields:
        return VoiceBookingResponse(
            success=False,
            message=f"I'm almost ready to book your appointment. Please mention {' and '.join(missing_fields)}.",
            intent=intent,
        )

    # 2. Find Best Matched Hospital
    hospital, found_nodes = get_best_hospital(
        db,
        specialization=intent.specialization,
        district=final_district,
        hospital_name=intent.hospital_name,
        state=final_state,
    )

    if not hospital:
        msg = f"Sorry, I couldn't find a hospital in {final_district} "
        if intent.hospital_name:
            msg += f"named {intent.hospital_name}."
        elif intent.specialization:
            msg += f"with a {intent.specialization} department."
            
        return VoiceBookingResponse(
            success=False,
            message=msg + " Please try selecting a different location.",
            intent=intent,
            found_nodes=found_nodes,
        )

    # 3. Schedule Appointment Context
    valid_slots = ["9:00 AM – 11:00 AM", "11:00 AM – 1:00 PM", "2:00 PM – 3:00 PM", "3:00 PM – 6:00 PM"]
    preferred_time = data.time_slot or intent.time_preference or "Morning"
    appointment_date = intent.date or datetime.now().strftime("%Y-%m-%d")

    def get_slot_index(t_str: str) -> int:
        t = t_str.lower()
        if "morning"   in t: return 0
        if "afternoon" in t: return 2
        if "evening"   in t or "night" in t: return 3
        # Regex to catch "6 PM", "10:30 am", etc.
        m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", t)
        if m:
            h = int(m.group(1))
            ampm = m.group(3)
            if ampm == "pm" and h != 12: h += 12
            if ampm == "am" and h == 12: h = 0
            if 7 <= h < 11:   return 0
            if 11 <= h < 14:  return 1
            if 14 <= h < 15:  return 2
            if 15 <= h < 20:  return 3
        return 0 # Default to morning

    # Determine starting search index
    if preferred_time in valid_slots:
        base_idx = valid_slots.index(preferred_time)
    else:
        base_idx = get_slot_index(preferred_time)
    
    # 4. Find first available slot (capacity check: 5 appointments per slot)
    appointment_time = None
    suggested_alternative = False
    current_occupancy = 0

    for i in range(base_idx, len(valid_slots)):
        candidate_slot = valid_slots[i]
        slot_usage = db.query(Appointment).filter(
            Appointment.hospital_id == hospital.hospital_id,
            Appointment.date == appointment_date,
            Appointment.time == candidate_slot,
            Appointment.status == "confirmed"
        ).count()
        if slot_usage < 5:
            appointment_time = candidate_slot
            current_occupancy = slot_usage
            if i > base_idx: suggested_alternative = True
            break
            
    # If today is fully booked, check tomorrow
    if not appointment_time:
        appointment_date = (datetime.strptime(appointment_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        appointment_time = valid_slots[0] # Try morning tomorrow
        current_occupancy = db.query(Appointment).filter(
            Appointment.hospital_id == hospital.hospital_id,
            Appointment.date == appointment_date,
            Appointment.time == appointment_time,
            Appointment.status == "confirmed"
        ).count()
        suggested_alternative = True

    # 4. Formally Insert Appointment into DB
    appointment = Appointment(
        patient_name=data.patient_name or "Voice User",
        patient_phone=data.patient_phone,
        patient_email=data.patient_email,
        hospital_id=hospital.hospital_id,
        specialization=intent.specialization,
        date=appointment_date,
        time=appointment_time,
        status="confirmed",
        notes=f"Voice Intent: {data.text} | Symptom/Disease: {intent.disease}",
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    # 5. Email Notifications — fire-and-forget in background thread (non-blocking)
    notify_email = None
    try:
        from email_service import BOOKING_NOTIFY_EMAIL
        notify_email = BOOKING_NOTIFY_EMAIL

        def _send_email_bg():
            try:
                send_appointment_email(
                    to_email=notify_email,
                    hospital_name=hospital.hospital_name,
                    specialization=intent.specialization,
                    patient_name=appointment.patient_name,
                    date=appointment_date,
                    time=appointment_time,
                    district=hospital.district_name,
                )
                print(f"[EMAIL] OK: sent to {notify_email}")
            except Exception as e:
                print(f"[EMAIL] FAILED: {e}")

        threading.Thread(target=_send_email_bg, daemon=True).start()
    except Exception as e:
        print(f"[EMAIL] SETUP FAILED: {e}")

    # Mark this district as populated so future requests skip the DB count query
    if intent.district:
        _POPULATED_DISTRICTS.add(intent.district.strip().lower())

    # 6. Response Builder for TTS (Text to Speech)
    try:
        date_obj = datetime.strptime(appointment_date, "%Y-%m-%d")
        date_display = date_obj.strftime("%B %d, %Y")
    except Exception:
        date_display = appointment_date

    def slot_to_speech(slot: str) -> str:
        """
        Convert raw slot string like '9:00 AM – 11:00 AM'
        to natural spoken form like 'between 9 AM to 11 AM'.
        """
        import re as _re
        cleaned = _re.sub(r':(00)\s*', ' ', slot)   # '9:00 AM' -> '9 AM'
        cleaned = _re.sub(r'\s*[\u2013\u2014\-]+\s*', ' to ', cleaned)  # '–' -> 'to'
        return f"between {cleaned.strip()}"

    time_spoken = slot_to_speech(str(appointment_time))

    # Calculate token number as the sequential count for this specific slot (plus 1)
    # This makes it a real medical token (e.g. Patient 1, 2, 3...)
    token_number = current_occupancy + 1

    spec_msg = f"with a {intent.specialization}" if intent.specialization else "with a General Physician"

    # Explain if we moved the appointment due to capacity
    prefix = "Booking Confirmed."
    if suggested_alternative:
        prefix = f"Your requested time was full. I've scheduled you for the next available slot."

    # TTS-friendly message: uses natural spoken slot form and includes token
    message = (
        f"{prefix} Appointment booked in {hospital.hospital_name} "
        f"in {hospital.district_name} {spec_msg} on {date_display}, {time_spoken}. "
        f"Your token number is {token_number}."
    )

    return VoiceBookingResponse(
        success=True,
        message=message,
        intent=intent,
        matched_hospital=hospital,
        appointment=appointment,
        found_nodes=found_nodes,
        email_sent_to=notify_email,
        token_number=token_number
    )


@app.post("/api/voice/analyze", response_model=VoiceBookingResponse)
def analyze_voice_text(data: VoiceTextInput, db: Session = Depends(get_db)):
    """Analyze text and show best matches WITHOUT booking - map pin dropping preview."""
    
    intent_data = extract_intent(data.text, current_district=data.district, current_state=data.state)
    intent = ExtractedIntent(**intent_data)

    matches = find_matching_hospitals(
        db,
        specialization=intent.specialization,
        district=intent.district,
        hospital_name=intent.hospital_name,
        state=intent.state,
    )
    
    # Top 5 matches list conversion
    matched_hospitals = [m["hospital"] for m in matches[:5]]

    return VoiceBookingResponse(
        success=True,
        message="Analyzed query successfully",
        intent=intent,
        matched_hospital=matched_hospitals[0] if matched_hospitals else None,
        all_matches=matched_hospitals,
        found_nodes=len(matches),
    )


# ============================================================
#  STATS ROUTE (Dashboard)
# ============================================================

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    total_hospitals = db.query(Hospital).count()
    total_appointments = db.query(Appointment).count()
    confirmed = db.query(Appointment).filter(Appointment.status == "confirmed").count()
    cancelled = db.query(Appointment).filter(Appointment.status == "cancelled").count()

    return {
        "total_hospitals": total_hospitals,
        "total_appointments": total_appointments,
        "confirmed_appointments": confirmed,
        "cancelled_appointments": cancelled,
    }

# ============================================================
#  SERVE FRONTEND
# ============================================================

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/{path:path}")
def serve_index(path: str):
    if path.startswith("api/") or path.startswith("static/"):
        raise HTTPException(status_code=404)
        
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
         return FileResponse(index_path)
    return {"error": "Frontend not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
