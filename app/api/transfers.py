from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_db
from ..core.deps import current_user, require_roles
from ..models.models import Driver, Material, MaterialStatus, Match, MatchStatus, Organization, ReceiverNeed, Role, Route, Transfer, TransferStatus, User
from ..schemas.schemas import DriverAssignment, LocationPing, ReceiptConfirm, TransferCreate, TransferOut, TrackingOut
from ..services.notifications import send_notification, send_to_org
from ..services.routing import VEHICLES, calculate_route_values, haversine_km, normalize_vehicle
from ..services.serializers import transfer_out, org_out, route_out
from ..services.state import TRANSFER_TRANSITIONS, transition
from ..services.transfer import ACTIVE_TRANSFER_STATUSES, add_event, confirm_receipt, mark_arrival, participant_transfer

router = APIRouter(prefix='/api/transfers', tags=['Transport & Tracking'])


def get_transfer(db: Session, transfer_id: int) -> Transfer:
    transfer = db.get(Transfer, transfer_id)
    if not transfer: raise HTTPException(404, 'Transfer not found')
    return transfer


def require_participant(user: User, transfer: Transfer, db: Session):
    if not participant_transfer(db, user, transfer): raise HTTPException(403, 'You are not a participant in this transfer')


@router.post('', response_model=TransferOut)
def create_transfer(payload: TransferCreate, user: User = Depends(require_roles(Role.ORGANIZATION.value)), db: Session = Depends(get_db)):
    material = db.get(Material, payload.material_id); receiver = db.get(Organization, payload.receiver_organization_id); logistics = db.get(Organization, payload.logistics_partner_id); route = db.get(Route, payload.route_id)
    if not all([material, receiver, logistics, route]): raise HTTPException(404, 'Material, receiver, logistics partner or route not found')
    if material.owner_organization_id != user.organization_id: raise HTTPException(403, 'You do not own this material')
    if logistics.organization_type != 'Logistics' or logistics.verification_status != 'VERIFIED': raise HTTPException(409, 'Selected logistics partner is not verified')
    if route.material_id != material.id or route.partner_organization_id != receiver.id: raise HTTPException(400, 'Selected route does not belong to the material and receiver')
    match_query = select(Match).where(Match.material_id == material.id, Match.partner_organization_id == receiver.id, Match.status == MatchStatus.ACCEPTED.value)
    if payload.need_id is not None:
        match_query = match_query.where(Match.need_id == payload.need_id)
    accepted = db.scalar(match_query.order_by(desc(Match.created_at)))
    if not accepted: raise HTTPException(409, 'Receiver must accept the material request before transport is created')
    if accepted.need_id:
        need = db.get(ReceiverNeed, accepted.need_id)
        if not need or need.remaining_quantity < payload.quantity - 1e-9:
            raise HTTPException(409, 'Transfer quantity exceeds the receiver\'s remaining need')
        if need.unit.strip().lower() != material.unit.strip().lower():
            raise HTTPException(409, f'Unit mismatch: material is measured in {material.unit}, while the need is measured in {need.unit}')
    active_reserved = float(db.scalar(select(func.coalesce(func.sum(Transfer.quantity), 0)).where(Transfer.material_id == material.id, Transfer.status.in_(ACTIVE_TRANSFER_STATUSES))) or 0)
    available = material.remaining_quantity - active_reserved
    if payload.quantity > available + 1e-9: raise HTTPException(409, f'Only {max(0, available):g} {material.unit} is available')
    if route.capacity_units + 1e-9 < payload.quantity: raise HTTPException(409, 'Selected vehicle capacity is too small for this quantity')
    duplicate = db.scalar(select(Transfer).where(Transfer.material_id == material.id, Transfer.receiver_organization_id == receiver.id, Transfer.status.in_(ACTIVE_TRANSFER_STATUSES)))
    if duplicate: raise HTTPException(409, f'Active transfer #{duplicate.id} already exists for this material and receiver')
    transfer = Transfer(material_id=material.id, source_organization_id=material.owner_organization_id, receiver_organization_id=receiver.id, logistics_partner_id=logistics.id, route_id=route.id, match_id=accepted.id, need_id=accepted.need_id, quantity=payload.quantity, status=TransferStatus.REQUESTED.value)
    db.add(transfer); db.flush(); material.status = MaterialStatus.IN_TRANSFER.value
    add_event(db, transfer.id, 'TRANSPORT_REQUESTED', f'Transport request created for {payload.quantity:g} {material.unit} of {material.name}.', user.id)
    send_to_org(db, logistics.id, 'New transport request', f'Transfer #{transfer.id}: collect {payload.quantity:g} {material.unit} of {material.name} and deliver to {receiver.name}.', 'GENERAL', transfer.id)
    db.commit(); db.refresh(transfer); return transfer_out(transfer, db)


@router.get('', response_model=list[TransferOut])
def list_transfers(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role == Role.ADMIN.value:
        rows = list(db.scalars(select(Transfer).order_by(desc(Transfer.created_at))).all())
    elif user.role == Role.DRIVER.value:
        driver = db.scalar(select(Driver).where(Driver.user_id == user.id)); rows = [] if not driver else list(db.scalars(select(Transfer).where(Transfer.driver_id == driver.id).order_by(desc(Transfer.created_at))).all())
    else:
        rows = list(db.scalars(select(Transfer).where((Transfer.source_organization_id == user.organization_id) | (Transfer.receiver_organization_id == user.organization_id) | (Transfer.logistics_partner_id == user.organization_id)).order_by(desc(Transfer.created_at))).all())
    return [transfer_out(row, db) for row in rows]


@router.post('/{transfer_id}/assign-driver', response_model=TransferOut)
def assign_driver(transfer_id: int, payload: DriverAssignment, user: User = Depends(require_roles(Role.LOGISTICS.value, Role.ADMIN.value)), db: Session = Depends(get_db)):
    transfer = get_transfer(db, transfer_id); driver = db.get(Driver, payload.driver_id)
    if not driver or not driver.is_active: raise HTTPException(404, 'Driver not found or inactive')
    if user.role != Role.ADMIN.value and (transfer.logistics_partner_id != user.organization_id or driver.organization_id != user.organization_id): raise HTTPException(403, 'Driver and transport request must belong to your logistics organisation')
    if transfer.status != TransferStatus.REQUESTED.value or transfer.driver_id: raise HTTPException(409, 'Transfer is not waiting for driver assignment')
    if transfer.logistics_partner_id is None: raise HTTPException(409, 'A logistics partner must be selected before driver assignment')
    if driver.status != 'AVAILABLE': raise HTTPException(409, 'Driver is not available')
    route = db.get(Route, transfer.route_id) if transfer.route_id else None
    if not route: raise HTTPException(409, 'A route must be selected before driver assignment')
    vehicle_key = normalize_vehicle(driver.vehicle_type)
    if vehicle_key not in VEHICLES: raise HTTPException(409, 'Assigned driver has an unsupported vehicle type')
    if VEHICLES[vehicle_key]['capacity'] < transfer.quantity: raise HTTPException(409, 'Assigned vehicle cannot carry this quantity')
    material = db.get(Material, transfer.material_id); source = db.get(Organization, transfer.source_organization_id); receiver = db.get(Organization, transfer.receiver_organization_id)
    if not material or not source or not receiver: raise HTTPException(409, 'Transfer data is incomplete')

    # Logistics owns the operational vehicle choice. If the available driver uses a
    # different vehicle from the route selected during planning, transparently create
    # or refresh a route for the driver's vehicle rather than rejecting assignment.
    if normalize_vehicle(route.vehicle_type) != vehicle_key:
        values = calculate_route_values(material, receiver, vehicle_key, transfer.quantity)
        replanned = db.scalar(select(Route).where(
            Route.material_id == material.id,
            Route.partner_organization_id == receiver.id,
            Route.vehicle_type == vehicle_key,
        ))
        if replanned:
            for key, value in values.items(): setattr(replanned, key, value)
            route = replanned
        else:
            route = Route(material_id=material.id, partner_organization_id=receiver.id, **values)
            db.add(route); db.flush()
        transfer.route_id = route.id
        add_event(db, transfer.id, 'ROUTE_REPLANNED', f'Route automatically replanned for assigned vehicle {driver.vehicle_type}.', user.id)

    transition(transfer.status, TransferStatus.PICKUP_SCHEDULED.value, TRANSFER_TRANSITIONS, 'transfer')
    transfer.driver_id = driver.id; transfer.status = TransferStatus.PICKUP_SCHEDULED.value; transfer.pickup_time = datetime.utcnow(); driver.status = 'ASSIGNED'
    add_event(db, transfer.id, 'DRIVER_ASSIGNED', f'{driver.driver_code} assigned with {driver.vehicle_type} {driver.vehicle_number}.', user.id)
    if driver.user_id: send_notification(db, driver.user_id, 'New delivery job assigned', f'Transfer #{transfer.id}: {material.name} from {source.name} to {receiver.name}. Vehicle {driver.vehicle_number}.', 'DRIVER_ASSIGNED', transfer.id)
    send_to_org(db, source.id, 'Transport confirmed', f'Driver {driver.driver_code} ({driver.name}) and vehicle {driver.vehicle_number} were assigned to transfer #{transfer.id}.', 'DRIVER_ASSIGNED', transfer.id)
    send_to_org(db, receiver.id, 'Transport confirmed', f'Driver {driver.driver_code} and vehicle {driver.vehicle_number} are assigned to transfer #{transfer.id}.', 'DRIVER_ASSIGNED', transfer.id)
    db.commit(); db.refresh(transfer); return transfer_out(transfer, db)


@router.post('/{transfer_id}/accept-assignment', response_model=TransferOut)
def accept_assignment(transfer_id: int, user: User = Depends(require_roles(Role.DRIVER.value)), db: Session = Depends(get_db)):
    transfer = get_transfer(db, transfer_id)
    driver = db.scalar(select(Driver).where(Driver.user_id == user.id))
    if not driver or transfer.driver_id != driver.id:
        raise HTTPException(403, 'This trip is not assigned to you')
    if transfer.status != TransferStatus.PICKUP_SCHEDULED.value:
        raise HTTPException(409, 'This assignment is no longer awaiting driver acceptance')
    if transfer.driver_accepted_at is not None:
        return transfer_out(transfer, db)
    transfer.driver_accepted_at = datetime.utcnow()
    add_event(db, transfer.id, 'DRIVER_ACCEPTED', f'Driver {driver.driver_code} accepted the delivery assignment.', user.id)
    send_to_org(db, transfer.source_organization_id, 'Driver accepted assignment', f'Driver {driver.driver_code} accepted transfer #{transfer.id}. Pickup is now confirmed.', 'DRIVER_ACCEPTED', transfer.id)
    send_to_org(db, transfer.receiver_organization_id, 'Driver accepted assignment', f'Driver {driver.driver_code} accepted transfer #{transfer.id}. The pickup is now confirmed.', 'DRIVER_ACCEPTED', transfer.id)
    if transfer.logistics_partner_id:
        send_to_org(db, transfer.logistics_partner_id, 'Driver accepted assignment', f'Driver {driver.driver_code} accepted transfer #{transfer.id}.', 'DRIVER_ACCEPTED', transfer.id)
    db.commit()
    db.refresh(transfer)
    return transfer_out(transfer, db)


@router.post('/{transfer_id}/start-trip', response_model=TransferOut)
def start_trip(transfer_id: int, user: User = Depends(require_roles(Role.DRIVER.value)), db: Session = Depends(get_db)):
    transfer = get_transfer(db, transfer_id); driver = db.scalar(select(Driver).where(Driver.user_id == user.id))
    if not driver or transfer.driver_id != driver.id: raise HTTPException(403, 'This trip is not assigned to you')
    if transfer.status != TransferStatus.PICKUP_SCHEDULED.value: raise HTTPException(409, 'Trip can only start after driver assignment')
    if transfer.driver_accepted_at is None: raise HTTPException(409, 'Accept the assigned ride before starting the trip')
    transition(transfer.status, TransferStatus.IN_TRANSIT.value, TRANSFER_TRANSITIONS, 'transfer'); transfer.status = TransferStatus.IN_TRANSIT.value; driver.status = 'IN_TRANSIT'; driver.last_seen_at = datetime.utcnow()
    add_event(db, transfer.id, 'TRIP_STARTED', f'Driver {driver.driver_code} started the trip.', user.id)
    send_to_org(db, transfer.source_organization_id, 'Trip started', f'Driver {driver.driver_code} started transfer #{transfer.id}.', 'TRIP_STARTED', transfer.id)
    send_to_org(db, transfer.receiver_organization_id, 'Delivery is in transit', f'Driver {driver.driver_code} started transfer #{transfer.id}. Live tracking is active.', 'TRIP_STARTED', transfer.id)
    if transfer.logistics_partner_id: send_to_org(db, transfer.logistics_partner_id, 'Driver started trip', f'Driver {driver.driver_code} started transfer #{transfer.id}.', 'TRIP_STARTED', transfer.id)
    db.commit(); db.refresh(transfer); return transfer_out(transfer, db)


@router.post('/{transfer_id}/location', response_model=TransferOut)
def update_location(transfer_id: int, payload: LocationPing, user: User = Depends(current_user), db: Session = Depends(get_db)):
    transfer = get_transfer(db, transfer_id)
    if user.role == Role.DRIVER:
        driver = db.scalar(select(Driver).where(Driver.user_id == user.id))
        if not driver or transfer.driver_id != driver.id: raise HTTPException(403, 'This transfer is not assigned to you')
    else:
        raise HTTPException(403, 'Only the assigned driver can publish GPS')
    driver.current_lat = payload.latitude; driver.current_lng = payload.longitude; driver.last_seen_at = datetime.utcnow()
    from ..models.models import LocationUpdate
    db.add(LocationUpdate(transfer_id=transfer.id, driver_id=driver.id, latitude=payload.latitude, longitude=payload.longitude, accuracy_m=payload.accuracy_m, speed_kmph=payload.speed_kmph, recorded_at=datetime.utcnow()))
    arrived = mark_arrival(db, transfer, driver, user.id)
    db.commit(); db.refresh(transfer); return transfer_out(transfer, db)


@router.post('/{transfer_id}/mark-arrived', response_model=TransferOut)
def mark_arrived_endpoint(
    transfer_id: int,
    payload: LocationPing,
    user: User = Depends(require_roles(Role.DRIVER.value, Role.ADMIN.value)),
    db: Session = Depends(get_db),
):
    transfer = get_transfer(db, transfer_id)
    driver = db.get(Driver, transfer.driver_id) if transfer.driver_id else None
    if not driver:
        raise HTTPException(409, 'This transfer has no assigned driver')
    if user.role == Role.DRIVER.value:
        own = db.scalar(select(Driver).where(Driver.user_id == user.id))
        if not own or own.id != driver.id:
            raise HTTPException(403, 'This trip is not assigned to you')
    if transfer.status != TransferStatus.IN_TRANSIT.value:
        raise HTTPException(409, 'The trip must be in transit before marking arrival')
    driver.current_lat = payload.latitude
    driver.current_lng = payload.longitude
    driver.last_seen_at = datetime.utcnow()
    from ..models.models import LocationUpdate
    db.add(LocationUpdate(
        transfer_id=transfer.id,
        driver_id=driver.id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_m=payload.accuracy_m,
        speed_kmph=payload.speed_kmph,
        recorded_at=datetime.utcnow(),
    ))
    route = db.get(Route, transfer.route_id) if transfer.route_id else None
    if not route:
        raise HTTPException(409, 'Route not found')
    distance = haversine_km(payload.latitude, payload.longitude, route.destination_lat, route.destination_lng)
    if distance > settings.arrival_radius_km:
        raise HTTPException(409, f'You are still {distance * 1000:.0f} m from the destination. Arrival requires GPS within {settings.arrival_radius_km * 1000:.0f} m.')
    mark_arrival(db, transfer, driver, user.id)
    db.commit()
    db.refresh(transfer)
    return transfer_out(transfer, db)


@router.post('/{transfer_id}/simulate-location', response_model=TransferOut)
def simulate_location(transfer_id: int, progress: float, user: User = Depends(require_roles(Role.DRIVER.value, Role.ADMIN.value)), db: Session = Depends(get_db)):
    if progress < 0 or progress > 1: raise HTTPException(422, 'Progress must be between 0 and 1')
    transfer = get_transfer(db, transfer_id); driver = db.get(Driver, transfer.driver_id) if transfer.driver_id else None; route = db.get(Route, transfer.route_id) if transfer.route_id else None
    if not driver or not route: raise HTTPException(409, 'Transfer must have a driver and route')
    if user.role == Role.DRIVER.value:
        own = db.scalar(select(Driver).where(Driver.user_id == user.id));
        if not own or own.id != driver.id: raise HTTPException(403, 'This trip is not assigned to you')
    if transfer.status != TransferStatus.IN_TRANSIT.value: raise HTTPException(409, 'Demo movement is available only while the trip is in transit')
    # Linear demo path between source and destination for a deterministic presentation.
    source_lat, source_lng = route.source_lat, route.source_lng; dest_lat, dest_lng = route.destination_lat, route.destination_lng
    lat = source_lat + (dest_lat - source_lat) * progress; lng = source_lng + (dest_lng - source_lng) * progress
    driver.current_lat = lat; driver.current_lng = lng; driver.last_seen_at = datetime.utcnow()
    from ..models.models import LocationUpdate
    db.add(LocationUpdate(transfer_id=transfer.id, driver_id=driver.id, latitude=lat, longitude=lng, accuracy_m=15, speed_kmph=35 if progress < 1 else 0, recorded_at=datetime.utcnow()))
    mark_arrival(db, transfer, driver, user.id); db.commit(); db.refresh(transfer); return transfer_out(transfer, db)


@router.post('/{transfer_id}/confirm-receipt', response_model=TransferOut)
def confirm_receipt_endpoint(transfer_id: int, payload: ReceiptConfirm, user: User = Depends(require_roles(Role.RECEIVER.value, Role.RECYCLER.value)), db: Session = Depends(get_db)):
    transfer = get_transfer(db, transfer_id); confirm_receipt(db, transfer, user, payload.received_quantity, payload.received_condition, payload.notes, payload.receipt_photo_url); db.commit(); db.refresh(transfer); return transfer_out(transfer, db)


@router.post('/{transfer_id}/cancel', response_model=TransferOut)
def cancel_transfer(transfer_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    transfer = get_transfer(db, transfer_id)
    if user.role != Role.ADMIN.value and user.organization_id not in {transfer.source_organization_id, transfer.logistics_partner_id}: raise HTTPException(403, 'You cannot cancel this transfer')
    if transfer.status not in {TransferStatus.REQUESTED.value, TransferStatus.PICKUP_SCHEDULED.value}: raise HTTPException(409, 'Only pre-trip transfers can be cancelled')
    transition(transfer.status, TransferStatus.CANCELLED.value, TRANSFER_TRANSITIONS, 'transfer'); transfer.status = TransferStatus.CANCELLED.value; transfer.cancelled_at = datetime.utcnow()
    material = db.get(Material, transfer.material_id); driver = db.get(Driver, transfer.driver_id) if transfer.driver_id else None
    if transfer.need_id:
        need = db.get(ReceiverNeed, transfer.need_id)
        if need and need.remaining_quantity > 1e-9:
            other_active = db.scalar(select(func.count(Transfer.id)).where(Transfer.need_id == need.id, Transfer.id != transfer.id, Transfer.status.in_(ACTIVE_TRANSFER_STATUSES))) or 0
            if not other_active:
                need.status = 'OPEN'
    if material:
        active_left = db.scalar(select(func.count(Transfer.id)).where(Transfer.material_id == material.id, Transfer.id != transfer.id, Transfer.status.in_(ACTIVE_TRANSFER_STATUSES))) or 0
        material.status = MaterialStatus.IN_TRANSFER.value if active_left else (MaterialStatus.AVAILABLE.value if material.remaining_quantity > 0 else MaterialStatus.COMPLETED.value)
    if driver: driver.status = 'AVAILABLE'
    add_event(db, transfer.id, 'CANCELLED', 'Transport request cancelled and resources released.', user.id)
    db.commit(); db.refresh(transfer); return transfer_out(transfer, db)


@router.get('/{transfer_id}/tracking', response_model=TrackingOut)
def tracking(transfer_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    transfer = get_transfer(db, transfer_id); require_participant(user, transfer, db)
    driver = db.get(Driver, transfer.driver_id) if transfer.driver_id else None; route = db.get(Route, transfer.route_id) if transfer.route_id else None
    source = db.get(Organization, transfer.source_organization_id); receiver = db.get(Organization, transfer.receiver_organization_id); logistics = db.get(Organization, transfer.logistics_partner_id) if transfer.logistics_partner_id else None
    from ..models.models import LocationUpdate, TransferEvent
    locations = list(db.scalars(select(LocationUpdate).where(LocationUpdate.transfer_id == transfer.id).order_by(desc(LocationUpdate.recorded_at)).limit(60)).all())
    events = list(db.scalars(select(TransferEvent).where(TransferEvent.transfer_id == transfer.id).order_by(TransferEvent.created_at)).all())
    latest = None
    if locations:
        latest = {'latitude': locations[0].latitude, 'longitude': locations[0].longitude, 'accuracy_m': locations[0].accuracy_m, 'speed_kmph': locations[0].speed_kmph, 'recorded_at': locations[0].recorded_at}
    elif driver and driver.current_lat is not None:
        latest = {'latitude': driver.current_lat, 'longitude': driver.current_lng, 'accuracy_m': None, 'speed_kmph': None, 'recorded_at': driver.last_seen_at}
    outcome = None
    from ..models.models import OutcomeEvidence
    outcome = db.scalar(select(OutcomeEvidence).where(OutcomeEvidence.transfer_id == transfer.id))
    return TrackingOut(
        transfer=transfer_out(transfer, db), driver=driver, source=org_out(source), receiver=org_out(receiver), logistics=org_out(logistics), route=route_out(route) if route else None,
        latest_location=latest,
        location_history=[{'latitude': x.latitude, 'longitude': x.longitude, 'accuracy_m': x.accuracy_m, 'speed_kmph': x.speed_kmph, 'recorded_at': x.recorded_at} for x in reversed(locations)],
        event_history=[{'event_type': x.event_type, 'message': x.message, 'created_at': x.created_at} for x in events], arrived=transfer.status in {TransferStatus.DELIVERED.value, TransferStatus.RECEIVED.value, TransferStatus.COMPLETED.value}
    )


@router.get('/{transfer_id}/locations')
def locations(transfer_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    transfer = get_transfer(db, transfer_id); require_participant(user, transfer, db)
    from ..models.models import LocationUpdate
    rows = list(db.scalars(select(LocationUpdate).where(LocationUpdate.transfer_id == transfer_id).order_by(LocationUpdate.recorded_at)).all())
    return [{'latitude': x.latitude, 'longitude': x.longitude, 'accuracy_m': x.accuracy_m, 'speed_kmph': x.speed_kmph, 'recorded_at': x.recorded_at} for x in rows]
