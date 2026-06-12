import hmac
import os

from fastapi import Depends, Header, HTTPException, status

from database.info.users import getUserByToken
from database.types import RowDict


def get_bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta la cabecera Authorization.",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization debe usar el formato 'Bearer <token>'.",
        )

    return token.strip()


def get_current_user(token: str = Depends(get_bearer_token)) -> RowDict:
    return getUserByToken(token)


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> str:
    expected_admin_token = os.getenv("ADMIN_PANEL_PASSWORD") or os.getenv("DEBUG_DB_TOKEN")
    if not expected_admin_token or not isinstance(x_admin_token, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Necesitas un token de admin valido.",
        )
    if not hmac.compare_digest(x_admin_token, expected_admin_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Necesitas un token de admin valido.",
        )
    return x_admin_token
