from __future__ import annotations

from database.init_db import get_connection, init_db
from database.types import JsonList


def getPlayersOverview() -> JsonList:
    init_db()

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                players.id,
                players.team_id,
                players.name,
                players.surname,
                players.number,
                players.num_goals,
                players.num_assists,
                players.num_yellow_cards,
                players.num_red_cards,
                players.created_at,
                players.updated_at,
                teams.name AS team_name,
                teams.fifa_slug AS team_fifa_slug,
                teams.group_id AS team_group_id,
                groups.letter AS team_group_letter
            FROM players
            INNER JOIN teams ON teams.id = players.team_id
            INNER JOIN groups ON groups.id = teams.group_id
            ORDER BY
                teams.name ASC,
                players.number ASC,
                players.surname ASC,
                players.name ASC,
                players.id ASC
            """
        ).fetchall()

    return [
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
            "team_name": row["team_name"],
            "team_fifa_slug": row["team_fifa_slug"],
            "team_group_id": row["team_group_id"],
            "team_group_letter": row["team_group_letter"],
        }
        for row in rows
    ]
