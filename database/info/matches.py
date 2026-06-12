from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime

from database.init_db import get_connection, init_db
from database.normalize import normalize_optional_text, normalize_required_text
from database.types import RowDict, UNSET
ALLOWED_STAGES = {"groups", "32", "16", "qf", "sf", "3", "f"}


class MatchNotFoundError(ValueError):
    pass


def _validate_stage(stage: str) -> str:
    normalized_stage = normalize_required_text(stage, "stage").lower()
    if normalized_stage not in ALLOWED_STAGES:
        raise ValueError("El stage no es valido.")
    return normalized_stage


def _validate_match_basics(connection: sqlite3.Connection, local_team_id: int, away_team_id: int) -> None:
    if local_team_id == away_team_id:
        raise ValueError("El equipo local y visitante no pueden ser el mismo.")

    local_team = connection.execute(
        "SELECT id FROM teams WHERE id = ?",
        (local_team_id,),
    ).fetchone()
    if local_team is None:
        raise ValueError(f"No existe el equipo local con id {local_team_id}.")

    away_team = connection.execute(
        "SELECT id FROM teams WHERE id = ?",
        (away_team_id,),
    ).fetchone()
    if away_team is None:
        raise ValueError(f"No existe el equipo visitante con id {away_team_id}.")


def _validate_group_for_stage(connection: sqlite3.Connection, stage: str, group_id: int | None) -> None:
    if stage == "groups":
        if group_id is None:
            raise ValueError("Los partidos de grupos necesitan group_id.")
        group = connection.execute(
            "SELECT id FROM groups WHERE id = ?",
            (group_id,),
        ).fetchone()
        if group is None:
            raise ValueError(f"No existe el grupo con id {group_id}.")
        return

    if group_id is not None:
        raise ValueError("Solo los partidos de grupos pueden tener group_id.")


def _validate_kickoff_at(kickoff_at: str) -> str:
    normalized_kickoff_at = normalize_required_text(kickoff_at, "kickoff_at")
    try:
        datetime.fromisoformat(normalized_kickoff_at)
    except ValueError as exc:
        raise ValueError("kickoff_at debe estar en formato ISO 8601.") from exc
    return normalized_kickoff_at


def _serialize_match(row: sqlite3.Row) -> RowDict:
    match: dict[str, object] = dict(row)
    match["scorer_ids"] = json.loads(str(match.get("scorer_ids", "[]")))
    match["assists_ids"] = json.loads(str(match.get("assists_ids", "[]")))
    match["yellow_card_ids"] = json.loads(str(match.get("yellow_card_ids", "[]")))
    match["red_card_ids"] = json.loads(str(match.get("red_card_ids", "[]")))
    match["has_extra_time"] = bool(match.get("has_extra_time", 0))
    match["has_penalties"] = bool(match.get("has_penalties", 0))
    return match


def _validate_player_event_ids(
    connection: sqlite3.Connection,
    player_ids: list[int],
    local_team_id: int,
    away_team_id: int,
    field_name: str,
) -> str:
    if any(not isinstance(player_id, int) for player_id in player_ids):
        raise ValueError(f"Todos los {field_name} deben ser enteros.")

    for player_id in player_ids:
        player = connection.execute(
            """
            SELECT id, team_id
            FROM players
            WHERE id = ?
            """,
            (player_id,),
        ).fetchone()
        if player is None:
            raise ValueError(f"No existe el jugador con id {player_id}.")
        if int(player["team_id"]) not in (local_team_id, away_team_id):
            raise ValueError(f"El jugador {player_id} no pertenece a ninguno de los equipos del partido.")

    return json.dumps(player_ids)


def _apply_player_stat_delta(
    connection: sqlite3.Connection,
    old_ids: list[int],
    new_ids: list[int],
    column_name: str,
) -> None:
    old_counter = Counter(old_ids)
    new_counter = Counter(new_ids)

    for player_id in set(old_counter) | set(new_counter):
        delta = new_counter[player_id] - old_counter[player_id]
        if delta == 0:
            continue
        connection.execute(
            f"""
            UPDATE players
            SET {column_name} = {column_name} + ?
            WHERE id = ?
            """,
            (delta, player_id),
        )


def createMatch(
    stage: str,
    group_id: int | None,
    local_team_id: int,
    away_team_id: int,
    kickoff_at: str,
    venue: str | None = None,
    scorer_ids: list[int] | None = None,
    assists_ids: list[int] | None = None,
    yellow_card_ids: list[int] | None = None,
    red_card_ids: list[int] | None = None,
) -> RowDict:
    init_db()
    normalized_stage = _validate_stage(stage)
    normalized_kickoff_at = _validate_kickoff_at(kickoff_at)
    normalized_venue = normalize_optional_text(venue)

    with get_connection() as connection:
        _validate_match_basics(connection, local_team_id, away_team_id)
        _validate_group_for_stage(connection, normalized_stage, group_id)
        normalized_scorer_ids = _validate_player_event_ids(
            connection,
            [] if scorer_ids is None else scorer_ids,
            local_team_id,
            away_team_id,
            "scorer_ids",
        )
        normalized_assists_ids = _validate_player_event_ids(
            connection,
            [] if assists_ids is None else assists_ids,
            local_team_id,
            away_team_id,
            "assists_ids",
        )
        normalized_yellow_card_ids = _validate_player_event_ids(
            connection,
            [] if yellow_card_ids is None else yellow_card_ids,
            local_team_id,
            away_team_id,
            "yellow_card_ids",
        )
        normalized_red_card_ids = _validate_player_event_ids(
            connection,
            [] if red_card_ids is None else red_card_ids,
            local_team_id,
            away_team_id,
            "red_card_ids",
        )

        cursor = connection.execute(
            """
            INSERT INTO matches (
                stage,
                group_id,
                local_team_id,
                away_team_id,
                kickoff_at,
                venue,
                scorer_ids,
                assists_ids,
                yellow_card_ids,
                red_card_ids
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_stage,
                group_id,
                local_team_id,
                away_team_id,
                normalized_kickoff_at,
                normalized_venue,
                normalized_scorer_ids,
                normalized_assists_ids,
                normalized_yellow_card_ids,
                normalized_red_card_ids,
            ),
        )
        connection.commit()

        match = connection.execute(
            """
            SELECT id, stage, group_id, local_team_id, away_team_id, kickoff_at, venue,
                   local_goals, away_goals, winner_id, scorer_ids, assists_ids, yellow_card_ids, red_card_ids,
                   has_extra_time, has_penalties, local_penalties,
                   away_penalties, created_at, updated_at
            FROM matches
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return _serialize_match(match)


def setMatchResult(
    match_id: int,
    local_goals: int,
    away_goals: int,
    winner_id: int | None = None,
    scorer_ids: list[int] | None = None,
    assists_ids: list[int] | None = None,
    yellow_card_ids: list[int] | None = None,
    red_card_ids: list[int] | None = None,
    has_extra_time: bool = False,
    has_penalties: bool = False,
    local_penalties: int | None = None,
    away_penalties: int | None = None,
) -> RowDict:
    init_db()
    if local_goals < 0 or away_goals < 0:
        raise ValueError("Los goles no pueden ser negativos.")

    with get_connection() as connection:
        match = connection.execute(
            """
            SELECT id, stage, local_team_id, away_team_id, scorer_ids, assists_ids, yellow_card_ids, red_card_ids
            FROM matches
            WHERE id = ?
            """,
            (match_id,),
        ).fetchone()
        if match is None:
            raise MatchNotFoundError(f"No existe el partido con id {match_id}.")

        local_team_id = int(match["local_team_id"])
        away_team_id = int(match["away_team_id"])
        if match["stage"] == "groups" and has_penalties:
            raise ValueError("Los partidos de grupos no pueden tener penaltis.")
        normalized_scorer_ids = _validate_player_event_ids(
            connection,
            [] if scorer_ids is None else scorer_ids,
            local_team_id,
            away_team_id,
            "scorer_ids",
        )
        normalized_assists_ids = _validate_player_event_ids(
            connection,
            [] if assists_ids is None else assists_ids,
            local_team_id,
            away_team_id,
            "assists_ids",
        )
        normalized_yellow_card_ids = _validate_player_event_ids(
            connection,
            [] if yellow_card_ids is None else yellow_card_ids,
            local_team_id,
            away_team_id,
            "yellow_card_ids",
        )
        normalized_red_card_ids = _validate_player_event_ids(
            connection,
            [] if red_card_ids is None else red_card_ids,
            local_team_id,
            away_team_id,
            "red_card_ids",
        )
        old_scorer_ids = json.loads(match["scorer_ids"])
        old_assists_ids = json.loads(match["assists_ids"])
        old_yellow_card_ids = json.loads(match["yellow_card_ids"])
        old_red_card_ids = json.loads(match["red_card_ids"])
        new_scorer_ids = json.loads(normalized_scorer_ids)
        new_assists_ids = json.loads(normalized_assists_ids)
        new_yellow_card_ids = json.loads(normalized_yellow_card_ids)
        new_red_card_ids = json.loads(normalized_red_card_ids)
        if len(json.loads(normalized_scorer_ids)) != local_goals + away_goals:
            raise ValueError("La lista scorer_ids debe tener tantos elementos como goles totales del partido.")

        if match["stage"] == "groups" and has_extra_time:
            raise ValueError("Los partidos de grupos no pueden tener prorroga.")
        if has_penalties and not has_extra_time:
            raise ValueError("Si hay penaltis debe haber prorroga.")

        if has_penalties:
            if local_penalties is None or away_penalties is None:
                raise ValueError("Si hay penaltis debes indicar el marcador de penaltis.")
            if local_penalties < 0 or away_penalties < 0:
                raise ValueError("Los penaltis no pueden ser negativos.")
            if local_penalties == away_penalties:
                raise ValueError("En una tanda de penaltis no puede haber empate.")
            if local_goals != away_goals:
                raise ValueError("Si hay penaltis, el marcador tras juego/prorroga debe acabar en empate.")
            expected_winner_id = local_team_id if local_penalties > away_penalties else away_team_id
            if winner_id is None:
                winner_id = expected_winner_id
            elif winner_id != expected_winner_id:
                raise ValueError("winner_id no coincide con el ganador por penaltis.")
        else:
            if local_penalties is not None or away_penalties is not None:
                raise ValueError("No puedes indicar penaltis si has_penalties es False.")
            if match["stage"] == "groups":
                if local_goals > away_goals:
                    expected_winner_id = local_team_id
                elif away_goals > local_goals:
                    expected_winner_id = away_team_id
                else:
                    expected_winner_id = None
            else:
                if local_goals == away_goals:
                    raise ValueError("Los partidos de eliminatoria no pueden acabar en empate sin penaltis.")
                expected_winner_id = local_team_id if local_goals > away_goals else away_team_id

            if winner_id is None:
                winner_id = expected_winner_id
            elif winner_id != expected_winner_id:
                raise ValueError("winner_id no coincide con el resultado del partido.")

        if winner_id is not None and winner_id not in (local_team_id, away_team_id):
            raise ValueError("winner_id debe ser uno de los equipos del partido.")

        connection.execute(
            """
            UPDATE matches
            SET local_goals = ?, away_goals = ?, winner_id = ?, scorer_ids = ?, assists_ids = ?,
                yellow_card_ids = ?, red_card_ids = ?, has_extra_time = ?, has_penalties = ?,
                local_penalties = ?, away_penalties = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                local_goals,
                away_goals,
                winner_id,
                normalized_scorer_ids,
                normalized_assists_ids,
                normalized_yellow_card_ids,
                normalized_red_card_ids,
                1 if has_extra_time else 0,
                1 if has_penalties else 0,
                local_penalties,
                away_penalties,
                match_id,
            ),
        )
        _apply_player_stat_delta(connection, old_scorer_ids, new_scorer_ids, "num_goals")
        _apply_player_stat_delta(connection, old_assists_ids, new_assists_ids, "num_assists")
        _apply_player_stat_delta(connection, old_yellow_card_ids, new_yellow_card_ids, "num_yellow_cards")
        _apply_player_stat_delta(connection, old_red_card_ids, new_red_card_ids, "num_red_cards")
        connection.commit()

        updated_match = connection.execute(
            """
            SELECT id, stage, group_id, local_team_id, away_team_id, kickoff_at, venue,
                   local_goals, away_goals, winner_id, scorer_ids, assists_ids, yellow_card_ids, red_card_ids,
                   has_extra_time, has_penalties, local_penalties,
                   away_penalties, created_at, updated_at
            FROM matches
            WHERE id = ?
            """,
            (match_id,),
        ).fetchone()

    return _serialize_match(updated_match)


def getMatchPredictionsSummary(match_id: int) -> dict:
    init_db()

    with get_connection() as connection:
        match = connection.execute(
            "SELECT id, local_team_id, away_team_id FROM matches WHERE id = ?",
            (match_id,),
        ).fetchone()
        if match is None:
            raise MatchNotFoundError(f"No existe el partido con id {match_id}.")

        local_id = int(match["local_team_id"])
        away_id = int(match["away_team_id"])

        pred_rows = connection.execute(
            """
            SELECT mp.local_goals, mp.away_goals, u.name AS user_name, u.img AS user_img
            FROM match_predictions mp
            JOIN predictions p ON p.id = mp.prediction_id
            JOIN users u ON u.id = p.player_id
            WHERE mp.match_id = ?
            ORDER BY u.name
            """,
            (match_id,),
        ).fetchall()

    predictions = []
    votes = {"local": 0, "draw": 0, "away": 0}
    for row in pred_rows:
        local = int(row["local_goals"])
        away = int(row["away_goals"])
        predictions.append({
            "user_name": row["user_name"],
            "user_img": row["user_img"],
            "local_goals": local,
            "away_goals": away,
        })
        if local > away:
            votes["local"] += 1
        elif away > local:
            votes["away"] += 1
        else:
            votes["draw"] += 1

    return {
        "match_id": match_id,
        "predictions": predictions,
        "votes": votes,
        "total": len(predictions),
    }
