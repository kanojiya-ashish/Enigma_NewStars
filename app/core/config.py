from __future__ import annotations

import os
from dataclasses import dataclass


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(',') if item.strip())


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv('APP_NAME', 'Reloop API')
    version: str = '8.5.1'
    database_url: str = os.getenv('RELOOP_DATABASE_URL') or os.getenv('DATABASE_URL', 'sqlite:///./reloop.db')
    secret_key: str = os.getenv('SECRET_KEY', 'reloop-local-demo-secret-change-in-production')
    cors_origins: tuple[str, ...] = _csv(os.getenv('RELOOP_CORS_ORIGINS') or os.getenv('CORS_ORIGINS') or 'http://localhost:5173,http://127.0.0.1:5173')
    upload_dir: str = os.getenv('UPLOAD_DIR', 'uploads')
    arrival_radius_km: float = float(os.getenv('ARRIVAL_RADIUS_KM', '0.25'))
    tracking_interval_seconds: int = int(os.getenv('TRACKING_INTERVAL_SECONDS', '3'))


settings = Settings()
