"""
SmartClinic GeoVoice Receptionist - Pydantic Schemas
Request/Response models for all API endpoints.
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ---------- State / District Schemas ----------
class StateOut(BaseModel):
    state_id: int
    state_name: str

    class Config:
        from_attributes = True


class DistrictOut(BaseModel):
    district_id: int
    district_name: str
    state_id: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    class Config:
        from_attributes = True


# ---------- Hospital Schemas ----------
class HospitalBase(BaseModel):
    hospital_name: str
    specializations: str
    district_name: str
    state_name: str
    latitude: float
    longitude: float
    available_doctors: Optional[int] = 5
    email: Optional[str] = None
    phone: Optional[str] = None
    rating: Optional[float] = 4.0
    address: Optional[str] = None


class HospitalCreate(HospitalBase):
    district_id: int
    state_id: int


class HospitalUpdate(BaseModel):
    hospital_name: Optional[str] = None
    specializations: Optional[str] = None
    available_doctors: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    rating: Optional[float] = None
    address: Optional[str] = None


class HospitalOut(HospitalBase):
    hospital_id: int
    district_id: int
    state_id: int

    class Config:
        from_attributes = True


class HospitalMapOut(BaseModel):
    name: str
    lat: float
    lng: float
    specialization: str
    rating: float


# ---------- Appointment Schemas ----------
class AppointmentCreate(BaseModel):
    hospital_id: int
    patient_name: Optional[str] = "Voice User"
    patient_phone: Optional[str] = None
    patient_email: Optional[str] = None
    specialization: Optional[str] = None
    date: str
    time: str
    notes: Optional[str] = None


class AppointmentOut(BaseModel):
    appointment_id: int
    hospital_id: int
    patient_name: str
    patient_phone: Optional[str] = None
    patient_email: Optional[str] = None
    specialization: Optional[str] = None
    date: str
    time: str
    status: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    hospital: Optional[HospitalOut] = None

    class Config:
        from_attributes = True


# ---------- Auth Schemas ----------
class ReceptionistCreate(BaseModel):
    name: str
    email: str
    password: str


class ReceptionistLogin(BaseModel):
    email: str
    password: str


class ReceptionistOut(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str
    receptionist: ReceptionistOut


# ---------- Voice/Intent Schemas ----------
class VoiceTextInput(BaseModel):
    text: str
    patient_name: Optional[str] = "Voice User"
    patient_phone: Optional[str] = None
    patient_email: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    receptionist_email: Optional[str] = None  # logged-in user's email for notifications
    time_slot: Optional[str] = None


class ExtractedIntent(BaseModel):
    command: Optional[str] = "book"
    disease: Optional[str] = None
    specialization: Optional[str] = None
    hospital_name: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    date: Optional[str] = None
    time_preference: Optional[str] = None
    raw_text: str


class VoiceBookingResponse(BaseModel):
    success: bool
    message: str
    intent: Optional[ExtractedIntent] = None
    matched_hospital: Optional[HospitalOut] = None
    appointment: Optional[AppointmentOut] = None
    all_matches: Optional[List[HospitalOut]] = None
    found_nodes: Optional[int] = 0
    email_sent_to: Optional[str] = None
    token_number: Optional[int] = None
