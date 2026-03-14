"""
SmartClinic GeoVoice Receptionist - Intent Extraction Engine
Extracts disease, specialization, hospital name, district, state,
date, and time preference from natural language voice input.

Supports ALL Indian states and districts — not just seeded ones.
"""

import re
from datetime import datetime, timedelta
from disease_specialization_engine import map_disease_to_specialization
from seed_data import INDIA_STATES_DISTRICTS, HOSPITALS_DATA


# ---------------------------------------------------------------------------
# Specialization keyword aliases
# ---------------------------------------------------------------------------
SPECIALIZATION_MAP = {
    # Dentist
    "dentist": "Dentist",
    "dental": "Dentist",
    "tooth": "Dentist",
    "teeth": "Dentist",
    "root canal": "Dentist",

    # Cardiologist
    "cardiologist": "Cardiologist",
    "cardio": "Cardiologist",
    "heart specialist": "Cardiologist",
    "heart doctor": "Cardiologist",
    "cardiac": "Cardiologist",

    # Dermatologist
    "dermatologist": "Dermatologist",
    "skin doctor": "Dermatologist",
    "skin specialist": "Dermatologist",
    "skin clinic": "Dermatologist",

    # Pediatrician
    "pediatrician": "Pediatrician",
    "paediatrician": "Pediatrician",
    "child doctor": "Pediatrician",
    "child specialist": "Pediatrician",
    "kids doctor": "Pediatrician",
    "baby doctor": "Pediatrician",

    # Orthopedic
    "orthopedic": "Orthopedic",
    "orthopaedic": "Orthopedic",
    "ortho": "Orthopedic",
    "bone doctor": "Orthopedic",
    "bone specialist": "Orthopedic",

    # General Physician
    "general physician": "General Physician",
    "general doctor": "General Physician",
    "physician": "General Physician",
    "general practice": "General Physician",
    "gp": "General Physician",

    # ENT
    "ent specialist": "ENT Specialist",
    "ent": "ENT Specialist",
    "ear doctor": "ENT Specialist",
    "ear nose throat": "ENT Specialist",

    # Ophthalmologist
    "ophthalmologist": "Ophthalmologist",
    "eye doctor": "Ophthalmologist",
    "eye specialist": "Ophthalmologist",
    "optometrist": "Ophthalmologist",

    # Gynecologist
    "gynecologist": "Gynecologist",
    "gynaecologist": "Gynecologist",
    "gynae": "Gynecologist",
    "women doctor": "Gynecologist",
    "obstetrician": "Gynecologist",

    # Neurologist
    "neurologist": "Neurologist",
    "nerve doctor": "Neurologist",
    "brain doctor": "Neurologist",
    "neurosurgeon": "Neurologist",

    # Oncologist
    "oncologist": "Oncologist",
    "cancer doctor": "Oncologist",
    "cancer specialist": "Oncologist",

    # Psychiatrist
    "psychiatrist": "Psychiatrist",
    "psychologist": "Psychiatrist",
    "mental health": "Psychiatrist",

    # Diabetologist
    "diabetologist": "Diabetologist",
    "diabetes doctor": "Diabetologist",
    "sugar doctor": "Diabetologist",

    # Urologist
    "urologist": "Urologist",
    "kidney doctor": "Urologist",

    # Gastroenterologist
    "gastroenterologist": "Gastroenterologist",
    "stomach doctor": "Gastroenterologist",
    "gastro": "Gastroenterologist",

    # Pulmonologist
    "pulmonologist": "Pulmonologist",
    "lung doctor": "Pulmonologist",
    "chest doctor": "Pulmonologist",

    # Physiotherapist
    "physiotherapist": "Physiotherapist",
    "physio": "Physiotherapist",
    "physiotherapy": "Physiotherapist",

    # --- Hindi / Kannada Aliases ---
    "ಹೃದಯ": "Cardiologist",
    "दिल": "Cardiologist",
    "ಕಣ್ಣು": "Ophthalmologist",
    "आँख": "Ophthalmologist",
    "ಹಲ್ಲು": "Dentist",
    "दाँत": "Dentist",
    "ಮಕ್ಕಳ": "Pediatrician",
    "बच्च": "Pediatrician",
    "ಮೂಳೆ": "Orthopedic",
    "ಹಡ್ಡಿ": "Orthopedic",
    "ಚರ್ಮ": "Dermatologist",
    "त्वचा": "Dermatologist",
    "ಮೆದುಳು": "Neurologist",
    "दिमाग": "Neurologist",
    "ನರ": "Neurologist",
    "नस": "Neurologist",
    "ಮಹಿಳಾ": "Gynecologist",
    "स्त्री": "Gynecologist",
    "ಹೊಟ್ಟೆ": "Gastroenterologist",
    "पेट": "Gastroenterologist",
    "ಶ್ವಾಸಕೋಶ": "Pulmonologist",
    "फेफड़े": "Pulmonologist",
    "ಮನೋವೈದ್ಯ": "Psychiatrist",
    "ಮನೋ": "Psychiatrist",
    "मानसिक": "Psychiatrist",
    "कಣ್ಣ": "Ophthalmologist",
    "ಕಣ್ಣಿನ": "Ophthalmologist",
}

# Mapping of native location names to canonical English district names
NATIVE_LOCATION_MAP = {
    "ಬೆಂಗಳೂರು": "Bangalore Urban",
    "ಮಂಗಳೂರು": "Mangalore",
    "ಮಂಗಳೂರ": "Mangalore",
    "ಉಡುಪಿ": "Udupi",
    "ಶಿವಮೊಗ್ಗ": "Shivamogga",
    "ಮೈಸೂರು": "Mysore",
    "ಬೆಳಗಾವಿ": "Belgaum",
    "ಕಲಬುರಗಿ": "Gulbarga",
    "ಧಾರವಾಡ": "Hubli-Dharwad",
    "ಹುಬ್ಬಳ್ಳಿ": "Hubli-Dharwad",
    "बेंಗಳೂರಿ": "Bangalore Urban",
    "ಬೆಂಗಳೂರಿನ": "Bangalore Urban",
    "ಬೆಂಗಳೂರಿ": "Bangalore Urban",
    "मंगलुरु": "Mangalore",
    "मंगलौर": "Mangalore",
    "बैंगलोर": "Bangalore Urban",
    "बेंगलुरु": "Bangalore Urban",
    "उडुपी": "Udupi",
    "मैसूर": "Mysore",
    "शिवमोगा": "Shivamogga",
    "शिमोगा": "Shivamogga",
}


# ---------------------------------------------------------------------------
# Extended India district database
# Built from seed_data + additional districts for comprehensive coverage.
# We also support runtime DB lookup (handled in extract_intent via db kwarg).
# ---------------------------------------------------------------------------

# Build known districts dict from seed data: lowercase_name -> (proper_name, state)
_SEEDED_DISTRICTS: dict[str, tuple[str, str]] = {}
for _state, _data in INDIA_STATES_DISTRICTS.items():
    for _dist in _data["districts"]:
        _SEEDED_DISTRICTS[_dist["name"].lower()] = (_dist["name"], _state)

# Additional well-known Indian districts not necessarily in seed data
_EXTRA_DISTRICTS: list[tuple[str, str]] = [
    # Andhra Pradesh
    ("Srikakulam", "Andhra Pradesh"), ("Vizianagaram", "Andhra Pradesh"),
    ("East Godavari", "Andhra Pradesh"), ("West Godavari", "Andhra Pradesh"),
    ("Krishna", "Andhra Pradesh"), ("Prakasam", "Andhra Pradesh"),
    ("Chittoor", "Andhra Pradesh"), ("Kadapa", "Andhra Pradesh"),
    ("Anantapur", "Andhra Pradesh"), ("Eluru", "Andhra Pradesh"),
    # Karnataka
    ("Tumkur", "Karnataka"), ("Kolar", "Karnataka"), ("Raichur", "Karnataka"),
    ("Bidar", "Karnataka"), ("Chitradurga", "Karnataka"), ("Hassan", "Karnataka"),
    ("Chikmagalur", "Karnataka"), ("Kodagu", "Karnataka"), ("Mandya", "Karnataka"),
    ("Gadag", "Karnataka"), ("Koppal", "Karnataka"), ("Yadgir", "Karnataka"),
    ("Bagalkot", "Karnataka"), ("Vijayapura", "Karnataka"), ("Dharwad", "Karnataka"),
    ("Uttara Kannada", "Karnataka"), ("Dakshina Kannada", "Karnataka"),
    # Maharashtra
    ("Kolhapur", "Maharashtra"), ("Solapur", "Maharashtra"), ("Jalgaon", "Maharashtra"),
    ("Nanded", "Maharashtra"), ("Latur", "Maharashtra"), ("Osmanabad", "Maharashtra"),
    ("Satara", "Maharashtra"), ("Sangli", "Maharashtra"), ("Ratnagiri", "Maharashtra"),
    ("Sindhudurg", "Maharashtra"), ("Chandrapur", "Maharashtra"), ("Yavatmal", "Maharashtra"),
    ("Akola", "Maharashtra"), ("Amravati", "Maharashtra"), ("Buldana", "Maharashtra"),
    ("Wardha", "Maharashtra"), ("Gondia", "Maharashtra"), ("Bhandara", "Maharashtra"),
    # Tamil Nadu
    ("Vellore", "Tamil Nadu"), ("Thanjavur", "Tamil Nadu"), ("Erode", "Tamil Nadu"),
    ("Dindigul", "Tamil Nadu"), ("Thoothukudi", "Tamil Nadu"), ("Kanyakumari", "Tamil Nadu"),
    ("Cuddalore", "Tamil Nadu"), ("Villupuram", "Tamil Nadu"), ("Krishnagiri", "Tamil Nadu"),
    ("Dharmapuri", "Tamil Nadu"), ("Namakkal", "Tamil Nadu"), ("Ramanathapuram", "Tamil Nadu"),
    ("Sivaganga", "Tamil Nadu"), ("Virudhunagar", "Tamil Nadu"),
    # Gujarat
    ("Anand", "Gujarat"), ("Bharuch", "Gujarat"), ("Bhavnagar", "Gujarat"),
    ("Junagadh", "Gujarat"), ("Kutch", "Gujarat"), ("Mehsana", "Gujarat"),
    ("Navsari", "Gujarat"), ("Patan", "Gujarat"), ("Porbandar", "Gujarat"),
    ("Surendranagar", "Gujarat"), ("Valsad", "Gujarat"),
    # Uttar Pradesh
    ("Allahabad", "Uttar Pradesh"), ("Meerut", "Uttar Pradesh"), ("Bareilly", "Uttar Pradesh"),
    ("Aligarh", "Uttar Pradesh"), ("Moradabad", "Uttar Pradesh"), ("Gorakhpur", "Uttar Pradesh"),
    ("Ghaziabad", "Uttar Pradesh"), ("Mathura", "Uttar Pradesh"), ("Firozabad", "Uttar Pradesh"),
    ("Jhansi", "Uttar Pradesh"), ("Rampur", "Uttar Pradesh"), ("Shahjahanpur", "Uttar Pradesh"),
    ("Muzaffarnagar", "Uttar Pradesh"), ("Hapur", "Uttar Pradesh"), ("Mau", "Uttar Pradesh"),
    # Rajasthan
    ("Bikaner", "Rajasthan"), ("Alwar", "Rajasthan"), ("Bharatpur", "Rajasthan"),
    ("Bhilwara", "Rajasthan"), ("Barmer", "Rajasthan"), ("Jaisalmer", "Rajasthan"),
    ("Sikar", "Rajasthan"), ("Nagaur", "Rajasthan"), ("Hanumangarh", "Rajasthan"),
    ("Chittorgarh", "Rajasthan"), ("Dhaulpur", "Rajasthan"),
    # Madhya Pradesh
    ("Ujjain", "Madhya Pradesh"), ("Sagar", "Madhya Pradesh"), ("Rewa", "Madhya Pradesh"),
    ("Satna", "Madhya Pradesh"), ("Khargone", "Madhya Pradesh"), ("Chhindwara", "Madhya Pradesh"),
    ("Ratlam", "Madhya Pradesh"), ("Mandsaur", "Madhya Pradesh"), ("Shahdol", "Madhya Pradesh"),
    # Kerala
    ("Malappuram", "Kerala"), ("Palakkad", "Kerala"), ("Kannur", "Kerala"),
    ("Kasaragod", "Kerala"), ("Pathanamthitta", "Kerala"), ("Alappuzha", "Kerala"),
    ("Idukki", "Kerala"), ("Wayanad", "Kerala"),
    # West Bengal
    ("Bardhaman", "West Bengal"), ("Murshidabad", "West Bengal"), ("Nadia", "West Bengal"),
    ("North 24 Parganas", "West Bengal"), ("South 24 Parganas", "West Bengal"),
    ("Purulia", "West Bengal"), ("Birbhum", "West Bengal"), ("Bankura", "West Bengal"),
    ("Malda", "West Bengal"), ("Jalpaiguri", "West Bengal"), ("Cooch Behar", "West Bengal"),
    # Bihar
    ("Darbhanga", "Bihar"), ("Purnia", "Bihar"), ("Saharsa", "Bihar"),
    ("Araria", "Bihar"), ("Kishanganj", "Bihar"), ("Madhubani", "Bihar"),
    ("Sitamarhi", "Bihar"), ("Begusarai", "Bihar"), ("Samastipur", "Bihar"),
    ("Nalanda", "Bihar"), ("Nawada", "Bihar"), ("Jehanabad", "Bihar"),
    # Haryana
    ("Hisar", "Haryana"), ("Karnal", "Haryana"), ("Rohtak", "Haryana"),
    ("Sirsa", "Haryana"), ("Sonipat", "Haryana"), ("Bhiwani", "Haryana"),
    ("Rewari", "Haryana"), ("Mahendragarh", "Haryana"), ("Kurukshetra", "Haryana"),
    # Punjab
    ("Bathinda", "Punjab"), ("Hoshiarpur", "Punjab"), ("Firozpur", "Punjab"),
    ("Kapurthala", "Punjab"), ("Moga", "Punjab"), ("Muktsar", "Punjab"),
    ("Pathankot", "Punjab"), ("Patiala", "Punjab"), ("Fatehgarh Sahib", "Punjab"),
    # Telangana
    ("Khammam", "Telangana"), ("Mahbubnagar", "Telangana"), ("Medak", "Telangana"),
    ("Nalgonda", "Telangana"), ("Rangareddy", "Telangana"), ("Adilabad", "Telangana"),
    ("Suryapet", "Telangana"), ("Siddipet", "Telangana"),
    # Jharkhand
    ("Bokaro", "Jharkhand"), ("Hazaribagh", "Jharkhand"), ("Giridih", "Jharkhand"),
    ("Deoghar", "Jharkhand"), ("Dumka", "Jharkhand"), ("Godda", "Jharkhand"),
    # Chhattisgarh
    ("Korba", "Chhattisgarh"), ("Rajnandgaon", "Chhattisgarh"), ("Jagdalpur", "Chhattisgarh"),
    ("Ambikapur", "Chhattisgarh"), ("Dhamtari", "Chhattisgarh"),
    # Odisha
    ("Balasore", "Odisha"), ("Berhampur", "Odisha"), ("Sambalpur", "Odisha"),
    ("Puri", "Odisha"), ("Koraput", "Odisha"), ("Kendujhar", "Odisha"),
    # Assam
    ("Jorhat", "Assam"), ("Nagaon", "Assam"), ("Tezpur", "Assam"),
    ("Tinsukia", "Assam"), ("Lakhimpur", "Assam"), ("Dhemaji", "Assam"),
    # Himachal Pradesh
    ("Solan", "Himachal Pradesh"), ("Kangra", "Himachal Pradesh"),
    ("Mandi", "Himachal Pradesh"), ("Kullu", "Himachal Pradesh"),
    ("Una", "Himachal Pradesh"), ("Hamirpur", "Himachal Pradesh"),
    # Uttarakhand
    ("Roorkee", "Uttarakhand"), ("Rishikesh", "Uttarakhand"),
    ("Haldwani", "Uttarakhand"), ("Rudrapur", "Uttarakhand"),
    ("Kotdwar", "Uttarakhand"), ("Pithoragarh", "Uttarakhand"),
    # Aliases
    ("Shimoga", "Karnataka"), ("Bangalore", "Karnataka"),
    ("Mangalore", "Karnataka"), ("Mysore", "Karnataka"),
    ("Belgaum", "Karnataka"), ("Gulbarga", "Karnataka"),
    ("Bellary", "Karnataka"), ("Hubli", "Karnataka"),
]

for _dist_name, _state_name in _EXTRA_DISTRICTS:
    key = _dist_name.lower()
    if key not in _SEEDED_DISTRICTS:
        _SEEDED_DISTRICTS[key] = (_dist_name, _state_name)

# Pre-sort by length descending (longest first) for greedy matching
KNOWN_DISTRICTS_SORTED: list[tuple[str, str, str]] = sorted(
    [(k, v[0], v[1]) for k, v in _SEEDED_DISTRICTS.items()],
    key=lambda x: len(x[0]),
    reverse=True,
)

# Known hospital names from seed data
KNOWN_HOSPITALS = [h["name"].lower() for h in HOSPITALS_DATA]


# ---------------------------------------------------------------------------
# Extraction sub-functions
# ---------------------------------------------------------------------------

def extract_specialization_direct(text: str) -> str | None:
    """Extract doctor specialization directly mentioned in text."""
    text_lower = text.lower()
    for keyword in sorted(SPECIALIZATION_MAP.keys(), key=len, reverse=True):
        # Use a more robust boundary that works with mixed scripts:
        # (?<![a-z0-9]) ensures the match doesn't start in the middle of an English word/number.
        # It allows matching if preceded by a space or a native script character (which is not a-z0-9).
        pattern = rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])"
        if re.search(pattern, text_lower):
            return SPECIALIZATION_MAP[keyword]
    return None


def extract_disease_and_specialization(text: str) -> tuple[str | None, str | None]:
    """Map symptoms/diseases to specialization. Falls back to direct mention."""
    text_lower = text.lower()
    
    # 1. First check if a specialization is directly mentioned in the sentence
    spec = extract_specialization_direct(text_lower)
    if spec:
        return None, spec

    # 2. If not, try to find a disease/symptom keyword and map it
    disease_word, mapped_spec = map_disease_to_specialization(text_lower)
    if mapped_spec:
        return disease_word, mapped_spec
        
    return None, None


# Words that must NEVER be mistaken for a hospital name.
# Covers: disease names, symptom words, booking filler words, and common English words.
HOSPITAL_NAME_BLOCKLIST = {
    # ------- disease / symptom words -------
    "allergy", "fever", "cold", "cough", "flu", "viral", "headache",
    "body ache", "weakness", "malaria", "dengue", "chest pain", "heart",
    "heart attack", "palpitations", "hypertension", "bp", "cholesterol",
    "breathlessness", "toothache", "tooth pain", "cavity", "gums",
    "bleeding gums", "braces", "skin", "rash", "skin rash", "acne",
    "pimples", "hair fall", "dandruff", "eczema", "itching", "pain",
    "fracture", "joint pain", "knee pain", "back pain", "arthritis",
    "muscle pain", "sprain", "ear ache", "ear pain", "hearing loss",
    "nose bleed", "sinus", "sore throat", "tonsils", "throat pain",
    "eye pain", "vision", "cataract", "red eye", "pregnancy", "periods",
    "migraine", "stroke", "seizures", "memory loss", "paralysis",
    "cancer", "tumor", "chemo", "infection", "diabetes", "sugar",
    "vomiting", "nausea", "diarrhea", "constipation", "stomach",
    "kidney", "liver", "lung", "thyroid", "asthma", "pneumonia",
    # ------- generic booking filler phrases -------
    "an", "a", "the", "an appointment", "appointment", "book", "book an",
    "book a", "booking", "please", "nearby", "near me", "help", "urgent",
    "good", "best", "top", "any", "some", "nearest", "local",
    # ------- specialization words (shouldn't be hospital names) -------
    "cardiologist", "dermatologist", "neurologist", "orthopedic", "dentist",
    "pediatrician", "gynecologist", "ophthalmologist", "psychiatrist",
    "diabetologist", "urologist", "gastroenterologist", "pulmonologist",
    "physiotherapist", "oncologist", "general physician", "physician",
    "ent", "ent specialist",
}


def extract_hospital_name(text: str) -> str | None:
    """
    Extract hospital name from text.
    Checks known seeded hospitals then generic patterns like 'book X hospital'.
    Rejects disease/symptom words and generic filler so they are never
    mistaken for hospital names.
    """
    text_lower = text.lower()

    # 1. Check against known seeded hospital names (longest first)
    for hosp_name in sorted(KNOWN_HOSPITALS, key=len, reverse=True):
        if hosp_name in text_lower:
            for orig in HOSPITALS_DATA:
                if orig["name"].lower() == hosp_name:
                    return orig["name"]

    # 2. Generic regex patterns — only use if a real proper name is captured
    patterns = [
        # e.g. "book apollo hospital" / "book an appointment at apollo hospital"
        r"(?<![a-z0-9])book\s+(?:an?\s+appointment\s+(?:at|in|with)\s+)?([A-Za-z][A-Za-z\s]{2,40}?)\s+(?:hospital|clinic|centre|center|nursing home)",
        # e.g. "appointment at apollo hospital"
        r"(?<![a-z0-9])(?:at|in|with)\s+([A-Za-z][A-Za-z\s]{2,40}?)\s+(?:hospital|clinic|centre|center|nursing home)",
        # e.g. "apollo hospital please"
        r"([A-Za-z][A-Za-z\s]{2,40}?)\s+(?:hospital|clinic|centre|center|nursing home)\s+(?:please|appointment|booking|book)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            candidate_lower = candidate.lower()

            # Reject if the candidate is a disease/symptom/filler word
            if candidate_lower in HOSPITAL_NAME_BLOCKLIST:
                continue
            # Also reject if any blocklist word makes up the majority of the candidate
            if any(bl_word == candidate_lower or
                   (len(bl_word) > 4 and bl_word in candidate_lower)
                   for bl_word in HOSPITAL_NAME_BLOCKLIST):
                continue
            # Reject overly short or numeric names
            if len(candidate) <= 3 or candidate.isdigit():
                continue

            candidate_titled = candidate.title()

            # Only append the institution suffix if the candidate doesn't already
            # end with a facility word (prevents "Apollo Hospital Hospital" doubling)
            _FACILITY_WORDS = {
                "hospital", "clinic", "centre", "center", "nursing home",
                "polyclinic", "dispensary", "infirmary"
            }
            already_has_suffix = any(
                candidate_lower.endswith(fw) for fw in _FACILITY_WORDS
            )
            if already_has_suffix:
                return candidate_titled

            suffix_match = re.search(
                r"(hospital|clinic|centre|center|nursing home)", text_lower
            )
            if suffix_match:
                return f"{candidate_titled} {suffix_match.group(1).title()}"
            return candidate_titled

    return None


def extract_location(text: str) -> tuple[str | None, str | None]:
    """
    Extract district and state from text using the comprehensive district list.
    Performs word-boundary matching to avoid false positives.
    """
    text_lower = text.lower()

    # 0. Check native mapping (Mangaluru -> Mangalore, etc.)
    for native_key, canonical in NATIVE_LOCATION_MAP.items():
        if native_key in text_lower: # Substring match is okay for native script due to suffixes
             return canonical, "Karnataka" # Default to Karnataka for these specific matches

    # 1. Check full known district list (seeded + extras)
    for key, proper_name, state_name in KNOWN_DISTRICTS_SORTED:
        pattern = rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])"
        if re.search(pattern, text_lower):
            return proper_name, state_name

    # Words that are never a district name
    _LOCATION_STOP_WORDS = {
        "the", "a", "an", "india", "my", "our", "this", "that",
        # facility suffixes — prevent 'Apollo Hospital' being treated as a district
        "hospital", "hospitals", "clinic", "clinics", "centre", "center",
        "nursing home", "medical", "health", "care", "doctor", "doctors",
    }

    # 2. Heuristic: look for "in <word(s)>" pattern and return as district
    in_match = re.search(
        r"\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", text, re.IGNORECASE
    )
    if in_match:
        candidate = in_match.group(1).strip()
        candidate_lower = candidate.lower()
        # Strip trailing facility words from candidate before accepting
        for fw in ("hospital", "clinic", "centre", "center", "nursing home",
                   "medical", "health centre"):
            if candidate_lower.endswith(fw):
                candidate = candidate[:-(len(fw))].strip()
                candidate_lower = candidate.lower()
                break
        if candidate_lower not in _LOCATION_STOP_WORDS and len(candidate) > 2:
            return candidate.title(), None

    return None, None


def extract_date(text: str) -> str | None:
    """Extract appointment date from text. Returns 'YYYY-MM-DD'."""
    text_lower = text.lower()
    today = datetime.now()

    if "today" in text_lower:
        return today.strftime("%Y-%m-%d")
    if "day after tomorrow" in text_lower:
        return (today + timedelta(days=2)).strftime("%Y-%m-%d")
    if "tomorrow" in text_lower:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")

    day_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2,
        "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
    }
    for day_name, day_num in day_map.items():
        if day_name in text_lower:
            days_ahead = day_num - today.weekday()
            if "next" in text_lower:
                days_ahead += 7
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    return (today + timedelta(days=1)).strftime("%Y-%m-%d")


def extract_time_preference(text: str) -> str | None:
    """Extract preferred appointment time from text."""
    text_lower = text.lower()
    if "morning" in text_lower:
        return "Morning"
    if "afternoon" in text_lower:
        return "Afternoon"
    if "evening" in text_lower or "night" in text_lower:
        return "Evening"

    time_match = re.search(r"(\d{1,2})\s*(?::(\d{2}))?\s*(am|pm)", text_lower)
    if time_match:
        hour = time_match.group(1)
        minutes = time_match.group(2) or "00"
        ampm = time_match.group(3).upper()
        return f"{hour}:{minutes} {ampm}"

    return None


def extract_command(text: str) -> str:
    """Detect if the user wants to book or cancel."""
    text_lower = text.lower()
    # Support English, Kannada (radda-golisu), and Hindi (radd karein)
    cancel_keywords = [
        "cancel", "stop", "remove", "delete", "radda golisu", "radd karein",
        "ಕ್ಯಾನ್ಸಲ್", "ರದ್ದುಗೊಳಿಸು", "cancel booking"
    ]
    if any(k in text_lower for k in cancel_keywords):
        return "cancel"
    return "book"


# ---------------------------------------------------------------------------
# Main intent extractor
# ---------------------------------------------------------------------------

def extract_intent(
    text: str,
    current_district: str = None,
    current_state: str = None,
) -> dict:
    """
    Master function to extract intent from voice/text input.
    Falls back to dropdown-selected district/state when text doesn't mention location.
    """
    disease, specialization = extract_disease_and_specialization(text)
    hospital_name = extract_hospital_name(text)
    district, state = extract_location(text)

    # Use frontend-selected district/state if text doesn't specify location
    if not district:
        district = current_district
        state = current_state
    elif not state and current_state:
        state = current_state      # fill state from context if only district found

    return {
        "command": extract_command(text),
        "disease": disease,
        "specialization": specialization,
        "hospital_name": hospital_name,
        "district": district,
        "state": state,
        "date": extract_date(text),
        "time_preference": extract_time_preference(text),
        "raw_text": text,
    }
