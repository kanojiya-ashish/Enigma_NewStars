from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import current_user, require_roles
from ..core.security import hash_password
from ..models.models import Driver, Role, Transfer, TransferStatus, User
from ..schemas.schemas import DriverCreate, DriverOut
from ..services.routing import VEHICLES, normalize_vehicle

router = APIRouter(prefix='/api/logistics', tags=['Logistics & Drivers'])


@router.get('/drivers', response_model=list[DriverOut])
def list_drivers(user: User = Depends(require_roles(Role.LOGISTICS.value, Role.ADMIN.value)), db: Session = Depends(get_db)):
    q = select(Driver).where(Driver.is_active.is_(True)).order_by(Driver.status, Driver.name)
    if user.role != Role.ADMIN.value:
        q = q.where(Driver.organization_id == user.organization_id)
    return list(db.scalars(q).all())


@router.get('/drivers/eligible')
def eligible_drivers(
    quantity: float,
    vehicle_type: str | None = None,
    user: User = Depends(require_roles(Role.LOGISTICS.value, Role.ADMIN.value)),
    db: Session = Depends(get_db),
):
    if quantity <= 0:
        raise HTTPException(422, 'Quantity must be greater than zero')
    q = select(Driver).where(Driver.is_active.is_(True), Driver.status == 'AVAILABLE')
    if user.role != Role.ADMIN.value:
        q = q.where(Driver.organization_id == user.organization_id)
    requested = normalize_vehicle(vehicle_type) if vehicle_type else None
    rows = list(db.scalars(q.order_by(Driver.name)).all())
    eligible = []
    for driver in rows:
        key = normalize_vehicle(driver.vehicle_type)
        spec = VEHICLES.get(key)
        if not spec or spec['capacity'] < quantity:
            continue
        if requested and key != requested:
            continue
        eligible.append(driver)
    return [
        {
            'id': driver.id,
            'organization_id': driver.organization_id,
            'user_id': driver.user_id,
            'driver_code': driver.driver_code,
            'name': driver.name,
            'phone': driver.phone,
            'vehicle_type': normalize_vehicle(driver.vehicle_type),
            'vehicle_number': driver.vehicle_number,
            'status': driver.status,
            'current_lat': driver.current_lat,
            'current_lng': driver.current_lng,
            'last_seen_at': driver.last_seen_at,
            'is_active': driver.is_active,
        }
        for driver in eligible
    ]

@router.get('/drivers/me', response_model=DriverOut)
def my_driver(user: User = Depends(require_roles(Role.DRIVER.value)), db: Session = Depends(get_db)):
    driver = db.scalar(select(Driver).where(Driver.user_id == user.id))
    if not driver: raise HTTPException(404, 'Driver profile not found')
    return driver


@router.post('/drivers', response_model=DriverOut)
def create_driver(payload: DriverCreate, user: User = Depends(require_roles(Role.LOGISTICS.value, Role.ADMIN.value)), db: Session = Depends(get_db)):
    org_id = user.organization_id
    if user.role == Role.ADMIN.value:
        org_id = db.scalar(select(Driver.organization_id).order_by(desc(Driver.id)))
    if not org_id:
        raise HTTPException(400, 'A logistics organisation is required')
    vehicle = normalize_vehicle(payload.vehicle_type)
    if vehicle not in VEHICLES: raise HTTPException(422, 'Unsupported vehicle type')
    if db.scalar(select(User).where(User.email == payload.email.lower().strip())):
        raise HTTPException(409, 'Driver email already exists')
    user_row = User(name=payload.name, email=payload.email.lower().strip(), password_hash=hash_password(payload.password), role=Role.DRIVER.value, organization_id=org_id)
    db.add(user_row); db.flush()
    code = f'DRV-{1000 + int(db.scalar(select(Driver.id).order_by(desc(Driver.id))) or 0) + 1}'
    driver = Driver(organization_id=org_id, user_id=user_row.id, driver_code=code, name=payload.name, phone=payload.phone, vehicle_type=vehicle, vehicle_number=payload.vehicle_number, status='AVAILABLE')
    db.add(driver); db.commit(); db.refresh(driver)
    return driver


@router.get('/jobs')
def jobs(user: User = Depends(require_roles(Role.LOGISTICS.value)), db: Session = Depends(get_db)):
    rows = db.scalars(select(Transfer).where(Transfer.logistics_partner_id == user.organization_id).order_by(desc(Transfer.created_at))).all()
    return [{'id': row.id, 'status': row.status, 'quantity': row.quantity, 'driver_id': row.driver_id, 'route_id': row.route_id} for row in rows]
