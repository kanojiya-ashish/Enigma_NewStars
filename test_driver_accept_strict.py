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


def run():
  with TestClient(app) as client:
    def login(email):
      r=client.post('/api/auth/login',json={'email':email,'password':'demo123'}); assert r.status_code==200,r.text; return r.json()['access_token']
    org, recv, logi = (login(x) for x in ['org@reloop.demo','receiver@reloop.demo','logistics@reloop.demo'])
    d1, d2 = login('driver@reloop.demo'), login('driver2@reloop.demo')
    ah={'Authorization':f'Bearer {org}'}; rh={'Authorization':f'Bearer {recv}'}; lh={'Authorization':f'Bearer {logi}'}; dh1={'Authorization':f'Bearer {d1}'}; dh2={'Authorization':f'Bearer {d2}'}
    mats=client.get('/api/materials',headers=ah).json(); m=next(x for x in mats if x['name']=='Office Chairs')
    matches=client.get(f"/api/matching/material/{m['id']}",headers=ah).json(); cm=next(x for x in matches if x['partner']['id']==2 and x.get('need_id'))
    r=client.post('/api/matching/request',headers=ah,json={'material_id':m['id'],'partner_organization_id':cm['partner']['id'],'need_id':cm['need_id']}); assert r.status_code==200,r.text; match=r.json()
    r=client.patch(f"/api/matching/{match['id']}",headers=rh,json={'decision':'ACCEPTED'}); assert r.status_code==200,r.text
    opts=client.get(f"/api/routes/options/{m['id']}/{cm['partner']['id']}?quantity=20",headers=ah); assert opts.status_code==200,opts.text; route=opts.json()[0]
    logorg=client.get('/api/organizations?kind=LOGISTICS',headers=ah).json()[0]
    tr=client.post('/api/transfers',headers=ah,json={'material_id':m['id'],'receiver_organization_id':cm['partner']['id'],'logistics_partner_id':logorg['id'],'route_id':route['id'],'quantity':20,'need_id':match['need_id']}); assert tr.status_code==200,tr.text; tid=tr.json()['id']
    drivers=client.get('/api/logistics/drivers',headers=lh).json(); drv=next(d for d in drivers if d['driver_code']=='DRV-1001')
    r=client.post(f'/api/transfers/{tid}/assign-driver',headers=lh,json={'driver_id':drv['id']}); assert r.status_code==200,r.text
    assigned=r.json(); assert assigned['status']=='PICKUP_SCHEDULED'; assert assigned['driver_accepted_at'] is None
    # Before acceptance, start is blocked.
    r=client.post(f'/api/transfers/{tid}/start-trip',headers=dh1); assert r.status_code==409,r.text
    # Wrong driver cannot accept the assignment.
    r=client.post(f'/api/transfers/{tid}/accept-assignment',headers=dh2); assert r.status_code==403,r.text
    notes=client.get('/api/notifications?limit=50',headers=dh1).json(); assert any(n['transfer_id']==tid and n['type']=='DRIVER_ASSIGNED' for n in notes),notes
    # Assigned driver accepts.
    r=client.post(f'/api/transfers/{tid}/accept-assignment',headers=dh1); assert r.status_code==200,r.text; accepted=r.json(); assert accepted['driver_accepted_at']
    # Idempotent second accept.
    r=client.post(f'/api/transfers/{tid}/accept-assignment',headers=dh1); assert r.status_code==200,r.text
    # Start now works.
    r=client.post(f'/api/transfers/{tid}/start-trip',headers=dh1); assert r.status_code==200,r.text; assert r.json()['status']=='IN_TRANSIT'
    # Org, receiver and logistics get acceptance notification.
    for h in (ah,rh,lh):
      ns=client.get('/api/notifications?limit=100',headers=h).json(); assert any(n['transfer_id']==tid and n['type']=='DRIVER_ACCEPTED' for n in ns), ns
    print('DRIVER_ACCEPTANCE_STRICT_FLOW: PASS')

if __name__=='__main__': run()
