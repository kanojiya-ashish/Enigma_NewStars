from __future__ import annotations

from datetime import datetime
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from fastapi import HTTPException

from ..core.config import settings
from ..models.models import Driver, Impact, LocationUpdate, Material, MaterialStatus, Match, Organization, OutcomeEvidence, ReceiverNeed, Role, Route, Transfer, TransferEvent, TransferStatus, OutcomeStatus, User
from .impact import create_verified_impact
from .notifications import send_notification, send_to_admins, send_to_org
from .routing import haversine_km
from .state import OUTCOME_TRANSITIONS, TRANSFER_TRANSITIONS, transition

ACTIVE_TRANSFER_STATUSES = {TransferStatus.REQUESTED.value, TransferStatus.PICKUP_SCHEDULED.value, TransferStatus.IN_TRANSIT.value, TransferStatus.DELIVERED.value, TransferStatus.RECEIVED.value}


def add_event(db: Session, transfer_id: int, event_type: str, message: str, actor_user_id: int | None = None):
    db.add(TransferEvent(transfer_id=transfer_id, event_type=event_type, message=message, actor_user_id=actor_user_id))


def participant_transfer(db: Session, user: User, transfer: Transfer) -> bool:
    if user.role == Role.ADMIN.value:
        return True
    if user.role == Role.DRIVER.value:
        driver = db.scalar(select(Driver).where(Driver.user_id == user.id))
        return bool(driver and transfer.driver_id == driver.id)
    return bool(user.organization_id and user.organization_id in {transfer.source_organization_id, transfer.receiver_organization_id, transfer.logistics_partner_id})


def mark_arrival(db: Session, transfer: Transfer, driver: Driver, actor_user_id: int | None = None) -> bool:
    if transfer.status != TransferStatus.IN_TRANSIT.value or not transfer.route_id or driver.current_lat is None or driver.current_lng is None:
        return False
    route = db.get(Route, transfer.route_id)
    if not route:
        return False
    distance = haversine_km(driver.current_lat, driver.current_lng, route.destination_lat, route.destination_lng)
    if distance > settings.arrival_radius_km:
        return False
    now = datetime.utcnow()
    transition(transfer.status, TransferStatus.DELIVERED.value, TRANSFER_TRANSITIONS, 'transfer')
    transfer.status = TransferStatus.DELIVERED.value
    transfer.arrived_at = now
    transfer.delivery_time = now
    driver.status = 'AT_DESTINATION'
    add_event(db, transfer.id, 'ARRIVAL', f'{driver.driver_code} reached the destination ({distance * 1000:.0f} m from receiver coordinates).', actor_user_id)
    source = db.get(Organization, transfer.source_organization_id)
    receiver = db.get(Organization, transfer.receiver_organization_id)
    logistics = db.get(Organization, transfer.logistics_partner_id) if transfer.logistics_partner_id else None
    material = db.get(Material, transfer.material_id)
    send_to_org(db, source.id, 'Vehicle reached destination', f'Transfer #{transfer.id} reached {receiver.name}. Receipt verification is now available.', 'ARRIVAL', transfer.id)
    send_to_org(db, receiver.id, 'Delivery has arrived', f'Transfer #{transfer.id}: {driver.driver_code} arrived with {transfer.quantity:g} {material.unit} of {material.name}. Please verify the physical receipt.', 'ARRIVAL', transfer.id)
    if logistics:
        send_to_org(db, logistics.id, 'Vehicle reached destination', f'Transfer #{transfer.id} arrived at {receiver.name}. Awaiting receipt verification.', 'ARRIVAL', transfer.id)
    if driver.user_id:
        send_notification(db, driver.user_id, 'Destination reached', 'The receiver location has been reached. The receiver must now verify the physical delivery.', 'ARRIVAL', transfer.id)
    return True


def confirm_receipt(
    db: Session,
    transfer: Transfer,
    user: User,
    received_quantity: float,
    received_condition: str,
    notes: str,
    receipt_photo_url: str | None,
):
    if transfer.receiver_organization_id != user.organization_id:
        raise HTTPException(403, 'Only the receiving organisation can confirm receipt')
    if transfer.status != TransferStatus.DELIVERED.value:
        raise HTTPException(409, 'The driver must reach the destination before receipt confirmation')
    if received_quantity <= 0:
        raise HTTPException(422, 'Received quantity must be greater than zero')
    if received_quantity > transfer.quantity + 1e-9:
        raise HTTPException(422, 'Received quantity cannot exceed the transport quantity')
    material = db.get(Material, transfer.material_id)
    if not material:
        raise HTTPException(404, 'Material not found')

    now = datetime.utcnow()
    transition(transfer.status, TransferStatus.RECEIVED.value, TRANSFER_TRANSITIONS, 'transfer')
    transfer.status = TransferStatus.RECEIVED.value
    transfer.received_at = now
    transfer.received_quantity = received_quantity
    transfer.received_condition = received_condition
    transfer.receipt_notes = notes.strip()
    transfer.receipt_photo_url = receipt_photo_url

    # Physical receipt fulfills part/all of the receiver's demand. Circular outcome is verified later.
    if transfer.need_id:
        need = db.get(ReceiverNeed, transfer.need_id)
        if need and need.status != 'CLOSED':
            need.remaining_quantity = max(0.0, need.remaining_quantity - received_quantity)
            need.status = 'CLOSED' if need.remaining_quantity <= 1e-9 else 'OPEN'

    add_event(
        db,
        transfer.id,
        'RECEIPT_CONFIRMED',
        f'Receiver confirmed physical receipt of {received_quantity:g} {material.unit}.',
        user.id,
    )
    send_to_org(
        db,
        transfer.source_organization_id,
        'Receipt confirmed',
        f'Transfer #{transfer.id}: receiver confirmed receipt of {received_quantity:g} {material.unit}. Circular outcome proof is now due.',
        'RECEIPT_CONFIRMED',
        transfer.id,
    )
    if transfer.logistics_partner_id:
        send_to_org(
            db,
            transfer.logistics_partner_id,
            'Delivery handover complete',
            f'Transfer #{transfer.id} has been physically received. Logistics work is complete.',
            'RECEIPT_CONFIRMED',
            transfer.id,
        )
    driver = db.get(Driver, transfer.driver_id) if transfer.driver_id else None
    if driver:
        driver.status = 'AVAILABLE'
        if driver.user_id:
            send_notification(
                db,
                driver.user_id,
                'Delivery handed over',
                'The receiving organisation confirmed physical receipt. Your trip is closed.',
                'RECEIPT_CONFIRMED',
                transfer.id,
            )


def _validate_outcome_pathway(receiver: Organization | None, pathway: str):
    if not receiver:
        return
    if receiver.organization_type in {'Recycler', 'Recovery Partner'} and pathway not in {'RECYCLE', 'RECOVER'}:
        raise HTTPException(422, 'A recycler must submit RECYCLE or RECOVER evidence')
    if receiver.organization_type == 'Refurbisher' and pathway != 'REFURBISH':
        raise HTTPException(422, 'A refurbisher must submit REFURBISH evidence')
    if receiver.organization_type in {'NGO', 'College', 'Institution', 'Small Business'} and pathway not in {'REUSE', 'REFURBISH'}:
        raise HTTPException(422, 'This receiver type can only submit REUSE or REFURBISH evidence')


def _validate_outcome_evidence(payload):
    required = {
        'REUSE': bool(payload.after_photo_url) or bool(payload.outcome_document_url),
        'REFURBISH': bool(payload.before_photo_url and payload.after_photo_url) and bool(payload.narrative.strip()),
        'RECYCLE': bool(payload.process_document_url and payload.outcome_document_url) and bool(payload.narrative.strip()),
        'RECOVER': bool(payload.process_document_url or payload.outcome_document_url) and bool(payload.narrative.strip()),
    }
    if not required[payload.pathway]:
        raise HTTPException(422, f'Please provide the required {payload.pathway.lower()} evidence before submission')


def submit_outcome(db: Session, transfer: Transfer, user: User, payload):
    if transfer.status != TransferStatus.RECEIVED.value:
        raise HTTPException(409, 'Physical receipt must be confirmed before circular outcome proof is submitted')
    if user.organization_id != transfer.receiver_organization_id:
        raise HTTPException(403, 'Only the receiving organisation can submit circular outcome evidence')
    existing = db.scalar(select(OutcomeEvidence).where(OutcomeEvidence.transfer_id == transfer.id))
    if existing and existing.evidence_status == OutcomeStatus.VERIFIED.value:
        raise HTTPException(409, 'This outcome is already verified and cannot be replaced')
    received = float(transfer.received_quantity or 0)
    if abs(payload.claimed_quantity - received) > 1e-9:
        raise HTTPException(422, 'Outcome quantity must account for the full physically received quantity before verification')
    receiver = db.get(Organization, transfer.receiver_organization_id)
    _validate_outcome_pathway(receiver, payload.pathway)
    _validate_outcome_evidence(payload)

    if existing and existing.evidence_status not in {OutcomeStatus.REJECTED.value, OutcomeStatus.CORRECTION_REQUESTED.value}:
        raise HTTPException(409, 'Submitted evidence is locked while awaiting review. Resubmission is available only after rejection or a correction request.')

    now = datetime.utcnow()
    if existing:
        existing.pathway = payload.pathway
        existing.claimed_quantity = payload.claimed_quantity
        existing.narrative = payload.narrative.strip()
        existing.before_photo_url = payload.before_photo_url
        existing.after_photo_url = payload.after_photo_url
        existing.process_document_url = payload.process_document_url
        existing.outcome_document_url = payload.outcome_document_url
        existing.evidence_status = OutcomeStatus.SUBMITTED.value
        existing.submitted_by_user_id = user.id
        existing.submitted_at = now
        existing.reviewer_note = ''
        existing.reviewer_user_id = None
        existing.reviewed_at = None
        outcome = existing
    else:
        outcome = OutcomeEvidence(
            transfer_id=transfer.id,
            pathway=payload.pathway,
            claimed_quantity=payload.claimed_quantity,
            narrative=payload.narrative.strip(),
            evidence_status=OutcomeStatus.SUBMITTED.value,
            before_photo_url=payload.before_photo_url,
            after_photo_url=payload.after_photo_url,
            process_document_url=payload.process_document_url,
            outcome_document_url=payload.outcome_document_url,
            submitted_by_user_id=user.id,
        )
        db.add(outcome)
        db.flush()

    add_event(db, transfer.id, 'OUTCOME_SUBMITTED', f'Circular outcome evidence submitted: {payload.pathway}, {payload.claimed_quantity:g} units.', user.id)
    send_to_org(db, transfer.source_organization_id, 'Circular outcome submitted', f'Transfer #{transfer.id} has submitted {payload.pathway.lower()} evidence for platform verification.', 'OUTCOME_SUBMITTED', transfer.id)
    send_to_admins(db, 'Outcome proof awaiting review', f'Transfer #{transfer.id} submitted {payload.pathway} evidence for {payload.claimed_quantity:g} units.', 'OUTCOME_SUBMITTED', transfer.id)
    return outcome


def review_outcome(db: Session, outcome: OutcomeEvidence, reviewer: User, decision: str, note: str):
    if outcome.evidence_status not in {OutcomeStatus.SUBMITTED.value, OutcomeStatus.UNDER_REVIEW.value}:
        raise HTTPException(409, f'Outcome cannot be reviewed from {outcome.evidence_status}')
    if decision not in {'VERIFIED', 'CORRECTION_REQUESTED', 'REJECTED'}:
        raise HTTPException(422, 'Decision must be VERIFIED, CORRECTION_REQUESTED or REJECTED')

    transfer = db.get(Transfer, outcome.transfer_id)
    if not transfer:
        raise HTTPException(404, 'Transfer not found for outcome')
    if transfer.status != TransferStatus.RECEIVED.value:
        raise HTTPException(409, 'Transfer must be in RECEIVED state for outcome review')

    if decision in {'CORRECTION_REQUESTED', 'REJECTED'}:
        if not note.strip():
            raise HTTPException(422, 'A reviewer note is required when requesting correction or rejecting evidence')
        outcome.evidence_status = OutcomeStatus.CORRECTION_REQUESTED.value if decision == 'CORRECTION_REQUESTED' else OutcomeStatus.REJECTED.value
        outcome.reviewer_user_id = reviewer.id
        outcome.reviewer_note = note.strip()
        outcome.reviewed_at = datetime.utcnow()
        event_type = 'OUTCOME_CORRECTION_REQUESTED' if decision == 'CORRECTION_REQUESTED' else 'OUTCOME_REJECTED'
        title = 'Outcome proof needs correction' if decision == 'CORRECTION_REQUESTED' else 'Outcome proof rejected'
        notification_type = 'OUTCOME_REJECTED'
        add_event(db, transfer.id, event_type, f'Circular outcome review action: {note.strip()}.', reviewer.id)
        send_to_org(db, transfer.receiver_organization_id, title, f'Transfer #{transfer.id}: {note.strip()} Submit corrected evidence before the circular outcome can be verified.', notification_type, transfer.id)
        send_to_org(db, transfer.source_organization_id, 'Outcome verification update', f'Transfer #{transfer.id}: the submitted outcome requires reviewer action before verified impact can be counted.', notification_type, transfer.id)
        return

    # VERIFIED
    route = db.get(Route, transfer.route_id) if transfer.route_id else None
    material = db.get(Material, transfer.material_id)
    if not material:
        raise HTTPException(404, 'Material not found')
    if abs(outcome.claimed_quantity - float(transfer.received_quantity or 0)) > 1e-9:
        raise HTTPException(422, 'Verified outcome quantity must equal the full physically received quantity')

    outcome.evidence_status = OutcomeStatus.VERIFIED.value
    outcome.reviewer_user_id = reviewer.id
    outcome.reviewer_note = note.strip()
    outcome.reviewed_at = datetime.utcnow()

    existing_impact = db.scalar(select(Impact).where(Impact.transfer_id == transfer.id))
    if not existing_impact:
        value, waste, co2 = create_verified_impact(material, transfer, route, outcome.pathway, outcome.claimed_quantity)
        db.add(Impact(
            material_id=material.id,
            transfer_id=transfer.id,
            outcome_id=outcome.id,
            value_recovered=value,
            waste_avoided_kg=waste,
            co2_avoided_kg=co2,
            pathway=outcome.pathway,
            verified_quantity=outcome.claimed_quantity,
        ))

    transition(transfer.status, TransferStatus.COMPLETED.value, TRANSFER_TRANSITIONS, 'transfer')
    transfer.status = TransferStatus.COMPLETED.value
    matched_request = db.get(Match, transfer.match_id) if transfer.match_id else None
    if matched_request and matched_request.status == 'ACCEPTED':
        transition(matched_request.status, 'FULFILLED', {'ACCEPTED': {'FULFILLED'}}, 'match')
        matched_request.status = 'FULFILLED'
    material.remaining_quantity = max(0.0, material.remaining_quantity - float(transfer.received_quantity or 0))
    material.status = MaterialStatus.AVAILABLE.value if material.remaining_quantity > 1e-9 else MaterialStatus.COMPLETED.value

    add_event(db, transfer.id, 'OUTCOME_VERIFIED', f'{outcome.pathway} outcome verified for {outcome.claimed_quantity:g} units. Impact is now counted.', reviewer.id)
    send_to_org(db, transfer.source_organization_id, 'Circular impact verified', f'Transfer #{transfer.id}: {outcome.pathway.lower()} outcome evidence is verified. Impact is now included.', 'OUTCOME_VERIFIED', transfer.id)
    send_to_org(db, transfer.receiver_organization_id, 'Outcome verified', f'Transfer #{transfer.id}: your {outcome.pathway.lower()} evidence is verified.', 'OUTCOME_VERIFIED', transfer.id)

