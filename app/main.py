from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .api.ai import router as ai_router
from .api.auth import router as auth_router
from .api.dashboard import router as dashboard_router
from .api.impact import router as impact_router
from .api.logistics import router as logistics_router
from .api.matching import needs_router, router as matching_router
from .api.materials import router as materials_router
from .api.notifications import router as notifications_router
from .api.organizations import router as organizations_router
from .api.outcomes import router as outcomes_router
from .api.reports import router as reports_router
from .api.routes import router as routes_router
from .api.transfers import router as transfers_router
from .core.config import settings
from .core.db import SessionLocal, engine, prepare_database
from .seed import seed_demo

app = FastAPI(title=settings.app_name, version=settings.version, description='Reloop: AI circular resource exchange, verified transport and circular outcome proof.')
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app.mount('/uploads', StaticFiles(directory=settings.upload_dir), name='uploads')
for router in [auth_router, organizations_router, dashboard_router, materials_router, ai_router, matching_router, needs_router, routes_router, logistics_router, transfers_router, notifications_router, outcomes_router, impact_router, reports_router]:
    app.include_router(router)


@app.on_event('startup')
def startup():
    prepare_database()
    db: Session = SessionLocal()
    try: seed_demo(db)
    finally: db.close()


@app.get('/')
def root(): return {'service': 'Reloop API', 'status': 'ok', 'version': settings.version, 'docs': '/docs'}


@app.get('/api/health')
def health():
    return {'status': 'healthy', 'service': 'reloop-api', 'tracking': 'browser_gps', 'arrival_radius_m': settings.arrival_radius_km * 1000, 'impact_policy': 'verified_outcomes_only'}


@app.get('/api/meta')
def meta():
    from .services.routing import VEHICLES
    return {'pathways':['REUSE','REFURBISH','RECYCLE','RECOVER'], 'vehicle_types':[{'name':k, **v} for k,v in VEHICLES.items()], 'arrival_radius_m': settings.arrival_radius_km * 1000, 'impact_policy':'Only platform-verified outcome evidence contributes to impact.'}
