from __future__ import annotations

import html
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.init_db import DB_PATH, SCHEMA_PATH, get_connection, init_db
from database.normalize import normalize_optional_text, normalize_required_text, normalize_slug, normalize_spaces


WIKIPEDIA_GROUP_URLS = [
    "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_A",
    "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_B",
    "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_C",
    "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_D",
    "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_E",
    "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_F",
    "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_G",
    "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_H",
    "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_I",
    "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_J",
    "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_K",
    "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_L",
]

TEAM_SLUG_OVERRIDES = {
    "Argentina": "ARG",
    "Australia": "AUS",
    "Austria": "AUT",
    "Belgium": "BEL",
    "Bosnia and Herzegovina": "BIH",
    "Brazil": "BRA",
    "Cape Verde": "CPV",
    "Canada": "CAN",
    "Costa Rica": "CRC",
    "Cura\u00e7ao": "CUW",
    "Czech Republic": "CZE",
    "DR Congo": "COD",
    "Egypt": "EGY",
    "England": "ENG",
    "France": "FRA",
    "Haiti": "HAI",
    "Iran": "IRN",
    "Iraq": "IRQ",
    "Ivory Coast": "CIV",
    "Japan": "JPN",
    "Mexico": "MEX",
    "Morocco": "MAR",
    "Netherlands": "NED",
    "New Zealand": "NZL",
    "Norway": "NOR",
    "Panama": "PAN",
    "Paraguay": "PAR",
    "Portugal": "POR",
    "Saudi Arabia": "KSA",
    "Scotland": "SCO",
    "Senegal": "SEN",
    "South Africa": "RSA",
    "South Korea": "KOR",
    "Spain": "ESP",
    "Switzerland": "SUI",
    "Turkey": "TUR",
    "United States": "USA",
    "Uruguay": "URU",
    "Uzbekistan": "UZB",
    "Wales": "WAL",
}

CITY_UTC_OFFSETS = {
    "Arlington": "-05:00",
    "Atlanta": "-04:00",
    "East Rutherford": "-04:00",
    "Foxborough": "-04:00",
    "Guadalupe": "-06:00",
    "Houston": "-05:00",
    "Inglewood": "-07:00",
    "Kansas City": "-05:00",
    "Mexico City": "-06:00",
    "Miami Gardens": "-04:00",
    "Philadelphia": "-04:00",
    "Santa Clara": "-07:00",
    "Seattle": "-07:00",
    "Toronto": "-04:00",
    "Vancouver": "-07:00",
    "Zapopan": "-06:00",
}


def fetch_raw_page(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def clean_team_name(name: str) -> str:
    cleaned_name = name.replace("Korea Republic", "South Korea").replace("Czechia", "Czech Republic")
    cleaned_name = re.sub(r"\s*\(H\)$", "", cleaned_name)
    return normalize_required_text(cleaned_name, "team_name")


def strip_tags(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "", value)
    return normalize_required_text(html.unescape(without_tags).replace("\xa0", " "), "html_text")


def build_fifa_slug(team_name: str) -> str:
    if team_name in TEAM_SLUG_OVERRIDES:
        return TEAM_SLUG_OVERRIDES[team_name]
    letters = re.sub(r"[^A-Za-z]", "", team_name).upper()
    return normalize_slug(letters[:3], "fifa_slug")


def parse_kickoff_at(date_text: str, time_text: str, venue: str | None) -> str:
    normalized_date = strip_tags(date_text).replace(" ,", ",")
    normalized_date = re.sub(r"\s*\(\d{4}-\d{2}-\d{2}\)$", "", normalized_date).strip()
    normalized_time = strip_tags(time_text)
    timezone_match = re.search(r"UTC([+\-\u2212]\d+)", normalized_time)
    meridiem_time = normalized_time.split("UTC")[0].strip()
    meridiem_time = meridiem_time.replace("a.m.", "AM").replace("p.m.", "PM")
    timestamp = f"{normalized_date} {meridiem_time}"
    from datetime import datetime

    kickoff = datetime.strptime(timestamp, "%B %d, %Y %I:%M %p")
    if timezone_match is not None:
        offset_hours = int(timezone_match.group(1).replace("\u2212", "-"))
        offset = f"{offset_hours:+03d}:00"
    else:
        if venue is None or "," not in venue:
            raise ValueError("No se ha podido inferir la zona horaria del partido.")
        city = normalize_spaces(venue.split(",")[-1])
        offset = CITY_UTC_OFFSETS.get(city)
        if offset is None:
            raise ValueError(f"No hay offset configurado para la ciudad '{city}'.")
    return f"{kickoff.strftime('%Y-%m-%dT%H:%M:%S')}{offset}"


def parse_group_page(page_url: str, html_text: str) -> tuple[dict[str, str | list[str]], list[dict[str, str | None]]]:
    group_match = re.search(r"Group_([A-L])", page_url)
    if group_match is None:
        raise ValueError("No se ha podido extraer la letra del grupo desde la URL.")
    group_letter = group_match.group(1)

    match_blocks = re.findall(
        r'<div itemscope="" itemtype="http&#58;//schema.org/SportsEvent" class="footballbox".*?</div></div>',
        html_text,
        flags=re.DOTALL,
    )
    if len(match_blocks) != 6:
        raise ValueError(f"Se esperaban 6 partidos en el grupo {group_letter} y se han encontrado {len(match_blocks)}.")

    teams: list[str] = []
    matches = []
    for block in match_blocks:
        local_team_match = re.search(r'class="fhome".*?<a [^>]*>([^<]+)</a>', block, flags=re.DOTALL)
        away_team_match = re.search(r'class="faway".*?<a [^>]*>([^<]+)</a>', block, flags=re.DOTALL)
        date_match = re.search(r'class="fdate">(.*?)</div>', block, flags=re.DOTALL)
        time_match = re.search(r'class="ftime">(.*?)</div>', block, flags=re.DOTALL)
        venue_match = re.search(
            r'itemprop="name address">(.*?)</span>',
            block,
            flags=re.DOTALL,
        )
        if (
            local_team_match is None
            or away_team_match is None
            or date_match is None
            or time_match is None
        ):
            continue

        local_team_name = clean_team_name(strip_tags(local_team_match.group(1)))
        away_team_name = clean_team_name(strip_tags(away_team_match.group(1)))
        if local_team_name not in teams:
            teams.append(local_team_name)
        if away_team_name not in teams:
            teams.append(away_team_name)

        parsed_venue = None
        if venue_match is not None:
            parsed_venue = normalize_optional_text(strip_tags(venue_match.group(1)))
        kickoff_at = parse_kickoff_at(date_match.group(1), time_match.group(1), parsed_venue)

        matches.append(
            {
                "stage": "groups",
                "group_letter": group_letter,
                "local_team_name": local_team_name,
                "away_team_name": away_team_name,
                "kickoff_at": kickoff_at,
                "venue": parsed_venue,
            }
        )

    return (
        {
            "letter": group_letter,
            "teams": teams,
        },
        matches,
    )


def recreate_group_stage_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        DROP TABLE IF EXISTS user_sessions;
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS matches;
        DROP TABLE IF EXISTS players;
        DROP TABLE IF EXISTS teams;
        DROP TABLE IF EXISTS groups;
        """
    )
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def seed_world_cup_group_stage() -> Path:
    init_db()
    groups_data: list[dict[str, object]] = []
    matches_data: list[dict[str, object]] = []

    for url in WIKIPEDIA_GROUP_URLS:
        html_text = fetch_raw_page(url)
        group_data, group_matches = parse_group_page(url, html_text)
        groups_data.append(group_data)
        matches_data.extend(group_matches)

    with get_connection() as connection:
        recreate_group_stage_tables(connection)

        group_ids: dict[str, int] = {}
        for group_data in groups_data:
            cursor = connection.execute(
                "INSERT INTO groups (letter) VALUES (?)",
                (str(group_data["letter"]),),
            )
            group_ids[str(group_data["letter"])] = int(cursor.lastrowid)

        team_ids: dict[str, int] = {}
        for group_data in groups_data:
            group_id = group_ids[str(group_data["letter"])]
            for team_name in group_data["teams"]:
                if team_name in team_ids:
                    continue
                cursor = connection.execute(
                    """
                    INSERT INTO teams (name, fifa_slug, group_id)
                    VALUES (?, ?, ?)
                    """,
                    (
                        team_name,
                        build_fifa_slug(team_name),
                        group_id,
                    ),
                )
                team_ids[team_name] = int(cursor.lastrowid)

        for match_data in matches_data:
            connection.execute(
                """
                INSERT INTO matches (
                    stage,
                    group_id,
                    local_team_id,
                    away_team_id,
                    kickoff_at,
                    venue,
                    has_penalties
                )
                VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    "groups",
                    group_ids[str(match_data["group_letter"])],
                    team_ids[str(match_data["local_team_name"])],
                    team_ids[str(match_data["away_team_name"])],
                    str(match_data["kickoff_at"]),
                    match_data["venue"],
                ),
            )

        connection.commit()

    return DB_PATH


if __name__ == "__main__":
    print("ATENCION: Este script borrara TODAS las tablas (users, user_sessions, matches, players, teams, groups)")
    print("y las recreara desde cero con los datos de la fase de grupos del Mundial 2026.")
    respuesta = input("Escribe 'SI' para continuar: ")
    if respuesta.strip() != "SI":
        print("Operacion cancelada.")
        sys.exit(0)
    seeded_db_path = seed_world_cup_group_stage()
    print(f"Datos cargados en: {seeded_db_path}")
