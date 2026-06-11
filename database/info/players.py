from __future__ import annotations

import sqlite3

from database.init_db import get_connection, init_db
from database.normalize import normalize_required_text
from database.predictions._helpers import team_exists
from database.types import RowDict


class PlayerAlreadyExistsError(ValueError):
    pass


def createPlayer(team_id: int, name: str, surname: str, number: int) -> RowDict:
    init_db()
    normalized_name = normalize_required_text(name, "name")
    normalized_surname = normalize_required_text(surname, "surname")

    if number <= 0:
        raise ValueError("El dorsal debe ser mayor que 0.")

    with get_connection() as connection:
        if not team_exists(connection, team_id):
            raise ValueError(f"No existe el equipo con id {team_id}.")

        existing_number = connection.execute(
            "SELECT id FROM players WHERE team_id = ? AND number = ?",
            (team_id, number),
        ).fetchone()
        if existing_number is not None:
            raise PlayerAlreadyExistsError(
                f"Ya existe un jugador con el dorsal {number} en el equipo {team_id}."
            )

        cursor = connection.execute(
            """
            INSERT INTO players (team_id, name, surname, number)
            VALUES (?, ?, ?, ?)
            """,
            (team_id, normalized_name, normalized_surname, number),
        )
        connection.commit()

        player = connection.execute(
            """
            SELECT id, team_id, name, surname, number,
                   num_goals, num_assists, num_yellow_cards, num_red_cards,
                   created_at, updated_at
            FROM players
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return dict(player)
