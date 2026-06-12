from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from api.dependencies import get_current_user
from api import media as media_module
from database.info.chat import get_messages, send_message
from database.types import JsonDict, JsonList, RowDict
from secrets import token_hex

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/messages")
def list_messages(since: int = 0) -> JsonList:
    return get_messages(since_id=since)


@router.post("/messages")
def post_message(
    text: str = Form(default=""),
    current_user: RowDict = Depends(get_current_user),
) -> JsonDict:
    msg = send_message(user_id=int(current_user["id"]), text=text.strip() if text.strip() else None)
    return {"message": msg}


@router.post("/messages/image")
async def post_image(
    image: UploadFile = File(...),
    text: str = Form(default=""),
    current_user: RowDict = Depends(get_current_user),
) -> JsonDict:
    media_module.ensure_media_dirs()

    content_type = (image.content_type or "").lower().strip()
    if content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La imagen debe ser JPG, PNG o WEBP.",
        )

    content = await image.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La imagen no puede estar vacia.",
        )
    if len(content) > media_module.MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La imagen supera el maximo de 5 MB.",
        )

    ext = ".jpg" if "jpeg" in content_type else ".png" if "png" in content_type else ".webp"
    filename = f"chat_{token_hex(8)}{ext}"
    file_path = media_module.USER_MEDIA_DIR / filename
    file_path.write_bytes(content)

    image_url = f"/media/users/{filename}"
    msg = send_message(
        user_id=int(current_user["id"]),
        text=text.strip() if text.strip() else None,
        image_url=image_url,
    )
    return {"message": msg}
