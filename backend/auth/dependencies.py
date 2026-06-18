"""Authentication dependency — the single swap seam for auth.

`get_current_user` is the ONLY place that turns a request into a `User`. Today it
verifies a JWT we issued ourselves. To delegate login to an external IdP later
(e.g. Supabase Auth), change only how the token is verified here — every route and
every tenant-scoping check downstream stays identical.
"""

import logging

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from backend.auth.security import decode_access_token
from backend.database import get_session
from backend.models.user import User

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

_CREDENTIALS_ERROR = HTTPException(
    status_code=401,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> User:
    if credentials is None:
        raise _CREDENTIALS_ERROR
    try:
        user_id = decode_access_token(credentials.credentials)
    except (jwt.PyJWTError, ValueError, KeyError):
        raise _CREDENTIALS_ERROR from None

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise _CREDENTIALS_ERROR
    return user
