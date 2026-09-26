from __future__ import annotations
import os, tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

DB = Path(tempfile.gettempdir()) / 'reloop_v8_security_test.sqlite'
if DB.exists(): DB.unlink()
os.environ['RELOOP_DATABASE_URL'] = f'sqlite:///{DB}'
os.environ['RELOOP_CORS_ORIGINS'] = 'http://localhost:5173'

from fastapi.testclient import TestClient
from backend.app.main import app


def login(c, email, role):
    r = c.post('/api/auth/login', json={'email': email, 'password': 'demo123', 'role': role})
    assert r.status_code == 200, (email, r.status_code, r.text)
    return {'Authorization': f"Bearer {r.json()['access_token']}"}


def expect(c, method, path, headers, code, **kw):
    r = getattr(c, method)(path, headers=headers, **kw)
    assert r.status_code == code, (path, r.status_code, r.text)
    return r

with TestClient(app) as c:
    org = login(c, 'org@reloop.demo', 'ORGANIZATION')
    receiver = login(c, 'receiver@reloop.demo', 'RECEIVER')
    logistics = login(c, 'logistics@reloop.demo', 'LOGISTICS')
    driver = login(c, 'driver2@reloop.demo', 'DRIVER')

    materials = c.get('/api/materials', headers=org).json()
    chair = next(m for m in materials if m['name'] == 'Office Chairs')
    matches = c.get(f"/api/matching/material/{chair['id']}", headers=org).json()
    target = next(m for m in matches if m['partner']['organization_type'] == 'NGO')
    match = c.post('/api/matching/request', headers=org, json={'material_id': chair['id'], 'partner_organization_id': target['partner']['id'], 'need_id': target['need_id']}).json()
    mid = match['id']

    # Organization cannot bypass the receiver acceptance step.
    expect(c, 'patch', f'/api/matching/{mid}', org, 403, json={'decision': 'ACCEPTED'})
    # Receiver can accept it.
    expect(c, 'patch', f'/api/matching/{mid}', receiver, 200, json={'decision': 'ACCEPTED'})

    routes = c.get(f"/api/routes/options/{chair['id']}/{target['partner']['id']}?quantity=5", headers=org).json()
    logistics_org = c.get('/api/organizations?kind=LOGISTICS', headers=org).json()[0]
    transfer = c.post('/api/transfers', headers=org, json={'material_id': chair['id'], 'receiver_organization_id': target['partner']['id'], 'logistics_partner_id': logistics_org['id'], 'route_id': routes[0]['id'], 'quantity': 5, 'need_id': target['need_id']}).json()
    tid = transfer['id']

    # Receiver cannot assign driver; only logistics can.
    driver_rows = c.get('/api/logistics/drivers', headers=logistics).json()
    driver_row = next(d for d in driver_rows if d['status'] == 'AVAILABLE' and d['vehicle_type'] == transfer['route_vehicle_type'])
    expect(c, 'post', f'/api/transfers/{tid}/assign-driver', receiver, 403, json={'driver_id': driver_row['id']})
    expect(c, 'post', f'/api/transfers/{tid}/assign-driver', logistics, 200, json={'driver_id': driver_row['id']})

    # Unrelated driver cannot start another driver's trip.
    other = login(c, 'driver@reloop.demo', 'DRIVER')
    expect(c, 'post', f'/api/transfers/{tid}/start-trip', other, 403)

    # Original driver must accept the assignment before starting the trip.
    expect(c, 'post', f'/api/transfers/{tid}/accept-assignment', driver, 200)
    expect(c, 'post', f'/api/transfers/{tid}/start-trip', driver, 200)
    expect(c, 'post', f'/api/transfers/{tid}/simulate-location?progress=0.5', driver, 200)
    track = expect(c, 'get', f'/api/transfers/{tid}/tracking', receiver, 200).json()
    assert track['latest_location'] is not None

    # Cancel is blocked after trip start.
    expect(c, 'post', f'/api/transfers/{tid}/cancel', org, 409)

    # Need status remains MATCHED during an active transfer.
    needs = c.get('/api/needs', headers=receiver).json()
    chair_need = next(n for n in needs if n['id'] == target['need_id'])
    assert chair_need['status'] == 'MATCHED'

print('RELOOP V8 SECURITY/ACCESS TEST: PASS')
if DB.exists(): DB.unlink()
