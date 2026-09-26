from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .core.security import hash_password
from .models.models import Assessment, Driver, Impact, Match, MatchStatus, Material, MaterialStatus, Notification, NeedStatus, Organization, OutcomeEvidence, OutcomeStatus, ReceiverNeed, Role, Route, Transfer, TransferEvent, TransferStatus, User
from .services.ai import assess_material
from .services.impact import create_verified_impact
from .services.matching import build_matches
from .services.routing import calculate_route_values

DEMO_PASSWORD = 'demo123'


def ensure_org(db: Session, **data) -> Organization:
    org = db.scalar(select(Organization).where(Organization.contact_email == data['contact_email']))
    if org:
        for key, value in data.items(): setattr(org, key, value)
        return org
    org = Organization(**data); db.add(org); db.flush(); return org


def ensure_user(db: Session, email: str, name: str, role: str, org: Organization | None):
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        user = User(email=email, name=name, role=role, organization_id=org.id if org else None, password_hash=hash_password(DEMO_PASSWORD), is_active=True)
        db.add(user); db.flush()
    else:
        user.name=name; user.role=role; user.organization_id=org.id if org else None; user.password_hash=hash_password(DEMO_PASSWORD); user.is_active=True
    return user


def ensure_material(db: Session, org: Organization, spec):
    name, category, description, quantity, unit, condition, age, value = spec
    material = db.scalar(select(Material).where(Material.owner_organization_id == org.id, Material.name == name))
    if material: return material
    material = Material(owner_organization_id=org.id, name=name, category=category, description=description, quantity=quantity, remaining_quantity=quantity, unit=unit, condition=condition, age_years=age, city=org.city, state=org.state, latitude=org.latitude, longitude=org.longitude, estimated_value=value, status=MaterialStatus.AVAILABLE.value)
    db.add(material); db.flush(); return material


def ensure_need(db: Session, org: Organization, material_name: str, category: str, quantity: float, unit: str, condition: str, notes: str):
    need = db.scalar(select(ReceiverNeed).where(ReceiverNeed.organization_id == org.id, ReceiverNeed.material_name == material_name, ReceiverNeed.status == NeedStatus.OPEN.value))
    if need: return need
    need = ReceiverNeed(organization_id=org.id, material_name=material_name, category=category, quantity=quantity, remaining_quantity=quantity, unit=unit, acceptable_condition=condition, notes=notes, status=NeedStatus.OPEN.value)
    db.add(need); db.flush(); return need


def ensure_driver(db: Session, org: Organization, name: str, email: str, code: str, vehicle_type: str, vehicle_number: str, phone: str):
    user = ensure_user(db, email, name, Role.DRIVER.value, org)
    driver = db.scalar(select(Driver).where(Driver.driver_code == code))
    if driver:
        driver.organization_id=org.id; driver.user_id=user.id; driver.name=name; driver.phone=phone; driver.vehicle_type=vehicle_type; driver.vehicle_number=vehicle_number; driver.is_active=True
        active_assignment = db.scalar(select(Transfer).where(
            Transfer.driver_id == driver.id,
            Transfer.status.in_({TransferStatus.PICKUP_SCHEDULED.value, TransferStatus.IN_TRANSIT.value, TransferStatus.DELIVERED.value, TransferStatus.RECEIVED.value})
        ))
        if active_assignment:
            if active_assignment.status == TransferStatus.PICKUP_SCHEDULED.value: driver.status='ASSIGNED'
            elif active_assignment.status == TransferStatus.IN_TRANSIT.value: driver.status='IN_TRANSIT'
            else: driver.status='AT_DESTINATION'
        elif driver.status not in {'IN_TRANSIT','AT_DESTINATION'}:
            driver.status='AVAILABLE'
        if driver.current_lat is None: driver.current_lat=org.latitude
        if driver.current_lng is None: driver.current_lng=org.longitude
        return driver
    driver=Driver(organization_id=org.id,user_id=user.id,driver_code=code,name=name,phone=phone,vehicle_type=vehicle_type,vehicle_number=vehicle_number,status='AVAILABLE',current_lat=org.latitude,current_lng=org.longitude,last_seen_at=datetime.utcnow(),is_active=True)
    db.add(driver); db.flush(); return driver


def ensure_assessment(db: Session, material: Material):
    assessment = db.scalar(select(Assessment).where(Assessment.material_id == material.id).order_by(desc(Assessment.created_at)))
    if assessment: return assessment
    result=assess_material(material)
    assessment=Assessment(material_id=material.id,condition_score=result.condition_score,recommendation=result.recommendation,confidence=result.confidence,reuse_score=result.scores['REUSE'],refurbish_score=result.scores['REFURBISH'],recycle_score=result.scores['RECYCLE'],recover_score=result.scores['RECOVER'],reason_json=json.dumps({'reasons':result.reasons,'factor_breakdown':result.factor_breakdown}))
    db.add(assessment); db.flush(); return assessment


def seed_demo(db: Session):
    nova=ensure_org(db,name='NovaTech Industries',organization_type='Company',city='Navi Mumbai',state='Maharashtra',address='Turbhe MIDC',latitude=19.082,longitude=73.0175,contact_email='org@reloop.demo',verification_status='VERIFIED',materials_supported='furniture,electronics,paper,metal,plastic,textiles',capacity=1200,service_area_km=90,certifications='ISO 14001')
    green=ensure_org(db,name='GreenWorks Community',organization_type='NGO',city='Mumbai',state='Maharashtra',address='Andheri East',latitude=19.1136,longitude=72.8697,contact_email='receiver@reloop.demo',verification_status='VERIFIED',materials_supported='furniture,paper,plastic,textiles',capacity=700,service_area_km=80,certifications='Registered NGO')
    recycle=ensure_org(db,name='ReCycle Hub',organization_type='Recycler',city='Thane',state='Maharashtra',address='Wagle Estate',latitude=19.2183,longitude=72.9781,contact_email='recycler@reloop.demo',verification_status='VERIFIED',materials_supported='electronics,plastic,paper,metal',capacity=2500,service_area_km=120,certifications='E-waste Authorization')
    move=ensure_org(db,name='MoveGreen Logistics',organization_type='Logistics',city='Mumbai',state='Maharashtra',address='BKC',latitude=19.0596,longitude=72.8656,contact_email='logistics@reloop.demo',verification_status='VERIFIED',materials_supported='all',capacity=5000,service_area_km=120,certifications='Fleet verified')
    college=ensure_org(db,name='Urban Skills College',organization_type='College',city='Panvel',state='Maharashtra',address='Kalamboli',latitude=19.234,longitude=73.129,contact_email='college@reloop.demo',verification_status='VERIFIED',materials_supported='furniture,electronics,paper,metal',capacity=300,service_area_km=100,certifications='Institutional receiver')
    refurb=ensure_org(db,name='RenewWorks Refurbishment',organization_type='Refurbisher',city='Thane',state='Maharashtra',address='MIDC Wagle Estate',latitude=19.207,longitude=72.972,contact_email='refurbisher@reloop.demo',verification_status='VERIFIED',materials_supported='furniture,electronics,metal',capacity=800,service_area_km=100,certifications='Refurbishment partner')

    org_user=ensure_user(db,'org@reloop.demo','NovaTech Operations',Role.ORGANIZATION.value,nova)
    receiver_user=ensure_user(db,'receiver@reloop.demo','GreenWorks Procurement',Role.RECEIVER.value,green)
    recycler_user=ensure_user(db,'recycler@reloop.demo','ReCycle Hub Operations',Role.RECYCLER.value,recycle)
    logistics_user=ensure_user(db,'logistics@reloop.demo','MoveGreen Dispatch',Role.LOGISTICS.value,move)
    admin_user=ensure_user(db,'admin@reloop.demo','Reloop Platform Admin',Role.ADMIN.value,None)
    ensure_driver(db,move,'Ajay Patil','driver@reloop.demo','DRV-1001','MINI TRUCK','MH-46-RL-1001','9876543210')
    ensure_driver(db,move,'Neha Shah','driver2@reloop.demo','DRV-1002','EV VAN','MH-04-RL-2002','9876500002')
    ensure_driver(db,move,'Ravi More','driver3@reloop.demo','DRV-1003','BIKE','MH-04-RL-3003','9876500003')
    ensure_driver(db,move,'Priya Kulkarni','driver4@reloop.demo','DRV-1004','TRUCK','MH-04-RL-4004','9876500004')

    chairs=ensure_material(db,nova,('Office Chairs','furniture','Ergonomic office chairs from a facility refresh. Good structural condition and usable upholstery.',120,'units','GOOD',3,180000))
    monitors=ensure_material(db,nova,('LED Monitors','electronics','24-inch monitors replaced during an office IT refresh. Tested and working.',48,'units','GOOD',4,240000))
    boxes=ensure_material(db,nova,('Corrugated Boxes','paper','Clean used cartons suitable for direct reuse or fibre recovery.',900,'kg','FAIR',1,27000))
    e_waste=ensure_material(db,nova,('Mixed E-Waste','electronics','Older devices requiring certified recycling/recovery.',300,'kg','POOR',6,150000))
    frames=ensure_material(db,nova,('Aluminium Frames','metal','Lightweight structural frames from a showroom renovation.',260,'kg','EXCELLENT',2,95000))

    chair_need=ensure_need(db,green,'Office Chairs','furniture',80,'units','GOOD','Classroom and community workspaces; prefer direct reuse.')
    ensure_need(db,green,'Corrugated Boxes','paper',200,'kg','FAIR','Packing and community distribution reuse.')
    ensure_need(db,college,'LED Monitors','electronics',20,'units','GOOD','Digital lab upgrade.')

    db.commit()

    # Generate explainable assessments.
    for material in [chairs,monitors,boxes,e_waste,frames]: ensure_assessment(db,material)
    build_matches(db,chairs); build_matches(db,monitors); build_matches(db,boxes); build_matches(db,e_waste); build_matches(db,frames)

    # Seed one demo request only once. Do not resurrect an accepted/rejected request on every restart.
    existing_demo_match = db.scalar(select(Match).where(Match.material_id == chairs.id, Match.partner_organization_id == green.id, Match.need_id == chair_need.id))
    if existing_demo_match is None:
        pending = Match(
            material_id=chairs.id,
            partner_organization_id=green.id,
            need_id=chair_need.id,
            match_score=94,
            distance_km=7.2,
            reason_json=json.dumps({
                'reasons': [
                    'Receiver has an open demand for this category and unit.',
                    'Condition meets the receiver threshold.',
                    'Local distance supports a lower-impact transfer.',
                ],
                'factor_breakdown': {
                    'Material compatibility': 100,
                    'Condition': 95,
                    'Quantity': 94,
                    'Need/capability': 100,
                    'Location': 91,
                },
            }),
            status=MatchStatus.REQUESTED.value,
        )
        db.add(pending)
        db.flush()
        db.add(Notification(
            user_id=receiver_user.id,
            type='MATCH_REQUEST',
            title='Demo request awaiting your decision',
            message='NovaTech Industries has offered 80 Office Chairs. Review the incoming request to exercise the complete workflow.',
            created_at=datetime.utcnow(),
        ))

    # Historical verified reuse transfer for non-empty impact dashboard.
    historical=db.scalar(select(Transfer).where(Transfer.material_id==boxes.id,Transfer.status==TransferStatus.COMPLETED.value))
    if not historical:
        route_values=calculate_route_values(boxes,green,'EV VAN',100)
        route=Route(material_id=boxes.id,partner_organization_id=green.id,**route_values); db.add(route); db.flush()
        historical=Transfer(material_id=boxes.id,source_organization_id=nova.id,receiver_organization_id=green.id,logistics_partner_id=move.id,driver_id=None,route_id=route.id,quantity=100,status=TransferStatus.COMPLETED.value,pickup_time=datetime.utcnow()-timedelta(days=30),delivery_time=datetime.utcnow()-timedelta(days=29),arrived_at=datetime.utcnow()-timedelta(days=29),received_at=datetime.utcnow()-timedelta(days=29),received_quantity=100,received_condition='FAIR',receipt_notes='Historical demo receipt verified.',created_at=datetime.utcnow()-timedelta(days=31))
        db.add(historical); db.flush()
        event_specs=[('TRANSPORT_REQUESTED','Historical demo transport request recorded.'),('DRIVER_ASSIGNED','Historical demo logistics handover recorded.'),('TRIP_STARTED','Historical demo trip recorded.'),('ARRIVAL','Historical demo vehicle arrival recorded.'),('RECEIPT_CONFIRMED','Historical demo receiver confirmation recorded.')]
        for et,msg in event_specs: db.add(TransferEvent(transfer_id=historical.id,event_type=et,message=msg,actor_user_id=org_user.id))
        outcome=OutcomeEvidence(transfer_id=historical.id,pathway='REUSE',claimed_quantity=100,narrative='Historical demo: cartons were received and deployed for community distribution packing. Evidence is seeded as a verified demonstration record.',evidence_status=OutcomeStatus.VERIFIED.value,before_photo_url='/uploads/demo-before.txt',after_photo_url='/uploads/demo-after.txt',outcome_document_url='/uploads/demo-reuse-proof.txt',submitted_by_user_id=receiver_user.id,reviewer_user_id=admin_user.id,reviewer_note='Seeded verified demo outcome.',submitted_at=datetime.utcnow()-timedelta(days=28),reviewed_at=datetime.utcnow()-timedelta(days=27))
        db.add(outcome); db.flush()
        value,waste,co2=create_verified_impact(boxes,historical,route,'REUSE',100)
        db.add(Impact(material_id=boxes.id,transfer_id=historical.id,outcome_id=outcome.id,value_recovered=value,waste_avoided_kg=waste,co2_avoided_kg=co2,pathway='REUSE',verified_quantity=100))
        boxes.remaining_quantity -= 100

    db.commit()
