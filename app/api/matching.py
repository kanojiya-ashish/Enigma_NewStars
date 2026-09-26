from __future__ import annotations

import json
from math import exp
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import current_user, require_roles
from ..models.models import Match, MatchStatus, Material, MaterialStatus, Organization, ReceiverNeed, NeedStatus, Role, User
from ..schemas.schemas import MatchDecision, MatchOut, MatchRequest, ReceiverNeedCreate, ReceiverNeedOut
from ..services.matching import build_matches
from ..services.notifications import send_to_org
from ..services.serializers import match_out
from ..services.state import MATCH_TRANSITIONS, transition

router = APIRouter(prefix='/api/matching', tags=['Smart Matching'])
needs_router = APIRouter(prefix='/api/needs', tags=['Receiver Needs'])


@needs_router.get('', response_model=list[ReceiverNeedOut])
def list_needs(user: User = Depends(require_roles(Role.RECEIVER.value, Role.ADMIN.value)), db: Session = Depends(get_db)):
    q = select(ReceiverNeed).order_by(desc(ReceiverNeed.created_at))
    if user.role != Role.ADMIN.value:
        q = q.where(ReceiverNeed.organization_id == user.organization_id)
    return list(db.scalars(q).all())


@needs_router.post('', response_model=ReceiverNeedOut)
def create_need(payload: ReceiverNeedCreate, user: User = Depends(require_roles(Role.RECEIVER.value)), db: Session = Depends(get_db)):
    need = ReceiverNeed(organization_id=user.organization_id, material_name=payload.material_name, category=payload.category.lower(), quantity=payload.quantity,
                        remaining_quantity=payload.quantity, unit=payload.unit, acceptable_condition=payload.acceptable_condition,
                        needed_by=payload.needed_by, notes=payload.notes, status=NeedStatus.OPEN.value)
    db.add(need)
    db.commit()
    db.refresh(need)
    return need


@router.get('/material/{material_id}', response_model=list[MatchOut])
def get_matches(material_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    material = db.get(Material, material_id)
    if not material:
        raise HTTPException(404, 'Material not found')
    if user.role == Role.ORGANIZATION and material.owner_organization_id != user.organization_id and user.role != Role.ADMIN.value:
        raise HTTPException(403, 'You do not own this material')
    rows = build_matches(db, material)
    source = db.get(Organization, material.owner_organization_id)
    return [match_out(row, db.get(Organization, row.partner_organization_id), source, db) for row in rows]


@router.get('/sent', response_model=list[MatchOut])
def sent(user: User = Depends(require_roles(Role.ORGANIZATION.value)), db: Session = Depends(get_db)):
    q = select(Match).join(Material, Match.material_id == Material.id).where(Material.owner_organization_id == user.organization_id).order_by(desc(Match.created_at))
    rows = list(db.scalars(q).all())
    return [match_out(m, db.get(Organization, m.partner_organization_id), db.get(Organization, db.get(Material, m.material_id).owner_organization_id), db) for m in rows]


@router.get('/incoming', response_model=list[MatchOut])
def incoming(user: User = Depends(require_roles(Role.RECEIVER.value, Role.RECYCLER.value)), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Match).where(Match.partner_organization_id == user.organization_id, Match.status.in_([MatchStatus.REQUESTED.value, MatchStatus.ACCEPTED.value])).order_by(desc(Match.created_at))).all())
    out = []
    for row in rows:
        material = db.get(Material, row.material_id)
        source = db.get(Organization, material.owner_organization_id) if material else None
        partner = db.get(Organization, row.partner_organization_id)
        if material and source and partner:
            out.append(match_out(row, partner, source, db))
    return out


@router.get('/incoming/count')
def incoming_count(user: User = Depends(require_roles(Role.RECEIVER.value, Role.RECYCLER.value)), db: Session = Depends(get_db)):
    return {'count': int(db.scalar(select(func.count(Match.id)).where(Match.partner_organization_id == user.organization_id, Match.status == MatchStatus.REQUESTED.value)) or 0)}


@router.post('/request', response_model=MatchOut)
def request_match(payload: MatchRequest, user: User = Depends(require_roles(Role.ORGANIZATION.value)), db: Session = Depends(get_db)):
    material = db.get(Material, payload.material_id)
    partner = db.get(Organization, payload.partner_organization_id)
    if not material or not partner:
        raise HTTPException(404, 'Material or partner not found')
    if material.owner_organization_id != user.organization_id:
        raise HTTPException(403, 'You do not own this material')
    if material.remaining_quantity <= 0 or material.status in {MaterialStatus.IN_TRANSFER.value, MaterialStatus.COMPLETED.value, MaterialStatus.CANCELLED.value}:
        raise HTTPException(409, 'Material is not currently available for a new partner request')
    accepted_match = db.scalar(select(Match).where(Match.material_id == material.id, Match.status == MatchStatus.ACCEPTED.value))
    if accepted_match and accepted_match.partner_organization_id != partner.id:
        accepted_partner = db.get(Organization, accepted_match.partner_organization_id)
        raise HTTPException(409, f'Material is already reserved for {accepted_partner.name if accepted_partner else "another partner"}')
    eligible_types = {'NGO', 'College', 'Institution', 'Small Business', 'Refurbisher', 'Recycler', 'Recovery Partner'}
    if partner.organization_type not in eligible_types:
        raise HTTPException(400, 'Selected partner is not eligible for material exchange')
    if payload.need_id:
        need = db.get(ReceiverNeed, payload.need_id)
        if not need or need.organization_id != partner.id or need.status == NeedStatus.CLOSED.value:
            raise HTTPException(409, 'Selected receiver need is not open')
        if need.unit.strip().lower() != material.unit.strip().lower():
            raise HTTPException(409, f'Unit mismatch: material is measured in {material.unit}, while the selected need expects {need.unit}')
    existing = db.scalar(select(Match).where(Match.material_id == material.id, Match.partner_organization_id == partner.id, Match.need_id == payload.need_id,
                                        Match.status.in_([MatchStatus.REQUESTED.value, MatchStatus.ACCEPTED.value])))
    if existing:
        raise HTTPException(409, f'An active request already exists for this partner (request #{existing.id})')
    matches = build_matches(db, material)
    generated = next((m for m in matches if m.partner_organization_id == partner.id and (payload.need_id is None or m.need_id == payload.need_id)), None)
    if not generated:
        raise HTTPException(409, 'Partner is outside the current service area or does not match this material')
    generated.need_id = payload.need_id or generated.need_id
    if generated.status != MatchStatus.REQUESTED.value:
        transition(generated.status, MatchStatus.REQUESTED.value, MATCH_TRANSITIONS, 'match')
        generated.status = MatchStatus.REQUESTED.value
    source = db.get(Organization, material.owner_organization_id)
    send_to_org(db, partner.id, 'New material request', f'{source.name} offered {material.remaining_quantity:g} {material.unit} of {material.name}. Request #{generated.id} is awaiting your decision.', 'MATCH_REQUEST', None)
    db.commit()
    db.refresh(generated)
    return match_out(generated, partner, source, db)


@router.patch('/{match_id}', response_model=MatchOut)
def decision(match_id: int, payload: MatchDecision, user: User = Depends(current_user), db: Session = Depends(get_db)):
    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(404, 'Request not found')
    material = db.get(Material, match.material_id)
    partner = db.get(Organization, match.partner_organization_id)
    source = db.get(Organization, material.owner_organization_id) if material else None
    if user.role in {Role.RECEIVER.value, Role.RECYCLER.value}:
        if user.organization_id != match.partner_organization_id:
            raise HTTPException(403, 'This request is addressed to another partner')
        if match.status != MatchStatus.REQUESTED.value:
            raise HTTPException(409, 'Only requested matches can be accepted or rejected')
    elif user.role == Role.ADMIN.value:
        pass
    else:
        raise HTTPException(403, 'Only the receiving partner can accept or reject a material request')
    next_status = payload.decision
    transition(match.status, next_status, MATCH_TRANSITIONS, 'match')
    match.status = next_status
    if next_status == MatchStatus.ACCEPTED.value:
        other_accepted = db.scalar(
            select(Match).where(
                Match.material_id == material.id,
                Match.id != match.id,
                Match.status == MatchStatus.ACCEPTED.value,
            )
        )
        if other_accepted:
            other_partner = db.get(Organization, other_accepted.partner_organization_id)
            raise HTTPException(409, f'Material already has an accepted receiver: {other_partner.name if other_partner else "another partner"}')
        # One material has one active receiving partner. Close other pending offers so the network cannot
        # show multiple simultaneous requests that can never be fulfilled.
        pending_others = db.scalars(
            select(Match).where(
                Match.material_id == material.id,
                Match.id != match.id,
                Match.status == MatchStatus.REQUESTED.value,
            )
        ).all()
        for pending_match in pending_others:
            pending_match.status = MatchStatus.CANCELLED.value
            pending_partner = db.get(Organization, pending_match.partner_organization_id)
            if pending_partner:
                send_to_org(
                    db,
                    pending_partner.id,
                    'Material offer closed',
                    f'Material request #{pending_match.id} for {material.name} was closed because another receiving partner accepted the material.',
                    'GENERAL',
                    None,
                )
        material.status = MaterialStatus.RESERVED.value
        if match.need_id:
            need = db.get(ReceiverNeed, match.need_id)
            if not need or need.status == NeedStatus.CLOSED.value:
                raise HTTPException(409, 'The receiver need is no longer open')
            if need.remaining_quantity <= 0:
                raise HTTPException(409, 'The receiver need has no remaining quantity')
            need.status = NeedStatus.MATCHED.value
        add_reason = 'Receiver accepted the request; transport can now be arranged.'
        details = json.loads(match.reason_json or '{}')
        reasons = details.get('reasons', [])
        if add_reason not in reasons:
            reasons.append(add_reason)
        match.reason_json = json.dumps({**details, 'reasons': reasons})
        send_to_org(db, source.id, 'Partner accepted your request', f'{partner.name} accepted material request #{match.id}. You can now arrange transport.', 'MATCH_ACCEPTED', None)
    elif next_status == MatchStatus.REJECTED.value:
        send_to_org(db, source.id, 'Partner declined your request', f'{partner.name} declined material request #{match.id}.', 'GENERAL', None)
    db.commit()
    db.refresh(match)
    return match_out(match, partner, source)
