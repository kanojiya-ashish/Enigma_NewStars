from __future__ import annotations

import json

from ..models.models import Assessment, Match, Organization, OutcomeEvidence, Route, Transfer, Driver, ReceiverNeed
from ..schemas.schemas import AssessmentOut, MatchOut, OrganizationOut, OutcomeOut, RouteOut, TransferOut


def org_out(org):
    return OrganizationOut.model_validate(org) if org else None


def outcome_out(outcome: OutcomeEvidence | None):
    if not outcome:
        return None
    return OutcomeOut.model_validate(outcome)


def transfer_out(transfer: Transfer, db):
    driver = db.get(Driver, transfer.driver_id) if transfer.driver_id else None
    outcome = db.scalar(__import__('sqlalchemy').select(OutcomeEvidence).where(OutcomeEvidence.transfer_id == transfer.id))
    route = db.get(Route, transfer.route_id) if transfer.route_id else None
    return TransferOut(
        id=transfer.id, material_id=transfer.material_id, source_organization_id=transfer.source_organization_id,
        receiver_organization_id=transfer.receiver_organization_id, logistics_partner_id=transfer.logistics_partner_id,
        driver_id=transfer.driver_id, driver_accepted_at=transfer.driver_accepted_at, driver_code=driver.driver_code if driver else None, driver_name=driver.name if driver else None,
        driver_vehicle_type=driver.vehicle_type if driver else None, driver_vehicle_number=driver.vehicle_number if driver else None,
        route_id=transfer.route_id, route_vehicle_type=route.vehicle_type if route else None, match_id=transfer.match_id, need_id=transfer.need_id, quantity=transfer.quantity, status=transfer.status, pickup_time=transfer.pickup_time,
        delivery_time=transfer.delivery_time, arrived_at=transfer.arrived_at, received_at=transfer.received_at,
        received_quantity=transfer.received_quantity, received_condition=transfer.received_condition, receipt_notes=transfer.receipt_notes,
        receipt_photo_url=transfer.receipt_photo_url, cancelled_at=transfer.cancelled_at, created_at=transfer.created_at,
        outcome=outcome_out(outcome),
    )


def route_out(route):
    return RouteOut.model_validate(route)


def assessment_out(assessment):
    details = json.loads(assessment.reason_json or '{}')
    return AssessmentOut(
        id=assessment.id, material_id=assessment.material_id, condition_score=assessment.condition_score,
        recommendation=assessment.recommendation, confidence=assessment.confidence,
        scores={'REUSE': assessment.reuse_score, 'REFURBISH': assessment.refurbish_score, 'RECYCLE': assessment.recycle_score, 'RECOVER': assessment.recover_score},
        reasons=details.get('reasons', []), factor_breakdown=details.get('factor_breakdown', {}),
        methodology='Prototype explainable scoring uses declared condition, age, category suitability and circular-value factors. Production deployment should calibrate these weights on audited labelled material data.',
    )


def match_out(match, partner, source, db=None):
    details = json.loads(match.reason_json or '{}')
    need = db.get(ReceiverNeed, match.need_id) if db is not None and match.need_id else None
    return MatchOut(
        id=match.id,
        material_id=match.material_id,
        need_id=match.need_id,
        need_remaining_quantity=need.remaining_quantity if need else None,
        need_unit=need.unit if need else None,
        partner=org_out(partner),
        source=org_out(source),
        match_score=round(match.match_score, 1),
        distance_km=round(match.distance_km, 2),
        reasons=details.get('reasons', []),
        status=match.status,
        factor_breakdown=details.get('factor_breakdown', {}),
    )
