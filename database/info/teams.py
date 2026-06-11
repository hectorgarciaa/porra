from __future__ import annotations

import sqlite3

from database.init_db import get_connection, init_db
from database.normalize import normalize_required_text, normalize_slug
from database.types import RowDict


class TeamAlreadyExistsError(ValueError):
    pass


class TeamNotFoundError(ValueError):
    pass


def _group_exists(connection: sqlite3.Connection, group_id: int) -> bool:
    row = connection.execute(
        "SELECT id FROM groups WHERE id = ?",
        (group_id,),
    ).fetchone()
    return row is not None


def createTeam(name: str, fifa_slug: str, group_id: int) -> RowDict:
    init_db()
    normalized_name = normalize_required_text(name, "name")
    normalized_slug = normalize_slug(fifa_slug, "fifa_slug")

    with get_connection() as connection:
        if not _group_exists(connection, group_id):
            raise ValueError(f"No existe el grupo con id {group_id}.")

        existing_name = connection.execute(
            "SELECT id FROM teams WHERE lower(name) = lower(?)",
            (normalized_name,),
        ).fetchone()
        if existing_name is not None:
            raise TeamAlreadyExistsError(f"Ya existe el equipo '{normalized_name}'.")

        existing_slug = connection.execute(
            "SELECT id FROM teams WHERE fifa_slug = ?",
            (normalized_slug,),
        ).fetchone()
        if existing_slug is not None:
            raise TeamAlreadyExistsError(f"Ya existe el fifa_slug '{normalized_slug}'.")

        cursor = connection.execute(
            """
            INSERT INTO teams (name, fifa_slug, group_id)
            VALUES (?, ?, ?)
            """,
            (normalized_name, normalized_slug, group_id),
        )
        connection.commit()

        team = connection.execute(
            """
            SELECT id, name, fifa_slug, group_id, created_at, updated_at
            FROM teams
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return dict(team)
