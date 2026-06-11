from fastapi import APIRouter, Depends, File, UploadFile

from api.dependencies import get_bearer_token, get_current_user
from api.media import delete_local_media_file, save_user_avatar
from api.schemas.auth import UserResponse
from api.schemas.users import UpdateMeRequest
from database.info.users import updateUser
from database.types import RowDict

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UpdateMeRequest,
    token: str = Depends(get_bearer_token),
    current_user: RowDict = Depends(get_current_user),
) -> UserResponse:
    updated_user = updateUser(
        token=token,
        user_id=int(current_user["id"]),
        name=payload.name,
    )
    return UserResponse.model_validate(dict(updated_user))


@router.post("/me/avatar", response_model=UserResponse)
async def upload_my_avatar(
    image: UploadFile = File(...),
    token: str = Depends(get_bearer_token),
    current_user: RowDict = Depends(get_current_user),
) -> UserResponse:
    previous_img = current_user.get("img")
    image_url = await save_user_avatar(int(current_user["id"]), image)

    try:
        updated_user = updateUser(
            token=token,
            user_id=int(current_user["id"]),
            img=image_url,
        )
    except Exception:
        delete_local_media_file(image_url)
        raise

    if previous_img and previous_img != image_url:
        delete_local_media_file(str(previous_img))

    return UserResponse.model_validate(dict(updated_user))
