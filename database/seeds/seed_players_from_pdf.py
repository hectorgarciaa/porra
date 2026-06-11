from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.init_db import DB_PATH, get_connection, init_db
from database.normalize import normalize_required_text


PDF_TEAM_NAME_MAP = {
    "Cabo Verde": "Cape Verde",
    "Congo DR": "DR Congo",
    "Côte D'Ivoire": "Ivory Coast",
    "Bosnia And Herzegovina": "Bosnia and Herzegovina",
    "Czechia": "Czech Republic",
    "IR Iran": "Iran",
    "Korea Republic": "South Korea",
    "Türkiye": "Turkey",
    "USA": "United States",
}


def extract_pdf_text(pdf_path: Path) -> str:
    completed = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return completed.stdout


def normalize_team_name(raw_team_name: str) -> str:
    cleaned_team_name = normalize_required_text(raw_team_name, "team_name")
    return PDF_TEAM_NAME_MAP.get(cleaned_team_name, cleaned_team_name)


def parse_player_line(line: str) -> dict[str, str | int] | None:
    if not re.match(r"^\s*\d+\s+", line):
        return None

    parts = re.split(r"\s{2,}", line.strip())
    if len(parts) < 11:
        return None

    try:
        number = int(parts[0])
    except ValueError:
        return None

    return {
        "number": number,
        "name": normalize_required_text(parts[3], "name"),
        "surname": normalize_required_text(parts[4], "surname"),
    }


def parse_players_by_team(text: str) -> dict[str, list[dict[str, str | int]]]:
    pages = text.split("\f")
    players_by_team: dict[str, list[dict[str, str | int]]] = {}

    for page in pages:
        team_match = re.search(r"^\s*([^\n(]+)\s+\(([A-Z]{3})\)\s*$", page, flags=re.MULTILINE)
        if team_match is None:
            continue

        team_name = normalize_team_name(team_match.group(1))
        players: list[dict[str, str | int]] = []

        for line in page.splitlines():
            player_data = parse_player_line(line)
            if player_data is None:
                continue
            if int(player_data["number"]) < 1 or int(player_data["number"]) > 26:
                continue
            players.append(player_data)

        if players:
            players_by_team[team_name] = players

    return players_by_team


def recreate_players_table(connection: sqlite3.Connection) -> None:
    connection.execute("DROP TABLE IF EXISTS players")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            surname TEXT NOT NULL,
            number INTEGER NOT NULL,
            num_goals INTEGER NOT NULL DEFAULT 0,
            num_assists INTEGER NOT NULL DEFAULT 0,
            num_yellow_cards INTEGER NOT NULL DEFAULT 0,
            num_red_cards INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            UNIQUE (team_id, number)
        )
        """
    )


def seed_players_from_pdf(pdf_path: Path) -> Path:
    init_db()
    pdf_text = extract_pdf_text(pdf_path)
    players_by_team = parse_players_by_team(pdf_text)

    with get_connection() as connection:
        recreate_players_table(connection)

        teams = connection.execute(
            "SELECT id, name FROM teams ORDER BY id"
        ).fetchall()
        team_ids = {row["name"]: row["id"] for row in teams}

        missing_teams = sorted(set(players_by_team) - set(team_ids))
        if missing_teams:
            raise ValueError(f"Hay equipos del PDF que no existen en la BD: {', '.join(missing_teams)}")

        for team_name, players in players_by_team.items():
            team_id = int(team_ids[team_name])
            for player in players:
                connection.execute(
                    """
                    INSERT INTO players (team_id, name, surname, number)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        team_id,
                        str(player["name"]),
                        str(player["surname"]),
                        int(player["number"]),
                    ),
                )

        connection.commit()

    return DB_PATH


if __name__ == "__main__":
    pdf_path = Path(r"c:\Users\hecto\Downloads\SquadLists-English.pdf")
    seeded_db_path = seed_players_from_pdf(pdf_path)
    print(f"Jugadores cargados en: {seeded_db_path}")
