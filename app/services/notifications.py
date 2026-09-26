from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.models import Notification, Organization, User


def send_notification(db: Session, user_id: int, title: str, message: str, notification_type: str, transfer_id: int | None = None):
    db.add(Notification(user_id=user_id, transfer_id=transfer_id, type=notification_type, title=title, message=message))


def send_to_org(db: Session, organization_id: int | None, title: str, message: str, notification_type: str, transfer_id: int | None = None):
    if not organization_id:
        return
    users = db.scalars(select(User).where(User.organization_id == organization_id, User.is_active.is_(True))).all()
    for user in users:
        send_notification(db, user.id, title, message, notification_type, transfer_id)


def send_to_admins(db: Session, title: str, message: str, notification_type: str, transfer_id: int | None = None):
    for user in db.scalars(select(User).where(User.role == 'ADMIN', User.is_active.is_(True))).all():
        send_notification(db, user.id, title, message, notification_type, transfer_id)
