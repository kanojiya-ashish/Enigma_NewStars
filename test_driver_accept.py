import os, tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

td = tempfile.TemporaryDirectory()
os.environ['RELOOP_DATABASE_URL'] = f'sqlite:///{Path(td.name)/"test.db"}'
os.environ['UPLOAD_DIR'] = str(Path(td.name)/'uploads')
os.environ['SECRET_KEY'] = 'test-secret'
os.environ['RELOOP_CORS_ORIGINS'] = 'http://localhost:5173'

from fastapi.testclient import TestClient
from backend.app.main import app

client = None


def login(email, password='demo123'):
    r = client.post('/api/auth/login', json={'email':email,'password':password})
    assert r.status_code == 200, (email, r.status_code, r.text)
    return r.json()['access_token']

with TestClient(app) as client:
    org = login('org@reloop.demo')
    recv = login('receiver@reloop.demo')
    logi = login('logistics@reloop.demo')
    driver = login('driver@reloop.demo')

    # Create a fresh organization -> receiver request using an existing generated match.
    materials = client.get('/api/materials', headers={'Authorization':f'Bearer {org}'}).json()
    chairs = next(m for m in materials if m['name']=='Office Chairs')
    matches = client.get(f"/api/matching/material/{chairs['id']}", headers={'Authorization':f'Bearer {org}'}).json()
    receiver_match = next(m for m in matches if m['partner']['id'] == 2 and m.get('need_id'))
    r = client.post('/api/matching/request', headers={'Authorization':f'Bearer {org}'}, json={'material_id':chairs['id'],'partner_organization_id':receiver_match['partner']['id'],'need_id':receiver_match['need_id']})
    assert r.status_code == 200, r.text
    match = r.json()
    r = client.patch(f"/api/matching/{match['id']}", headers={'Authorization':f'Bearer {recv}'}, json={'decision':'ACCEPTED'})
    assert r.status_code == 200, r.text
    incoming = client.get('/api/matching/incoming', headers={'Authorization':f'Bearer {recv}'}).json()
    assert any(m['id']==match['id'] and m['status']=='ACCEPTED' for m in incoming), incoming

    # Create transport using a route option and logistics partner.
    materials = client.get('/api/materials', headers={'Authorization':f'Bearer {org}'}).json()
    chairs = next(m for m in materials if m['name']=='Office Chairs')
    opts = client.get(f"/api/routes/options/{chairs['id']}/{match['partner']['id']}?quantity=20", headers={'Authorization':f'Bearer {org}'})
    assert opts.status_code == 200, opts.text
    route = opts.json()[0]
    logistics_org = client.get('/api/organizations?kind=LOGISTICS', headers={'Authorization':f'Bearer {org}'}).json()[0]
    tr = client.post('/api/transfers', headers={'Authorization':f'Bearer {org}'}, json={
        'material_id': chairs['id'],
        'receiver_organization_id': incoming[0]['partner']['id'],
        'logistics_partner_id': logistics_org['id'],
        'route_id': route['id'],
        'quantity': 20,
        'need_id': match['need_id'],
    })
    assert tr.status_code == 200, tr.text
    transfer_id = tr.json()['id']

    # Logistics assigns an available driver.
    drivers = client.get('/api/logistics/drivers', headers={'Authorization':f'Bearer {logi}'}).json()
    eligible = [d for d in drivers if d['status']=='AVAILABLE']
    assert eligible, drivers
    drv = eligible[0]
    r = client.post(f'/api/transfers/{transfer_id}/assign-driver', headers={'Authorization':f'Bearer {logi}'}, json={'driver_id':drv['id']})
    assert r.status_code == 200, r.text
    assigned = r.json()
    assert assigned['status']=='PICKUP_SCHEDULED'
    assert assigned['driver_accepted_at'] is None

    # Driver sees assignment notification containing transfer id.
    notes = client.get('/api/notifications?limit=50', headers={'Authorization':f'Bearer {driver}'}).json()
    assert any(n['transfer_id']==transfer_id and n['type']=='DRIVER_ASSIGNED' for n in notes), notes

    # Driver opens notification target and accepts ride.
    r = client.post(f'/api/transfers/{transfer_id}/accept-assignment', headers={'Authorization':f'Bearer {driver}'})
    assert r.status_code == 200, r.text
    accepted = r.json()
    assert accepted['driver_accepted_at'] is not None

    # Driver can now start trip.
    r = client.post(f'/api/transfers/{transfer_id}/start-trip', headers={'Authorization':f'Bearer {driver}'})
    assert r.status_code == 200, r.text
    started = r.json()
    assert started['status']=='IN_TRANSIT'

    print('DRIVER_ACCEPTANCE_FLOW: PASS')
    print('transfer', transfer_id, 'driver', drv['driver_code'])
