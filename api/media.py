from __future__ import annotations

from pathlib import Path
from secrets import token_hex
from zipfile import ZIP_DEFLATED, ZipFile
import shutil
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile, status


BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_DIR = BASE_DIR / "media"
USER_MEDIA_DIR = MEDIA_DIR / "users"
MEDIA_BACKUP_DIR = MEDIA_DIR / "backups" / "users"

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024


def ensure_media_dirs() -> None:
    USER_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_BACKUP_DIR.mkdir(parents=True, exist_ok=True)


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


def create_user_media_backup() -> Path:
    ensure_media_dirs()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = MEDIA_BACKUP_DIR / f"users_backup_{timestamp}.zip"

    with ZipFile(backup_path, "w", compression=ZIP_DEFLATED) as zip_file:
        for file_path in sorted(USER_MEDIA_DIR.rglob("*")):
            if file_path.is_file():
                zip_file.write(file_path, arcname=file_path.relative_to(USER_MEDIA_DIR))

    return backup_path


def _resolve_backup_path(backup_filename: str | None = None) -> Path:
    ensure_media_dirs()

    if backup_filename:
        candidate = (MEDIA_BACKUP_DIR / backup_filename).resolve()
        resolved_backup_dir = MEDIA_BACKUP_DIR.resolve()
        if resolved_backup_dir not in candidate.parents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nombre de backup invalido.",
            )
        if not candidate.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No existe ese backup.",
            )
        return candidate

    backups = sorted(MEDIA_BACKUP_DIR.glob("users_backup_*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not backups:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay backups de media/users.",
        )
    return backups[0]


def restore_user_media_backup(backup_filename: str | None = None) -> dict[str, object]:
    ensure_media_dirs()
    backup_path = _resolve_backup_path(backup_filename)
    resolved_user_media_dir = USER_MEDIA_DIR.resolve()

    for child in USER_MEDIA_DIR.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    restored_files = 0
    with ZipFile(backup_path, "r") as zip_file:
        for member in zip_file.infolist():
            if member.is_dir():
                continue

            destination = (USER_MEDIA_DIR / member.filename).resolve()
            if resolved_user_media_dir not in destination.parents:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El backup contiene rutas no validas.",
                )

            destination.parent.mkdir(parents=True, exist_ok=True)
            with zip_file.open(member, "r") as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
            restored_files += 1

    return {
        "backup_filename": backup_path.name,
        "backup_path": str(backup_path),
        "restored_files": restored_files,
    }


def restore_user_media_backup_from_upload(uploaded_file: UploadFile) -> dict[str, object]:
    ensure_media_dirs()
    resolved_user_media_dir = USER_MEDIA_DIR.resolve()

    content = uploaded_file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo esta vacio.",
        )

    filename = (uploaded_file.filename or "").lower()
    if not filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser un ZIP.",
        )

    import io
    zip_buffer = io.BytesIO(content)

    try:
        zip_file = ZipFile(zip_buffer, "r")
        _ = zip_file.infolist()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no es un ZIP valido.",
        )

    for child in USER_MEDIA_DIR.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    restored_files = 0
    with zip_file:
        for member in zip_file.infolist():
            if member.is_dir():
                continue

            destination = (USER_MEDIA_DIR / member.filename).resolve()
            if resolved_user_media_dir not in destination.parents:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El backup contiene rutas no validas.",
                )

            destination.parent.mkdir(parents=True, exist_ok=True)
            with zip_file.open(member, "r") as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
            restored_files += 1

    return {
        "restored_files": restored_files,
        "message": f"Backup restaurado: {restored_files} archivos.",
    }
