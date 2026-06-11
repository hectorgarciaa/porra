from __future__ import annotations

import sqlite3

from database.init_db import get_connection, init_db
from database.types import RowDict


class PredictionNotFoundError(ValueError):
    pass


class PredictionAlreadyExistsError(ValueError):
    pass


def _user_exists(connection: sqlite3.Connection, player_id: int) -> bool:
    row = connection.execute(
        "SELECT id FROM users WHERE id = ?",
        (player_id,),
    ).fetchone()
    return row is not None


def createPrediction(player_id: int) -> RowDict:
    init_db()

    with get_connection() as connection:
        if not _user_exists(connection, player_id):
            raise ValueError(f"No existe el usuario con id {player_id}.")

        existing_prediction = connection.execute(
            "SELECT id FROM predictions WHERE player_id = ?",
            (player_id,),
        ).fetchone()
        if existing_prediction is not None:
            raise PredictionAlreadyExistsError(
                f"Ya existe una prediccion para el usuario {player_id}."
            )

        cursor = connection.execute(
            """
            INSERT INTO predictions (player_id)
            VALUES (?)
            """,
            (player_id,),
        )
        connection.commit()

        prediction = connection.execute(
            """
            SELECT id, player_id, points, created_at, updated_at
            FROM predictions
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return dict(prediction)


def getPredictionById(prediction_id: int) -> RowDict:
    init_db()

    with get_connection() as connection:
        prediction = connection.execute(
            """
            SELECT id, player_id, points, created_at, updated_at
            FROM predictions
            WHERE id = ?
            """,
            (prediction_id,),
        ).fetchone()

    if prediction is None:
        raise PredictionNotFoundError(f"No existe la prediccion con id {prediction_id}.")

    return dict(prediction)


def getPredictionByPlayerId(player_id: int) -> RowDict:
    init_db()

    with get_connection() as connection:
        prediction = connection.execute(
            """
            SELECT id, player_id, points, created_at, updated_at
            FROM predictions
            WHERE player_id = ?
            """,
            (player_id,),
        ).fetchone()

    if prediction is None:
        raise PredictionNotFoundError(f"No existe una prediccion para el usuario {player_id}.")

    return dict(prediction)


def updatePredictionPoints(prediction_id: int, points: int) -> RowDict:
    init_db()
    if points < 0:
        raise ValueError("Los puntos no pueden ser negativos.")

    with get_connection() as connection:
        existing_prediction = connection.execute(
            "SELECT id FROM predictions WHERE id = ?",
            (prediction_id,),
        ).fetchone()
        if existing_prediction is None:
            raise PredictionNotFoundError(f"No existe la prediccion con id {prediction_id}.")

        connection.execute(
            """
            UPDATE predictions
            SET points = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (points, prediction_id),
        )
        connection.commit()

        prediction = connection.execute(
            """
            SELECT id, player_id, points, created_at, updated_at
            FROM predictions
            WHERE id = ?
            """,
            (prediction_id,),
        ).fetchone()

    return dict(prediction)
