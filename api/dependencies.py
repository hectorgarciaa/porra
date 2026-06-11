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
