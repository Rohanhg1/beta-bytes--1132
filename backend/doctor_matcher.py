"""
Doctor Matching Engine
Finds the best available doctor based on extracted intent.
Priority: specialization > location > available timing > earliest slot.
"""

from sqlalchemy.orm import Session
from models import Doctor
from datetime import datetime

DAY_ABBREVIATIONS = {
    "Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed",
    "Thursday": "Thu", "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun"
}

DAY_FULL = {v: k for k, v in DAY_ABBREVIATIONS.items()}


def parse_day_range(day_str: str) -> list[str]:
    """Parse day range like 'Mon-Fri' or 'Mon,Wed,Fri' into list of day abbreviations."""
    day_str = day_str.strip()
    days_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    # Handle range like "Mon-Fri"
    if "-" in day_str:
        parts = [p.strip() for p in day_str.split("-")]
        if len(parts) == 2:
            start = parts[0][:3]
            end = parts[1][:3]
            try:
                start_idx = days_order.index(start)
                end_idx = days_order.index(end)
                if start_idx <= end_idx:
                    return days_order[start_idx:end_idx + 1]
                else:
                    return days_order[start_idx:] + days_order[:end_idx + 1]
            except ValueError:
                return days_order

    # Handle comma-separated like "Mon,Wed,Fri"
    if "," in day_str:
        return [d.strip()[:3] for d in day_str.split(",")]

    return days_order


def parse_time_slot(time_str: str) -> tuple[int, int]:
    """Parse time slot like '5:00 PM - 8:00 PM' into (start_hour_24, end_hour_24)."""
    try:
        parts = time_str.split("-")
        if len(parts) != 2:
            return (0, 24)

        start = parts[0].strip()
        end = parts[1].strip()

        def to_24h(t: str) -> int:
            t = t.strip().upper()
            match = None
            import re
            match = re.match(r"(\d{1,2}):?(\d{2})?\s*(AM|PM)", t)
            if match:
                hour = int(match.group(1))
                ampm = match.group(3)
                if ampm == "PM" and hour != 12:
                    hour += 12
                elif ampm == "AM" and hour == 12:
                    hour = 0
                return hour
            return 0

        return (to_24h(start), to_24h(end))
    except Exception:
        return (0, 24)


def is_time_preference_match(time_pref: str | None, time_slot: str) -> bool:
    """Check if a time preference matches a doctor's time slot."""
    if not time_pref:
        return True

    start_h, end_h = parse_time_slot(time_slot)

    pref = time_pref.lower()
    if pref == "morning":
        # Morning: 6 AM - 12 PM
        return start_h < 12
    elif pref == "afternoon":
        # Afternoon: 12 PM - 5 PM
        return (start_h < 17 and end_h > 12)
    elif pref == "evening":
        # Evening: 5 PM - 10 PM
        return (end_h > 17 or start_h >= 16)
    else:
        return True


def is_available_on_date(doctor: Doctor, date_str: str) -> bool:
    """Check if doctor is available on the given date."""
    if not date_str:
        return True

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = date_obj.strftime("%a")  # Mon, Tue, etc.
        available_days = parse_day_range(doctor.available_days)
        return day_name in available_days
    except Exception:
        return True


def find_matching_doctors(
    db: Session,
    specialization: str | None,
    location: str | None,
    date: str | None,
    time_preference: str | None,
) -> list[dict]:
    """
    Find matching doctors with scoring.
    Returns list of dicts with doctor and match_score, sorted by score desc.
    """
    query = db.query(Doctor)

    # Start broad query
    doctors = query.all()

    results = []
    for doc in doctors:
        score = 0

        # Specialization match (highest priority: 100 points)
        if specialization:
            if doc.specialization.lower() == specialization.lower():
                score += 100
            else:
                continue  # Must match specialization

        # Location match (50 points)
        if location:
            if doc.clinic_area.lower() == location.lower():
                score += 50
            # Partial match
            elif location.lower() in doc.clinic_area.lower():
                score += 25

        # Date availability (30 points)
        if date:
            if is_available_on_date(doc, date):
                score += 30
            else:
                score -= 50  # Penalize unavailable

        # Time preference match (20 points)
        if time_preference:
            if is_time_preference_match(time_preference, doc.available_time_slots):
                score += 20

        if score > 0:
            results.append({
                "doctor": doc,
                "score": score,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def get_best_doctor(
    db: Session,
    specialization: str | None,
    location: str | None,
    date: str | None,
    time_preference: str | None,
) -> Doctor | None:
    """Get the single best matching doctor."""
    matches = find_matching_doctors(db, specialization, location, date, time_preference)
    if matches:
        return matches[0]["doctor"]
    return None


def suggest_time_for_appointment(doctor: Doctor, time_preference: str | None) -> str:
    """Suggest a specific time within the doctor's available slot."""
    start_h, end_h = parse_time_slot(doctor.available_time_slots)

    # Pick a time based on preference
    if time_preference and time_preference.lower() == "morning":
        hour = max(start_h, 9)
    elif time_preference and time_preference.lower() == "afternoon":
        hour = max(start_h, 13)
    elif time_preference and time_preference.lower() == "evening":
        hour = max(start_h, 17)
    else:
        # Default to start + 30 min
        hour = start_h

    if hour >= end_h:
        hour = start_h

    # Format
    if hour >= 12:
        display_hour = hour - 12 if hour > 12 else 12
        ampm = "PM"
    else:
        display_hour = hour if hour > 0 else 12
        ampm = "AM"

    return f"{display_hour}:30 {ampm}"
