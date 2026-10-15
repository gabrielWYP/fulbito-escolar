"""Seguridad: sesión firmada, CSRF, rate limiting y comparación constante."""
from __future__ import annotations

import hmac
import logging
import os
import secrets
import time

from itsdangerous import BadSignature, URLSafeTimedSerializer

log = logging.getLogger("fulbito.security")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or ""
SESSION_SECRET = os.environ.get("SESSION_SECRET") or secrets.token_urlsafe(32)
SESSION_COOKIE = "fulbito_session"
CSRF_COOKIE = "fulbito_csrf"
SESSION_MAX_AGE = 60 * 60 * 8  # 8 horas

if not os.environ.get("SESSION_SECRET"):
    log.warning(
        "SESSION_SECRET no definido: secreto efímero (las sesiones no persisten entre reinicios)."
    )

ADMIN_ENABLED = bool(ADMIN_PASSWORD)
if not ADMIN_ENABLED:
    log.warning("ADMIN_PASSWORD no definido: el panel de administración está DESHABILITADO.")

_serializer = URLSafeTimedSerializer(SESSION_SECRET, salt="fulbito-session")

# Rate limiting en memoria para login: ip -> [timestamps]
_login_attempts: dict[str, list[float]] = {}
_LOGIN_WINDOW = 300.0   # 5 min
_LOGIN_MAX = 5          # intentos por ventana


def verify_password(candidate: str) -> bool:
    """Comparación en tiempo constante contra ADMIN_PASSWORD."""
    if not ADMIN_ENABLED:
        return False
    return hmac.compare_digest(candidate.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))


def make_session() -> str:
    return _serializer.dumps({"admin": True})


def valid_session(token: str | None) -> bool:
    if not token:
        return False
    try:
        data = _serializer.loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return False
    except Exception:
        return False
    return bool(isinstance(data, dict) and data.get("admin"))


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_ok(cookie_token: str | None, form_token: str | None) -> bool:
    if not cookie_token or not form_token:
        return False
    return hmac.compare_digest(cookie_token, form_token)


def rate_limited(ip: str) -> bool:
    now = time.time()
    attempts = [t for t in _login_attempts.get(ip, []) if now - t < _LOGIN_WINDOW]
    _login_attempts[ip] = attempts
    return len(attempts) >= _LOGIN_MAX


def record_attempt(ip: str) -> None:
    _login_attempts.setdefault(ip, []).append(time.time())


def reset_attempts(ip: str) -> None:
    _login_attempts.pop(ip, None)
