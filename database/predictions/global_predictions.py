from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from database.init_db import get_connection, init_db
from database.predictions._helpers import player_exists, prediction_exists, team_exists
from database.types import RowDict, UNSET
GLOBAL_PREDICTION_DEADLINE = datetime(2026, 6, 23, 23, 59, 59, tzinfo=timezone.utc)

GLOBAL_PREDICTION_COLUMNS = (
    "id, prediction_id, winner_team_id, runner_up_team_id, third_place_team_id, "
    "fourth_place_team_id, best_player_player_id, max_scorer_player_id, max_assister_player_id, "
    "max_yellow_cards_player_id, max_red_cards_player_id, created_at, updated_at"
)


class GlobalPredictionNotFoundError(ValueError):
    pass


def _validate_global_prediction_refs(
    connection: sqlite3.Connection,
    winner_team_id: int | None,
    runner_up_team_id: int | None,
    third_place_team_id: int | None,
    fourth_place_team_id: int | None,
    best_player_player_id: int | None,
    max_scorer_player_id: int | None,
    max_assister_player_id: int | None,
    max_yellow_cards_player_id: int | None,
    max_red_cards_player_id: int | None,
) -> None:
    team_ids: list[int | None] = [
        winner_team_id,
        runner_up_team_id,
        third_place_team_id,
        fourth_place_team_id,
    ]
    non_null_teams = [t for t in team_ids if t is not None]
    if len(set(non_null_teams)) != len(non_null_teams):
        raise ValueError("Los equipos de la prediccion global deben ser distintos entre si.")

    team_fields: dict[str, int | None] = {
        "winner_team_id": winner_team_id,
        "runner_up_team_id": runner_up_team_id,
        "third_place_team_id": third_place_team_id,
        "fourth_place_team_id": fourth_place_team_id,
    }
    for field_name, team_id in team_fields.items():
        if not team_exists(connection, team_id):
            raise ValueError(f"No existe el equipo indicado en {field_name}.")

    player_fields: dict[str, int | None] = {
        "best_player_player_id": best_player_player_id,
        "max_scorer_player_id": max_scorer_player_id,
        "max_assister_player_id": max_assister_player_id,
        "max_yellow_cards_player_id": max_yellow_cards_player_id,
        "max_red_cards_player_id": max_red_cards_player_id,
    }
    for field_name, player_id in player_fields.items():
        if not player_exists(connection, player_id):
            raise ValueError(f"No existe el jugador indicado en {field_name}.")


def _check_deadline() -> None:
    if datetime.now(timezone.utc) > GLOBAL_PREDICTION_DEADLINE:
        raise ValueError(
            "El plazo para hacer la prediccion global finalizo el 23 de junio de 2026."
        )


def createGlobalPrediction(
    prediction_id: int,
    winner_team_id: int | None = None,
    runner_up_team_id: int | None = None,
    third_place_team_id: int | None = None,
    fourth_place_team_id: int | None = None,
    best_player_player_id: int | None = None,
    max_scorer_player_id: int | None = None,
    max_assister_player_id: int | None = None,
    max_yellow_cards_player_id: int | None = None,
    max_red_cards_player_id: int | None = None,
) -> RowDict:
    init_db()
    _check_deadline()

    with get_connection() as connection:
        if not prediction_exists(connection, prediction_id):
            raise ValueError(f"No existe la prediccion con id {prediction_id}.")
        _validate_global_prediction_refs(
            connection,
            winner_team_id,
            runner_up_team_id,
            third_place_team_id,
            fourth_place_team_id,
            best_player_player_id,
            max_scorer_player_id,
            max_assister_player_id,
            max_yellow_cards_player_id,
            max_red_cards_player_id,
        )

        cursor = connection.execute(
            f"""
            INSERT INTO global_predictions (
                prediction_id, winner_team_id, runner_up_team_id, third_place_team_id,
                fourth_place_team_id, best_player_player_id, max_scorer_player_id,
                max_assister_player_id, max_yellow_cards_player_id, max_red_cards_player_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prediction_id, winner_team_id, runner_up_team_id, third_place_team_id,
                fourth_place_team_id, best_player_player_id, max_scorer_player_id,
                max_assister_player_id, max_yellow_cards_player_id, max_red_cards_player_id,
            ),
        )
        connection.commit()

        global_prediction = connection.execute(
            f"SELECT {GLOBAL_PREDICTION_COLUMNS} FROM global_predictions WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()

    return dict(global_prediction)


def updateGlobalPrediction(
    global_prediction_id: int,
    winner_team_id: int | None | object = UNSET,
    runner_up_team_id: int | None | object = UNSET,
    third_place_team_id: int | None | object = UNSET,
    fourth_place_team_id: int | None | object = UNSET,
    best_player_player_id: int | None | object = UNSET,
    max_scorer_player_id: int | None | object = UNSET,
    max_assister_player_id: int | None | object = UNSET,
    max_yellow_cards_player_id: int | None | object = UNSET,
    max_red_cards_player_id: int | None | object = UNSET,
) -> RowDict:
    init_db()
    _check_deadline()

    field_values = (
        winner_team_id, runner_up_team_id, third_place_team_id, fourth_place_team_id,
        best_player_player_id, max_scorer_player_id, max_assister_player_id,
        max_yellow_cards_player_id, max_red_cards_player_id,
    )
    if all(value is UNSET for value in field_values):
        raise ValueError("Debes indicar al menos un campo para actualizar.")

    with get_connection() as connection:
        global_prediction = connection.execute(
            f"SELECT {GLOBAL_PREDICTION_COLUMNS} FROM global_predictions WHERE id = ?",
            (global_prediction_id,),
        ).fetchone()
        if global_prediction is None:
            raise GlobalPredictionNotFoundError(
                f"No existe la global_prediction con id {global_prediction_id}."
            )

        next_values: dict[str, int | None] = {
            "winner_team_id": global_prediction["winner_team_id"] if winner_team_id is UNSET else winner_team_id,
            "runner_up_team_id": global_prediction["runner_up_team_id"] if runner_up_team_id is UNSET else runner_up_team_id,
            "third_place_team_id": global_prediction["third_place_team_id"] if third_place_team_id is UNSET else third_place_team_id,
            "fourth_place_team_id": global_prediction["fourth_place_team_id"] if fourth_place_team_id is UNSET else fourth_place_team_id,
            "best_player_player_id": global_prediction["best_player_player_id"] if best_player_player_id is UNSET else best_player_player_id,
            "max_scorer_player_id": global_prediction["max_scorer_player_id"] if max_scorer_player_id is UNSET else max_scorer_player_id,
            "max_assister_player_id": global_prediction["max_assister_player_id"] if max_assister_player_id is UNSET else max_assister_player_id,
            "max_yellow_cards_player_id": global_prediction["max_yellow_cards_player_id"] if max_yellow_cards_player_id is UNSET else max_yellow_cards_player_id,
            "max_red_cards_player_id": global_prediction["max_red_cards_player_id"] if max_red_cards_player_id is UNSET else max_red_cards_player_id,
        }

        _validate_global_prediction_refs(
            connection,
            next_values["winner_team_id"],
            next_values["runner_up_team_id"],
            next_values["third_place_team_id"],
            next_values["fourth_place_team_id"],
            next_values["best_player_player_id"],
            next_values["max_scorer_player_id"],
            next_values["max_assister_player_id"],
            next_values["max_yellow_cards_player_id"],
            next_values["max_red_cards_player_id"],
        )

        connection.execute(
            """
            UPDATE global_predictions
            SET winner_team_id = ?, runner_up_team_id = ?, third_place_team_id = ?,
                fourth_place_team_id = ?, best_player_player_id = ?, max_scorer_player_id = ?,
                max_assister_player_id = ?, max_yellow_cards_player_id = ?,
                max_red_cards_player_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                next_values["winner_team_id"], next_values["runner_up_team_id"],
                next_values["third_place_team_id"], next_values["fourth_place_team_id"],
                next_values["best_player_player_id"], next_values["max_scorer_player_id"],
                next_values["max_assister_player_id"], next_values["max_yellow_cards_player_id"],
                next_values["max_red_cards_player_id"], global_prediction_id,
            ),
        )
        connection.commit()

        updated = connection.execute(
            f"SELECT {GLOBAL_PREDICTION_COLUMNS} FROM global_predictions WHERE id = ?",
            (global_prediction_id,),
        ).fetchone()

    return dict(updated)


def upsertGlobalPrediction(
    prediction_id: int,
    winner_team_id: int | None = None,
    runner_up_team_id: int | None = None,
    third_place_team_id: int | None = None,
    fourth_place_team_id: int | None = None,
    best_player_player_id: int | None = None,
    max_scorer_player_id: int | None = None,
    max_assister_player_id: int | None = None,
    max_yellow_cards_player_id: int | None = None,
    max_red_cards_player_id: int | None = None,
) -> RowDict:
    init_db()
    _check_deadline()

    with get_connection() as connection:
        if not prediction_exists(connection, prediction_id):
            raise ValueError(f"No existe la prediccion con id {prediction_id}.")
        _validate_global_prediction_refs(
            connection,
            winner_team_id, runner_up_team_id, third_place_team_id, fourth_place_team_id,
            best_player_player_id, max_scorer_player_id, max_assister_player_id,
            max_yellow_cards_player_id, max_red_cards_player_id,
        )

        existing = connection.execute(
            "SELECT id FROM global_predictions WHERE prediction_id = ?",
            (prediction_id,),
        ).fetchone()

        if existing is None:
            cursor = connection.execute(
                f"""
                INSERT INTO global_predictions (
                    prediction_id, winner_team_id, runner_up_team_id, third_place_team_id,
                    fourth_place_team_id, best_player_player_id, max_scorer_player_id,
                    max_assister_player_id, max_yellow_cards_player_id, max_red_cards_player_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prediction_id, winner_team_id, runner_up_team_id, third_place_team_id,
                    fourth_place_team_id, best_player_player_id, max_scorer_player_id,
                    max_assister_player_id, max_yellow_cards_player_id, max_red_cards_player_id,
                ),
            )
            connection.commit()
            result = connection.execute(
                f"SELECT {GLOBAL_PREDICTION_COLUMNS} FROM global_predictions WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        else:
            gid = int(existing["id"])
            connection.execute(
                """
                UPDATE global_predictions
                SET winner_team_id = ?, runner_up_team_id = ?, third_place_team_id = ?,
                    fourth_place_team_id = ?, best_player_player_id = ?, max_scorer_player_id = ?,
                    max_assister_player_id = ?, max_yellow_cards_player_id = ?,
                    max_red_cards_player_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    winner_team_id, runner_up_team_id, third_place_team_id, fourth_place_team_id,
                    best_player_player_id, max_scorer_player_id, max_assister_player_id,
                    max_yellow_cards_player_id, max_red_cards_player_id, gid,
                ),
            )
            connection.commit()
            result = connection.execute(
                f"SELECT {GLOBAL_PREDICTION_COLUMNS} FROM global_predictions WHERE id = ?",
                (gid,),
            ).fetchone()

    return dict(result)


def getGlobalPredictionByPredictionId(prediction_id: int) -> RowDict:
    init_db()

    with get_connection() as connection:
        global_prediction = connection.execute(
            f"SELECT {GLOBAL_PREDICTION_COLUMNS} FROM global_predictions WHERE prediction_id = ?",
            (prediction_id,),
        ).fetchone()

    if global_prediction is None:
        raise GlobalPredictionNotFoundError(
            f"No existe la global_prediction para prediction {prediction_id}."
        )

    return dict(global_prediction)
