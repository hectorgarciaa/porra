import hmac
import os

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_current_user
from api.schemas.auth import (
    AdminUnlockRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserResponse,
)
from database.info.users import createUser, login
from database.types import RowDict


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest) -> UserResponse:
    user = createUser(name=payload.name, password=payload.password)
    return UserResponse.model_validate(dict(user))


@router.post("/login", response_model=LoginResponse)
def login_user(payload: LoginRequest) -> LoginResponse:
    session = login(name=payload.name, password=payload.password)
    return LoginResponse.model_validate(
        {"token": session["token"], "user": dict(session["user"])}
    )


@router.post("/admin/unlock", status_code=status.HTTP_200_OK)
def unlock_admin(payload: AdminUnlockRequest) -> dict[str, bool]:
    expected_password = os.getenv("ADMIN_PANEL_PASSWORD") or os.getenv("DEBUG_DB_TOKEN")
    if not expected_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El acceso admin no esta configurado en el entorno.",
        )
    if not hmac.compare_digest(payload.password, expected_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contrasena de admin incorrecta.",
        )
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: RowDict = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(dict(current_user))
