from __future__ import annotations

import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from database.init_db import DB_PATH, DATA_DIR, get_database_url, is_postgres_enabled
from database.types import JsonDict


DB_BACKUP_DIR = DATA_DIR / "db_backups"


def ensure_db_backup_dirs() -> None:
    DB_BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def create_db_backup() -> Path:
    ensure_db_backup_dirs()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if is_postgres_enabled():
        database_url = get_database_url()
        if not database_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo obtener DATABASE_URL para el backup.",
            )

        backup_path = DB_BACKUP_DIR / f"db_backup_{timestamp}.sql"

        pg_dump_path = shutil.which("pg_dump")
        if not pg_dump_path:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="pg_dump no esta disponible en el servidor.",
            )

        result = subprocess.run(
            [pg_dump_path, "--no-owner", "--no-acl", "--clean", "--if-exists", database_url],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"pg_dump fallo: {result.stderr[:500]}",
            )

        backup_path.write_text(result.stdout, encoding="utf-8")
        return backup_path

    if not DB_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe la base de datos SQLite todavia.",
        )

    backup_path = DB_BACKUP_DIR / f"db_backup_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


async def restore_db_backup(uploaded_file: UploadFile) -> JsonDict:
    ensure_db_backup_dirs()

    content = await uploaded_file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo esta vacio.",
        )

    filename = (uploaded_file.filename or "").lower()

    if is_postgres_enabled():
        if not filename.endswith(".sql"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Para PostgreSQL, el archivo debe ser un dump SQL (.sql).",
            )

        database_url = get_database_url()
        if not database_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No DATABASE_URL configurada.",
            )

        psql_path = shutil.which("psql")
        if not psql_path:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="psql no esta disponible en el servidor.",
            )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False, encoding="utf-8") as tmp:
            tmp.write(content.decode("utf-8"))
            tmp_path = Path(tmp.name)

        try:
            result = subprocess.run(
                [psql_path, database_url, "-f", str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"psql fallo: {result.stderr[:500]}",
                )

            return {
                "restored": True,
                "message": "Base de datos PostgreSQL restaurada correctamente.",
                "type": "postgresql",
            }
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
    else:
        if not filename.endswith(".db"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Para SQLite, el archivo debe ser .db.",
            )

        try:
            test_conn = sqlite3.connect(":memory:")
            test_conn.deserialize(content)
            test_conn.close()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo no es una base de datos SQLite valida.",
            )

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safety_backup = DB_BACKUP_DIR / f"db_safety_backup_{timestamp}.db"
        if DB_PATH.exists():
            shutil.copy2(DB_PATH, safety_backup)

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        DB_PATH.write_bytes(content)

        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute("SELECT COUNT(*) FROM users")
            conn.close()
        except Exception as exc:
            if safety_backup.exists():
                shutil.copy2(safety_backup, DB_PATH)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"La base de datos restaurada no es funcional: {exc}",
            )

        return {
            "restored": True,
            "message": "Base de datos SQLite restaurada correctamente.",
            "type": "sqlite",
        }
