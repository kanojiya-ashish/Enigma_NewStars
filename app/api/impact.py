from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.deps import current_user
from ..models.models import Impact, Match, Role, Transfer, User
from ..schemas.schemas import ImpactOut

router = APIRouter(prefix='/api/impact', tags=['Verified Impact'])


@router.get('/dashboard', response_model=ImpactOut)
def impact_dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Impact)
    if user.role != Role.ADMIN.value and user.organization_id:
        q = q.join(Transfer, Impact.transfer_id == Transfer.id).where((Transfer.source_organization_id == user.organization_id) | (Transfer.receiver_organization_id == user.organization_id) | (Transfer.logistics_partner_id == user.organization_id))
    rows = list(db.scalars(q).all())
    values = {'value_recovered': sum(x.value_recovered for x in rows), 'waste_avoided_kg': sum(x.waste_avoided_kg for x in rows), 'co2_avoided_kg': sum(x.co2_avoided_kg for x in rows)}
    pathways = {}; counts = {}
    for row in rows:
        pathways[row.pathway] = round(pathways.get(row.pathway, 0) + row.verified_quantity, 2)
        counts[row.pathway] = counts.get(row.pathway, 0) + 1
    match_scores = []
    for row in rows:
        transfer = db.get(Transfer, row.transfer_id)
        if not transfer: continue
        score = db.scalar(select(func.max(Match.match_score)).where(Match.material_id == transfer.material_id, Match.partner_organization_id == transfer.receiver_organization_id, Match.status.in_(['ACCEPTED', 'FULFILLED'])))
        if score is not None: match_scores.append(float(score))
    return ImpactOut(value_recovered=round(values['value_recovered'],2), waste_avoided_kg=round(values['waste_avoided_kg'],2), co2_avoided_kg=round(values['co2_avoided_kg'],2), verified_transfers=len(rows), verified_quantity=round(sum(x.verified_quantity for x in rows),2), by_pathway=pathways, pathway_counts=counts, average_match_score=round(sum(match_scores)/len(match_scores),1) if match_scores else 0)
