"""
SmartClinic GeoVoice Receptionist - Disease to Specialization Engine
Maps patient symptoms/diseases to the correct medical specialization.
"""

# Extensive mapping of diseases/symptoms to medical specializations
DISEASE_TO_SPECIALIZATION = {
    # General Physician
    "fever": "General Physician",
    "cold": "General Physician",
    "cough": "General Physician",
    "flu": "General Physician",
    "viral": "General Physician",
    "headache": "General Physician",
    "body ache": "General Physician",
    "weakness": "General Physician",
    "malaria": "General Physician",
    "dengue": "General Physician",
    
    # Cardiologist
    "chest pain": "Cardiologist",
    "heart": "Cardiologist",
    "heart attack": "Cardiologist",
    "palpitations": "Cardiologist",
    "high blood pressure": "Cardiologist",
    "bp": "Cardiologist",
    "hypertension": "Cardiologist",
    "cholesterol": "Cardiologist",
    "breathlessness": "Cardiologist",
    
    # Dentist
    "tooth": "Dentist",
    "toothache": "Dentist",
    "tooth pain": "Dentist",
    "cavity": "Dentist",
    "gums": "Dentist",
    "bleeding gums": "Dentist",
    "braces": "Dentist",
    "dental": "Dentist",
    "root canal": "Dentist",

    # Dermatologist
    "skin": "Dermatologist",
    "rash": "Dermatologist",
    "skin rash": "Dermatologist",
    "acne": "Dermatologist",
    "pimples": "Dermatologist",
    "hair fall": "Dermatologist",
    "dandruff": "Dermatologist",
    "eczema": "Dermatologist",
    "itching": "Dermatologist",
    "allergy": "Dermatologist",

    # Pediatrician (Adding "child" prefix logic will be handled in the extractor)
    "child fever": "Pediatrician",
    "baby fever": "Pediatrician",
    "child cough": "Pediatrician",
    "vaccination": "Pediatrician",
    "child": "Pediatrician",
    "kid": "Pediatrician",
    "baby": "Pediatrician",

    # Orthopedic
    "bone": "Orthopedic",
    "fracture": "Orthopedic",
    "joint pain": "Orthopedic",
    "knee pain": "Orthopedic",
    "back pain": "Orthopedic",
    "arthritis": "Orthopedic",
    "muscle pain": "Orthopedic",
    "sprain": "Orthopedic",

    # ENT Specialist
    "ear ache": "ENT Specialist",
    "ear pain": "ENT Specialist",
    "hearing loss": "ENT Specialist",
    "nose bleed": "ENT Specialist",
    "sinus": "ENT Specialist",
    "sore throat": "ENT Specialist",
    "tonsils": "ENT Specialist",
    "throat pain": "ENT Specialist",

    # Ophthalmologist
    "eye": "Ophthalmologist",
    "eye pain": "Ophthalmologist",
    "vision": "Ophthalmologist",
    "cataract": "Ophthalmologist",
    "blur vision": "Ophthalmologist",
    "red eye": "Ophthalmologist",
    
    # Gynecologist
    "pregnancy": "Gynecologist",
    "periods": "Gynecologist",
    "menstruation": "Gynecologist",
    "women": "Gynecologist",
    
    # Neurologist
    "migraine": "Neurologist",
    "brain": "Neurologist",
    "nerve": "Neurologist",
    "stroke": "Neurologist",
    "seizures": "Neurologist",
    "memory loss": "Neurologist",
    "paralysis": "Neurologist",
    
    # Oncologist
    "cancer": "Oncologist",
    "tumor": "Oncologist",
    "chemo": "Oncologist",
    # Urologist
    "kidney": "Urologist",
    "urine": "Urologist",
    "urinary": "Urologist",

    # Gastroenterologist
    "stomach": "Gastroenterologist",
    "stomach ache": "Gastroenterologist",
    "gastric": "Gastroenterologist",
    "digestion": "Gastroenterologist",
    "acidity": "Gastroenterologist",
    "vomiting": "Gastroenterologist",
    "nausea": "Gastroenterologist",
    "diarrhea": "Gastroenterologist",
    "constipation": "Gastroenterologist",

    # Pulmonologist
    "lung": "Pulmonologist",
    "asthma": "Pulmonologist",
    "pneumonia": "Pulmonologist",
    "breathing": "Pulmonologist",

    # Psychiatrist
    "mental": "Psychiatrist",
    "depression": "Psychiatrist",
    "anxiety": "Psychiatrist",
    "stress": "Psychiatrist",
    
    # Diabetologist
    "diabetes": "Diabetologist",
    "sugar": "Diabetologist",

    # --- Hindi / Kannada Aliases ---
    "ಜ್ವರ": "General Physician",
    "बुखार": "General Physician",
    "ಕೆಮ್ಮು": "General Physician",
    "खांसी": "General Physician",
    "ಶೀತ": "General Physician",
    "जुकाम": "General Physician",
    "ತಲೆನೋವು": "General Physician",
    "दर्द": "General Physician",
    "ಹೃದಯ ನೋವು": "Cardiologist",
    "ಹಾರ್ಟ್": "Cardiologist",
    "ಹಲ್ಲು ನೋವು": "Dentist",
    "ಮಕ್ಕಳ ಜ್ವರ": "Pediatrician",
    "ಮೂಳೆ ನೋವು": "Orthopedic",
    "ಚರ್ಮದ ಕಾಯಿಲೆ": "Dermatologist",
}

import re

def map_disease_to_specialization(disease: str) -> tuple[str | None, str | None]:
    """
    Map a given disease/symptom to a medical specialization using exact keyword boundaries.
    Returns (matched_disease_keyword, specialization) tuple.
    """
    if not disease:
        return None, None
        
    disease_lower = disease.lower().strip()
    
    # Sort keys by length descending to match longer phrases first e.g., "joint pain" before "pain"
    sorted_diseases = sorted(DISEASE_TO_SPECIALIZATION.keys(), key=len, reverse=True)
    
    for key in sorted_diseases:
        pattern = rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])"
        if re.search(pattern, disease_lower):
            spec = DISEASE_TO_SPECIALIZATION[key]
            # Special case for "child/baby/kid" prefix
            if re.search(r"\b(child|baby|kid|kids)\b", disease_lower):
                 spec = "Pediatrician"
            return key.title(), spec
            
    return None, None
