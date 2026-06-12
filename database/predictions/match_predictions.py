from __future__ import annotations

import sqlite3
from datetime import datetime

from database.init_db import get_connection, init_db
from database.predictions._helpers import prediction_exists
from database.types import RowDict, UNSET
MATCH_PREDICTION_COLUMNS = (
    "id, prediction_id, match_id, local_goals, away_goals, winner_team_id, "
    "has_extra_time, has_penalties, created_at, updated_at"
)


def _get_match_row(connection: sqlite3.Connection, match_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT id, stage, kickoff_at, local_team_id, away_team_id
        FROM matches
        WHERE id = ?
        """,
        (match_id,),
    ).fetchone()


def _validate_score(local_goals: int, away_goals: int) -> None:
    if local_goals < 0 or away_goals < 0:
        raise ValueError("Los goles no pueden ser negativos.")


def _has_match_started(kickoff_at: str) -> bool:
    kickoff = datetime.fromisoformat(kickoff_at)
    now = datetime.now(kickoff.tzinfo) if kickoff.tzinfo is not None else datetime.now()
    return now >= kickoff


def _validate_match_prediction_outcome(
    match_row: sqlite3.Row,
    local_goals: int,
    away_goals: int,
    winner_team_id: int | None,
    has_extra_time: bool,
    has_penalties: bool,
) -> int | None:
    stage = str(match_row["stage"])
    local_team_id = int(match_row["local_team_id"])
    away_team_id = int(match_row["away_team_id"])

    if has_penalties and not has_extra_time:
        raise ValueError("Si una prediccion tiene penaltis, tambien debe tener prorroga.")
    if stage == "groups" and has_extra_time:
        raise ValueError("En fase de grupos no se puede predecir prorroga.")
    if stage == "groups" and has_penalties:
        raise ValueError("En fase de grupos no se puede predecir penaltis.")

    if winner_team_id is not None and winner_team_id not in (local_team_id, away_team_id):
        raise ValueError("winner_team_id debe ser uno de los equipos del partido.")

    if has_penalties:
        if local_goals != away_goals:
            raise ValueError("Si predices penaltis, el marcador tras juego/prorroga debe acabar en empate.")
        if winner_team_id is None:
            raise ValueError("Si predices penaltis, debes indicar el equipo ganador.")
        return winner_team_id

    if local_goals > away_goals:
        inferred_winner_team_id = local_team_id
    elif away_goals > local_goals:
        inferred_winner_team_id = away_team_id
    else:
        inferred_winner_team_id = None

    if winner_team_id is not None and winner_team_id != inferred_winner_team_id:
        raise ValueError("winner_team_id no coincide con el marcador predicho.")

    if stage != "groups" and local_goals == away_goals:
        raise ValueError("Si el marcador predicho acaba en empate en eliminatoria, debes marcar penaltis.")

    return inferred_winner_team_id if winner_team_id is None else winner_team_id


def createMatchPrediction(
    prediction_id: int,
    match_id: int,
    local_goals: int,
    away_goals: int,
    winner_team_id: int | None = None,
    has_extra_time: bool = False,
    has_penalties: bool = False,
) -> RowDict:
    init_db()
    _validate_score(local_goals, away_goals)

    with get_connection() as connection:
        if not prediction_exists(connection, prediction_id):
            raise ValueError(f"No existe la prediccion con id {prediction_id}.")
        match_row = _get_match_row(connection, match_id)
        if match_row is None:
            raise ValueError(f"No existe el partido con id {match_id}.")
        if _has_match_started(str(match_row["kickoff_at"])):
            raise ValueError("No puedes crear una prediccion de un partido que ya ha empezado.")
        normalized_winner_team_id = _validate_match_prediction_outcome(
            match_row,
            local_goals,
            away_goals,
            winner_team_id,
            has_extra_time,
            has_penalties,
        )

        cursor = connection.execute(
            """
            INSERT INTO match_predictions (
                prediction_id,
                match_id,
                local_goals,
                away_goals,
                winner_team_id,
                has_extra_time,
                has_penalties
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prediction_id,
                match_id,
                local_goals,
                away_goals,
                normalized_winner_team_id,
                1 if has_extra_time else 0,
                1 if has_penalties else 0,
            ),
        )
        connection.commit()

        match_prediction = connection.execute(
            f"""
            SELECT {MATCH_PREDICTION_COLUMNS}
            FROM match_predictions
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    result: RowDict = dict(match_prediction)
    result["has_extra_time"] = bool(result["has_extra_time"])
    result["has_penalties"] = bool(result["has_penalties"])
    return result


def updateMatchPrediction(
    match_prediction_id: int,
    local_goals: int | object = UNSET,
    away_goals: int | object = UNSET,
    winner_team_id: int | None | object = UNSET,
    has_extra_time: bool | object = UNSET,
    has_penalties: bool | object = UNSET,
) -> RowDict:
    init_db()
    if (
        local_goals is UNSET
        and away_goals is UNSET
        and winner_team_id is UNSET
        and has_extra_time is UNSET
        and has_penalties is UNSET
    ):
        raise ValueError("Debes indicar al menos un campo para actualizar.")

    with get_connection() as connection:
        match_prediction = connection.execute(
            f"""
            SELECT {MATCH_PREDICTION_COLUMNS}
            FROM match_predictions
            WHERE id = ?
            """,
            (match_prediction_id,),
        ).fetchone()
        if match_prediction is None:
            raise ValueError(
                f"No existe la match_prediction con id {match_prediction_id}."
            )

        match_row = _get_match_row(connection, int(match_prediction["match_id"]))
        if match_row is None:
            raise ValueError(f"No existe el partido con id {match_prediction['match_id']}.")
        if _has_match_started(str(match_row["kickoff_at"])):
            raise ValueError("No puedes modificar una prediccion de partido despues de que el partido haya empezado.")

        next_local_goals = match_prediction["local_goals"] if local_goals is UNSET else int(local_goals)
        next_away_goals = match_prediction["away_goals"] if away_goals is UNSET else int(away_goals)
        next_has_extra_time = bool(match_prediction["has_extra_time"]) if has_extra_time is UNSET else bool(has_extra_time)
        next_has_penalties = bool(match_prediction["has_penalties"]) if has_penalties is UNSET else bool(has_penalties)
        _validate_score(next_local_goals, next_away_goals)
        next_winner_team_id = (
            match_prediction["winner_team_id"]
            if winner_team_id is UNSET
            else winner_team_id
        )
        normalized_winner_team_id = _validate_match_prediction_outcome(
            match_row,
            next_local_goals,
            next_away_goals,
            next_winner_team_id,
            next_has_extra_time,
            next_has_penalties,
        )

        connection.execute(
            """
            UPDATE match_predictions
            SET local_goals = ?, away_goals = ?, winner_team_id = ?,
                has_extra_time = ?, has_penalties = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                next_local_goals,
                next_away_goals,
                normalized_winner_team_id,
                1 if next_has_extra_time else 0,
                1 if next_has_penalties else 0,
                match_prediction_id,
            ),
        )
        connection.commit()

        updated_match_prediction = connection.execute(
            f"""
            SELECT {MATCH_PREDICTION_COLUMNS}
            FROM match_predictions
            WHERE id = ?
            """,
            (match_prediction_id,),
        ).fetchone()

    result: RowDict = dict(updated_match_prediction)
    result["has_extra_time"] = bool(result["has_extra_time"])
    result["has_penalties"] = bool(result["has_penalties"])
    return result


def upsertMatchPrediction(
    prediction_id: int,
    match_id: int,
    local_goals: int,
    away_goals: int,
    winner_team_id: int | None = None,
    has_extra_time: bool = False,
    has_penalties: bool = False,
) -> RowDict:
    init_db()
    _validate_score(local_goals, away_goals)

    with get_connection() as connection:
        if not prediction_exists(connection, prediction_id):
            raise ValueError(f"No existe la prediccion con id {prediction_id}.")
        match_row = _get_match_row(connection, match_id)
        if match_row is None:
            raise ValueError(f"No existe el partido con id {match_id}.")
        if _has_match_started(str(match_row["kickoff_at"])):
            raise ValueError("No puedes predecir un partido que ya ha empezado.")
        normalized_winner_team_id = _validate_match_prediction_outcome(
            match_row, local_goals, away_goals,
            winner_team_id, has_extra_time, has_penalties,
        )

        existing = connection.execute(
            "SELECT id FROM match_predictions WHERE prediction_id = ? AND match_id = ?",
            (prediction_id, match_id),
        ).fetchone()

        extra_time_int = 1 if has_extra_time else 0
        penalties_int = 1 if has_penalties else 0

        if existing is None:
            cursor = connection.execute(
                """
                INSERT INTO match_predictions (
                    prediction_id, match_id, local_goals, away_goals,
                    winner_team_id, has_extra_time, has_penalties
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prediction_id, match_id, local_goals, away_goals,
                    normalized_winner_team_id, extra_time_int, penalties_int,
                ),
            )
            connection.commit()
            result = connection.execute(
                f"SELECT {MATCH_PREDICTION_COLUMNS} FROM match_predictions WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        else:
            mid = int(existing["id"])
            connection.execute(
                """
                UPDATE match_predictions
                SET local_goals = ?, away_goals = ?, winner_team_id = ?,
                    has_extra_time = ?, has_penalties = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    local_goals, away_goals, normalized_winner_team_id,
                    extra_time_int, penalties_int, mid,
                ),
            )
            connection.commit()
            result = connection.execute(
                f"SELECT {MATCH_PREDICTION_COLUMNS} FROM match_predictions WHERE id = ?",
                (mid,),
            ).fetchone()

    final: RowDict = dict(result)
    final["has_extra_time"] = bool(final["has_extra_time"])
    final["has_penalties"] = bool(final["has_penalties"])
    return final


def getMatchPredictionsByPrediction(prediction_id: int) -> list[RowDict]:
    init_db()

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT {MATCH_PREDICTION_COLUMNS}
            FROM match_predictions
            WHERE prediction_id = ?
            ORDER BY match_id
            """,
            (prediction_id,),
        ).fetchall()

    results: list[RowDict] = [dict(row) for row in rows]
    for result in results:
        result["has_extra_time"] = bool(result["has_extra_time"])
        result["has_penalties"] = bool(result["has_penalties"])
    return results
