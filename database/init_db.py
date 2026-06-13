import os
from pathlib import Path
import sqlite3
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from database.seeds.static_data import seed_static_data_if_empty
from database.types import SqliteValue

load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "porra.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
POSTGRES_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.postgres.sql"


def get_database_url() -> str | None:
    value = os.getenv("DATABASE_URL")
    return value.strip() if isinstance(value, str) and value.strip() else None


def is_postgres_enabled() -> bool:
    return get_database_url() is not None


class PostgresCursor:
    def __init__(self, cursor: Any, lastrowid: int | None = None, prefetched_row: Any = None):
        self._cursor = cursor
        self.lastrowid = lastrowid
        self._prefetched_row = prefetched_row

    def fetchone(self) -> Any:
        if self._prefetched_row is not None:
            row = self._prefetched_row
            self._prefetched_row = None
            return None if row is None else CompatRow(row)
        row = self._cursor.fetchone()
        return None if row is None else CompatRow(row)

    def fetchall(self) -> list[Any]:
        return [CompatRow(row) for row in self._cursor.fetchall()]


class CompatRow(dict):
    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class PostgresConnection:
    def __init__(self, connection: psycopg.Connection):
        self._connection = connection

    def __enter__(self) -> "PostgresConnection":
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool | None:
        return self._connection.__exit__(exc_type, exc, tb)

    def execute(self, query: str, params: tuple[Any, ...] | list[Any] = ()) -> PostgresCursor:
        sql = _to_postgres_query(query)
        should_return_id = _looks_like_insert_without_returning(sql)
        if should_return_id:
            sql = f"{sql.rstrip().rstrip(';')} RETURNING id"
        cursor = self._connection.execute(sql, tuple(params))
        prefetched_row = None
        lastrowid = None
        if should_return_id:
            prefetched_row = cursor.fetchone()
            if prefetched_row is not None:
                lastrowid = int(prefetched_row["id"])
        return PostgresCursor(cursor, lastrowid, prefetched_row=prefetched_row)

    def commit(self) -> None:
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()


def _to_postgres_query(query: str) -> str:
    return query.replace("?", "%s")


def _looks_like_insert_without_returning(query: str) -> bool:
    normalized = query.lstrip().lower()
    return normalized.startswith("insert ") and " returning " not in normalized


def _sync_postgres_sequences(connection: PostgresConnection) -> None:
    tables = (
        "users",
        "user_sessions",
        "groups",
        "teams",
        "players",
        "matches",
        "predictions",
        "match_predictions",
        "global_predictions",
        "chat_messages",
    )
    for table_name in tables:
        connection.execute(
            """
            SELECT setval(
                pg_get_serial_sequence(?, 'id'),
                COALESCE((SELECT MAX(id) FROM %s), 1),
                (SELECT MAX(id) IS NOT NULL FROM %s)
            )
            """
            % (table_name, table_name),
            (table_name,),
        )


def _acquire_postgres_init_lock(connection: PostgresConnection) -> None:
    connection.execute("SELECT pg_advisory_xact_lock(hashtext('porra_init_db'))")


def _run_migrations(connection: sqlite3.Connection) -> None:
    match_columns: set[str] = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(matches)").fetchall()
    }
    if match_columns and "scorer_ids" not in match_columns:
        connection.execute(
            "ALTER TABLE matches ADD COLUMN scorer_ids TEXT NOT NULL DEFAULT '[]'"
        )
    if match_columns and "own_goal_ids" not in match_columns:
        connection.execute(
            "ALTER TABLE matches ADD COLUMN own_goal_ids TEXT NOT NULL DEFAULT '[]'"
        )
    if match_columns and "assists_ids" not in match_columns:
        connection.execute(
            "ALTER TABLE matches ADD COLUMN assists_ids TEXT NOT NULL DEFAULT '[]'"
        )
    if match_columns and "yellow_card_ids" not in match_columns:
        connection.execute(
            "ALTER TABLE matches ADD COLUMN yellow_card_ids TEXT NOT NULL DEFAULT '[]'"
        )
    if match_columns and "red_card_ids" not in match_columns:
        connection.execute(
            "ALTER TABLE matches ADD COLUMN red_card_ids TEXT NOT NULL DEFAULT '[]'"
        )
    if match_columns and "has_extra_time" not in match_columns:
        connection.execute(
            "ALTER TABLE matches ADD COLUMN has_extra_time INTEGER NOT NULL DEFAULT 0 CHECK (has_extra_time IN (0, 1))"
        )
    player_columns: set[str] = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(players)").fetchall()
    }
    if player_columns and "num_goals" not in player_columns:
        connection.execute(
            "ALTER TABLE players ADD COLUMN num_goals INTEGER NOT NULL DEFAULT 0"
        )
    if player_columns and "num_assists" not in player_columns:
        connection.execute(
            "ALTER TABLE players ADD COLUMN num_assists INTEGER NOT NULL DEFAULT 0"
        )
    if player_columns and "num_yellow_cards" not in player_columns:
        connection.execute(
            "ALTER TABLE players ADD COLUMN num_yellow_cards INTEGER NOT NULL DEFAULT 0"
        )
    if player_columns and "num_red_cards" not in player_columns:
        connection.execute(
            "ALTER TABLE players ADD COLUMN num_red_cards INTEGER NOT NULL DEFAULT 0"
        )
    match_prediction_columns: set[str] = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(match_predictions)").fetchall()
    }
    if match_prediction_columns and "winner_team_id" not in match_prediction_columns:
        connection.execute(
            "ALTER TABLE match_predictions ADD COLUMN winner_team_id INTEGER DEFAULT NULL REFERENCES teams(id) ON DELETE SET NULL"
        )
    if match_prediction_columns and "has_extra_time" not in match_prediction_columns:
        connection.execute(
            "ALTER TABLE match_predictions ADD COLUMN has_extra_time INTEGER NOT NULL DEFAULT 0 CHECK (has_extra_time IN (0, 1))"
        )
    if match_prediction_columns and "has_penalties" not in match_prediction_columns:
        connection.execute(
            "ALTER TABLE match_predictions ADD COLUMN has_penalties INTEGER NOT NULL DEFAULT 0 CHECK (has_penalties IN (0, 1))"
        )
    global_prediction_columns: set[str] = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(global_predictions)").fetchall()
    }
    if global_prediction_columns and "best_player_player_id" not in global_prediction_columns:
        connection.execute(
            "ALTER TABLE global_predictions ADD COLUMN best_player_player_id INTEGER DEFAULT NULL REFERENCES players(id) ON DELETE SET NULL"
        )
    if global_prediction_columns and "best_gk_player_id" not in global_prediction_columns:
        connection.execute(
            "ALTER TABLE global_predictions ADD COLUMN best_gk_player_id INTEGER DEFAULT NULL REFERENCES players(id) ON DELETE SET NULL"
        )
    if global_prediction_columns and "best_young_player_id" not in global_prediction_columns:
        connection.execute(
            "ALTER TABLE global_predictions ADD COLUMN best_young_player_id INTEGER DEFAULT NULL REFERENCES players(id) ON DELETE SET NULL"
        )
    if global_prediction_columns and "revelation_team_id" not in global_prediction_columns:
        connection.execute(
            "ALTER TABLE global_predictions ADD COLUMN revelation_team_id INTEGER DEFAULT NULL REFERENCES teams(id) ON DELETE SET NULL"
        )
    if global_prediction_columns and "disappointment_team_id" not in global_prediction_columns:
        connection.execute(
            "ALTER TABLE global_predictions ADD COLUMN disappointment_team_id INTEGER DEFAULT NULL REFERENCES teams(id) ON DELETE SET NULL"
        )
    if global_prediction_columns and "revelation_player_id" not in global_prediction_columns:
        connection.execute(
            "ALTER TABLE global_predictions ADD COLUMN revelation_player_id INTEGER DEFAULT NULL REFERENCES players(id) ON DELETE SET NULL"
        )
    if global_prediction_columns and "disappointment_player_id" not in global_prediction_columns:
        connection.execute(
            "ALTER TABLE global_predictions ADD COLUMN disappointment_player_id INTEGER DEFAULT NULL REFERENCES players(id) ON DELETE SET NULL"
        )
    chat_columns: set[str] = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(chat_messages)").fetchall()
    }
    if not chat_columns:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT,
                image_url TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )


def _run_postgres_migrations(connection: PostgresConnection) -> None:
    current_schema_row = connection.execute("SELECT current_schema() AS schema_name").fetchone()
    current_schema_name = str(current_schema_row["schema_name"]) if current_schema_row is not None else "public"
    table_columns: dict[str, set[str]] = {}

    def get_columns(table_name: str) -> set[str]:
        if table_name not in table_columns:
            table_columns[table_name] = {
                str(row["column_name"])
                for row in connection.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = ? AND table_name = ?
                    """,
                    (current_schema_name, table_name),
                ).fetchall()
            }
        return table_columns[table_name]

    match_columns = get_columns("matches")
    if match_columns:
        new_match_columns = [
            ("scorer_ids", "TEXT NOT NULL DEFAULT '[]'"),
            ("own_goal_ids", "TEXT NOT NULL DEFAULT '[]'"),
            ("assists_ids", "TEXT NOT NULL DEFAULT '[]'"),
            ("yellow_card_ids", "TEXT NOT NULL DEFAULT '[]'"),
            ("red_card_ids", "TEXT NOT NULL DEFAULT '[]'"),
            ("has_extra_time", "INTEGER NOT NULL DEFAULT 0 CHECK (has_extra_time IN (0, 1))"),
            ("has_penalties", "INTEGER NOT NULL DEFAULT 0 CHECK (has_penalties IN (0, 1))"),
            ("local_penalties", "INTEGER"),
            ("away_penalties", "INTEGER"),
        ]
        for col_name, col_def in new_match_columns:
            if col_name not in match_columns:
                connection.execute(
                    f"ALTER TABLE matches ADD COLUMN IF NOT EXISTS {col_name} {col_def}"
                )

    player_columns = get_columns("players")
    if player_columns:
        new_player_columns = [
            ("num_goals", "INTEGER NOT NULL DEFAULT 0"),
            ("num_assists", "INTEGER NOT NULL DEFAULT 0"),
            ("num_yellow_cards", "INTEGER NOT NULL DEFAULT 0"),
            ("num_red_cards", "INTEGER NOT NULL DEFAULT 0"),
        ]
        for col_name, col_def in new_player_columns:
            if col_name not in player_columns:
                connection.execute(
                    f"ALTER TABLE players ADD COLUMN IF NOT EXISTS {col_name} {col_def}"
                )

    match_prediction_columns = get_columns("match_predictions")
    if match_prediction_columns:
        new_match_prediction_columns = [
            ("winner_team_id", "INTEGER DEFAULT NULL REFERENCES teams(id) ON DELETE SET NULL"),
            ("has_extra_time", "INTEGER NOT NULL DEFAULT 0 CHECK (has_extra_time IN (0, 1))"),
            ("has_penalties", "INTEGER NOT NULL DEFAULT 0 CHECK (has_penalties IN (0, 1))"),
        ]
        for col_name, col_def in new_match_prediction_columns:
            if col_name not in match_prediction_columns:
                connection.execute(
                    f"ALTER TABLE match_predictions ADD COLUMN IF NOT EXISTS {col_name} {col_def}"
                )

    global_prediction_columns = get_columns("global_predictions")
    if not global_prediction_columns:
        return
    new_columns = [
        ("best_player_player_id", "INTEGER DEFAULT NULL REFERENCES players(id) ON DELETE SET NULL"),
        ("best_gk_player_id", "INTEGER DEFAULT NULL REFERENCES players(id) ON DELETE SET NULL"),
        ("best_young_player_id", "INTEGER DEFAULT NULL REFERENCES players(id) ON DELETE SET NULL"),
        ("max_scorer_player_id", "INTEGER DEFAULT NULL REFERENCES players(id) ON DELETE SET NULL"),
        ("max_assister_player_id", "INTEGER DEFAULT NULL REFERENCES players(id) ON DELETE SET NULL"),
        ("max_yellow_cards_player_id", "INTEGER DEFAULT NULL REFERENCES players(id) ON DELETE SET NULL"),
        ("max_red_cards_player_id", "INTEGER DEFAULT NULL REFERENCES players(id) ON DELETE SET NULL"),
        ("revelation_team_id", "INTEGER DEFAULT NULL REFERENCES teams(id) ON DELETE SET NULL"),
        ("disappointment_team_id", "INTEGER DEFAULT NULL REFERENCES teams(id) ON DELETE SET NULL"),
        ("revelation_player_id", "INTEGER DEFAULT NULL REFERENCES players(id) ON DELETE SET NULL"),
        ("disappointment_player_id", "INTEGER DEFAULT NULL REFERENCES players(id) ON DELETE SET NULL"),
    ]
    for col_name, col_def in new_columns:
        if col_name not in global_prediction_columns:
            connection.execute(
                f"ALTER TABLE global_predictions ADD COLUMN IF NOT EXISTS {col_name} {col_def}"
            )


def init_db() -> Path:
    if is_postgres_enabled():
        with get_connection() as connection:
            _acquire_postgres_init_lock(connection)
            connection.execute(POSTGRES_SCHEMA_PATH.read_text(encoding="utf-8"))
            _run_postgres_migrations(connection)
            seed_static_data_if_empty(connection)
            _sync_postgres_sequences(connection)
            connection.commit()
        return Path("postgres://DATABASE_URL")

    DATA_DIR.mkdir(exist_ok=True)

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _run_migrations(connection)
        seed_static_data_if_empty(connection)
        connection.commit()

    return DB_PATH


def get_connection() -> sqlite3.Connection:
    if is_postgres_enabled():
        database_url = get_database_url()
        assert database_url is not None
        return PostgresConnection(psycopg.connect(database_url, row_factory=dict_row))

    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.row_factory = sqlite3.Row
    return connection


if __name__ == "__main__":
    created_path = init_db()
    print(f"Base de datos creada en: {created_path}")
