from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import current_user, require_roles
from ..models.models import Organization, Role, User
from ..schemas.schemas import OrganizationOut, VerificationUpdate

router = APIRouter(prefix='/api/organizations', tags=['Partners'])


@router.get('', response_model=list[OrganizationOut])
def organizations(kind: str | None = Query(default=None), user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Organization).where(Organization.verification_status == 'VERIFIED').order_by(Organization.name)
    if kind:
        if kind.upper() == 'RECEIVER':
            q = q.where(Organization.organization_type.in_(['NGO', 'College', 'Institution', 'Small Business', 'Refurbisher']))
        elif kind.upper() == 'RECYCLER':
            q = q.where(Organization.organization_type.in_(['Recycler', 'Recovery Partner']))
        elif kind.upper() == 'LOGISTICS':
            q = q.where(Organization.organization_type == 'Logistics')
        else:
            q = q.where(Organization.organization_type == kind)
    return list(db.scalars(q).all())


@router.get('/manage', response_model=list[OrganizationOut])
def manage(status: str | None = Query(default=None), user: User = Depends(require_roles(Role.ADMIN.value)), db: Session = Depends(get_db)):
    q = select(Organization).order_by(Organization.name)
    if status:
        q = q.where(Organization.verification_status == status.upper())
    return list(db.scalars(q).all())


@router.patch('/{organization_id}/verification', response_model=OrganizationOut)
def verification(organization_id: int, payload: VerificationUpdate, user: User = Depends(require_roles(Role.ADMIN.value)), db: Session = Depends(get_db)):
    org = db.get(Organization, organization_id)
    if not org:
        raise HTTPException(404, 'Organisation not found')
    org.verification_status = payload.status
    db.commit()
    db.refresh(org)
    return org
