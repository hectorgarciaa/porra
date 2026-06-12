from __future__ import annotations

import json
import sqlite3

from database.info.groups import GroupNotFoundError
from database.info.matches import MatchNotFoundError
from database.info.teams import TeamNotFoundError
from database.init_db import get_connection, init_db
from database.types import JsonDict, JsonList, RowDict


def _serialize_team(row: sqlite3.Row) -> JsonDict:
    return {
        "id": row["id"],
        "name": row["name"],
        "fifa_slug": row["fifa_slug"],
        "group_id": row["group_id"],
    }


def _serialize_group(row: sqlite3.Row) -> JsonDict:
    return {
        "id": row["id"],
        "letter": row["letter"],
    }


def _serialize_match_summary(row: sqlite3.Row) -> JsonDict:
    return {
        "id": row["id"],
        "stage": row["stage"],
        "group_id": row["group_id"],
        "kickoff_at": row["kickoff_at"],
        "venue": row["venue"],
        "local_goals": row["local_goals"],
        "away_goals": row["away_goals"],
        "winner_id": row["winner_id"],
        "has_extra_time": bool(row["has_extra_time"]),
        "has_penalties": bool(row["has_penalties"]),
        "local_penalties": row["local_penalties"],
        "away_penalties": row["away_penalties"],
        "local_team": {
            "id": row["local_team_id"],
            "name": row["local_team_name"],
            "fifa_slug": row["local_team_slug"],
            "group_id": row["local_team_group_id"],
        },
        "away_team": {
            "id": row["away_team_id"],
            "name": row["away_team_name"],
            "fifa_slug": row["away_team_slug"],
            "group_id": row["away_team_group_id"],
        },
    }


def _build_player_map(connection: sqlite3.Connection, player_ids: list[int]) -> dict[int, JsonDict]:
    unique_ids = list(dict.fromkeys(player_ids))
    if not unique_ids:
        return {}

    placeholders = ", ".join("?" for _ in unique_ids)
    rows = connection.execute(
        f"""
        SELECT
            players.id,
            players.team_id,
            players.name,
            players.surname,
            players.number,
            teams.name AS team_name,
            teams.fifa_slug AS team_slug
        FROM players
        INNER JOIN teams ON teams.id = players.team_id
        WHERE players.id IN ({placeholders})
        """,
        tuple(unique_ids),
    ).fetchall()

    return {
        row["id"]: {
            "id": row["id"],
            "team_id": row["team_id"],
            "name": row["name"],
            "surname": row["surname"],
            "number": row["number"],
            "team_name": row["team_name"],
            "team_slug": row["team_slug"],
        }
        for row in rows
    }


def _expand_players(player_ids: list[int], player_map: dict[int, JsonDict]) -> JsonList:
    return [player_map[player_id] for player_id in player_ids if player_id in player_map]


def _build_group_standings(connection: sqlite3.Connection, group_id: int) -> JsonList:
    team_rows = connection.execute(
        """
        SELECT id, name, fifa_slug, group_id
        FROM teams
        WHERE group_id = ?
        ORDER BY name
        """,
        (group_id,),
    ).fetchall()

    standings = {
        row["id"]: {
            "team": _serialize_team(row),
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "points": 0,
            "goals_for": 0,
            "goals_against": 0,
            "goal_difference": 0,
        }
        for row in team_rows
    }

    match_rows = connection.execute(
        """
        SELECT local_team_id, away_team_id, local_goals, away_goals
        FROM matches
        WHERE stage = 'groups' AND group_id = ?
        """,
        (group_id,),
    ).fetchall()

    for row in match_rows:
        if row["local_goals"] is None or row["away_goals"] is None:
            continue

        local = standings[int(row["local_team_id"])]
        away = standings[int(row["away_team_id"])]
        local_goals = int(row["local_goals"])
        away_goals = int(row["away_goals"])

        local["played"] += 1
        away["played"] += 1
        local["goals_for"] += local_goals
        local["goals_against"] += away_goals
        away["goals_for"] += away_goals
        away["goals_against"] += local_goals

        if local_goals > away_goals:
            local["won"] += 1
            away["lost"] += 1
            local["points"] += 3
        elif away_goals > local_goals:
            away["won"] += 1
            local["lost"] += 1
            away["points"] += 3
        else:
            local["drawn"] += 1
            away["drawn"] += 1
            local["points"] += 1
            away["points"] += 1

    ordered_standings = list(standings.values())
    for team_row in ordered_standings:
        team_row["goal_difference"] = team_row["goals_for"] - team_row["goals_against"]

    ordered_standings.sort(
        key=lambda team_row: (
            -team_row["points"],
            -team_row["goal_difference"],
            -team_row["goals_for"],
            team_row["team"]["name"].lower(),
        )
    )
    return ordered_standings


def getGroupsOverview() -> JsonList:
    init_db()

    with get_connection() as connection:
        group_rows = connection.execute(
            """
            SELECT id, letter
            FROM groups
            ORDER BY letter
            """
        ).fetchall()

        return [
            {
                **_serialize_group(group_row),
                "standings": _build_group_standings(connection, int(group_row["id"])),
            }
            for group_row in group_rows
        ]


def getMatchesOverview() -> JsonList:
    init_db()

    with get_connection() as connection:
        match_rows = connection.execute(
            """
            SELECT
                matches.id,
                matches.stage,
                matches.group_id,
                matches.kickoff_at,
                matches.venue,
                matches.local_goals,
                matches.away_goals,
                matches.winner_id,
                matches.has_extra_time,
                matches.has_penalties,
                matches.local_penalties,
                matches.away_penalties,
                groups.letter AS group_letter,
                local_team.id AS local_team_id,
                local_team.name AS local_team_name,
                local_team.fifa_slug AS local_team_slug,
                local_team.group_id AS local_team_group_id,
                away_team.id AS away_team_id,
                away_team.name AS away_team_name,
                away_team.fifa_slug AS away_team_slug,
                away_team.group_id AS away_team_group_id
            FROM matches
            LEFT JOIN groups ON groups.id = matches.group_id
            INNER JOIN teams AS local_team ON local_team.id = matches.local_team_id
            INNER JOIN teams AS away_team ON away_team.id = matches.away_team_id
            ORDER BY matches.kickoff_at, matches.id
            """
        ).fetchall()

    matches = []
    for row in match_rows:
        match = _serialize_match_summary(row)
        if row["group_letter"] is not None:
            match["group"] = {
                "id": row["group_id"],
                "letter": row["group_letter"],
            }
        else:
            match["group"] = None
        matches.append(match)

    return matches


def getGroupOverviewById(group_id: int) -> JsonDict:
    init_db()

    with get_connection() as connection:
        group_row = connection.execute(
            """
            SELECT id, letter
            FROM groups
            WHERE id = ?
            """,
            (group_id,),
        ).fetchone()
        if group_row is None:
            raise GroupNotFoundError(f"No existe el grupo con id {group_id}.")

        match_rows = connection.execute(
            """
            SELECT
                matches.id,
                matches.stage,
                matches.group_id,
                matches.local_team_id,
                matches.away_team_id,
                matches.kickoff_at,
                matches.venue,
                matches.local_goals,
                matches.away_goals,
                matches.winner_id,
                matches.has_extra_time,
                matches.has_penalties,
                matches.local_penalties,
                matches.away_penalties,
                local_team.name AS local_team_name,
                local_team.fifa_slug AS local_team_slug,
                local_team.group_id AS local_team_group_id,
                away_team.name AS away_team_name,
                away_team.fifa_slug AS away_team_slug,
                away_team.group_id AS away_team_group_id
            FROM matches
            INNER JOIN teams AS local_team ON local_team.id = matches.local_team_id
            INNER JOIN teams AS away_team ON away_team.id = matches.away_team_id
            WHERE matches.group_id = ?
            ORDER BY matches.kickoff_at, matches.id
            """,
            (group_id,),
        ).fetchall()

        return {
            **_serialize_group(group_row),
            "standings": _build_group_standings(connection, group_id),
            "matches": [_serialize_match_summary(row) for row in match_rows],
        }


def getMatchOverviewById(match_id: int) -> JsonDict:
    init_db()

    with get_connection() as connection:
        match_row = connection.execute(
            """
            SELECT
                matches.id,
                matches.stage,
                matches.group_id,
                matches.local_team_id,
                matches.away_team_id,
                matches.kickoff_at,
                matches.venue,
                matches.local_goals,
                matches.away_goals,
                matches.winner_id,
                matches.scorer_ids,
                matches.assists_ids,
                matches.yellow_card_ids,
                matches.red_card_ids,
                matches.has_extra_time,
                matches.has_penalties,
                matches.local_penalties,
                matches.away_penalties,
                matches.created_at,
                matches.updated_at,
                groups.letter AS group_letter,
                local_team.name AS local_team_name,
                local_team.fifa_slug AS local_team_slug,
                local_team.group_id AS local_team_group_id,
                away_team.name AS away_team_name,
                away_team.fifa_slug AS away_team_slug,
                away_team.group_id AS away_team_group_id,
                winner_team.name AS winner_team_name,
                winner_team.fifa_slug AS winner_team_slug,
                winner_team.group_id AS winner_team_group_id
            FROM matches
            LEFT JOIN groups ON groups.id = matches.group_id
            INNER JOIN teams AS local_team ON local_team.id = matches.local_team_id
            INNER JOIN teams AS away_team ON away_team.id = matches.away_team_id
            LEFT JOIN teams AS winner_team ON winner_team.id = matches.winner_id
            WHERE matches.id = ?
            """,
            (match_id,),
        ).fetchone()

        if match_row is None:
            raise MatchNotFoundError(f"No existe el partido con id {match_id}.")

        scorer_ids = json.loads(match_row["scorer_ids"])
        assists_ids = json.loads(match_row["assists_ids"])
        yellow_card_ids = json.loads(match_row["yellow_card_ids"])
        red_card_ids = json.loads(match_row["red_card_ids"])

        player_map = _build_player_map(
            connection,
            scorer_ids + assists_ids + yellow_card_ids + red_card_ids,
        )

        winner_team = None
        if match_row["winner_id"] is not None:
            winner_team = {
                "id": match_row["winner_id"],
                "name": match_row["winner_team_name"],
                "fifa_slug": match_row["winner_team_slug"],
                "group_id": match_row["winner_team_group_id"],
            }

        group = None
        if match_row["group_id"] is not None:
            group = {
                "id": match_row["group_id"],
                "letter": match_row["group_letter"],
            }

        return {
            "id": match_row["id"],
            "stage": match_row["stage"],
            "group": group,
            "kickoff_at": match_row["kickoff_at"],
            "venue": match_row["venue"],
            "local_goals": match_row["local_goals"],
            "away_goals": match_row["away_goals"],
            "winner_team": winner_team,
            "has_extra_time": bool(match_row["has_extra_time"]),
            "has_penalties": bool(match_row["has_penalties"]),
            "local_penalties": match_row["local_penalties"],
            "away_penalties": match_row["away_penalties"],
            "local_team": {
                "id": match_row["local_team_id"],
                "name": match_row["local_team_name"],
                "fifa_slug": match_row["local_team_slug"],
                "group_id": match_row["local_team_group_id"],
            },
            "away_team": {
                "id": match_row["away_team_id"],
                "name": match_row["away_team_name"],
                "fifa_slug": match_row["away_team_slug"],
                "group_id": match_row["away_team_group_id"],
            },
            "scorers": _expand_players(scorer_ids, player_map),
            "assists": _expand_players(assists_ids, player_map),
            "yellow_cards": _expand_players(yellow_card_ids, player_map),
            "red_cards": _expand_players(red_card_ids, player_map),
            "created_at": match_row["created_at"],
            "updated_at": match_row["updated_at"],
        }


def getTeamOverviewById(team_id: int) -> JsonDict:
    init_db()

    with get_connection() as connection:
        team_row = connection.execute(
            """
            SELECT
                teams.id,
                teams.name,
                teams.fifa_slug,
                teams.group_id,
                teams.created_at,
                teams.updated_at,
                groups.letter AS group_letter
            FROM teams
            INNER JOIN groups ON groups.id = teams.group_id
            WHERE teams.id = ?
            """,
            (team_id,),
        ).fetchone()

        if team_row is None:
            raise TeamNotFoundError(f"No existe el equipo con id {team_id}.")

        standings = _build_group_standings(connection, int(team_row["group_id"]))
        standing_row = next(
            (row for row in standings if int(row["team"]["id"]) == int(team_id)),
            None,
        )
        group_position = None
        if standing_row is not None:
            group_position = next(
                index
                for index, row in enumerate(standings, start=1)
                if int(row["team"]["id"]) == int(team_id)
            )

        match_rows = connection.execute(
            """
            SELECT
                matches.id,
                matches.stage,
                matches.group_id,
                matches.local_team_id,
                matches.away_team_id,
                matches.kickoff_at,
                matches.venue,
                matches.local_goals,
                matches.away_goals,
                matches.winner_id,
                matches.has_extra_time,
                matches.has_penalties,
                matches.local_penalties,
                matches.away_penalties,
                local_team.name AS local_team_name,
                local_team.fifa_slug AS local_team_slug,
                local_team.group_id AS local_team_group_id,
                away_team.name AS away_team_name,
                away_team.fifa_slug AS away_team_slug,
                away_team.group_id AS away_team_group_id
            FROM matches
            INNER JOIN teams AS local_team ON local_team.id = matches.local_team_id
            INNER JOIN teams AS away_team ON away_team.id = matches.away_team_id
            WHERE matches.local_team_id = ? OR matches.away_team_id = ?
            ORDER BY matches.kickoff_at, matches.id
            """,
            (team_id, team_id),
        ).fetchall()

        matches = [_serialize_match_summary(row) for row in match_rows]

        player_rows = connection.execute(
            """
            SELECT
                id,
                team_id,
                name,
                surname,
                number,
                num_goals,
                num_assists,
                num_yellow_cards,
                num_red_cards,
                created_at,
                updated_at
            FROM players
            WHERE team_id = ?
            ORDER BY number, surname, name, id
            """,
            (team_id,),
        ).fetchall()

        players = [
            {
                "id": row["id"],
                "team_id": row["team_id"],
                "name": row["name"],
                "surname": row["surname"],
                "number": row["number"],
                "num_goals": row["num_goals"],
                "num_assists": row["num_assists"],
                "num_yellow_cards": row["num_yellow_cards"],
                "num_red_cards": row["num_red_cards"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in player_rows
        ]

        summary = {
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "points": 0,
            "goals_for": 0,
            "goals_against": 0,
            "goal_difference": 0,
            "group_position": group_position,
        }
        if standing_row is not None:
            summary.update(
                {
                    "played": standing_row["played"],
                    "won": standing_row["won"],
                    "drawn": standing_row["drawn"],
                    "lost": standing_row["lost"],
                    "points": standing_row["points"],
                    "goals_for": standing_row["goals_for"],
                    "goals_against": standing_row["goals_against"],
                    "goal_difference": standing_row["goal_difference"],
                }
            )

        return {
            "team": {
                "id": team_row["id"],
                "name": team_row["name"],
                "fifa_slug": team_row["fifa_slug"],
                "group_id": team_row["group_id"],
                "created_at": team_row["created_at"],
                "updated_at": team_row["updated_at"],
            },
            "group": {
                "id": team_row["group_id"],
                "letter": team_row["group_letter"],
            },
            "summary": summary,
            "matches": matches,
            "players": players,
        }
