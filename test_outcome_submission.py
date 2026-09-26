import os, tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

DB = Path(tempfile.gettempdir()) / 'reloop_v8_4_2_outcome_upload_test.sqlite'
if DB.exists(): DB.unlink()
os.environ['RELOOP_DATABASE_URL'] = f'sqlite:///{DB}'
os.environ['RELOOP_CORS_ORIGINS'] = 'http://localhost:5173'

from fastapi.testclient import TestClient
from backend.app.main import app

PNG = b'\x89PNG\r\n\x1a\n' + b'0' * 64

def login(client, email, role):
    r = client.post('/api/auth/login', json={'email': email, 'password': 'demo123', 'role': role})
    assert r.status_code == 200, r.text
    return {'Authorization': f"Bearer {r.json()['access_token']}"}

with TestClient(app) as client:
    org = login(client, 'org@reloop.demo', 'ORGANIZATION')
    receiver = login(client, 'receiver@reloop.demo', 'RECEIVER')
    logistics = login(client, 'logistics@reloop.demo', 'LOGISTICS')
    driver = login(client, 'driver@reloop.demo', 'DRIVER')

    material = next(m for m in client.get('/api/materials', headers=org).json() if m['name'] == 'Office Chairs')
    target = next(m for m in client.get(f"/api/matching/material/{material['id']}", headers=org).json() if m['partner']['organization_type'] == 'NGO')
    match = client.post('/api/matching/request', headers=org, json={'material_id': material['id'], 'partner_organization_id': target['partner']['id'], 'need_id': target['need_id']})
    assert match.status_code == 200, match.text
    mid = match.json()['id']
    accepted = client.patch(f'/api/matching/{mid}', headers=receiver, json={'decision': 'ACCEPTED'})
    assert accepted.status_code == 200, accepted.text

    route = client.get(f"/api/routes/options/{material['id']}/{target['partner']['id']}?quantity=5", headers=org).json()[0]
    logistics_org = client.get('/api/organizations?kind=LOGISTICS', headers=org).json()[0]
    transfer = client.post('/api/transfers', headers=org, json={'material_id': material['id'], 'receiver_organization_id': target['partner']['id'], 'logistics_partner_id': logistics_org['id'], 'route_id': route['id'], 'quantity': 5, 'need_id': target['need_id']})
    assert transfer.status_code == 200, transfer.text
    tid = transfer.json()['id']
    driver_row = next(d for d in client.get('/api/logistics/drivers', headers=logistics).json() if d['driver_code'] == 'DRV-1001')
    assert client.post(f'/api/transfers/{tid}/assign-driver', headers=logistics, json={'driver_id': driver_row['id']}).status_code == 200
    assert client.post(f'/api/transfers/{tid}/accept-assignment', headers=driver).status_code == 200
    assert client.post(f'/api/transfers/{tid}/start-trip', headers=driver).status_code == 200
    arrived = client.post(f'/api/transfers/{tid}/simulate-location?progress=1', headers=driver)
    assert arrived.status_code == 200 and arrived.json()['status'] == 'DELIVERED', arrived.text
    received = client.post(f'/api/transfers/{tid}/confirm-receipt', headers=receiver, json={'received_quantity': 5, 'received_condition': 'GOOD', 'notes': 'All five units physically received.'})
    assert received.status_code == 200, received.text

    upload = client.post('/api/materials/uploads', headers=receiver, files={'file': ('after.png', PNG, 'image/png')})
    assert upload.status_code == 200, upload.text
    outcome = client.post(f'/api/outcomes/transfer/{tid}/submit', headers=receiver, json={'pathway':'REUSE','claimed_quantity':5,'narrative':'Five chairs were cleaned, placed into active classroom use, and documented after deployment.','after_photo_url':upload.json()['url']})
    assert outcome.status_code == 200, outcome.text
    assert outcome.json()['evidence_status'] == 'SUBMITTED'

print('REAL EVIDENCE UPLOAD + OUTCOME SUBMISSION: PASS')
if DB.exists(): DB.unlink()
