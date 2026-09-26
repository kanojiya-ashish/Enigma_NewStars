from __future__ import annotations

from dataclasses import dataclass

CONDITION_SCORE = {'EXCELLENT': 96, 'GOOD': 84, 'FAIR': 66, 'POOR': 38}


@dataclass
class AssessmentResult:
    condition_score: float
    recommendation: str
    confidence: float
    scores: dict[str, float]
    reasons: list[str]
    factor_breakdown: dict[str, float]


def assess_material(material) -> AssessmentResult:
    condition = CONDITION_SCORE.get(material.condition.upper(), 60)
    age_penalty = min(18, material.age_years * 3.5)
    base = max(0, condition - age_penalty)
    category = material.category.lower()

    reuse = base + (7 if category in {'furniture', 'paper', 'textiles'} else 3)
    refurbish = base - 5 + (10 if material.condition in {'FAIR', 'POOR'} else 3)
    recycle = 48 + (14 if category in {'electronics', 'metal', 'plastic', 'paper'} else 2) + (10 if material.condition == 'POOR' else 0)
    recover = 35 + (18 if category in {'electronics', 'metal'} else 5)

    scores = {k: round(max(0, min(100, v)), 1) for k, v in {'REUSE': reuse, 'REFURBISH': refurbish, 'RECYCLE': recycle, 'RECOVER': recover}.items()}
    recommendation = max(scores, key=scores.get)
    sorted_scores = sorted(scores.values(), reverse=True)
    confidence = max(0.55, min(0.98, 0.62 + (sorted_scores[0] - sorted_scores[1]) / 100))
    reasons = [
        f'Condition score is {condition}/100 based on the declared condition.',
        f'Age contribution is {material.age_years:.1f} years; the model applies a bounded age penalty.',
        f'{category.title()} has pathway-specific circular value assumptions.',
        f'{recommendation.title()} has the highest explainable pathway score for this material profile.',
    ]
    factors = {'Condition': 35, 'Age': 15, 'Category suitability': 25, 'Circular value': 25}
    return AssessmentResult(round(base, 1), recommendation, round(confidence, 2), scores, reasons, factors)
