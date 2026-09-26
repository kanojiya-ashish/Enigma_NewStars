from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import current_user, require_roles
from ..models.models import Material, Organization, Role, Route, User
from ..schemas.schemas import RouteIn, RouteOut
from ..services.routing import VEHICLES, calculate_route_values

router = APIRouter(prefix='/api/routes', tags=['Smart Routing'])


@router.get('/options/{material_id}/{partner_organization_id}', response_model=list[RouteOut])
def route_options(material_id: int, partner_organization_id: int, quantity: float = Query(gt=0), user: User = Depends(current_user), db: Session = Depends(get_db)):
    material = db.get(Material, material_id); partner = db.get(Organization, partner_organization_id)
    if not material or not partner:
        raise HTTPException(404, 'Material or destination partner not found')
    if partner.verification_status != 'VERIFIED' or partner.organization_type not in {'NGO', 'College', 'Institution', 'Small Business', 'Refurbisher', 'Recycler', 'Recovery Partner'}:
        raise HTTPException(409, 'Destination partner is not a verified exchange partner')
    if user.role == Role.ORGANIZATION.value and material.owner_organization_id != user.organization_id:
        raise HTTPException(403, 'You do not own this material')
    if material.remaining_quantity <= 1e-9 or material.status in {'IN_TRANSFER', 'COMPLETED', 'CANCELLED'}:
        raise HTTPException(409, 'Material is not available for transport planning')
    if user.role not in {Role.ORGANIZATION.value, Role.RECEIVER.value, Role.RECYCLER.value, Role.LOGISTICS.value, Role.ADMIN.value}:
        raise HTTPException(403, 'This workspace cannot plan transport')
    rows = []
    for vehicle_type, spec in VEHICLES.items():
        if spec['capacity'] >= quantity:
            values = calculate_route_values(material, partner, vehicle_type, quantity)
            existing = db.scalar(select(Route).where(Route.material_id == material_id, Route.partner_organization_id == partner_organization_id, Route.vehicle_type == vehicle_type))
            if existing:
                for key, value in values.items(): setattr(existing, key, value)
                row = existing
            else:
                row = Route(material_id=material_id, partner_organization_id=partner_organization_id, **values)
                db.add(row); db.flush()
            rows.append(row)
    db.commit()
    return sorted(rows, key=lambda r: (r.estimated_co2_kg, r.estimated_time_min))


@router.post('/calculate', response_model=RouteOut)
def calculate_route(payload: RouteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    material = db.get(Material, payload.material_id); partner = db.get(Organization, payload.partner_organization_id)
    if not material or not partner:
        raise HTTPException(404, 'Material or destination partner not found')
    if user.role == Role.ORGANIZATION.value and material.owner_organization_id != user.organization_id:
        raise HTTPException(403, 'You do not own this material')
    if material.remaining_quantity <= 1e-9 or material.status in {'IN_TRANSFER', 'COMPLETED', 'CANCELLED'}:
        raise HTTPException(409, 'Material is not available for transport planning')
    if user.role not in {Role.ORGANIZATION.value, Role.RECEIVER.value, Role.RECYCLER.value, Role.LOGISTICS.value, Role.ADMIN.value}:
        raise HTTPException(403, 'This workspace cannot plan transport')
    allowed_destinations = {'NGO', 'College', 'Institution', 'Small Business', 'Refurbisher', 'Recycler', 'Recovery Partner'}
    if partner.verification_status != 'VERIFIED' or partner.organization_type not in allowed_destinations:
        raise HTTPException(409, 'Destination partner is not a verified exchange partner')
    normalized = payload.vehicle_type.strip().upper().replace('_', ' ')
    if normalized not in VEHICLES:
        raise HTTPException(422, 'Unsupported vehicle type')
    if VEHICLES[normalized]['capacity'] < payload.quantity:
        raise HTTPException(409, 'Vehicle capacity is smaller than the requested quantity')
    values = calculate_route_values(material, partner, normalized, payload.quantity)
    existing = db.scalar(select(Route).where(Route.material_id == payload.material_id, Route.partner_organization_id == payload.partner_organization_id, Route.vehicle_type == normalized))
    if existing:
        for key, value in values.items(): setattr(existing, key, value)
        row = existing
    else:
        row = Route(material_id=payload.material_id, partner_organization_id=payload.partner_organization_id, **values)
        db.add(row)
    db.commit(); db.refresh(row)
    return row
