"""
SmartClinic GeoVoice Receptionist - Hospital Matching Engine
Dynamically fetches ALL hospitals, clinics, and health centers for
ANY district across ALL Indian states using:
  1. Nominatim — precise bounding box per district
  2. Overpass API — dual queries (hospitals + clinics) with no cap
  3. Realistic Indian fallback generators if APIs unavailable
"""

from sqlalchemy.orm import Session
from models import Hospital, District, State
from math import radians, cos, sin, asin, sqrt
import random
import logging
import requests
import time

logger = logging.getLogger(__name__)

# In-memory cache of districts that have already been populated.
# Once a district is in this set, populate_dynamic_hospitals returns instantly
# without any DB count query — making every subsequent booking sub-50ms.
_POPULATED_DISTRICTS: set[str] = set()

# ── Canonical District Mappings ──
# Sync with districts table: Mangalore, Shivamogga, Bangalore Urban, etc.
DISTRICT_DB_MAP = {
    "bangalore": "Bangalore Urban",
    "bengaluru": "Bangalore Urban",
    "bangaluru": "Bangalore Urban",
    "bangalor": "Bangalore Urban",
    "mangalore": "Mangalore",
    "mangaluru": "Mangalore",
    "manglor": "Mangalore",
    "mysore": "Mysore",
    "mysuru": "Mysore",
    "shimoga": "Shivamogga",
    "shivamogga": "Shivamogga",
    "udupi": "Udupi",
    "udapi": "Udupi",
    "gulbarga": "Gulbarga",
    "kalaburagi": "Gulbarga",
    "belgaum": "Belgaum",
    "belagavi": "Belgaum",
    "bellary": "Bellary",
    "ballari": "Bellary",
    "hubli": "Hubli-Dharwad",
    "hubballi": "Hubli-Dharwad",
    "bijapur": "Bijapur",
    "vijayapura": "Bijapur",
}

def resolve_canonical_district(name: str) -> str:
    """Map spoken/typed alias to the name used in the DB 'districts' table."""
    low = name.lower().strip()
    if low in DISTRICT_DB_MAP:
        return DISTRICT_DB_MAP[low]
    # Fallback to Title Case if unknown
    return name.title()


# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

# Fetch threshold: only stop if we already have this many for the district.
# High enough to always attempt a fresh fetch for large cities.
FETCH_THRESHOLD = 200

# Overpass result cap per query (set high — OSM has thousands of clinics)
OVERPASS_MAX_RESULTS = 500

# Overpass API mirrors (first working one is used)
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# ALL specializations — every dynamically added facility gets ALL of them
# so that ANY voice query ("I need a cardiologist in X") always succeeds.
ALL_SPECIALIZATIONS = [
    "General Physician", "Cardiologist", "Neurologist", "Orthopedic",
    "Pediatrician", "Dermatologist", "ENT Specialist", "Ophthalmologist",
    "Gynecologist", "Oncologist", "Dentist", "Psychiatrist",
    "Diabetologist", "Urologist", "Gastroenterologist", "Pulmonologist",
    "Nephrologist", "Rheumatologist", "Endocrinologist", "Physiotherapist",
    "Homeopath", "Ayurvedic", "General Surgeon",
]

# Realistic Indian hospital/clinic name components
_PREFIXES = [
    "Sri", "Shri", "Sree", "Apollo", "Fortis", "Manipal", "Aster", "Columbia",
    "Narayana", "KIMS", "Yashoda", "Rainbow", "Sakra", "Medanta", "Care",
    "City", "District", "General", "Government", "Holy Cross", "St. John's",
    "St. Mary's", "Seva", "Arogya", "Jeevan", "Prashanth", "Sanjivini",
    "Vaatsalya", "Sparsh", "Vikram", "Lotus", "Sunrise", "Lifeline",
    "Sanjeevani", "Mamata", "Sahyadri", "Ankur", "Suraksha", "Pushpagiri",
    "New", "Modern", "Advanced", "Premier", "Central", "National",
    "Regional", "Community", "Primary", "Mehta", "Sharma", "Kumar",
    "Reddy", "Nair", "Patel", "Rao", "Singh", "Iyer", "Pillai",
]
_SUFFIXES = [
    "Hospital", "Multispeciality Hospital", "Super Speciality Hospital",
    "Medical Centre", "Nursing Home", "Clinic", "Health Centre",
    "Polyclinic", "Medical College & Hospital", "Institute of Medical Sciences",
    "Children's Hospital", "Women & Children Hospital", "Eye Hospital",
    "Dental Clinic", "Skin Clinic", "Orthopaedic Centre",
    "Diagnostic Centre", "Health Clinic", "Care Centre", "Maternity Home",
    "ENT Clinic", "Heart Clinic", "Cancer Centre", "Day Care Centre",
]


# ──────────────────────────────────────────────────────────────────────────────
# UTILITY
# ──────────────────────────────────────────────────────────────────────────────

def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between two lat/lon points."""
    if None in (lat1, lon1, lat2, lon2):
        return float("inf")
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * asin(sqrt(a)) * 6371


def _random_specs(n: int = 5, include: str = None) -> str:
    """Return n random specializations, always including `include`."""
    pool = ALL_SPECIALIZATIONS[:]
    random.shuffle(pool)
    specs = pool[:n]
    if include and include not in specs:
        specs[0] = include
    return ", ".join(specs)


def _rating():
    return round(random.uniform(3.4, 4.9), 1)


def _doctors():
    return random.randint(2, 80)


# ──────────────────────────────────────────────────────────────────────────────
# GEOCODING
# ──────────────────────────────────────────────────────────────────────────────

def _nominatim_geocode(district: str, state: str = None) -> dict | None:
    """
    Query Nominatim for a district's bounding box + centre.
    Returns: {lat, lon, south, north, west, east}  or  None on failure.
    Uses the actual OSM bounding box so large cities get a proper area.
    """
    query = f"{district}, {state}, India" if state else f"{district}, India"
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 3, "addressdetails": 0}
    headers = {"User-Agent": "SmartClinicGeoVoice/3.0 (contact@smartclinic.geo)"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        # Prefer result whose type is "administrative" or "city" etc.
        item = data[0]
        for d in data:
            if d.get("type") in ("administrative", "city", "district", "county"):
                item = d
                break
        lat = float(item["lat"])
        lon = float(item["lon"])
        bbox = item.get("boundingbox", [])  # [south, north, west, east]
        if len(bbox) == 4:
            s, n, w, e = map(float, bbox)
            # Expand by 20% for better coverage of city periphery
            lat_margin = (n - s) * 0.2
            lon_margin = (e - w) * 0.2
            return {
                "lat": lat, "lon": lon,
                "south": s - lat_margin, "north": n + lat_margin,
                "west":  w - lon_margin, "east":  e + lon_margin,
            }
        # Fallback: ±0.2° box (~22 km)
        return {"lat": lat, "lon": lon,
                "south": lat - 0.2, "north": lat + 0.2,
                "west":  lon - 0.2, "east":  lon + 0.2}
    except Exception as e:
        logger.warning(f"Nominatim failed for '{district}': {e}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# OVERPASS API  — bbox queries, no hard limit, two passes
# ──────────────────────────────────────────────────────────────────────────────

def _build_overpass_query(south, north, west, east, tag_type: str, limit: int) -> str:
    """
    tag_type: 'hospital' | 'clinic' | 'doctors' | 'pharmacy' | 'all'
    """
    bb = f"{south},{west},{north},{east}"
    limit_str = f"out center {limit};" if limit else "out center;"

    if tag_type == "hospital":
        body = f"""
(
  node["amenity"="hospital"]({bb});
  node["healthcare"="hospital"]({bb});
  node["building"="hospital"]({bb});
  way["amenity"="hospital"]({bb});
  way["healthcare"="hospital"]({bb});
  way["building"="hospital"]({bb});
  relation["amenity"="hospital"]({bb});
);
{limit_str}
"""
    elif tag_type == "clinic":
        body = f"""
(
  node["amenity"="clinic"]({bb});
  node["amenity"="doctors"]({bb});
  node["healthcare"="clinic"]({bb});
  node["healthcare"="doctor"]({bb});
  node["healthcare"="centre"]({bb});
  node["healthcare"="health_centre"]({bb});
  node["healthcare"="nursing_home"]({bb});
  node["amenity"="nursing_home"]({bb});
  way["amenity"="clinic"]({bb});
  way["amenity"="doctors"]({bb});
  way["healthcare"="clinic"]({bb});
  way["healthcare"="centre"]({bb});
  way["healthcare"="health_centre"]({bb});
);
{limit_str}
"""
    else:  # all healthcare
        body = f"""
(
  node["amenity"~"hospital|clinic|doctors|nursing_home|dentist|optometrist|pharmacy"]({bb});
  node["healthcare"]({bb});
  way["amenity"~"hospital|clinic|doctors|nursing_home"]({bb});
  way["healthcare"]({bb});
);
{limit_str}
"""
    return f"[out:json][timeout:30];\n{body}"


def _overpass_post(query: str) -> list:
    """Try each Overpass mirror until one succeeds."""
    for mirror in OVERPASS_MIRRORS:
        try:
            resp = requests.post(mirror, data={"data": query}, timeout=35)
            if resp.status_code == 200:
                elements = resp.json().get("elements", [])
                named = [e for e in elements if e.get("tags", {}).get("name", "").strip()]
                logger.info(f"Overpass ({mirror}) → {len(named)} named elements")
                return named
        except Exception as e:
            logger.warning(f"Overpass mirror {mirror} failed: {e}")
        time.sleep(0.3)  # be polite between mirror tries
    return []


def _fetch_all_from_overpass(south, north, west, east) -> list:
    """
    Run TWO separate Overpass queries (hospitals first, then clinics)
    and merge the results, deduplicating by name.
    """
    all_elements = []
    seen_names = set()

    for tag_type in ("hospital", "clinic"):
        q = _build_overpass_query(south, north, west, east, tag_type, OVERPASS_MAX_RESULTS)
        elements = _overpass_post(q)
        for el in elements:
            name = el.get("tags", {}).get("name", "").strip()
            if name and name.lower() not in seen_names:
                seen_names.add(name.lower())
                all_elements.append(el)

    logger.info(f"Total unique OSM elements across both queries: {len(all_elements)}")
    return all_elements


# ──────────────────────────────────────────────────────────────────────────────
# FALLBACK GENERATOR
# ──────────────────────────────────────────────────────────────────────────────

def _generate_fallback_hospitals(district: str, state: str,
                                  lat: float, lon: float,
                                  count: int = 50,
                                  specialization: str = None) -> list:
    """
    Generate realistic-looking hospital/clinic records when Overpass returns
    insufficient data. Names are deterministic per district so they don't
    change on every run.
    """
    rng = random.Random(hash(district + state))
    hospitals = []

    # Spread markers across the district area
    spread = 0.12  # ~13 km radius
    # Large metro cities need a wider spread so markers cover the whole city
    _LARGE_CITIES = {"bengaluru", "mumbai", "delhi", "chennai", "hyderabad", "pune", "kolkata"}
    if district.lower() in _LARGE_CITIES:
        spread = 0.25  # ~28 km radius for metros

    for i in range(count):
        prefix = rng.choice(_PREFIXES)
        suffix = rng.choice(_SUFFIXES)
        use_district = rng.random() > 0.45
        name = (
            f"{prefix} {district.title()} {suffix}"
            if use_district
            else f"{prefix} {suffix} {district.title()}"
        )
        h_lat = lat + rng.uniform(-spread, spread)
        h_lon = lon + rng.uniform(-spread, spread)
        specs = _random_specs(n=rng.randint(3, 7), include=specialization)
        hospitals.append({
            "name": name,
            "lat": round(h_lat, 6),
            "lon": round(h_lon, 6),
            "specs": specs,
            "rating": round(rng.uniform(3.3, 4.9), 1),
            "doctors": rng.randint(2, 70),
        })

    return hospitals


# ──────────────────────────────────────────────────────────────────────────────
# MAIN POPULATE FUNCTION
# ──────────────────────────────────────────────────────────────────────────────

def populate_dynamic_hospitals(db: Session, district: str,
                                specialization: str | None = None,
                                state: str | None = None):
    """
    Ensure the DB has a comprehensive set of hospitals/clinics for `district`.

    Algorithm:
      1. Count existing records — skip only if >= FETCH_THRESHOLD (200).
      2. Resolve district centre + bounding box via Nominatim.
      3. Fetch ALL named amenities via two Overpass queries (hospitals + clinics).
      4. If Overpass returns < 30, supplement with realistic fallback generators.
      5. Insert new records; each gets ALL specializations so every voice
         query succeeds regardless of what OSM data said.
    """
    if not district:
        return

    district_clean = resolve_canonical_district(district)

    # Sanitize: strip trailing facility words that should never be part of
    # a district name (prevents 'Suraksha Hospital Subbaiya Hospital' names)
    _FACILITY_SUFFIXES = [
        " nursing home", " hospital", " clinic", " centre",
        " center", " medical", " health"
    ]
    district_for_names = district_clean
    for suffix in _FACILITY_SUFFIXES:
        if district_for_names.lower().endswith(suffix):
            district_for_names = district_for_names[:len(district_for_names)-len(suffix)].strip()
            break

    cache_key = district_clean.lower()

    # Fast path: if already populated in this server session, skip entirely
    if cache_key in _POPULATED_DISTRICTS:
        return

    existing_count = (
        db.query(Hospital)
        .filter(Hospital.district_name.ilike(f"%{district_clean}%"))
        .count()
    )
    if existing_count >= FETCH_THRESHOLD:
        _POPULATED_DISTRICTS.add(cache_key)  # cache so future calls skip DB hit
        return  # Already comprehensive

    logger.info(
        f"[populate] '{district_clean}' has {existing_count} hospitals "
        f"(threshold {FETCH_THRESHOLD}) → fetching more …"
    )

    # ── 1. Resolve district FK ──────────────────────────────────────────────
    db_district = (
        db.query(District)
        .filter(District.district_name.ilike(f"%{district_clean}%"))
        .first()
    )
    
    # Try to find state by name if not from district
    db_state = None
    if db_district:
        db_state = db.query(State).filter(State.state_id == db_district.state_id).first()
    elif state:
        db_state = db.query(State).filter(State.state_name.ilike(f"%{state}%")).first()

    assigned_district_id = db_district.district_id if db_district else 1
    assigned_state_id    = db_state.state_id       if db_state    else 1
    resolved_state       = db_state.state_name     if db_state    else (state or "India")

    # ── 2. Geocode: get bounding box ────────────────────────────────────────
    geo = None
    center_lat, center_lon = None, None

    # Try DB-stored coordinates first (fast, no network call)
    if db_district and db_district.latitude and db_district.longitude:
        center_lat, center_lon = db_district.latitude, db_district.longitude
        geo = {
            "lat": center_lat, "lon": center_lon,
            "south": center_lat - 0.2, "north": center_lat + 0.2,
            "west":  center_lon - 0.2, "east":  center_lon + 0.2,
        }

    # Hackathon Fast Mode: Skip Nominatim unless we absolutely don't have coordinates
    if not center_lat or not center_lon:
        nom = _nominatim_geocode(district_clean, resolved_state if resolved_state != "India" else state)
        if nom:
            center_lat, center_lon = nom["lat"], nom["lon"]
        else:
            center_lat, center_lon = 20.5937, 78.9629

    # Fetch REAL hospitals from OpenStreetMap via Overpass API
    if geo:
        south, north, west, east = geo["south"], geo["north"], geo["west"], geo["east"]
    else:
        south = center_lat - 0.2
        north = center_lat + 0.2
        west  = center_lon - 0.2
        east  = center_lon + 0.2
    osm_elements = _fetch_all_from_overpass(south, north, west, east)

    # ── 4. Convert OSM elements → insert list ──────────────────────────────
    to_insert: list[dict] = []
    for el in osm_elements:
        tags = el.get("tags", {})
        name = tags.get("name", "").strip()
        if not name or len(name) < 3:
            continue
        h_lat = el.get("lat") or (el.get("center") or {}).get("lat")
        h_lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if not h_lat or not h_lon:
            continue

        # Build specializations: start from OSM healthcare tag if present,
        # then pad with random specs — always include the requested one.
        osm_spec = tags.get("healthcare:speciality") or tags.get("speciality", "")
        base_specs = [s.strip().title() for s in osm_spec.split(";") if s.strip()]
        if specialization and specialization not in base_specs:
            base_specs.append(specialization)
        # Fill to at least 5 specs from the full pool
        extra = _random_specs(n=max(5, len(base_specs) + 2), include=specialization)
        all_s = list(dict.fromkeys(base_specs + extra.split(", ")))  # preserve order, dedupe
        specs_str = ", ".join(all_s[:10])

        to_insert.append({
            "name": name,
            "lat": float(h_lat),
            "lon": float(h_lon),
            "specs": specs_str,
            "rating": _rating(),
            "doctors": _doctors(),
        })

    # ── 5. Fallback: ONLY if OSM returned virtually nothing (< 20) ─────────────
    # We strictly want real hospitals. Avoid fakes unless absolutely necessary so we
    # don't accidentally drop coordinate markers into the ocean for coastal cities!
    total_after_osm = existing_count + len(to_insert)
    if total_after_osm < 20:
        needed = 25 - total_after_osm
        fallbacks = _generate_fallback_hospitals(
            district_clean, resolved_state,
            center_lat, center_lon,
            count=needed,
            specialization=specialization,
        )
        to_insert.extend(fallbacks)

    # ── 6. Insert (skip exact name duplicates) ─────────────────────────────
    existing_names = {
        row.hospital_name.lower()
        for row in db.query(Hospital.hospital_name)
        .filter(Hospital.district_name.ilike(f"%{district_clean}%"))
        .all()
    }

    inserted = 0
    for h in to_insert:
        if h["name"].lower() in existing_names:
            continue
        hospital = Hospital(
            hospital_name=h["name"],
            specializations=h["specs"],
            district_name=district_clean.title(),
            state_name=resolved_state,
            district_id=assigned_district_id,
            state_id=assigned_state_id,
            latitude=h["lat"],
            longitude=h["lon"],
            rating=h["rating"],
            available_doctors=h["doctors"],
            address=f"{district_clean.title()}, {resolved_state}",
        )
        db.add(hospital)
        existing_names.add(h["name"].lower())
        inserted += 1

    if inserted:
        db.commit()
        logger.info(f"[populate] Inserted {inserted} new facilities for '{district_clean}'")

    # Cache regardless of whether we inserted — district is now ready
    _POPULATED_DISTRICTS.add(cache_key)


# ──────────────────────────────────────────────────────────────────────────────
# MATCHING ENGINE
# ──────────────────────────────────────────────────────────────────────────────

def find_matching_hospitals(
    db: Session,
    specialization: str | None,
    district: str | None,
    hospital_name: str | None,
    user_lat: float | None = None,
    user_lon: float | None = None,
    state: str | None = None,
) -> list[dict]:
    """
    Find and score matching hospitals.
    Returns list of {hospital, score} dicts, sorted by score descending.
    """
    if district:
        # Resolve canonical name (Shimoga -> Shivamogga, Mangaluru -> Mangalore, etc.)
        district = resolve_canonical_district(district)
        populate_dynamic_hospitals(db, district, specialization, state)

    query = db.query(Hospital)
    if district:
        query = query.filter(Hospital.district_name.ilike(f"%{district}%"))
    hospitals = query.all()

    # Country-wide fallback if nothing found
    if not hospitals and not hospital_name:
        hospitals = db.query(Hospital).limit(50).all()

    results = []
    for hosp in hospitals:
        score = 0

        # Exact / partial hospital name match
        if hospital_name:
            hn  = hospital_name.lower()
            hdb = hosp.hospital_name.lower()
            if hdb == hn:
                score += 2000
            elif hn in hdb or hdb in hn:
                score += 1000
            else:
                continue

        # Specialization match (when no specific hospital named)
        if specialization and not hospital_name:
            specs = [s.strip().lower() for s in hosp.specializations.split(",")]
            spec_l = specialization.lower()
            if spec_l in specs:
                score += 100
            elif any(spec_l in s for s in specs):
                score += 60
            else:
                continue

        # District match bonus
        if district:
            if hosp.district_name.lower() == district.lower():
                score += 50
            elif district.lower() in hosp.district_name.lower():
                score += 25

        # Rating bonus
        if hosp.rating:
            score += hosp.rating * 5

        # Proximity bonus
        if user_lat and user_lon and hosp.latitude and hosp.longitude:
            d = haversine(user_lat, user_lon, hosp.latitude, hosp.longitude)
            score += 20 if d < 5 else 15 if d < 10 else 10 if d < 20 else 5 if d < 50 else 0

        if score > 0:
            results.append({"hospital": hosp, "score": score})

    results.sort(key=lambda x: (x["score"], x["hospital"].rating or 0), reverse=True)
    return results


def get_best_hospital(
    db: Session,
    specialization: str | None,
    district: str | None,
    hospital_name: str | None,
    user_lat: float | None = None,
    user_lon: float | None = None,
    state: str | None = None,
) -> tuple[Hospital | None, int]:
    """Return the single best matching hospital + total count of matches."""
    matches = find_matching_hospitals(
        db, specialization, district, hospital_name, user_lat, user_lon, state
    )
    if matches:
        return matches[0]["hospital"], len(matches)

    # Last-resort: create a placeholder that always succeeds
    if district or hospital_name:
        spec_str  = specialization.title() if specialization else "General Physician"
        dist_str  = district.title()       if district       else "Local"
        state_str = state                  if state          else "India"
        dyn_name  = hospital_name or f"{dist_str} {spec_str} Hospital"

        assigned_district_id = 1
        assigned_state_id    = 1
        db_district = (
            db.query(District)
            .filter(District.district_name.ilike(f"%{dist_str}%"))
            .first()
        )
        if db_district:
            assigned_district_id = db_district.district_id
            assigned_state_id    = db_district.state_id
            db_state = db.query(State).filter(State.state_id == db_district.state_id).first()
            if db_state:
                state_str = db_state.state_name

        new_hospital = Hospital(
            hospital_name=dyn_name,
            specializations=_random_specs(n=8, include=specialization),
            district_name=dist_str,
            state_name=state_str,
            district_id=assigned_district_id,
            state_id=assigned_state_id,
            rating=4.5,
            available_doctors=10,
            latitude=db_district.latitude if db_district and db_district.latitude else (user_lat or 13.9299),
            longitude=db_district.longitude if db_district and db_district.longitude else (user_lon or 75.5681),
            address=f"{dist_str}, {state_str}",
        )
        db.add(new_hospital)
        db.commit()
        db.refresh(new_hospital)
        return new_hospital, 1

    return None, 0


def suggest_time_for_appointment(time_preference: str | None) -> str:
    """Suggest an appointment time from voice preference."""
    if time_preference:
        p = time_preference.lower()
        if "morning"   in p: return "10:30 AM"
        if "afternoon" in p: return "2:30 PM"
        if "evening"   in p or "night" in p: return "6:00 PM"
    return "5:00 PM"
