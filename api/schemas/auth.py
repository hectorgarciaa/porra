from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=255)


class AdminUnlockRequest(BaseModel):
    password: str = Field(min_length=1, max_length=255)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    img: str | None
    created_at: str
    updated_at: str


class LoginResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    token: str
    user: UserResponse
