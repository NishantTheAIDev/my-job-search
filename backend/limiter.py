"""Shared rate limiter instance — imported by app.py and routers.

Rate limits are keyed by authenticated user when a valid bearer token is present,
so one user can't exhaust another's budget (and many users behind one NAT/IP are
not throttled as a group). Unauthenticated requests (e.g. /auth/login, /auth/register)
fall back to the client IP, which is what brute-force protection needs anyway.
"""

import jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from backend.auth.security import decode_access_token


def _user_or_ip_key(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            return f"user:{decode_access_token(auth[7:])}"
        except jwt.PyJWTError, ValueError, KeyError:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=_user_or_ip_key)
