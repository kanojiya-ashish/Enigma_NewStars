from __future__ import annotations

from fastapi import HTTPException

MATCH_TRANSITIONS: dict[str, set[str]] = {
    'RECOMMENDED': {'REQUESTED', 'CANCELLED'},
    'REQUESTED': {'ACCEPTED', 'REJECTED', 'CANCELLED'},
    'ACCEPTED': {'FULFILLED', 'CANCELLED'},
    'FULFILLED': {'REQUESTED'},
    'REJECTED': {'REQUESTED'},
    'CANCELLED': {'REQUESTED'},
}

TRANSFER_TRANSITIONS: dict[str, set[str]] = {
    'REQUESTED': {'PICKUP_SCHEDULED', 'CANCELLED'},
    'PICKUP_SCHEDULED': {'IN_TRANSIT', 'CANCELLED'},
    'IN_TRANSIT': {'DELIVERED'},
    'DELIVERED': {'RECEIVED'},
    'RECEIVED': {'COMPLETED'},
    'COMPLETED': set(),
    'CANCELLED': set(),
}

OUTCOME_TRANSITIONS: dict[str, set[str]] = {
    'NOT_STARTED': {'SUBMITTED'},
    'SUBMITTED': {'UNDER_REVIEW'},
    'UNDER_REVIEW': {'VERIFIED', 'CORRECTION_REQUESTED', 'REJECTED'},
    'CORRECTION_REQUESTED': {'SUBMITTED'},
    'REJECTED': {'SUBMITTED'},
    'VERIFIED': set(),
}


def transition(current: str, next_status: str, transitions: dict[str, set[str]], entity: str) -> None:
    if next_status not in transitions.get(current, set()):
        raise HTTPException(409, f'Invalid {entity} transition: {current} → {next_status}')
