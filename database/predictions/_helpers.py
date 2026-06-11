from __future__ import annotations

import sqlite3


def prediction_exists(connection: sqlite3.Connection, prediction_id: int) -> bool:
    row = connection.execute(
        "SELECT id FROM predictions WHERE id = ?",
        (prediction_id,),
    ).fetchone()
    return row is not None


def team_exists(connection: sqlite3.Connection, team_id: int | None) -> bool:
    if team_id is None:
        return True
    row = connection.execute(
        "SELECT id FROM teams WHERE id = ?",
        (team_id,),
    ).fetchone()
    return row is not None


def player_exists(connection: sqlite3.Connection, player_id: int | None) -> bool:
    if player_id is None:
        return True
    row = connection.execute(
        "SELECT id FROM players WHERE id = ?",
        (player_id,),
    ).fetchone()
    return row is not None
