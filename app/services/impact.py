from __future__ import annotations

CATEGORY_MASS = {'furniture': 8.0, 'electronics': 6.0, 'plastic': 0.4, 'paper': 0.2, 'metal': 5.0, 'textiles': 0.8}
UNIT_MASS = {'kg': 1.0, 'tonnes': 1000.0, 'tons': 1000.0, 'units': 1.0, 'boxes': 0.5, 'litres': 0.8}
PATHWAY_VALUE = {'REUSE': 1.00, 'REFURBISH': 0.78, 'RECYCLE': 0.46, 'RECOVER': 0.22}
PATHWAY_WASTE = {'REUSE': 1.00, 'REFURBISH': 0.85, 'RECYCLE': 0.72, 'RECOVER': 0.55}
PATHWAY_CO2 = {'REUSE': 1.80, 'REFURBISH': 1.25, 'RECYCLE': 0.72, 'RECOVER': 0.42}


def create_verified_impact(material, transfer, route, pathway: str, verified_quantity: float):
    mass_factor = UNIT_MASS.get(material.unit.lower(), CATEGORY_MASS.get(material.category.lower(), 1.0))
    mass = verified_quantity * mass_factor
    source_value = material.estimated_value * (verified_quantity / max(material.quantity, 1))
    value = source_value * PATHWAY_VALUE[pathway]
    waste = mass * PATHWAY_WASTE[pathway]
    transport = route.estimated_co2_kg if route else 0.0
    avoided = max(0.0, mass * PATHWAY_CO2[pathway] - transport)
    return round(value, 2), round(waste, 2), round(avoided, 2)
