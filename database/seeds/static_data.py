from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


STATIC_DATA_PATH = Path(__file__).resolve().parent / "world_cup_2026_static_data.json"


def _table_count(connection: sqlite3.Connection, table_name: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def seed_static_data_if_empty(connection: sqlite3.Connection) -> bool:
    base_tables = ("groups", "teams", "matches", "players")
    counts = {table_name: _table_count(connection, table_name) for table_name in base_tables}

    if all(count > 0 for count in counts.values()):
        return False

    if any(count > 0 for count in counts.values()):
        raise RuntimeError(f"Static World Cup data is partially loaded: {counts}")

    data: dict[str, list[dict[str, Any]]] = json.loads(STATIC_DATA_PATH.read_text(encoding="utf-8"))

    for row in data["groups"]:
        connection.execute(
            "INSERT INTO groups (id, letter) VALUES (?, ?)",
            (row["id"], row["letter"]),
        )

    for row in data["teams"]:
        connection.execute(
            """
            INSERT INTO teams (id, name, fifa_slug, group_id)
            VALUES (?, ?, ?, ?)
            """,
            (row["id"], row["name"], row["fifa_slug"], row["group_id"]),
        )

    for row in data["matches"]:
        connection.execute(
            """
            INSERT INTO matches (
                id, stage, group_id, local_team_id, away_team_id, kickoff_at, venue,
                local_goals, away_goals, winner_id, scorer_ids, assists_ids,
                yellow_card_ids, red_card_ids, has_extra_time, has_penalties,
                local_penalties, away_penalties
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"], row["stage"], row["group_id"], row["local_team_id"], row["away_team_id"],
                row["kickoff_at"], row["venue"], row["local_goals"], row["away_goals"], row["winner_id"],
                row["scorer_ids"], row["assists_ids"], row["yellow_card_ids"], row["red_card_ids"],
                row["has_extra_time"], row["has_penalties"], row["local_penalties"], row["away_penalties"],
            ),
        )

    for row in data["players"]:
        connection.execute(
            """
            INSERT INTO players (
                id, team_id, name, surname, number, num_goals, num_assists,
                num_yellow_cards, num_red_cards
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"], row["team_id"], row["name"], row["surname"], row["number"],
                row["num_goals"], row["num_assists"], row["num_yellow_cards"], row["num_red_cards"],
            ),
        )

    return True
