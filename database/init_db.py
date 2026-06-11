from pathlib import Path
import sqlite3

from database.types import SqliteValue


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "porra.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _run_migrations(connection: sqlite3.Connection) -> None:
    match_columns: set[str] = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(matches)").fetchall()
    }
    if match_columns and "scorer_ids" not in match_columns:
        connection.execute(
            "ALTER TABLE matches ADD COLUMN scorer_ids TEXT NOT NULL DEFAULT '[]'"
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


def init_db() -> Path:
    DATA_DIR.mkdir(exist_ok=True)

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _run_migrations(connection)
        connection.commit()

    return DB_PATH


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.row_factory = sqlite3.Row
    return connection


if __name__ == "__main__":
    created_path = init_db()
    print(f"Base de datos creada en: {created_path}")
