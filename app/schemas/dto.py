from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    email: str


class FarmerCreate(BaseModel):
    farm_name: str
    region: str
    village: str = ""
    lat: float = 16.55
    lng: float = 82.0
    phone: str = ""


class BatchCreate(BaseModel):
    crop: str
    variety: str = ""
    quantity_kg: float = Field(gt=0)
    harvest_date: str
    origin: str
    expected_destination: str = ""
    farmer_id: str | None = None
    image_url: str = ""
    farmer_price: float = 0


class EventCreate(BaseModel):
    batch_id: str
    event_type: str
    location: str
    lat: float = 0
    lng: float = 0
    metadata: dict = Field(default_factory=dict)


class QualityCreate(BaseModel):
    batch_id: str
    moisture: float
    foreign_matter: float
    location: str
    inspection_date: str


class SensorIn(BaseModel):
    batch_id: str
    temperature: float | None = None
    humidity: float | None = None
    lat: float | None = None
    lng: float | None = None
    speed_kmh: float | None = None
    vibration: float | None = None
    spike: bool = False


class RecallIn(BaseModel):
    batch_id: str
    reason: str


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str
    organization: str = ""
    location: str = ""
