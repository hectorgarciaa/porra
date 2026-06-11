from __future__ import annotations

import secrets
import sqlite3

from database.init_db import get_connection, init_db
from database.normalize import normalize_optional_text, normalize_required_text
from database.types import RowDict, UNSET


class UserAlreadyExistsError(ValueError):
    pass


class UserNotFoundError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


class InvalidSessionError(ValueError):
    pass


class ForbiddenError(PermissionError):
    pass


def createUser(name: str, password: str) -> RowDict:
    init_db()
    normalized_name = normalize_required_text(name, "name")
    if not password:
        raise ValueError("La password no puede estar vacia.")

    with get_connection() as connection:
        existing_user = connection.execute(
            "SELECT id FROM users WHERE lower(name) = lower(?)",
            (normalized_name,),
        ).fetchone()
        if existing_user is not None:
            raise UserAlreadyExistsError(f"Ya existe un usuario con el nombre '{normalized_name}'.")

        cursor = connection.execute(
            """
            INSERT INTO users (name, password)
            VALUES (?, ?)
            """,
            (normalized_name, password),
        )
        connection.commit()

        user = connection.execute(
            """
            SELECT id, name, img, created_at, updated_at
            FROM users
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return dict(user)


def updateUser(
    token: str,
    user_id: int,
    name: str | object = UNSET,
    img: str | None | object = UNSET,
) -> RowDict:
    init_db()

    if name is UNSET and img is UNSET:
        raise ValueError("Debes indicar al menos un campo para actualizar.")

    requireUserAccess(token, user_id)

    with get_connection() as connection:
        user = connection.execute(
            "SELECT id, name, img, created_at, updated_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if user is None:
            raise UserNotFoundError(f"No existe el usuario con id {user_id}.")

        if name is not UNSET:
            normalized_name = normalize_required_text(str(name), "name")
            existing_user = connection.execute(
                "SELECT id FROM users WHERE lower(name) = lower(?) AND id <> ?",
                (normalized_name, user_id),
            ).fetchone()
            if existing_user is not None:
                raise UserAlreadyExistsError(f"Ya existe un usuario con el nombre '{normalized_name}'.")
        else:
            normalized_name = user["name"]

        next_name = normalized_name
        next_img = normalize_optional_text(str(img)) if isinstance(img, str) else (img if img is not UNSET else user["img"])

        connection.execute(
            """
            UPDATE users
            SET name = ?, img = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (next_name, next_img, user_id),
        )
        connection.commit()

        updated_user = connection.execute(
            """
            SELECT id, name, img, created_at, updated_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    return dict(updated_user)


def login(name: str, password: str) -> dict[str, RowDict]:
    init_db()
    normalized_name = normalize_required_text(name, "name")
    if not password:
        raise ValueError("La password no puede estar vacia.")

    with get_connection() as connection:
        user = connection.execute(
            """
            SELECT id, name, img, created_at, updated_at
            FROM users
            WHERE lower(name) = lower(?) AND password = ?
            """,
            (normalized_name, password),
        ).fetchone()
        if user is None:
            raise InvalidCredentialsError("Nombre o password incorrectos.")

        token = secrets.token_urlsafe(32)
        connection.execute(
            "DELETE FROM user_sessions WHERE user_id = ?",
            (user["id"],),
        )
        connection.execute(
            """
            INSERT INTO user_sessions (user_id, token)
            VALUES (?, ?)
            """,
            (user["id"], token),
        )
        connection.commit()

    return {
        "token": token,
        "user": dict(user),
    }


def getUserByToken(token: str) -> RowDict:
    init_db()
    normalize_required_text(token, "token")

    with get_connection() as connection:
        user = connection.execute(
            """
            SELECT users.id, users.name, users.img, users.created_at, users.updated_at
            FROM user_sessions
            INNER JOIN users ON users.id = user_sessions.user_id
            WHERE user_sessions.token = ?
            """,
            (token,),
        ).fetchone()

    if user is None:
        raise InvalidSessionError("Sesion no valida.")

    return dict(user)


def requireUserAccess(token: str, user_id: int) -> RowDict:
    user = getUserByToken(token)
    if int(user["id"]) != user_id:
        raise ForbiddenError("No tienes permisos para hacer esta operacion.")
    return user
