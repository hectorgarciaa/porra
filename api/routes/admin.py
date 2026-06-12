from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse

from api.db import create_db_backup, restore_db_backup
from api.dependencies import require_admin_token
from api.media import create_user_media_backup, restore_user_media_backup
from database.types import JsonDict


router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/media-users/backup")
def backup_media_users(_: str = Depends(require_admin_token)) -> FileResponse:
    backup_path = create_user_media_backup()
    return FileResponse(
        path=backup_path,
        media_type="application/zip",
        filename=backup_path.name,
    )


@router.post("/media-users/restore")
def restore_media_users(
    _: str = Depends(require_admin_token),
    backup_filename: str | None = Query(default=None),
) -> JsonDict:
    return restore_user_media_backup(backup_filename)


@router.post("/db/backup")
def backup_db(_: str = Depends(require_admin_token)) -> FileResponse:
    backup_path = create_db_backup()
    return FileResponse(
        path=backup_path,
        media_type="application/octet-stream",
        filename=backup_path.name,
    )


@router.post("/db/restore")
def restore_db(
    _: str = Depends(require_admin_token),
    file: UploadFile = File(...),
) -> JsonDict:
    return restore_db_backup(file)
