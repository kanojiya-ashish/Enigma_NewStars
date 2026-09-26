from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .security import decode_access_token
from ..models.models import Organization, Role, User

bearer = HTTPBearer(auto_error=False)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Authentication required')
    try:
        payload = decode_access_token(credentials.credentials)
        user = db.get(User, int(payload['sub']))
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Invalid or expired token') from exc
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'User not found or inactive')
    if user.organization_id and user.role != Role.ADMIN.value:
        org = db.get(Organization, user.organization_id)
        if org and org.verification_status == 'SUSPENDED':
            raise HTTPException(status.HTTP_403_FORBIDDEN, 'Organization access is suspended')
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f'Role {user.role} is not allowed for this action')
        return user
    return dependency
