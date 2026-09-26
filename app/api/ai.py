from __future__ import annotations

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import current_user, require_roles
from ..models.models import Assessment, Material, Role, User
from ..schemas.schemas import AssessmentOut
from ..services.ai import assess_material
from ..services.serializers import assessment_out

router = APIRouter(prefix='/api/assessment', tags=['AI Decision Engine'])


def get_owned_material(db: Session, material_id: int, user: User) -> Material:
    material = db.get(Material, material_id)
    if not material:
        raise HTTPException(404, 'Material not found')
    if user.role not in {Role.ADMIN.value} and material.owner_organization_id != user.organization_id:
        raise HTTPException(403, 'You cannot assess material from another organisation')
    return material


@router.post('/{material_id}', response_model=AssessmentOut)
def run_assessment(material_id: int, user: User = Depends(require_roles(Role.ORGANIZATION.value, Role.ADMIN.value)), db: Session = Depends(get_db)):
    material = get_owned_material(db, material_id, user)
    result = assess_material(material)
    assessment = Assessment(material_id=material.id, condition_score=result.condition_score, recommendation=result.recommendation, confidence=result.confidence,
                            reuse_score=result.scores['REUSE'], refurbish_score=result.scores['REFURBISH'], recycle_score=result.scores['RECYCLE'], recover_score=result.scores['RECOVER'],
                            reason_json=json.dumps({'reasons': result.reasons, 'factor_breakdown': result.factor_breakdown}))
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment_out(assessment)


@router.get('/{material_id}', response_model=AssessmentOut)
def latest_assessment(material_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    material = get_owned_material(db, material_id, user)
    assessment = db.scalar(select(Assessment).where(Assessment.material_id == material.id).order_by(desc(Assessment.created_at)))
    if not assessment:
        raise HTTPException(404, 'No AI assessment exists for this material yet')
    return assessment_out(assessment)


@router.get('/methodology/overview')
def methodology():
    return {
        'principle': 'Decide a material’s next life before matching it to a partner.',
        'pathways': ['REUSE', 'REFURBISH', 'RECYCLE', 'RECOVER'],
        'decision_factors': {'Condition': 35, 'Age': 15, 'Category suitability': 25, 'Circular value': 25},
        'matching': ['Material compatibility', 'Condition', 'Quantity', 'Partner need/capability', 'Location', 'Time'],
        'routing': ['Distance', 'Estimated travel time', 'Vehicle capacity', 'Transport emission factor'],
        'verification': 'Transport arrival, physical receipt, circular outcome evidence and platform verification are separate events. Only verified outcomes contribute to impact.',
    }
