import os, tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

DB = Path(tempfile.gettempdir()) / 'reloop_v85_verification_test.sqlite'
if DB.exists(): DB.unlink()
os.environ['RELOOP_DATABASE_URL'] = f'sqlite:///{DB}'
os.environ['UPLOAD_DIR'] = str(Path(tempfile.gettempdir()) / 'reloop_v85_uploads')
os.environ['SECRET_KEY'] = 'test-secret-v85'
os.environ['RELOOP_CORS_ORIGINS'] = 'http://localhost:5173'

from fastapi.testclient import TestClient
from backend.app.main import app


def login(client, email, role):
    r = client.post('/api/auth/login', json={'email': email, 'password': 'demo123', 'role': role})
    assert r.status_code == 200, r.text
    return {'Authorization': f"Bearer {r.json()['access_token']}"}

with TestClient(app) as client:
    org = login(client, 'org@reloop.demo', 'ORGANIZATION')
    receiver = login(client, 'receiver@reloop.demo', 'RECEIVER')
    logistics = login(client, 'logistics@reloop.demo', 'LOGISTICS')
    driver = login(client, 'driver@reloop.demo', 'DRIVER')
    admin = login(client, 'admin@reloop.demo', 'ADMIN')

    material = next(m for m in client.get('/api/materials', headers=org).json() if m['name'] == 'Office Chairs')
    match = next(m for m in client.get(f"/api/matching/material/{material['id']}", headers=org).json() if m['partner']['organization_type'] == 'NGO' and m.get('need_id'))
    r = client.post('/api/matching/request', headers=org, json={'material_id': material['id'], 'partner_organization_id': match['partner']['id'], 'need_id': match['need_id']}); assert r.status_code == 200, r.text
    mid = r.json()['id']
    assert client.patch(f'/api/matching/{mid}', headers=receiver, json={'decision': 'ACCEPTED'}).status_code == 200
    route = client.get(f"/api/routes/options/{material['id']}/{match['partner']['id']}?quantity=5", headers=org).json()[0]
    logi = client.get('/api/organizations?kind=LOGISTICS', headers=org).json()[0]
    r = client.post('/api/transfers', headers=org, json={'material_id': material['id'], 'receiver_organization_id': match['partner']['id'], 'logistics_partner_id': logi['id'], 'route_id': route['id'], 'quantity': 5, 'need_id': match['need_id']}); assert r.status_code == 200, r.text
    tid = r.json()['id']
    drv = next(d for d in client.get('/api/logistics/drivers', headers=logistics).json() if d['driver_code'] == 'DRV-1001')
    assert client.post(f'/api/transfers/{tid}/assign-driver', headers=logistics, json={'driver_id': drv['id']}).status_code == 200
    assert client.post(f'/api/transfers/{tid}/accept-assignment', headers=driver).status_code == 200
    assert client.post(f'/api/transfers/{tid}/start-trip', headers=driver).status_code == 200
    assert client.post(f'/api/transfers/{tid}/simulate-location?progress=1', headers=driver).status_code == 200
    assert client.post(f'/api/transfers/{tid}/confirm-receipt', headers=receiver, json={'received_quantity': 5, 'received_condition': 'GOOD', 'notes': 'Received all units.'}).status_code == 200

    upload = client.post('/api/materials/uploads', headers=receiver, files={'file': ('after.png', b'PNGDATA', 'image/png')})
    assert upload.status_code == 200, upload.text
    payload = {'pathway': 'REUSE', 'claimed_quantity': 5, 'narrative': 'The five chairs were cleaned and placed into active classroom use for daily teaching.', 'after_photo_url': upload.json()['url']}
    r = client.post(f'/api/outcomes/transfer/{tid}/submit', headers=receiver, json=payload); assert r.status_code == 200, r.text
    oid = r.json()['id']
    pending = client.get('/api/outcomes/pending', headers=admin); assert pending.status_code == 200 and any(x['id'] == oid for x in pending.json())

    # Ask for correction; it must return to the receiver without closing the transfer.
    r = client.post(f'/api/outcomes/{oid}/review', headers=admin, json={'decision': 'CORRECTION_REQUESTED', 'reviewer_note': 'Please add a clearer deployment note describing where the five chairs are being used.'})
    assert r.status_code == 200, r.text
    assert r.json()['evidence_status'] == 'CORRECTION_REQUESTED'
    t = next(x for x in client.get('/api/transfers', headers=receiver).json() if x['id'] == tid)
    assert t['status'] == 'RECEIVED', t

    # Resubmit after correction; Admin verifies and only then is the transfer completed.
    payload['narrative'] = 'All five chairs were cleaned, assigned to classrooms B101 through B105, and placed into active teaching use on the deployment date.'
    r = client.post(f'/api/outcomes/transfer/{tid}/submit', headers=receiver, json=payload); assert r.status_code == 200, r.text
    assert r.json()['evidence_status'] == 'SUBMITTED'
    oid = r.json()['id']
    r = client.post(f'/api/outcomes/{oid}/review', headers=admin, json={'decision': 'VERIFIED', 'reviewer_note': 'Evidence reviewed and accepted.'})
    assert r.status_code == 200, r.text
    assert r.json()['evidence_status'] == 'VERIFIED'
    t = next(x for x in client.get('/api/transfers', headers=receiver).json() if x['id'] == tid)
    assert t['status'] == 'COMPLETED', t
    impact = client.get('/api/impact/dashboard', headers=admin); assert impact.status_code == 200 and impact.json()['verified_transfers'] >= 1
    print('FINAL CIRCULAR OUTCOME VERIFICATION WORKFLOW: PASS')

if DB.exists(): DB.unlink()
