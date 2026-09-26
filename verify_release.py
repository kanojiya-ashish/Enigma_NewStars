from __future__ import annotations

import os
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

TEST_DB = Path(tempfile.gettempdir()) / 'reloop_v8_release_test.sqlite'
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ['RELOOP_DATABASE_URL'] = f'sqlite:///{TEST_DB}'
os.environ['RELOOP_CORS_ORIGINS'] = 'http://localhost:5173'

from fastapi.testclient import TestClient

from backend.app.main import app

BASE = 'http://testserver'


def assert_ok(response, label: str):
    if response.status_code >= 400:
        raise AssertionError(f'{label}: {response.status_code} {response.text}')
    return response.json()


def login(client: TestClient, email: str, role: str):
    data = assert_ok(client.post('/api/auth/login', json={'email': email, 'password': 'demo123', 'role': role}), f'login {role}')
    return {'Authorization': f"Bearer {data['access_token']}"}


def call(client, method, path, headers, **kwargs):
    return assert_ok(getattr(client, method)(path, headers=headers, **kwargs), path)


with TestClient(app) as client:
    h_org = login(client, 'org@reloop.demo', 'ORGANIZATION')
    h_receiver = login(client, 'receiver@reloop.demo', 'RECEIVER')
    h_recycler = login(client, 'recycler@reloop.demo', 'RECYCLER')
    h_logistics = login(client, 'logistics@reloop.demo', 'LOGISTICS')
    h_driver = login(client, 'driver2@reloop.demo', 'DRIVER')
    h_admin = login(client, 'admin@reloop.demo', 'ADMIN')

    materials = call(client, 'get', '/api/materials', h_org)
    chairs = next(x for x in materials if x['name'] == 'Office Chairs')
    mid = chairs['id']

    assessment = call(client, 'post', f'/api/assessment/{mid}', h_org)
    assert assessment['recommendation'] in {'REUSE', 'REFURBISH', 'RECYCLE', 'RECOVER'}

    matches = call(client, 'get', f'/api/matching/material/{mid}', h_org)
    target = next(x for x in matches if x['partner']['id'] and x['partner']['organization_type'] == 'NGO')
    request = call(client, 'post', '/api/matching/request', h_org, json={'material_id': mid, 'partner_organization_id': target['partner']['id'], 'need_id': target['need_id']})
    rid = request['id']
    incoming = call(client, 'get', '/api/matching/incoming', h_receiver)
    assert any(x['id'] == rid for x in incoming)
    call(client, 'patch', f'/api/matching/{rid}', h_receiver, json={'decision': 'ACCEPTED'})
    incoming_after_accept = call(client, 'get', '/api/matching/incoming', h_receiver)
    assert any(x['id'] == rid and x['status'] == 'ACCEPTED' for x in incoming_after_accept)

    # Once accepted, another partner cannot accept the same material concurrently.
    college = call(client, 'get', '/api/organizations?kind=RECEIVER', h_org)
    college_partner = next(x for x in college if x['organization_type'] == 'College')
    second_request = client.post('/api/matching/request', headers=h_org, json={'material_id': mid, 'partner_organization_id': college_partner['id']})
    assert second_request.status_code == 409, second_request.text

    options = call(client, 'get', f"/api/routes/options/{mid}/{target['partner']['id']}?quantity=10", h_org)
    assert options, 'route options should not be empty'
    route = options[0]
    logistics = call(client, 'get', '/api/organizations?kind=LOGISTICS', h_org)
    logistics_id = logistics[0]['id']
    transfer = call(client, 'post', '/api/transfers', h_org, json={'material_id': mid, 'receiver_organization_id': target['partner']['id'], 'logistics_partner_id': logistics_id, 'route_id': route['id'], 'quantity': 10, 'need_id': target['need_id']})
    tid = transfer['id']

    drivers = call(client, 'get', '/api/logistics/drivers', h_logistics)
    driver = next(x for x in drivers if x['vehicle_type'] == 'MINI TRUCK' and x['status'] == 'AVAILABLE')
    assigned = call(client, 'post', f'/api/transfers/{tid}/assign-driver', h_logistics, json={'driver_id': driver['id']})
    assert assigned['status'] == 'PICKUP_SCHEDULED'
    assert assigned['driver_id'] == driver['id']
    assert assigned['route_vehicle_type'] == driver['vehicle_type']
    selected_driver_email = next(email for email, code in [('driver@reloop.demo','DRV-1001'),('driver2@reloop.demo','DRV-1002'),('driver3@reloop.demo','DRV-1003'),('driver4@reloop.demo','DRV-1004')] if code == driver['driver_code'])
    h_selected_driver = login(client, selected_driver_email, 'DRIVER')
    notes = call(client, 'get', '/api/notifications?limit=30', h_selected_driver)
    assert any(n['transfer_id'] == tid and n['type'] == 'DRIVER_ASSIGNED' for n in notes)
    call(client, 'post', f'/api/transfers/{tid}/accept-assignment', h_selected_driver)
    call(client, 'post', f'/api/transfers/{tid}/start-trip', h_selected_driver)
    trip = call(client, 'get', f'/api/transfers/{tid}/tracking', h_receiver)
    assert trip['transfer']['status'] == 'IN_TRANSIT'
    arrived = call(client, 'post', f'/api/transfers/{tid}/simulate-location?progress=1', h_selected_driver)
    assert arrived['status'] == 'DELIVERED'
    receiver_notes = call(client, 'get', '/api/notifications?limit=30', h_receiver)
    org_notes = call(client, 'get', '/api/notifications?limit=30', h_org)
    assert any(n['transfer_id'] == tid and n['type'] == 'ARRIVAL' for n in receiver_notes)
    assert any(n['transfer_id'] == tid and n['type'] == 'ARRIVAL' for n in org_notes)

    call(client, 'post', f'/api/transfers/{tid}/confirm-receipt', h_receiver, json={'received_quantity': 9, 'received_condition': 'GOOD', 'notes': 'Nine units verified at handover.', 'receipt_photo_url': '/uploads/demo-after.txt'})
    transfer_after_receipt = call(client, 'get', '/api/transfers', h_org)
    current = next(x for x in transfer_after_receipt if x['id'] == tid)
    assert current['status'] == 'RECEIVED' and current['received_quantity'] == 9
    needs_after_receipt = call(client, 'get', '/api/needs', h_receiver)
    chair_need_after_receipt = next(x for x in needs_after_receipt if x['id'] == target['need_id'])
    assert chair_need_after_receipt['status'] == 'OPEN' and chair_need_after_receipt['remaining_quantity'] == 71
    assert current['outcome'] is None

    mismatch = client.post(f'/api/outcomes/transfer/{tid}/submit', headers=h_receiver, json={'pathway':'REUSE','claimed_quantity':8,'narrative':'This intentionally mismatches the physically received quantity to confirm the platform enforces full accounting before verification.','before_photo_url':'/uploads/demo-before.txt','after_photo_url':'/uploads/demo-after.txt'})
    assert mismatch.status_code == 422, mismatch.text

    call(client, 'post', f'/api/outcomes/transfer/{tid}/submit', h_receiver, json={'pathway':'REUSE','claimed_quantity':9,'narrative':'Nine chairs were cleaned, placed into active use in community classrooms, and photographed after deployment.','before_photo_url':'/uploads/demo-before.txt','after_photo_url':'/uploads/demo-after.txt'})
    pending = call(client, 'get', '/api/outcomes/pending', h_admin)
    outcome = next(x for x in pending if x['transfer_id'] == tid)
    assert outcome['evidence_status'] == 'SUBMITTED'

    # Rejection keeps transfer at RECEIVED and does not add impact.
    rejected = call(client, 'post', f"/api/outcomes/{outcome['id']}/review", h_admin, json={'decision':'REJECTED','reviewer_note':'Please provide a clearer deployment photo and location note.'})
    assert rejected['evidence_status'] == 'REJECTED'
    status_after_reject = call(client, 'get', '/api/transfers', h_receiver)
    assert next(x for x in status_after_reject if x['id']==tid)['status'] == 'RECEIVED'

    mismatch = client.post(f'/api/outcomes/transfer/{tid}/submit', headers=h_receiver, json={'pathway':'REUSE','claimed_quantity':8,'narrative':'This intentionally mismatches the physically received quantity to confirm the platform enforces full accounting before verification.','before_photo_url':'/uploads/demo-before.txt','after_photo_url':'/uploads/demo-after.txt'})
    assert mismatch.status_code == 422, mismatch.text

    call(client, 'post', f'/api/outcomes/transfer/{tid}/submit', h_receiver, json={'pathway':'REUSE','claimed_quantity':9,'narrative':'The nine chairs were deployed in active classrooms after cleaning and inspection; the submitted after photo documents the deployment.','before_photo_url':'/uploads/demo-before.txt','after_photo_url':'/uploads/demo-after.txt','outcome_document_url':'/uploads/demo-reuse-proof.txt'})
    pending = call(client, 'get', '/api/outcomes/pending', h_admin)
    outcome = next(x for x in pending if x['transfer_id'] == tid)
    verified = call(client, 'post', f"/api/outcomes/{outcome['id']}/review", h_admin, json={'decision':'VERIFIED','reviewer_note':'Evidence reviewed and accepted for the submitted circular outcome.'})
    assert verified['evidence_status'] == 'VERIFIED'

    completed = call(client, 'get', '/api/transfers', h_org)
    completed_t = next(x for x in completed if x['id'] == tid)
    assert completed_t['status'] == 'COMPLETED'
    source_matches_after_completion = call(client, 'get', f'/api/matching/material/{mid}', h_org)
    fulfilled_match = next(x for x in source_matches_after_completion if x['id'] == rid)
    assert fulfilled_match['status'] == 'FULFILLED'
    impact = call(client, 'get', '/api/impact/dashboard', h_org)
    assert impact['verified_transfers'] >= 2
    assert impact['verified_quantity'] >= 109

    # Recycler pathway and receipt restrictions.
    e_waste = next(x for x in materials if x['name'] == 'Mixed E-Waste')
    r_matches = call(client, 'get', f"/api/matching/material/{e_waste['id']}", h_org)
    recycler_match = next(x for x in r_matches if x['partner']['organization_type'] == 'Recycler')
    call(client, 'post', '/api/matching/request', h_org, json={'material_id': e_waste['id'], 'partner_organization_id': recycler_match['partner']['id'], 'need_id': recycler_match['need_id']})
    incoming_r = call(client, 'get', '/api/matching/incoming', h_recycler)
    r_req = next(x for x in incoming_r if x['partner']['id'] == recycler_match['partner']['id'] and x['material_id'] == e_waste['id'])
    call(client, 'patch', f"/api/matching/{r_req['id']}", h_recycler, json={'decision':'ACCEPTED'})

print('RELOOP V8 RELEASE TEST: PASS')
print('  Login: PASS')
print('  AI assessment: PASS')
print('  Matching + receiver acceptance: PASS')
print('  Transport + driver assignment: PASS')
print('  Driver notification + trip: PASS')
print('  GPS arrival + arrival notifications: PASS')
print('  Physical receipt + partial quantity: PASS')
print('  Outcome rejection + resubmission: PASS')
print('  Outcome verification + verified-only impact: PASS')
print('  Recycler workflow: PASS')
if TEST_DB.exists(): TEST_DB.unlink()
