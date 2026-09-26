from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from .config import settings

PBKDF2_ITERATIONS = 210_000


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode((value + '=' * (-len(value) % 4)).encode('ascii'))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, PBKDF2_ITERATIONS)
    return f'pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64(salt)}${_b64(digest)}'


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored.split('$')
        if algorithm != 'pbkdf2_sha256':
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), _unb64(salt_b64), int(iterations))
        return hmac.compare_digest(actual, _unb64(digest_b64))
    except Exception:
        return False


def create_access_token(user_id: int, role: str) -> str:
    now = int(time.time())
    payload = {'sub': user_id, 'role': role, 'iat': now, 'exp': now + 60 * 60 * 12}
    body = _b64(json.dumps(payload, separators=(',', ':')).encode())
    signature = hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).digest()
    return f'{body}.{_b64(signature)}'


def decode_access_token(token: str) -> dict:
    body, signature = token.split('.', 1)
    expected = hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _unb64(signature)):
        raise ValueError('Invalid token signature')
    payload = json.loads(_unb64(body).decode())
    if int(payload.get('exp', 0)) < int(time.time()):
        raise ValueError('Token expired')
    return payload
