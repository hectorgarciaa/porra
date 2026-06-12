from __future__ import annotations

import sqlite3

from database.init_db import get_connection, init_db
from database.predictions.predictions import updatePredictionPoints
from database.types import JsonDict, JsonList

POINTS_EXACT_SCORE = 7
POINTS_CORRECT_SIGN = 3
POINTS_CORRECT_GOAL_DIFFERENCE = 1
POINTS_CORRECT_ONE_TEAM_GOALS = 1


def _get_match_sign(local_goals: int, away_goals: int) -> int:
    if local_goals > away_goals:
        return 1
    if local_goals < away_goals:
        return -1
    return 0


def calculate_match_prediction_points(
    actual_local_goals: int | None,
    actual_away_goals: int | None,
    predicted_local_goals: int,
    predicted_away_goals: int,
) -> int:
    if actual_local_goals is None or actual_away_goals is None:
        return 0

    if predicted_local_goals == actual_local_goals and predicted_away_goals == actual_away_goals:
        return POINTS_EXACT_SCORE

    points = 0

    if _get_match_sign(predicted_local_goals, predicted_away_goals) == _get_match_sign(actual_local_goals, actual_away_goals):
        points += POINTS_CORRECT_SIGN

    if predicted_local_goals - predicted_away_goals == actual_local_goals - actual_away_goals:
        points += POINTS_CORRECT_GOAL_DIFFERENCE

    if predicted_local_goals == actual_local_goals or predicted_away_goals == actual_away_goals:
        points += POINTS_CORRECT_ONE_TEAM_GOALS

    return points


def build_prediction_points_by_match(connection: sqlite3.Connection) -> tuple[JsonList, dict[int, int]]:
    users = connection.execute(
        """
        SELECT id, name, img
        FROM users
        ORDER BY lower(name), id
        """
    ).fetchall()
    predictions = connection.execute(
        """
        SELECT id, player_id
        FROM predictions
        ORDER BY id
        """
    ).fetchall()
    played_matches = connection.execute(
        """
        SELECT
            id,
            stage,
            group_id,
            kickoff_at,
            venue,
            local_team_id,
            away_team_id,
            local_goals,
            away_goals,
            winner_id,
            has_extra_time,
            has_penalties,
            local_penalties,
            away_penalties
        FROM matches
        WHERE local_goals IS NOT NULL AND away_goals IS NOT NULL
        ORDER BY kickoff_at, id
        """
    ).fetchall()
    prediction_rows = connection.execute(
        """
        SELECT prediction_id, match_id, local_goals, away_goals
        FROM match_predictions
        """
    ).fetchall()

    prediction_by_user_id: dict[int, int] = {
        int(row["player_id"]): int(row["id"])
        for row in predictions
    }
    match_prediction_map: dict[tuple[int, int], tuple[int, int]] = {
        (int(row["prediction_id"]), int(row["match_id"])): (
            int(row["local_goals"]),
            int(row["away_goals"]),
        )
        for row in prediction_rows
    }

    cumulative_points_by_user_id: dict[int, int] = {
        int(row["id"]): 0
        for row in users
    }

    events: JsonList = []
    for match in played_matches:
        match_id = int(match["id"])
        user_scores: JsonList = []

        for user in users:
            user_id = int(user["id"])
            prediction_id = prediction_by_user_id.get(user_id)
            points_delta = 0
            if prediction_id is not None:
                predicted_score = match_prediction_map.get((prediction_id, match_id))
                if predicted_score is not None:
                    points_delta = calculate_match_prediction_points(
                        actual_local_goals=int(match["local_goals"]),
                        actual_away_goals=int(match["away_goals"]),
                        predicted_local_goals=predicted_score[0],
                        predicted_away_goals=predicted_score[1],
                    )

            cumulative_points_by_user_id[user_id] += points_delta
            user_scores.append(
                {
                    "user": {
                        "id": user_id,
                        "name": user["name"],
                        "img": user["img"],
                    },
                    "prediction_id": prediction_id,
                    "points_delta": points_delta,
                    "points_total": cumulative_points_by_user_id[user_id],
                }
            )

        user_scores.sort(
            key=lambda item: (
                -int(item["points_total"]),
                str(item["user"]["name"]).lower(),
                int(item["user"]["id"]),
            )
        )

        events.append(
            {
                "match": {
                    "id": match_id,
                    "stage": match["stage"],
                    "group_id": match["group_id"],
                    "kickoff_at": match["kickoff_at"],
                    "venue": match["venue"],
                    "local_team_id": match["local_team_id"],
                    "away_team_id": match["away_team_id"],
                    "local_goals": match["local_goals"],
                    "away_goals": match["away_goals"],
                    "winner_id": match["winner_id"],
                    "has_extra_time": bool(match["has_extra_time"]),
                    "has_penalties": bool(match["has_penalties"]),
                    "local_penalties": match["local_penalties"],
                    "away_penalties": match["away_penalties"],
                },
                "scores": user_scores,
            }
        )

    return events, cumulative_points_by_user_id


def recalculate_all_points() -> None:
    init_db()

    with get_connection() as connection:
        predictions = connection.execute(
            "SELECT id, player_id FROM predictions ORDER BY id"
        ).fetchall()
        prediction_by_user_id: dict[int, int] = {
            int(row["player_id"]): int(row["id"])
            for row in predictions
        }

        played_matches = connection.execute(
            """
            SELECT id, local_goals, away_goals
            FROM matches
            WHERE local_goals IS NOT NULL AND away_goals IS NOT NULL
            ORDER BY kickoff_at, id
            """
        ).fetchall()
        prediction_rows = connection.execute(
            """
            SELECT prediction_id, match_id, local_goals, away_goals
            FROM match_predictions
            """
        ).fetchall()
        match_prediction_map: dict[tuple[int, int], tuple[int, int]] = {
            (int(row["prediction_id"]), int(row["match_id"])): (
                int(row["local_goals"]),
                int(row["away_goals"]),
            )
            for row in prediction_rows
        }

        cumulative_by_user: dict[int, int] = {
            int(row["player_id"]): 0
            for row in predictions
        }

        for match in played_matches:
            match_id = int(match["id"])
            for row in predictions:
                user_id = int(row["player_id"])
                prediction_id = int(row["id"])
                predicted_score = match_prediction_map.get((prediction_id, match_id))
                if predicted_score is not None:
                    cumulative_by_user[user_id] += calculate_match_prediction_points(
                        actual_local_goals=int(match["local_goals"]),
                        actual_away_goals=int(match["away_goals"]),
                        predicted_local_goals=predicted_score[0],
                        predicted_away_goals=predicted_score[1],
                    )

    for user_id, total_points in cumulative_by_user.items():
        prediction_id = prediction_by_user_id.get(user_id)
        if prediction_id is not None:
            updatePredictionPoints(prediction_id, total_points)
