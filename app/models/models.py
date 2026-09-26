from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base


class Role(str, Enum):
    ORGANIZATION = 'ORGANIZATION'
    RECEIVER = 'RECEIVER'
    RECYCLER = 'RECYCLER'
    LOGISTICS = 'LOGISTICS'
    DRIVER = 'DRIVER'
    ADMIN = 'ADMIN'


class MaterialStatus(str, Enum):
    AVAILABLE = 'AVAILABLE'
    RESERVED = 'RESERVED'
    IN_TRANSFER = 'IN_TRANSFER'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'


class MatchStatus(str, Enum):
    RECOMMENDED = 'RECOMMENDED'
    REQUESTED = 'REQUESTED'
    ACCEPTED = 'ACCEPTED'
    FULFILLED = 'FULFILLED'
    REJECTED = 'REJECTED'
    CANCELLED = 'CANCELLED'


class TransferStatus(str, Enum):
    REQUESTED = 'REQUESTED'
    PICKUP_SCHEDULED = 'PICKUP_SCHEDULED'
    IN_TRANSIT = 'IN_TRANSIT'
    DELIVERED = 'DELIVERED'
    RECEIVED = 'RECEIVED'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'


class NeedStatus(str, Enum):
    OPEN = 'OPEN'
    MATCHED = 'MATCHED'
    CLOSED = 'CLOSED'


class OutcomeStatus(str, Enum):
    NOT_STARTED = 'NOT_STARTED'
    SUBMITTED = 'SUBMITTED'
    UNDER_REVIEW = 'UNDER_REVIEW'
    CORRECTION_REQUESTED = 'CORRECTION_REQUESTED'
    VERIFIED = 'VERIFIED'
    REJECTED = 'REJECTED'


class NotificationType(str, Enum):
    GENERAL = 'GENERAL'
    MATCH_REQUEST = 'MATCH_REQUEST'
    MATCH_ACCEPTED = 'MATCH_ACCEPTED'
    DRIVER_ASSIGNED = 'DRIVER_ASSIGNED'
    DRIVER_ACCEPTED = 'DRIVER_ACCEPTED'
    TRIP_STARTED = 'TRIP_STARTED'
    ARRIVAL = 'ARRIVAL'
    RECEIPT_CONFIRMED = 'RECEIPT_CONFIRMED'
    OUTCOME_SUBMITTED = 'OUTCOME_SUBMITTED'
    OUTCOME_VERIFIED = 'OUTCOME_VERIFIED'
    OUTCOME_REJECTED = 'OUTCOME_REJECTED'
    OUTCOME_CORRECTION_REQUESTED = 'OUTCOME_CORRECTION_REQUESTED'


class Organization(Base):
    __tablename__ = 'organizations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    organization_type: Mapped[str] = mapped_column(String(80), default='Company')
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100), default='Maharashtra')
    address: Mapped[str] = mapped_column(String(255), default='')
    latitude: Mapped[float] = mapped_column(Float, default=19.076)
    longitude: Mapped[float] = mapped_column(Float, default=72.8777)
    contact_email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    verification_status: Mapped[str] = mapped_column(String(30), default='PENDING')
    materials_supported: Mapped[str] = mapped_column(Text, default='all')
    capacity: Mapped[float] = mapped_column(Float, default=0)
    service_area_km: Mapped[float] = mapped_column(Float, default=50)
    certifications: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default=Role.ORGANIZATION.value)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey('organizations.id'), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    organization: Mapped[Organization | None] = relationship()


class ReceiverNeed(Base):
    __tablename__ = 'receiver_needs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'))
    material_name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(80), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    remaining_quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(30), default='units')
    acceptable_condition: Mapped[str] = mapped_column(String(30), default='GOOD')
    needed_by: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[str] = mapped_column(String(30), default=NeedStatus.OPEN.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    organization: Mapped[Organization] = relationship()


class Material(Base):
    __tablename__ = 'materials'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'))
    name: Mapped[str] = mapped_column(String(160), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(Text, default='')
    quantity: Mapped[float] = mapped_column(Float)
    remaining_quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(30), default='units')
    condition: Mapped[str] = mapped_column(String(30), default='GOOD')
    age_years: Mapped[float] = mapped_column(Float, default=1)
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100), default='Maharashtra')
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    estimated_value: Mapped[float] = mapped_column(Float, default=0)
    available_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(30), default=MaterialStatus.AVAILABLE.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    owner: Mapped[Organization] = relationship()


class MaterialImage(Base):
    __tablename__ = 'material_images'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey('materials.id'))
    filename: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Assessment(Base):
    __tablename__ = 'assessments'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey('materials.id'))
    condition_score: Mapped[float] = mapped_column(Float)
    recommendation: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float] = mapped_column(Float)
    reuse_score: Mapped[float] = mapped_column(Float)
    refurbish_score: Mapped[float] = mapped_column(Float)
    recycle_score: Mapped[float] = mapped_column(Float)
    recover_score: Mapped[float] = mapped_column(Float)
    reason_json: Mapped[str] = mapped_column(Text, default='{}')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Match(Base):
    __tablename__ = 'matches'
    __table_args__ = (UniqueConstraint('material_id', 'partner_organization_id', 'need_id', name='uq_match_material_partner_need'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey('materials.id'))
    partner_organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'))
    need_id: Mapped[int | None] = mapped_column(ForeignKey('receiver_needs.id'), nullable=True)
    match_score: Mapped[float] = mapped_column(Float)
    distance_km: Mapped[float] = mapped_column(Float)
    reason_json: Mapped[str] = mapped_column(Text, default='{}')
    status: Mapped[str] = mapped_column(String(30), default=MatchStatus.RECOMMENDED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Route(Base):
    __tablename__ = 'routes'
    __table_args__ = (UniqueConstraint('material_id', 'partner_organization_id', 'vehicle_type', name='uq_route_material_partner_vehicle'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey('materials.id'))
    partner_organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'))
    source_lat: Mapped[float] = mapped_column(Float)
    source_lng: Mapped[float] = mapped_column(Float)
    destination_lat: Mapped[float] = mapped_column(Float)
    destination_lng: Mapped[float] = mapped_column(Float)
    vehicle_type: Mapped[str] = mapped_column(String(60))
    distance_km: Mapped[float] = mapped_column(Float)
    estimated_time_min: Mapped[float] = mapped_column(Float)
    estimated_co2_kg: Mapped[float] = mapped_column(Float)
    route_score: Mapped[float] = mapped_column(Float)
    emission_factor_kg_per_km: Mapped[float] = mapped_column(Float)
    capacity_units: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Driver(Base):
    __tablename__ = 'drivers'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'))
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), unique=True, nullable=True)
    driver_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(30), default='')
    vehicle_type: Mapped[str] = mapped_column(String(60), default='MINI TRUCK')
    vehicle_number: Mapped[str] = mapped_column(String(40), default='')
    status: Mapped[str] = mapped_column(String(30), default='AVAILABLE')
    current_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    organization: Mapped[Organization] = relationship()
    user: Mapped[User | None] = relationship(foreign_keys=[user_id])


class Transfer(Base):
    __tablename__ = 'transfers'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey('materials.id'))
    source_organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'))
    receiver_organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'))
    logistics_partner_id: Mapped[int | None] = mapped_column(ForeignKey('organizations.id'), nullable=True)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey('drivers.id'), nullable=True)
    driver_accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    route_id: Mapped[int | None] = mapped_column(ForeignKey('routes.id'), nullable=True)
    match_id: Mapped[int | None] = mapped_column(ForeignKey('matches.id'), nullable=True)
    need_id: Mapped[int | None] = mapped_column(ForeignKey('receiver_needs.id'), nullable=True)
    quantity: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(40), default=TransferStatus.REQUESTED.value)
    pickup_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivery_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    received_condition: Mapped[str | None] = mapped_column(String(30), nullable=True)
    receipt_notes: Mapped[str] = mapped_column(Text, default='')
    receipt_photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TransferEvent(Base):
    __tablename__ = 'transfer_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey('transfers.id'))
    event_type: Mapped[str] = mapped_column(String(60))
    message: Mapped[str] = mapped_column(Text)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LocationUpdate(Base):
    __tablename__ = 'location_updates'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey('transfers.id'))
    driver_id: Mapped[int] = mapped_column(ForeignKey('drivers.id'))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_kmph: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = 'notifications'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    transfer_id: Mapped[int | None] = mapped_column(ForeignKey('transfers.id'), nullable=True)
    type: Mapped[str] = mapped_column(String(40), default=NotificationType.GENERAL.value)
    title: Mapped[str] = mapped_column(String(180))
    message: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(30), default='IN_APP')
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OutcomeEvidence(Base):
    __tablename__ = 'outcome_evidence'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey('transfers.id'), unique=True)
    pathway: Mapped[str] = mapped_column(String(30))
    claimed_quantity: Mapped[float] = mapped_column(Float)
    narrative: Mapped[str] = mapped_column(Text)
    evidence_status: Mapped[str] = mapped_column(String(30), default=OutcomeStatus.SUBMITTED.value)
    before_photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    after_photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    process_document_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    outcome_document_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    submitted_by_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    reviewer_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    reviewer_note: Mapped[str] = mapped_column(Text, default='')
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Impact(Base):
    __tablename__ = 'impacts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey('materials.id'))
    transfer_id: Mapped[int] = mapped_column(ForeignKey('transfers.id'), unique=True)
    outcome_id: Mapped[int] = mapped_column(ForeignKey('outcome_evidence.id'), unique=True)
    value_recovered: Mapped[float] = mapped_column(Float, default=0)
    waste_avoided_kg: Mapped[float] = mapped_column(Float, default=0)
    co2_avoided_kg: Mapped[float] = mapped_column(Float, default=0)
    pathway: Mapped[str] = mapped_column(String(30))
    verified_quantity: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
