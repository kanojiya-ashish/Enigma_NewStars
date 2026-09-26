from __future__ import annotations

import json
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .routing import haversine_km
from ..models.models import Assessment, Match, MatchStatus, Material, Organization, ReceiverNeed

CONDITION_ORDER = {'POOR': 1, 'FAIR': 2, 'GOOD': 3, 'EXCELLENT': 4}


def build_matches(db: Session, material: Material):
    # Never invent new partner matches for material that is already in transit, completed or cancelled.
    # A reserved material can only expose its currently accepted match.
    if material.remaining_quantity <= 1e-9 or material.status in {'IN_TRANSFER', 'COMPLETED', 'CANCELLED'}:
        return list(db.scalars(select(Match).where(Match.material_id == material.id, Match.status != MatchStatus.CANCELLED.value).order_by(desc(Match.match_score))).all())
    accepted = list(db.scalars(select(Match).where(Match.material_id == material.id, Match.status == MatchStatus.ACCEPTED.value).order_by(desc(Match.created_at))).all())
    if accepted:
        return accepted
    assessment = db.scalar(select(Assessment).where(Assessment.material_id == material.id).order_by(desc(Assessment.created_at)))
    pathway = assessment.recommendation if assessment else 'REUSE'
    supported_types = ['Recycler', 'Recovery Partner'] if pathway in {'RECYCLE', 'RECOVER'} else ['NGO', 'College', 'Institution', 'Small Business', 'Refurbisher']
    partners = list(db.scalars(select(Organization).where(Organization.verification_status == 'VERIFIED', Organization.organization_type.in_(supported_types))).all())
    results = []
    for partner in partners:
        distance = haversine_km(material.latitude, material.longitude, partner.latitude, partner.longitude)
        if distance > partner.service_area_km:
            continue
        supported = [x.strip().lower() for x in partner.materials_supported.split(',') if x.strip()]
        material_fit = 100 if 'all' in supported or material.category.lower() in supported else 25
        need = None
        needs = list(db.scalars(select(ReceiverNeed).where(ReceiverNeed.organization_id == partner.id, ReceiverNeed.status == 'OPEN', ReceiverNeed.category == material.category.lower())).all())
        if needs:
            same_unit = [n for n in needs if n.unit.lower() == material.unit.lower()]
            need = max(same_unit or needs, key=lambda n: n.remaining_quantity)
        need_fit = 95 if need and need.unit.lower() == material.unit.lower() and need.remaining_quantity > 0 else 55 if pathway in {'RECYCLE', 'RECOVER'} else 35
        condition_fit = 95 if need and CONDITION_ORDER.get(material.condition, 0) >= CONDITION_ORDER.get(need.acceptable_condition, 0) else 70 if not need else 30
        quantity_fit = 95 if not need else min(100, 40 + material.remaining_quantity / max(need.remaining_quantity, 1) * 60)
        location_fit = max(0, 100 - distance / max(partner.service_area_km, 1) * 100)
        score = 0.30 * material_fit + 0.20 * condition_fit + 0.15 * quantity_fit + 0.20 * need_fit + 0.15 * location_fit
        reasons = [
            'Material category is compatible with partner capability.' if material_fit >= 80 else 'Partner capability is only partially compatible.',
            f'Partner is approximately {distance:.1f} km from the source.',
            'An open receiver need matches this material.' if need else 'No explicit open need was found; capability/service area is used.',
            'The recommended next-life pathway is respected before matching.',
        ]
        details = {'reasons': reasons, 'factor_breakdown': {'Material compatibility': round(material_fit, 1), 'Condition': round(condition_fit, 1), 'Quantity': round(quantity_fit, 1), 'Need/capability': round(need_fit, 1), 'Location': round(location_fit, 1)}}
        existing = db.scalar(select(Match).where(Match.material_id == material.id, Match.partner_organization_id == partner.id, Match.need_id == (need.id if need else None)))
        if existing:
            existing.match_score = round(score, 1); existing.distance_km = round(distance, 2); existing.reason_json = json.dumps(details)
            results.append(existing)
        else:
            row = Match(material_id=material.id, partner_organization_id=partner.id, need_id=need.id if need else None, match_score=round(score, 1), distance_km=round(distance, 2), reason_json=json.dumps(details), status=MatchStatus.RECOMMENDED.value)
            db.add(row); db.flush(); results.append(row)
    db.commit()
    return sorted(results, key=lambda x: x.match_score, reverse=True)
