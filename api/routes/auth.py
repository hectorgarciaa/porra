from fastapi import APIRouter, Depends, status

from api.dependencies import get_current_user
from api.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, UserResponse
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


@router.get("/me", response_model=UserResponse)
def get_me(current_user: RowDict = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(dict(current_user))
