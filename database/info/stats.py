from __future__ import annotations

import sqlite3

from database.init_db import get_connection, init_db
from database.types import JsonDict


MAX_STATS_RANGE = 50
DEFAULT_RANGE_START = 1
DEFAULT_RANGE_END = 20

STAT_COLUMNS: dict[str, str] = {
    "scorers": "num_goals",
    "assisters": "num_assists",
    "yellows": "num_yellow_cards",
    "reds": "num_red_cards",
}


def _validate_range(start: int, end: int) -> tuple[int, int]:
    if start < 1:
        raise ValueError("start debe ser mayor o igual que 1.")
    if end < start:
        raise ValueError("end debe ser mayor o igual que start.")
    if end - start + 1 > MAX_STATS_RANGE:
        raise ValueError("No puedes pedir mas de 50 resultados por llamada.")
    return start, end


def _serialize_player_stat_row(row: sqlite3.Row, stat_key: str, stat_value: int, rank: int) -> JsonDict:
    return {
        "rank": rank,
        "player": {
            "id": row["id"],
            "team_id": row["team_id"],
            "name": row["name"],
            "surname": row["surname"],
            "number": row["number"],
        },
        "team": {
            "id": row["team_id"],
            "name": row["team_name"],
            "fifa_slug": row["team_fifa_slug"],
            "group_id": row["group_id"],
        },
        stat_key: stat_value,
    }


def _get_player_stats(stat_name: str, start: int = DEFAULT_RANGE_START, end: int = DEFAULT_RANGE_END) -> JsonDict:
    validated_start, validated_end = _validate_range(start, end)
    stat_column = STAT_COLUMNS[stat_name]
    limit = validated_end - validated_start + 1
    offset = validated_start - 1

    init_db()

    with get_connection() as connection:
        total = connection.execute("SELECT COUNT(*) FROM players").fetchone()[0]
        rows = connection.execute(
            f"""
            SELECT
                players.id,
                players.team_id,
                players.name,
                players.surname,
                players.number,
                players.{stat_column} AS stat_value,
                teams.name AS team_name,
                teams.fifa_slug AS team_fifa_slug,
                teams.group_id AS group_id
            FROM players
            INNER JOIN teams ON teams.id = players.team_id
            ORDER BY
                players.{stat_column} DESC,
                teams.name ASC,
                players.surname ASC,
                players.name ASC,
                players.number ASC,
                players.id ASC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

    items = [
        _serialize_player_stat_row(
            row=row,
            stat_key=stat_name,
            stat_value=int(row["stat_value"]),
            rank=validated_start + index,
        )
        for index, row in enumerate(rows)
    ]

    return {
        "range": {
            "start": validated_start,
            "end": validated_start + len(items) - 1 if items else validated_start - 1,
            "requested_end": validated_end,
            "max_per_request": MAX_STATS_RANGE,
        },
        "total_players": int(total),
        "items": items,
    }


def getScorers(start: int = DEFAULT_RANGE_START, end: int = DEFAULT_RANGE_END) -> JsonDict:
    return _get_player_stats("scorers", start, end)


def getAssisters(start: int = DEFAULT_RANGE_START, end: int = DEFAULT_RANGE_END) -> JsonDict:
    return _get_player_stats("assisters", start, end)


def getYellows(start: int = DEFAULT_RANGE_START, end: int = DEFAULT_RANGE_END) -> JsonDict:
    return _get_player_stats("yellows", start, end)


def getReds(start: int = DEFAULT_RANGE_START, end: int = DEFAULT_RANGE_END) -> JsonDict:
    return _get_player_stats("reds", start, end)
