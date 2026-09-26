from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import current_user, require_roles
from ..models.models import Driver, OutcomeEvidence, OutcomeStatus, Role, Transfer, User
from ..schemas.schemas import OutcomeOut, OutcomeReview, OutcomeSubmission
from ..services.notifications import send_to_org
from ..services.serializers import outcome_out
from ..services.transfer import review_outcome, submit_outcome

router = APIRouter(prefix='/api/outcomes', tags=['Circular Outcome Verification'])


@router.get('/pending', response_model=list[OutcomeOut])
def pending(user: User = Depends(require_roles(Role.ADMIN.value)), db: Session = Depends(get_db)):
    rows = db.scalars(select(OutcomeEvidence).where(OutcomeEvidence.evidence_status.in_([OutcomeStatus.SUBMITTED.value, OutcomeStatus.UNDER_REVIEW.value])).order_by(desc(OutcomeEvidence.submitted_at))).all()
    return list(rows)


@router.get('/transfer/{transfer_id}', response_model=OutcomeOut | None)
def transfer_outcome(transfer_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    transfer = db.get(Transfer, transfer_id)
    if not transfer: raise HTTPException(404, 'Transfer not found')
    driver = db.scalar(select(Driver).where(Driver.user_id == user.id)) if user.role == Role.DRIVER.value else None
    allowed = user.role == Role.ADMIN.value or (driver is not None and transfer.driver_id == driver.id) or (user.organization_id in {transfer.source_organization_id, transfer.receiver_organization_id, transfer.logistics_partner_id})
    if not allowed: raise HTTPException(403, 'You cannot view this outcome')
    row = db.scalar(select(OutcomeEvidence).where(OutcomeEvidence.transfer_id == transfer_id))
    return row


@router.post('/transfer/{transfer_id}/submit', response_model=OutcomeOut)
def submit(transfer_id: int, payload: OutcomeSubmission, user: User = Depends(require_roles(Role.RECEIVER.value, Role.RECYCLER.value)), db: Session = Depends(get_db)):
    transfer = db.get(Transfer, transfer_id)
    if not transfer: raise HTTPException(404, 'Transfer not found')
    outcome = submit_outcome(db, transfer, user, payload)
    db.commit(); db.refresh(outcome)
    return outcome


@router.post('/{outcome_id}/review', response_model=OutcomeOut)
def review(outcome_id: int, payload: OutcomeReview, user: User = Depends(require_roles(Role.ADMIN.value)), db: Session = Depends(get_db)):
    outcome = db.get(OutcomeEvidence, outcome_id)
    if not outcome: raise HTTPException(404, 'Outcome evidence not found')
    if outcome.evidence_status == OutcomeStatus.SUBMITTED.value:
        outcome.evidence_status = OutcomeStatus.UNDER_REVIEW.value
        db.flush()
    review_outcome(db, outcome, user, payload.decision, payload.reviewer_note)
    db.commit(); db.refresh(outcome)
    return outcome
