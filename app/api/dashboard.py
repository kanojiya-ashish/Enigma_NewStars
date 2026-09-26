from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import current_user
from ..models.models import Driver, Impact, Match, Material, MaterialStatus, Notification, Organization, OutcomeEvidence, OutcomeStatus, ReceiverNeed, Role, Transfer, TransferStatus, User
from ..schemas.schemas import DashboardOut
from ..services.serializers import org_out, transfer_out

router = APIRouter(prefix='/api/dashboard', tags=['Dashboards'])

ACTIVE = [TransferStatus.REQUESTED.value, TransferStatus.PICKUP_SCHEDULED.value, TransferStatus.IN_TRANSIT.value, TransferStatus.DELIVERED.value, TransferStatus.RECEIVED.value]


@router.get('', response_model=DashboardOut)
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    org = db.get(Organization, user.organization_id) if user.organization_id else None
    unread = int(db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user.id, Notification.is_read.is_(False))) or 0)
    recent = []
    metrics = {}
    if user.role == Role.ORGANIZATION.value:
        materials = list(db.scalars(select(Material).where(Material.owner_organization_id == user.organization_id)).all())
        recent = list(db.scalars(select(Transfer).where(Transfer.source_organization_id == user.organization_id).order_by(desc(Transfer.created_at)).limit(8)).all())
        pending = int(db.scalar(select(func.count(Match.id)).join(Material, Match.material_id == Material.id).where(Material.owner_organization_id == user.organization_id, Match.status == 'REQUESTED')) or 0)
        verified = int(db.scalar(select(func.count(Impact.id)).join(Transfer, Impact.transfer_id == Transfer.id).where(Transfer.source_organization_id == user.organization_id)) or 0)
        metrics = {'surplus_listed': len(materials), 'active_surplus': sum(m.remaining_quantity > 0 and m.status != 'CANCELLED' for m in materials), 'pending_requests': pending, 'active_transfers': int(db.scalar(select(func.count(Transfer.id)).where(Transfer.source_organization_id == user.organization_id, Transfer.status.in_(ACTIVE))) or 0), 'verified_outcomes': verified}
    elif user.role == Role.RECEIVER.value:
        recent = list(db.scalars(select(Transfer).where(Transfer.receiver_organization_id == user.organization_id).order_by(desc(Transfer.created_at)).limit(8)).all())
        metrics = {'open_needs': int(db.scalar(select(func.count(ReceiverNeed.id)).where(ReceiverNeed.organization_id == user.organization_id, ReceiverNeed.status == 'OPEN')) or 0), 'incoming_requests': int(db.scalar(select(func.count(Match.id)).where(Match.partner_organization_id == user.organization_id, Match.status == 'REQUESTED')) or 0), 'active_receipts': int(db.scalar(select(func.count(Transfer.id)).where(Transfer.receiver_organization_id == user.organization_id, Transfer.status.in_(ACTIVE))) or 0), 'outcome_actions': int(db.scalar(select(func.count(Transfer.id)).join(OutcomeEvidence, OutcomeEvidence.transfer_id == Transfer.id).where(Transfer.receiver_organization_id == user.organization_id, Transfer.status == TransferStatus.RECEIVED.value)) or 0)}
    elif user.role == Role.RECYCLER.value:
        recent = list(db.scalars(select(Transfer).where(Transfer.receiver_organization_id == user.organization_id).order_by(desc(Transfer.created_at)).limit(8)).all())
        metrics = {'recovery_requests': int(db.scalar(select(func.count(Match.id)).where(Match.partner_organization_id == user.organization_id, Match.status == 'REQUESTED')) or 0), 'active_recovery_jobs': int(db.scalar(select(func.count(Transfer.id)).where(Transfer.receiver_organization_id == user.organization_id, Transfer.status.in_(ACTIVE))) or 0), 'proof_pending': int(db.scalar(select(func.count(OutcomeEvidence.id)).join(Transfer, OutcomeEvidence.transfer_id == Transfer.id).where(Transfer.receiver_organization_id == user.organization_id, OutcomeEvidence.evidence_status.in_([OutcomeStatus.SUBMITTED.value, OutcomeStatus.REJECTED.value]))) or 0), 'verified_recovery': int(db.scalar(select(func.count(Impact.id)).join(Transfer, Impact.transfer_id == Transfer.id).where(Transfer.receiver_organization_id == user.organization_id)) or 0)}
    elif user.role == Role.LOGISTICS.value:
        recent = list(db.scalars(select(Transfer).where(Transfer.logistics_partner_id == user.organization_id).order_by(desc(Transfer.created_at)).limit(8)).all())
        metrics = {'transport_requests': int(db.scalar(select(func.count(Transfer.id)).where(Transfer.logistics_partner_id == user.organization_id, Transfer.status == TransferStatus.REQUESTED.value)) or 0), 'assigned_trips': int(db.scalar(select(func.count(Transfer.id)).where(Transfer.logistics_partner_id == user.organization_id, Transfer.driver_id.is_not(None), Transfer.status != TransferStatus.CANCELLED.value)) or 0), 'in_transit': int(db.scalar(select(func.count(Transfer.id)).where(Transfer.logistics_partner_id == user.organization_id, Transfer.status == TransferStatus.IN_TRANSIT.value)) or 0), 'available_drivers': int(db.scalar(select(func.count(Driver.id)).where(Driver.organization_id == user.organization_id, Driver.is_active.is_(True), Driver.status == 'AVAILABLE')) or 0)}
    elif user.role == Role.DRIVER.value:
        driver = db.scalar(select(Driver).where(Driver.user_id == user.id))
        recent = [] if not driver else list(db.scalars(select(Transfer).where(Transfer.driver_id == driver.id).order_by(desc(Transfer.created_at)).limit(8)).all())
        metrics = {'driver_code': driver.driver_code if driver else '—', 'vehicle': driver.vehicle_number if driver else '—', 'active_jobs': sum(t.status not in {'COMPLETED','CANCELLED'} for t in recent), 'completed_jobs': sum(t.status == 'COMPLETED' for t in recent)}
    else:
        recent = list(db.scalars(select(Transfer).order_by(desc(Transfer.created_at)).limit(8)).all())
        metrics = {'organizations': int(db.scalar(select(func.count(Organization.id))) or 0), 'materials': int(db.scalar(select(func.count(Material.id))) or 0), 'active_transfers': int(db.scalar(select(func.count(Transfer.id)).where(Transfer.status.in_(ACTIVE))) or 0), 'proof_pending': int(db.scalar(select(func.count(OutcomeEvidence.id)).where(OutcomeEvidence.evidence_status.in_([OutcomeStatus.SUBMITTED.value, OutcomeStatus.UNDER_REVIEW.value]))) or 0)}
    return DashboardOut(role=user.role, organization=org_out(org), metrics=metrics, recent_transfers=[transfer_out(t, db) for t in recent], notifications_unread=unread)
