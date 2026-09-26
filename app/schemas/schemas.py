from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    organization_type: str
    city: str
    state: str
    address: str
    latitude: float
    longitude: float
    contact_email: str
    verification_status: str
    materials_supported: str
    capacity: float
    service_area_km: float
    certifications: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    role: str
    organization_id: int | None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: UserOut
    organization: OrganizationOut | None = None


def _validate_email(value: str) -> str:
    value = value.strip().lower()
    if '@' not in value or '.' not in value.rsplit('@', 1)[-1] or ' ' in value:
        raise ValueError('Enter a valid email address')
    return value


class LoginIn(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)
    role: str | None = None

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email(value)


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    organization_name: str = Field(min_length=2, max_length=160)
    organization_type: str = Field(min_length=2, max_length=80)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(default='Maharashtra', min_length=2, max_length=100)
    address: str = Field(default='', max_length=255)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    email: str
    password: str = Field(min_length=8, max_length=128)
    role: Literal['ORGANIZATION', 'RECEIVER', 'RECYCLER', 'LOGISTICS']
    materials_supported: str = 'all'
    capacity: float = Field(default=500, ge=0)
    service_area_km: float = Field(default=50, gt=0)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email(value)


class VerificationUpdate(BaseModel):
    status: Literal['VERIFIED', 'SUSPENDED', 'PENDING']


class MaterialCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=80)
    description: str = Field(default='', max_length=2000)
    quantity: float = Field(gt=0)
    unit: str = Field(default='units', min_length=1, max_length=30)
    condition: Literal['EXCELLENT', 'GOOD', 'FAIR', 'POOR'] = 'GOOD'
    age_years: float = Field(default=1, ge=0)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(default='Maharashtra', min_length=2, max_length=100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    estimated_value: float = Field(default=0, ge=0)


class MaterialUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    estimated_value: float | None = Field(default=None, ge=0)
    available_from: datetime | None = None


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_organization_id: int
    name: str
    category: str
    description: str
    quantity: float
    remaining_quantity: float
    unit: str
    condition: str
    age_years: float
    city: str
    state: str
    latitude: float
    longitude: float
    estimated_value: float
    available_from: datetime
    status: str
    created_at: datetime


class AssessmentOut(BaseModel):
    id: int
    material_id: int
    condition_score: float
    recommendation: str
    confidence: float
    scores: dict[str, float]
    reasons: list[str]
    factor_breakdown: dict[str, float]
    methodology: str


class ReceiverNeedCreate(BaseModel):
    material_name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=80)
    quantity: float = Field(gt=0)
    unit: str = Field(default='units', min_length=1, max_length=30)
    acceptable_condition: Literal['EXCELLENT', 'GOOD', 'FAIR', 'POOR'] = 'GOOD'
    needed_by: datetime | None = None
    notes: str = Field(default='', max_length=1500)


class ReceiverNeedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organization_id: int
    material_name: str
    category: str
    quantity: float
    remaining_quantity: float
    unit: str
    acceptable_condition: str
    needed_by: datetime | None
    notes: str
    status: str
    created_at: datetime


class MatchOut(BaseModel):
    id: int | None
    material_id: int
    need_id: int | None
    need_remaining_quantity: float | None = None
    need_unit: str | None = None
    partner: OrganizationOut
    source: OrganizationOut | None
    match_score: float
    distance_km: float
    reasons: list[str]
    status: str
    factor_breakdown: dict[str, float]


class MatchRequest(BaseModel):
    material_id: int
    partner_organization_id: int
    need_id: int | None = None


class MatchDecision(BaseModel):
    decision: Literal['ACCEPTED', 'REJECTED']


class RouteIn(BaseModel):
    material_id: int
    partner_organization_id: int
    vehicle_type: str
    quantity: float = Field(gt=0)


class RouteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    material_id: int
    partner_organization_id: int
    vehicle_type: str
    distance_km: float
    estimated_time_min: float
    estimated_co2_kg: float
    route_score: float
    emission_factor_kg_per_km: float
    capacity_units: float
    source_lat: float
    source_lng: float
    destination_lat: float
    destination_lng: float


class DriverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organization_id: int
    user_id: int | None
    driver_code: str
    name: str
    phone: str
    vehicle_type: str
    vehicle_number: str
    status: str
    current_lat: float | None
    current_lng: float | None
    last_seen_at: datetime | None
    is_active: bool


class DriverCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str
    password: str = Field(min_length=8, max_length=128)
    phone: str = Field(default='', max_length=30)
    vehicle_type: str = Field(min_length=2, max_length=60)
    vehicle_number: str = Field(min_length=2, max_length=40)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email(value)


class TransferCreate(BaseModel):
    material_id: int
    receiver_organization_id: int
    logistics_partner_id: int
    route_id: int
    quantity: float = Field(gt=0)
    need_id: int | None = None


class DriverAssignment(BaseModel):
    driver_id: int


class LocationPing(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)
    speed_kmph: float | None = Field(default=None, ge=0)


class ReceiptConfirm(BaseModel):
    received_quantity: float = Field(gt=0)
    received_condition: Literal['EXCELLENT', 'GOOD', 'FAIR', 'POOR']
    notes: str = Field(default='', max_length=1500)
    receipt_photo_url: str | None = None


class OutcomeSubmission(BaseModel):
    pathway: Literal['REUSE', 'REFURBISH', 'RECYCLE', 'RECOVER']
    claimed_quantity: float = Field(gt=0)
    narrative: str = Field(min_length=20, max_length=3000)
    before_photo_url: str | None = None
    after_photo_url: str | None = None
    process_document_url: str | None = None
    outcome_document_url: str | None = None


class OutcomeReview(BaseModel):
    decision: Literal['VERIFIED', 'CORRECTION_REQUESTED', 'REJECTED']
    reviewer_note: str = Field(default='', max_length=2000)


class OutcomeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    transfer_id: int
    pathway: str
    claimed_quantity: float
    narrative: str
    evidence_status: str
    before_photo_url: str | None
    after_photo_url: str | None
    process_document_url: str | None
    outcome_document_url: str | None
    submitted_at: datetime
    reviewed_at: datetime | None
    reviewer_note: str


class TransferOut(BaseModel):
    id: int
    material_id: int
    source_organization_id: int
    receiver_organization_id: int
    logistics_partner_id: int | None
    driver_id: int | None
    driver_accepted_at: datetime | None = None
    driver_code: str | None = None
    driver_name: str | None = None
    driver_vehicle_type: str | None = None
    driver_vehicle_number: str | None = None
    route_id: int | None
    route_vehicle_type: str | None = None
    match_id: int | None = None
    need_id: int | None = None
    quantity: float
    status: str
    pickup_time: datetime | None
    delivery_time: datetime | None
    arrived_at: datetime | None
    received_at: datetime | None
    received_quantity: float | None
    received_condition: str | None
    receipt_notes: str
    receipt_photo_url: str | None
    cancelled_at: datetime | None
    created_at: datetime
    outcome: OutcomeOut | None = None


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    transfer_id: int | None
    type: str
    title: str
    message: str
    channel: str
    is_read: bool
    created_at: datetime


class TrackingOut(BaseModel):
    transfer: TransferOut
    driver: DriverOut | None
    source: OrganizationOut | None
    receiver: OrganizationOut | None
    logistics: OrganizationOut | None
    route: RouteOut | None
    latest_location: dict | None
    location_history: list[dict]
    event_history: list[dict]
    arrived: bool


class ImpactOut(BaseModel):
    value_recovered: float
    waste_avoided_kg: float
    co2_avoided_kg: float
    verified_transfers: int
    verified_quantity: float
    by_pathway: dict[str, float]
    pathway_counts: dict[str, int]
    average_match_score: float


class DashboardOut(BaseModel):
    role: str
    organization: OrganizationOut | None
    metrics: dict[str, float | int | str]
    recent_transfers: list[TransferOut]
    notifications_unread: int


class ReportOut(BaseModel):
    report: str
    generated_at: str
    transfer: dict
    material: dict | None
    source: dict | None
    receiver: dict | None
    logistics: dict | None
    driver: dict | None
    decision: dict | None
    route: dict | None
    tracking: dict
    receipt: dict | None
    outcome: dict | None
    impact: dict | None
    methodology: str
