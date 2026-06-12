from __future__ import annotations

import sqlite3

from database.init_db import get_connection, init_db
from database.types import RowDict


def send_message(user_id: int, text: str | None = None, image_url: str | None = None) -> RowDict:
    init_db()
    if not text and not image_url:
        raise ValueError("El mensaje debe tener texto o imagen.")

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO chat_messages (user_id, text, image_url)
            VALUES (?, ?, ?)
            """,
            (user_id, text, image_url),
        )
        connection.commit()
        message = connection.execute(
            """
            SELECT chat_messages.id, chat_messages.user_id, chat_messages.text, chat_messages.image_url,
                   chat_messages.created_at, users.name AS user_name, users.img AS user_img
            FROM chat_messages
            INNER JOIN users ON users.id = chat_messages.user_id
            WHERE chat_messages.id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return dict(message)


def get_messages(since_id: int = 0, before_id: int | None = None, limit: int = 50) -> list[RowDict]:
    init_db()

    with get_connection() as connection:
        if before_id is not None:
            rows = connection.execute(
                """
                SELECT chat_messages.id, chat_messages.user_id, chat_messages.text, chat_messages.image_url,
                       chat_messages.created_at, users.name AS user_name, users.img AS user_img
                FROM chat_messages
                INNER JOIN users ON users.id = chat_messages.user_id
                WHERE chat_messages.id < ?
                ORDER BY chat_messages.id DESC
                LIMIT ?
                """,
                (before_id, limit),
            ).fetchall()
            rows.reverse()
        else:
            rows = connection.execute(
                """
                SELECT chat_messages.id, chat_messages.user_id, chat_messages.text, chat_messages.image_url,
                       chat_messages.created_at, users.name AS user_name, users.img AS user_img
                FROM chat_messages
                INNER JOIN users ON users.id = chat_messages.user_id
                WHERE chat_messages.id > ?
                ORDER BY chat_messages.id ASC
                LIMIT ?
                """,
                (since_id, limit),
            ).fetchall()

    return [dict(row) for row in rows]
