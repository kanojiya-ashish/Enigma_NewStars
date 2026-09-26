from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

VEHICLES = {
    'BIKE': {'capacity': 20, 'speed': 30, 'emission': 0.08},
    'EV VAN': {'capacity': 80, 'speed': 42, 'emission': 0.06},
    'MINI TRUCK': {'capacity': 250, 'speed': 38, 'emission': 0.32},
    'TRUCK': {'capacity': 800, 'speed': 35, 'emission': 0.68},
}


def normalize_vehicle(value: str) -> str:
    return value.strip().upper().replace('_', ' ')


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(max(0.0, min(1.0, a))))


def calculate_route_values(material, partner, vehicle_type: str, quantity: float) -> dict:
    vehicle = normalize_vehicle(vehicle_type)
    spec = VEHICLES.get(vehicle)
    if not spec:
        raise ValueError('Unsupported vehicle type')
    distance = haversine_km(material.latitude, material.longitude, partner.latitude, partner.longitude)
    distance = max(0.2, distance * 1.12)
    time_min = max(8.0, distance / spec['speed'] * 60 + 10)
    co2 = distance * spec['emission']
    capacity = float(spec['capacity'])
    capacity_util = min(1.0, quantity / capacity)
    route_score = max(0.0, min(100.0, 92 - min(distance * 0.75, 40) - time_min * 0.12 - capacity_util * 12 + (8 if vehicle == 'EV VAN' else 0)))
    return {
        'source_lat': material.latitude,
        'source_lng': material.longitude,
        'destination_lat': partner.latitude,
        'destination_lng': partner.longitude,
        'vehicle_type': vehicle,
        'distance_km': round(distance, 2),
        'estimated_time_min': round(time_min, 1),
        'estimated_co2_kg': round(co2, 2),
        'route_score': round(route_score, 1),
        'emission_factor_kg_per_km': spec['emission'],
        'capacity_units': capacity,
    }
