import os

from fastapi import APIRouter, HTTPException, Query, status

from database.init_db import DB_PATH, get_connection, init_db
from database.types import JsonDict, JsonList


router = APIRouter(prefix="/debug", tags=["debug"])

ALLOWED_TABLES = (
    "chat_messages",
    "global_predictions",
    "groups",
    "match_predictions",
    "matches",
    "players",
    "predictions",
    "sessions",
    "teams",
    "users",
)


def _require_debug_token(token: str | None) -> None:
    expected_token = os.getenv("DEBUG_DB_TOKEN")
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debug route is disabled.",
        )
    if token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid debug token.",
        )


@router.get("/db-summary")
def get_db_summary(token: str | None = Query(default=None)) -> JsonDict:
    _require_debug_token(token)
    init_db()

    with get_connection() as connection:
        table_counts = {
            table_name: int(
                connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            )
            for table_name in ALLOWED_TABLES
        }

    return {
        "db_path": str(DB_PATH),
        "table_counts": table_counts,
    }


@router.get("/db-table/{table_name}")
def get_db_table_rows(
    table_name: str,
    token: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> JsonDict:
    _require_debug_token(token)
    init_db()

    if table_name not in ALLOWED_TABLES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not allowed.",
        )

    with get_connection() as connection:
        total = int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
        rows = connection.execute(
            f"SELECT * FROM {table_name} LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    items: JsonList = [dict(row) for row in rows]
    return {
        "table": table_name,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }
