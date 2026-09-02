from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(64), index=True)
    organization: Mapped[str] = mapped_column(String(255), default="")
    location: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Farmer(Base):
    __tablename__ = "farmers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    farmer_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    farm_name: Mapped[str] = mapped_column(String(255))
    region: Mapped[str] = mapped_column(String(255))
    village: Mapped[str] = mapped_column(String(255), default="")
    lat: Mapped[float] = mapped_column(Float, default=16.55)
    lng: Mapped[float] = mapped_column(Float, default=82.00)
    phone: Mapped[str] = mapped_column(String(32), default="")
    user: Mapped[User] = relationship()


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    crop: Mapped[str] = mapped_column(String(64), index=True)
    variety: Mapped[str] = mapped_column(String(128), default="")
    quantity_kg: Mapped[float] = mapped_column(Float)
    harvest_date: Mapped[str] = mapped_column(String(32))
    origin: Mapped[str] = mapped_column(String(255))
    farmer_id: Mapped[int | None] = mapped_column(ForeignKey("farmers.id"), nullable=True)
    farmer_name: Mapped[str] = mapped_column(String(255), default="")
    expected_destination: Mapped[str] = mapped_column(String(255), default="")
    image_url: Mapped[str] = mapped_column(String(512), default="")
    current_location: Mapped[str] = mapped_column(String(255), default="")
    current_stakeholder: Mapped[str] = mapped_column(String(64), default="FARMER")
    quality_grade: Mapped[str] = mapped_column(String(16), default="PENDING")
    quality_score: Mapped[float] = mapped_column(Float, default=0)
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    risk_level: Mapped[str] = mapped_column(String(16), default="LOW")
    trust_score: Mapped[float] = mapped_column(Float, default=70)
    sustainability_score: Mapped[float] = mapped_column(Float, default=70)
    verification_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    contaminated: Mapped[bool] = mapped_column(Boolean, default=False)
    recall_status: Mapped[str] = mapped_column(String(32), default="")
    farmer_price: Mapped[float] = mapped_column(Float, default=0)
    processor_price: Mapped[float] = mapped_column(Float, default=0)
    distributor_price: Mapped[float] = mapped_column(Float, default=0)
    retail_price: Mapped[float] = mapped_column(Float, default=0)
    payment_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


Index("ix_batches_crop_origin", Batch.crop, Batch.origin)


class SupplyChainEvent(Base):
    __tablename__ = "supply_chain_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    actor_email: Mapped[str] = mapped_column(String(255))
    actor_role: Mapped[str] = mapped_column(String(64))
    location: Mapped[str] = mapped_column(String(255))
    lat: Mapped[float] = mapped_column(Float, default=0)
    lng: Mapped[float] = mapped_column(Float, default=0)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    document_hash: Mapped[str] = mapped_column(String(64), default="")
    tx_id: Mapped[str] = mapped_column(String(64), index=True)
    block_index: Mapped[int] = mapped_column(Integer, default=0)
    block_hash: Mapped[str] = mapped_column(String(64), default="")
    data_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class BlockchainBlock(Base):
    __tablename__ = "blockchain_blocks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    index: Mapped[int] = mapped_column(Integer, unique=True)
    timestamp: Mapped[float] = mapped_column(Float)
    previous_hash: Mapped[str] = mapped_column(String(64))
    nonce: Mapped[int] = mapped_column(Integer)
    hash: Mapped[str] = mapped_column(String(64), index=True)
    tx_count: Mapped[int] = mapped_column(Integer, default=0)


class ChainTransaction(Base):
    __tablename__ = "chain_transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tx_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    block_index: Mapped[int] = mapped_column(Integer, index=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(255))
    payload_json: Mapped[str] = mapped_column(Text)


class QualityInspection(Base):
    __tablename__ = "quality_inspections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    moisture: Mapped[float] = mapped_column(Float)
    foreign_matter: Mapped[float] = mapped_column(Float)
    grade: Mapped[str] = mapped_column(String(16))
    quality_score: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32))
    inspector: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(255))
    inspection_date: Mapped[str] = mapped_column(String(32))
    certificate_hash: Mapped[str] = mapped_column(String(64), default="")


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    temperature: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float] = mapped_column(Float)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    speed_kmh: Mapped[float] = mapped_column(Float, default=0)
    vibration: Mapped[float] = mapped_column(Float, default=0)
    anomalous: Mapped[bool] = mapped_column(Boolean, default=False)
    anchored: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Transport(Base):
    __tablename__ = "transports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    vehicle_id: Mapped[str] = mapped_column(String(64))
    origin: Mapped[str] = mapped_column(String(255))
    destination: Mapped[str] = mapped_column(String(255))
    origin_lat: Mapped[float] = mapped_column(Float)
    origin_lng: Mapped[float] = mapped_column(Float)
    dest_lat: Mapped[float] = mapped_column(Float)
    dest_lng: Mapped[float] = mapped_column(Float)
    current_lat: Mapped[float] = mapped_column(Float)
    current_lng: Mapped[float] = mapped_column(Float)
    distance_km: Mapped[float] = mapped_column(Float)
    delay_hours: Mapped[float] = mapped_column(Float, default=0)
    progress: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(32), default="IN_TRANSIT")


class WarehouseRecord(Base):
    __tablename__ = "warehouse_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    warehouse_name: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ProcessingRecord(Base):
    __tablename__ = "processing_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    process_type: Mapped[str] = mapped_column(String(128))
    facility: Mapped[str] = mapped_column(String(255))
    notes: Mapped[str] = mapped_column(Text, default="")


class DistributionRecord(Base):
    __tablename__ = "distribution_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    hub: Mapped[str] = mapped_column(String(255))
    destination: Mapped[str] = mapped_column(String(255))


class RetailRecord(Base):
    __tablename__ = "retail_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    store: Mapped[str] = mapped_column(String(255))
    price_per_kg: Mapped[float] = mapped_column(Float)
    location: Mapped[str] = mapped_column(String(255))


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    doc_type: Mapped[str] = mapped_column(String(64))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    stored_path: Mapped[str] = mapped_column(String(512))
    tx_id: Mapped[str] = mapped_column(String(64), default="")
    uploaded_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    score: Mapped[float] = mapped_column(Float)
    level: Mapped[str] = mapped_column(String(16))
    reasons_json: Mapped[str] = mapped_column(Text)
    importance_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Recall(Base):
    __tablename__ = "recalls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    affected_locations_json: Mapped[str] = mapped_column(Text, default="[]")
    affected_units: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    batch_id: Mapped[str] = mapped_column(String(64), default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(128), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class OfflineQueueItem(Base):
    __tablename__ = "offline_queue"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
