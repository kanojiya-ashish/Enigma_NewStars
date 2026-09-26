from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_db
from ..core.deps import current_user, require_roles
from ..models.models import Material, MaterialImage, MaterialStatus, Role, Transfer, TransferStatus, User
from ..schemas.schemas import MaterialCreate, MaterialOut, MaterialUpdate

router = APIRouter(prefix='/api/materials', tags=['Materials'])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
EVIDENCE_TYPES = IMAGE_TYPES | {'application/pdf'}


def _save_upload(file: UploadFile, allowed_types: set[str]):
    content_type = (file.content_type or '').lower()
    if content_type not in allowed_types:
        raise HTTPException(415, 'Unsupported file type. Use JPG, PNG, WEBP or PDF where permitted.')
    suffix = Path(file.filename or 'upload.bin').suffix.lower()[:10]
    name = f'{uuid4().hex}{suffix}'
    target = Path(settings.upload_dir) / name
    total = 0
    try:
        with target.open('wb') as handle:
            while chunk := file.file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, 'File is larger than the 10 MB upload limit')
                handle.write(chunk)
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    except Exception:
        target.unlink(missing_ok=True)
        raise HTTPException(500, 'Could not save upload')
    return name, file.filename or name


@router.get('', response_model=list[MaterialOut])
def my_materials(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role == Role.ADMIN.value:
        q = select(Material).order_by(desc(Material.created_at))
    elif user.role == Role.ORGANIZATION.value:
        q = select(Material).where(Material.owner_organization_id == user.organization_id).order_by(desc(Material.created_at))
    else:
        q = select(Material).where(Material.remaining_quantity > 0, Material.status.in_([MaterialStatus.AVAILABLE.value, MaterialStatus.RESERVED.value])).order_by(desc(Material.created_at))
    return list(db.scalars(q).all())


@router.get('/all', response_model=list[MaterialOut])
def marketplace(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role == Role.ORGANIZATION.value:
        q = select(Material).where(Material.remaining_quantity > 0, Material.status.in_([MaterialStatus.AVAILABLE.value, MaterialStatus.RESERVED.value]), Material.owner_organization_id != user.organization_id).order_by(desc(Material.created_at))
    else:
        q = select(Material).where(Material.remaining_quantity > 0, Material.status.in_([MaterialStatus.AVAILABLE.value, MaterialStatus.RESERVED.value])).order_by(desc(Material.created_at))
    return list(db.scalars(q).all())


@router.post('', response_model=MaterialOut)
def create_material(payload: MaterialCreate, user: User = Depends(require_roles(Role.ORGANIZATION.value)), db: Session = Depends(get_db)):
    material = Material(owner_organization_id=user.organization_id, name=payload.name, category=payload.category.lower(), description=payload.description,
                        quantity=payload.quantity, remaining_quantity=payload.quantity, unit=payload.unit, condition=payload.condition,
                        age_years=payload.age_years, city=payload.city, state=payload.state, latitude=payload.latitude, longitude=payload.longitude,
                        estimated_value=payload.estimated_value, status=MaterialStatus.AVAILABLE.value)
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


@router.patch('/{material_id}', response_model=MaterialOut)
def update_material(material_id: int, payload: MaterialUpdate, user: User = Depends(require_roles(Role.ORGANIZATION.value)), db: Session = Depends(get_db)):
    material = db.get(Material, material_id)
    if not material:
        raise HTTPException(404, 'Material not found')
    if material.owner_organization_id != user.organization_id:
        raise HTTPException(403, 'You do not own this material')
    if material.status in {MaterialStatus.IN_TRANSFER.value, MaterialStatus.COMPLETED.value}:
        raise HTTPException(409, 'Material cannot be edited while in an active or completed transfer')
    for field in ('description', 'estimated_value', 'available_from'):
        value = getattr(payload, field)
        if value is not None:
            setattr(material, field, value)
    db.commit()
    db.refresh(material)
    return material


@router.post('/{material_id}/close', response_model=MaterialOut)
def close_material(material_id: int, user: User = Depends(require_roles(Role.ORGANIZATION.value)), db: Session = Depends(get_db)):
    material = db.get(Material, material_id)
    if not material or material.owner_organization_id != user.organization_id:
        raise HTTPException(404, 'Material not found')
    active = db.scalar(select(Transfer).where(Transfer.material_id == material.id, Transfer.status.in_([s.value for s in TransferStatus if s not in {TransferStatus.COMPLETED, TransferStatus.CANCELLED}])))
    if active:
        raise HTTPException(409, 'Material has an active transfer and cannot be closed')
    material.status = MaterialStatus.CANCELLED.value
    material.remaining_quantity = 0
    db.commit()
    db.refresh(material)
    return material


@router.get('/{material_id}', response_model=MaterialOut)
def get_material(material_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    material = db.get(Material, material_id)
    if not material:
        raise HTTPException(404, 'Material not found')
    if user.role == Role.ADMIN.value:
        pass
    elif user.role in {Role.RECEIVER.value, Role.RECYCLER.value}:
        pass
    elif user.role == Role.ORGANIZATION.value and user.organization_id == material.owner_organization_id:
        pass
    else:
        raise HTTPException(403, 'Material is not part of your workspace')
    return material


@router.post('/{material_id}/images')
def upload_material_image(material_id: int, file: UploadFile = File(...), user: User = Depends(require_roles(Role.ORGANIZATION.value)), db: Session = Depends(get_db)):
    material = db.get(Material, material_id)
    if not material or material.owner_organization_id != user.organization_id:
        raise HTTPException(404, 'Material not found')
    name, original_name = _save_upload(file, IMAGE_TYPES)
    record = MaterialImage(material_id=material.id, filename=original_name, url=f'/uploads/{name}')
    db.add(record)
    db.commit()
    return {'id': record.id, 'url': record.url, 'filename': record.filename}


@router.post('/uploads')
def upload_generic(file: UploadFile = File(...), user: User = Depends(current_user)):
    name, original_name = _save_upload(file, EVIDENCE_TYPES)
    return {'url': f'/uploads/{name}', 'filename': original_name}
