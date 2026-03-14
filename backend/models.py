"""
SmartClinic GeoVoice Receptionist - Database Models
Full schema: States, Districts, Hospitals, Appointments, Receptionists
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base
import datetime


class State(Base):
    __tablename__ = "states"

    state_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    state_name = Column(String(100), nullable=False, unique=True, index=True)

    districts = relationship("District", back_populates="state")
    hospitals = relationship("Hospital", back_populates="state")


class District(Base):
    __tablename__ = "districts"

    district_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    district_name = Column(String(100), nullable=False, index=True)
    state_id = Column(Integer, ForeignKey("states.state_id"), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    state = relationship("State", back_populates="districts")
    hospitals = relationship("Hospital", back_populates="district_rel")


class Hospital(Base):
    __tablename__ = "hospitals"

    hospital_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hospital_name = Column(String(200), nullable=False, index=True)
    specializations = Column(String(500), nullable=False)  # comma-separated
    district_id = Column(Integer, ForeignKey("districts.district_id"), nullable=False)
    state_id = Column(Integer, ForeignKey("states.state_id"), nullable=False)
    district_name = Column(String(100), nullable=False, index=True)
    state_name = Column(String(100), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    available_doctors = Column(Integer, default=5)
    email = Column(String(200), nullable=True)
    phone = Column(String(20), nullable=True)
    rating = Column(Float, default=4.0)
    address = Column(String(300), nullable=True)

    state = relationship("State", back_populates="hospitals")
    district_rel = relationship("District", back_populates="hospitals")
    appointments = relationship("Appointment", back_populates="hospital")


class Appointment(Base):
    __tablename__ = "appointments"

    appointment_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.hospital_id"), nullable=False)
    patient_name = Column(String(100), nullable=False, default="Voice User")
    patient_phone = Column(String(20), nullable=True)
    patient_email = Column(String(150), nullable=True)
    specialization = Column(String(100), nullable=True)
    date = Column(String(20), nullable=False)
    time = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="confirmed")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    hospital = relationship("Hospital", back_populates="appointments")


class Receptionist(Base):
    __tablename__ = "receptionists"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
