from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select, func
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import current_user
from ..models.models import Notification, User
from ..schemas.schemas import NotificationOut

router = APIRouter(prefix='/api/notifications', tags=['Notifications'])


@router.get('', response_model=list[NotificationOut])
def notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(desc(Notification.created_at)).limit(50)).all())


@router.get('/unread-count')
def unread_count(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {'count': int(db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user.id, Notification.is_read.is_(False))) or 0)}


@router.patch('/{notification_id}/read', response_model=NotificationOut)
def mark_read(notification_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    note = db.get(Notification, notification_id)
    if not note or note.user_id != user.id: raise HTTPException(404, 'Notification not found')
    note.is_read = True; db.commit(); db.refresh(note); return note


@router.post('/read-all')
def read_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False))).all()
    for note in rows: note.is_read = True
    db.commit(); return {'updated': len(rows)}
