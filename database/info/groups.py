from __future__ import annotations

import sqlite3

from database.init_db import get_connection, init_db
from database.normalize import normalize_required_text
from database.types import RowDict


class GroupAlreadyExistsError(ValueError):
    pass


class GroupNotFoundError(ValueError):
    pass


def createGroup(letter: str) -> RowDict:
    init_db()
    normalized_letter = normalize_required_text(letter, "letter").upper()

    with get_connection() as connection:
        existing_group = connection.execute(
            "SELECT id FROM groups WHERE letter = ?",
            (normalized_letter,),
        ).fetchone()
        if existing_group is not None:
            raise GroupAlreadyExistsError(f"Ya existe el grupo '{normalized_letter}'.")

        cursor = connection.execute(
            """
            INSERT INTO groups (letter)
            VALUES (?)
            """,
            (normalized_letter,),
        )
        connection.commit()

        group = connection.execute(
            """
            SELECT id, letter
            FROM groups
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return dict(group)
