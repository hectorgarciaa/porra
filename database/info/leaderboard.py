from __future__ import annotations

from database.init_db import get_connection, init_db
from database.predictions.scoring import build_prediction_points_by_match
from database.types import JsonList


def getLeaderboard() -> JsonList:
    init_db()

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                users.id,
                users.name,
                users.img,
                COALESCE(predictions.points, 0) AS points,
                predictions.id AS prediction_id,
                COALESCE((
                    SELECT COUNT(*)
                    FROM match_predictions mp
                    JOIN matches m ON m.id = mp.match_id AND m.local_goals IS NOT NULL
                    WHERE mp.prediction_id = predictions.id
                    AND mp.local_goals = m.local_goals
                    AND mp.away_goals = m.away_goals
                ), 0) AS perfect_results,
                COALESCE((
                    SELECT COUNT(*)
                    FROM match_predictions mp
                    JOIN matches m ON m.id = mp.match_id AND m.local_goals IS NOT NULL
                    WHERE mp.prediction_id = predictions.id
                    AND (
                        (mp.local_goals > mp.away_goals AND m.local_goals > m.away_goals) OR
                        (mp.local_goals < mp.away_goals AND m.local_goals < m.away_goals) OR
                        (mp.local_goals = mp.away_goals AND m.local_goals = m.away_goals)
                    )
                ), 0) AS exact_winners
            FROM users
            LEFT JOIN predictions ON predictions.player_id = users.id
            ORDER BY points DESC, lower(users.name) ASC, users.id ASC
            """
        ).fetchall()

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "img": row["img"],
            "points": int(row["points"]),
            "prediction_id": row["prediction_id"],
            "perfect_results": int(row["perfect_results"]),
            "exact_winners": int(row["exact_winners"]),
        }
        for row in rows
    ]


def getLeaderboardEvolution() -> JsonList:
    init_db()

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, letter
            FROM groups
            """
        ).fetchall()
        group_map = {
            int(row["id"]): row["letter"]
            for row in rows
        }
        team_rows = connection.execute(
            """
            SELECT id, name, fifa_slug
            FROM teams
            """
        ).fetchall()
        team_map = {
            int(row["id"]): {
                "id": row["id"],
                "name": row["name"],
                "fifa_slug": row["fifa_slug"],
            }
            for row in team_rows
        }
        events, _ = build_prediction_points_by_match(connection)

    for event in events:
        match = event["match"]
        group_id = match.pop("group_id")
        match["group"] = (
            {"id": group_id, "letter": group_map[group_id]}
            if group_id is not None and group_id in group_map
            else None
        )
        match["local_team"] = team_map.get(int(match.pop("local_team_id")))
        match["away_team"] = team_map.get(int(match.pop("away_team_id")))

    return events
