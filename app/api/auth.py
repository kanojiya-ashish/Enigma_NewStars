from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import current_user
from ..core.security import create_access_token, hash_password, verify_password
from ..models.models import Organization, Role, User
from ..schemas.schemas import LoginIn, OrganizationOut, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix='/api/auth', tags=['Authentication'])


def org_for_user(user: User, db: Session):
    return db.get(Organization, user.organization_id) if user.organization_id else None


def token_response(user: User, db: Session, token: str) -> TokenOut:
    org = org_for_user(user, db)
    return TokenOut(access_token=token, user=UserOut.model_validate(user), organization=OrganizationOut.model_validate(org) if org else None)


@router.post('/login', response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, 'Invalid email or password')
    if payload.role and payload.role != user.role:
        raise HTTPException(403, f'This account belongs to the {user.role.title()} workspace')
    if not user.is_active:
        raise HTTPException(403, 'User account is inactive')
    if user.organization_id:
        org = db.get(Organization, user.organization_id)
        if org and org.verification_status == 'SUSPENDED':
            raise HTTPException(403, 'Organization access is suspended')
    return token_response(user, db, create_access_token(user.id, user.role))


@router.get('/me', response_model=TokenOut)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return token_response(user, db, '')


@router.post('/register', response_model=TokenOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(409, 'Email already registered')
    type_map = {
        Role.RECEIVER.value: {'NGO', 'College', 'Institution', 'Small Business', 'Refurbisher'},
        Role.RECYCLER.value: {'Recycler', 'Recovery Partner'},
        Role.LOGISTICS.value: {'Logistics'},
        Role.ORGANIZATION.value: {'Company', 'Institution', 'College', 'Small Business', 'NGO'},
    }
    if payload.organization_type not in type_map.get(payload.role, set()):
        # Allow custom company types for the generic organization role.
        if payload.role != Role.ORGANIZATION.value:
            raise HTTPException(422, 'Organisation type does not match the selected workspace')
    org = Organization(
        name=payload.organization_name, organization_type=payload.organization_type, city=payload.city, state=payload.state,
        address=payload.address, latitude=payload.latitude, longitude=payload.longitude, contact_email=payload.email,
        verification_status='PENDING', materials_supported=payload.materials_supported, capacity=payload.capacity,
        service_area_km=payload.service_area_km, certifications='',
    )
    db.add(org)
    db.flush()
    user = User(name=payload.name, email=payload.email, password_hash=hash_password(payload.password), role=payload.role, organization_id=org.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return token_response(user, db, create_access_token(user.id, user.role))
