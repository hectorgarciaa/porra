from pydantic import BaseModel, Field

from api.schemas.auth import UserResponse


class UpdateMeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


__all__ = ["UpdateMeRequest", "UserResponse"]
