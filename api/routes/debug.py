from __future__ import annotations

import os

from fastapi import APIRouter, Body, HTTPException, Query, status

from database.init_db import DB_PATH, get_connection, init_db, is_postgres_enabled
from database.types import JsonDict, JsonList


router = APIRouter(prefix="/debug", tags=["debug"])


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


def _get_existing_tables(connection) -> list[str]:
    if is_postgres_enabled():
        rows = connection.execute(
            """
            SELECT table_name AS name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        ).fetchall()
        return [str(row["name"]) for row in rows]

    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [str(row["name"]) for row in rows]


def _get_column_info(connection, table_name: str) -> list[dict[str, object]]:
    if is_postgres_enabled():
        rows = connection.execute(
            """
            SELECT column_name AS name, data_type AS type,
                   CASE WHEN is_nullable = 'NO' THEN 1 ELSE 0 END AS notnull,
                   column_default AS dflt_value
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ?
            ORDER BY ordinal_position
            """,
            (table_name,),
        ).fetchall()

        pk_rows = connection.execute(
            """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = 'public'
                AND tc.table_name = ?
            """,
            (table_name,),
        ).fetchall()
        pk_columns = {str(row["column_name"]) for row in pk_rows}

        return [
            {
                "name": str(row["name"]),
                "type": str(row["type"]).upper(),
                "nullable": not bool(row["notnull"]),
                "pk": row["name"] in pk_columns,
                "default": row["dflt_value"],
            }
            for row in rows
        ]

    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [
        {
            "name": str(row["name"]),
            "type": (str(row["type"]) if row["type"] else "TEXT").upper(),
            "nullable": not bool(row["notnull"]),
            "pk": bool(row["pk"]),
            "default": row["dflt_value"],
        }
        for row in rows
    ]


def _get_pk_column(columns: list[dict[str, object]]) -> str:
    for col in columns:
        if col["pk"]:
            return str(col["name"])
    return "id"


@router.get("/db-summary")
def get_db_summary(token: str | None = Query(default=None)) -> JsonDict:
    _require_debug_token(token)
    init_db()

    with get_connection() as connection:
        existing_tables = _get_existing_tables(connection)
        table_counts = {
            table_name: int(
                connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            )
            for table_name in existing_tables
        }

    return {
        "db_path": "postgres:DATABASE_URL" if is_postgres_enabled() else str(DB_PATH),
        "table_counts": table_counts,
    }


@router.get("/db-table/{table_name}/columns")
def get_table_columns(
    table_name: str,
    token: str | None = Query(default=None),
) -> JsonList:
    _require_debug_token(token)
    init_db()

    with get_connection() as connection:
        existing_tables = _get_existing_tables(connection)
        if table_name not in existing_tables:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Table not found.",
            )
        return _get_column_info(connection, table_name)


@router.post("/db-table/{table_name}")
def insert_table_row(
    table_name: str,
    token: str | None = Query(default=None),
    data: JsonDict = Body(...),
) -> JsonDict:
    _require_debug_token(token)
    init_db()

    with get_connection() as connection:
        existing_tables = _get_existing_tables(connection)
        if table_name not in existing_tables:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")

        columns = _get_column_info(connection, table_name)
        col_names = {c["name"] for c in columns}
        pk_columns = {c["name"] for c in columns if c["pk"]}
        pk_col = _get_pk_column(columns)

        insert_data: dict[str, object] = {}
        for k, v in data.items():
            if k not in col_names or k in pk_columns:
                continue
            if isinstance(v, str) and v.strip() == "":
                insert_data[k] = None
            else:
                insert_data[k] = v

        if not insert_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid columns to insert.")

        columns_str = ", ".join(insert_data.keys())
        placeholders = ", ".join(["?" for _ in insert_data])
        values = tuple(insert_data.values())

        connection.execute(
            f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})",
            values,
        )
        connection.commit()

        cursor = connection.execute(f"SELECT MAX({pk_col}) AS pk FROM {table_name}")
        last_pk = cursor.fetchone()["pk"]

    row = _refetch_row(table_name, pk_col, int(last_pk))
    return {"row": row}


@router.put("/db-table/{table_name}/{row_id}")
def update_table_row(
    table_name: str,
    row_id: int,
    token: str | None = Query(default=None),
    data: JsonDict = Body(...),
) -> JsonDict:
    _require_debug_token(token)
    init_db()

    with get_connection() as connection:
        existing_tables = _get_existing_tables(connection)
        if table_name not in existing_tables:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")

        columns = _get_column_info(connection, table_name)
        col_names = {c["name"] for c in columns}
        pk_columns = {c["name"] for c in columns if c["pk"]}
        pk_col = _get_pk_column(columns)

        update_data: dict[str, object] = {}
        for k, v in data.items():
            if k not in col_names or k in pk_columns:
                continue
            if isinstance(v, str) and v.strip() == "":
                update_data[k] = None
            else:
                update_data[k] = v

        if not update_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid columns to update.")

        set_clause = ", ".join(f"{k} = ?" for k in update_data)
        values = tuple(update_data.values()) + (row_id,)

        connection.execute(
            f"UPDATE {table_name} SET {set_clause} WHERE {pk_col} = ?",
            values,
        )
        connection.commit()

    row = _refetch_row(table_name, pk_col, row_id)
    return {"row": row}


@router.delete("/db-table/{table_name}/{row_id}")
def delete_table_row(
    table_name: str,
    row_id: int,
    token: str | None = Query(default=None),
) -> JsonDict:
    _require_debug_token(token)
    init_db()

    with get_connection() as connection:
        existing_tables = _get_existing_tables(connection)
        if table_name not in existing_tables:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")

        columns = _get_column_info(connection, table_name)
        pk_col = _get_pk_column(columns)

        connection.execute(
            f"DELETE FROM {table_name} WHERE {pk_col} = ?",
            (row_id,),
        )
        connection.commit()

    return {"deleted": True, "table": table_name, "id": row_id}


@router.get("/db-table/{table_name}")
def get_db_table_rows(
    table_name: str,
    token: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> JsonDict:
    _require_debug_token(token)
    init_db()

    with get_connection() as connection:
        existing_tables = _get_existing_tables(connection)
        if table_name not in existing_tables:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Table not found.",
            )
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


def _refetch_row(table_name: str, pk_col: str, row_id: int) -> JsonDict | None:
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT * FROM {table_name} WHERE {pk_col} = ?",
            (row_id,),
        ).fetchall()
        return dict(rows[0]) if rows else None
