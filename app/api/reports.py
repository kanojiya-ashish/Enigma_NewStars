from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import current_user
from ..models.models import Assessment, Driver, Impact, Material, Organization, OutcomeEvidence, Route, Role, Transfer, TransferEvent, User
from ..schemas.schemas import ReportOut
from ..services.serializers import transfer_out

router = APIRouter(prefix='/api/reports', tags=['Reports'])


def accessible(user: User, transfer: Transfer) -> bool:
    return user.role == Role.ADMIN.value or (user.organization_id in {transfer.source_organization_id, transfer.receiver_organization_id, transfer.logistics_partner_id})


@router.get('/transfer/{transfer_id}', response_model=ReportOut)
def report(transfer_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    transfer = db.get(Transfer, transfer_id)
    if not transfer: raise HTTPException(404, 'Transfer not found')
    if not accessible(user, transfer): raise HTTPException(403, 'You cannot view this report')
    material = db.get(Material, transfer.material_id)
    source = db.get(Organization, transfer.source_organization_id)
    receiver = db.get(Organization, transfer.receiver_organization_id)
    logistics = db.get(Organization, transfer.logistics_partner_id) if transfer.logistics_partner_id else None
    driver = db.get(Driver, transfer.driver_id) if transfer.driver_id else None
    route = db.get(Route, transfer.route_id) if transfer.route_id else None
    assessment = db.scalar(select(Assessment).where(Assessment.material_id == transfer.material_id).order_by(Assessment.created_at.desc()))
    outcome = db.scalar(select(OutcomeEvidence).where(OutcomeEvidence.transfer_id == transfer.id))
    impact = db.scalar(select(Impact).where(Impact.transfer_id == transfer.id))
    events = list(db.scalars(select(TransferEvent).where(TransferEvent.transfer_id == transfer.id).order_by(TransferEvent.created_at)).all())

    def clean(obj): return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')} if obj else None

    return ReportOut(
        report=f'Reloop Circular Transfer Report #{transfer.id}', generated_at=datetime.utcnow().isoformat(), transfer=transfer_out(transfer, db).model_dump(mode='json'),
        material=clean(material), source=clean(source), receiver=clean(receiver), logistics=clean(logistics), driver=clean(driver),
        decision={'recommendation': assessment.recommendation, 'condition_score': assessment.condition_score, 'confidence': assessment.confidence} if assessment else None,
        route=clean(route), tracking={'event_history':[{'type': e.event_type, 'message': e.message, 'at': e.created_at.isoformat()} for e in events]},
        receipt={'received_quantity': transfer.received_quantity, 'received_condition': transfer.received_condition, 'notes': transfer.receipt_notes, 'received_at': transfer.received_at.isoformat() if transfer.received_at else None} if transfer.received_at else None,
        outcome=clean(outcome), impact=clean(impact), methodology='Transport arrival proves delivery. Physical receipt proves handover. Only reviewer-verified circular outcome evidence creates verified impact.'
    )
