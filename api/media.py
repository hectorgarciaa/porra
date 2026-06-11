from __future__ import annotations

from pathlib import Path
from secrets import token_hex

from fastapi import HTTPException, UploadFile, status


BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_DIR = BASE_DIR / "media"
USER_MEDIA_DIR = MEDIA_DIR / "users"

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024


def ensure_media_dirs() -> None:
    USER_MEDIA_DIR.mkdir(parents=True, exist_ok=True)


async def save_user_avatar(user_id: int, image: UploadFile) -> str:
    ensure_media_dirs()

    content_type = (image.content_type or "").lower().strip()
    extension = ALLOWED_IMAGE_TYPES.get(content_type)
    if extension is None:
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
    if len(content) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La imagen supera el maximo de 5 MB.",
        )

    filename = f"user_{user_id}_{token_hex(8)}{extension}"
    file_path = USER_MEDIA_DIR / filename
    file_path.write_bytes(content)

    return f"/media/users/{filename}"


def delete_local_media_file(media_url: str | None) -> None:
    if not media_url or not media_url.startswith("/media/"):
        return

    relative_path = media_url.removeprefix("/media/").strip()
    if not relative_path:
        return

    file_path = MEDIA_DIR / relative_path
    resolved_media_dir = MEDIA_DIR.resolve()
    resolved_file_path = file_path.resolve()

    if resolved_media_dir not in resolved_file_path.parents:
        return

    if resolved_file_path.is_file():
        resolved_file_path.unlink()
