from __future__ import annotations

import sqlite3
from collections import defaultdict

from database.predictions.global_predictions import (
    GlobalPredictionNotFoundError,
    getGlobalPredictionByPredictionId,
)
from database.predictions.match_predictions import (
    getMatchPredictionsByPrediction,
)
from database.predictions.predictions import (
    PredictionAlreadyExistsError,
    getPredictionById,
    createPrediction,
)
from database.init_db import get_connection, init_db
from database.info.matches import setMatchResult
from database.predictions.scoring import recalculate_all_points
from database.types import JsonDict, RowDict


def processMatchResult(
    match_id: int,
    local_goals: int,
    away_goals: int,
    winner_id: int | None = None,
    scorer_ids: list[int] | None = None,
    assists_ids: list[int] | None = None,
    yellow_card_ids: list[int] | None = None,
    red_card_ids: list[int] | None = None,
    has_extra_time: bool = False,
    has_penalties: bool = False,
    local_penalties: int | None = None,
    away_penalties: int | None = None,
) -> RowDict:
    match = setMatchResult(
        match_id,
        local_goals,
        away_goals,
        winner_id=winner_id,
        scorer_ids=scorer_ids,
        assists_ids=assists_ids,
        yellow_card_ids=yellow_card_ids,
        red_card_ids=red_card_ids,
        has_extra_time=has_extra_time,
        has_penalties=has_penalties,
        local_penalties=local_penalties,
        away_penalties=away_penalties,
    )
    recalculate_all_points()
    return match


def createEmptyPrediction(player_id: int) -> RowDict:
    init_db()
    try:
        prediction = createPrediction(player_id)
    except PredictionAlreadyExistsError as exc:
        raise PredictionAlreadyExistsError(
            f"El usuario {player_id} ya tiene una porra creada."
        ) from exc
    return prediction


def _get_team_map(connection: sqlite3.Connection, team_ids: list[int | None]) -> dict[int, JsonDict]:
    unique_ids = list(dict.fromkeys(team_id for team_id in team_ids if team_id is not None))
    if not unique_ids:
        return {}

    placeholders = ", ".join("?" for _ in unique_ids)
    rows = connection.execute(
        f"""
        SELECT id, name, fifa_slug, group_id
        FROM teams
        WHERE id IN ({placeholders})
        """,
        tuple(unique_ids),
    ).fetchall()

    return {
        int(row["id"]): {
            "id": row["id"],
            "name": row["name"],
            "fifa_slug": row["fifa_slug"],
            "group_id": row["group_id"],
        }
        for row in rows
    }


def _get_player_map(connection: sqlite3.Connection, player_ids: list[int | None]) -> dict[int, JsonDict]:
    unique_ids = list(dict.fromkeys(player_id for player_id in player_ids if player_id is not None))
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
            teams.fifa_slug AS team_fifa_slug
        FROM players
        INNER JOIN teams ON teams.id = players.team_id
        WHERE players.id IN ({placeholders})
        """,
        tuple(unique_ids),
    ).fetchall()

    return {
        int(row["id"]): {
            "id": row["id"],
            "team_id": row["team_id"],
            "name": row["name"],
            "surname": row["surname"],
            "number": row["number"],
            "team_name": row["team_name"],
            "team_fifa_slug": row["team_fifa_slug"],
        }
        for row in rows
    }


def _build_predicted_groups(
    connection: sqlite3.Connection,
    match_predictions: list[RowDict],
    match_map: dict[int, RowDict],
    team_map: dict[int, JsonDict],
) -> list[JsonDict]:
    group_rows = connection.execute(
        """
        SELECT
            groups.id,
            groups.letter,
            teams.id AS team_id
        FROM groups
        INNER JOIN teams ON teams.group_id = groups.id
        ORDER BY groups.letter, teams.name, teams.id
        """
    ).fetchall()

    groups: dict[int, JsonDict] = {}
    standings_by_group: dict[int, dict[int, JsonDict]] = defaultdict(dict)

    for row in group_rows:
        group_id = int(row["id"])
        team_id = int(row["team_id"])
        if group_id not in groups:
            groups[group_id] = {
                "id": group_id,
                "letter": row["letter"],
                "predicted_match_count": 0,
                "total_group_match_count": 0,
                "is_complete": False,
                "standings": [],
            }

        standings_by_group[group_id][team_id] = {
            "team": team_map.get(team_id, {"id": team_id}),
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "points": 0,
            "goals_for": 0,
            "goals_against": 0,
            "goal_difference": 0,
        }

    for match in match_map.values():
        if match["stage"] != "groups" or match["group_id"] is None:
            continue
        group_id = int(match["group_id"])
        if group_id in groups:
            groups[group_id]["total_group_match_count"] += 1

    for item in match_predictions:
        match = match_map.get(int(item["match_id"]))
        if match is None or match["stage"] != "groups" or match["group_id"] is None:
            continue

        group_id = int(match["group_id"])
        local_team_id = int(match["local_team_id"])
        away_team_id = int(match["away_team_id"])
        local_goals = int(item["local_goals"])
        away_goals = int(item["away_goals"])

        groups[group_id]["predicted_match_count"] += 1

        local_row = standings_by_group[group_id][local_team_id]
        away_row = standings_by_group[group_id][away_team_id]

        local_row["played"] += 1
        away_row["played"] += 1
        local_row["goals_for"] += local_goals
        local_row["goals_against"] += away_goals
        away_row["goals_for"] += away_goals
        away_row["goals_against"] += local_goals

        if local_goals > away_goals:
            local_row["won"] += 1
            away_row["lost"] += 1
            local_row["points"] += 3
        elif away_goals > local_goals:
            away_row["won"] += 1
            local_row["lost"] += 1
            away_row["points"] += 3
        else:
            local_row["drawn"] += 1
            away_row["drawn"] += 1
            local_row["points"] += 1
            away_row["points"] += 1

    result: list[JsonDict] = []
    for group_id, group in sorted(groups.items(), key=lambda item: item[1]["letter"]):
        standings = list(standings_by_group[group_id].values())
        for row in standings:
            row["goal_difference"] = row["goals_for"] - row["goals_against"]

        standings.sort(
            key=lambda row: (
                -int(row["points"]),
                -int(row["goal_difference"]),
                -int(row["goals_for"]),
                str(row["team"].get("name", "")),
                int(row["team"].get("id", 0)),
            )
        )

        for index, row in enumerate(standings, start=1):
            row["position"] = index

        group["standings"] = standings
        group["is_complete"] = group["predicted_match_count"] == group["total_group_match_count"]
        result.append(group)

    return result


def getFullPredictionById(prediction_id: int) -> JsonDict:
    init_db()
    prediction = getPredictionById(prediction_id)
    match_predictions = getMatchPredictionsByPrediction(prediction["id"])

    try:
        global_prediction = getGlobalPredictionByPredictionId(prediction["id"])
    except GlobalPredictionNotFoundError:
        global_prediction = None

    with get_connection() as connection:
        user = connection.execute(
            """
            SELECT id, name, img, created_at, updated_at
            FROM users
            WHERE id = ?
            """,
            (prediction["player_id"],),
        ).fetchone()

        match_ids = [int(item["match_id"]) for item in match_predictions]
        match_map: dict[int, RowDict] = {}
        team_ids: list[int | None] = []

        if match_ids:
            placeholders = ", ".join("?" for _ in match_ids)
            match_rows = connection.execute(
                f"""
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
                    groups.letter AS group_letter
                FROM matches
                LEFT JOIN groups ON groups.id = matches.group_id
                WHERE matches.id IN ({placeholders})
                """,
                tuple(match_ids),
            ).fetchall()

            for row in match_rows:
                match_map[int(row["id"])] = dict(row)
                team_ids.extend(
                    [
                        int(row["local_team_id"]),
                        int(row["away_team_id"]),
                        int(row["winner_id"]) if row["winner_id"] is not None else None,
                    ]
                )

        global_team_ids: list[int | None] = []
        global_player_ids: list[int | None] = []
        if global_prediction is not None:
            global_team_ids.extend(
                [
                    global_prediction["winner_team_id"],
                    global_prediction["runner_up_team_id"],
                    global_prediction["third_place_team_id"],
                    global_prediction["fourth_place_team_id"],
                    global_prediction["revelation_team_id"],
                    global_prediction["disappointment_team_id"],
                ]
            )
            global_player_ids.extend(
                [
                    global_prediction["best_player_player_id"],
                    global_prediction["best_gk_player_id"],
                    global_prediction["best_young_player_id"],
                    global_prediction["max_scorer_player_id"],
                    global_prediction["max_assister_player_id"],
                    global_prediction["max_yellow_cards_player_id"],
                    global_prediction["max_red_cards_player_id"],
                    global_prediction["revelation_player_id"],
                    global_prediction["disappointment_player_id"],
                ]
            )

        team_map = _get_team_map(connection, team_ids + global_team_ids)
        player_map = _get_player_map(connection, global_player_ids)

        enriched_match_predictions = []
        for item in match_predictions:
            match = match_map.get(int(item["match_id"]))
            if match is None:
                enriched_match_predictions.append(item)
                continue

            winner_team = None
            if match["winner_id"] is not None:
                winner_team = team_map.get(int(match["winner_id"]))

            enriched_match_predictions.append(
                {
                    **item,
                    "match": {
                        "id": match["id"],
                        "stage": match["stage"],
                        "group": (
                            {"id": match["group_id"], "letter": match["group_letter"]}
                            if match["group_id"] is not None
                            else None
                        ),
                        "kickoff_at": match["kickoff_at"],
                        "venue": match["venue"],
                        "local_goals": match["local_goals"],
                        "away_goals": match["away_goals"],
                        "winner_team": winner_team,
                        "has_extra_time": bool(match["has_extra_time"]),
                        "has_penalties": bool(match["has_penalties"]),
                        "local_penalties": match["local_penalties"],
                        "away_penalties": match["away_penalties"],
                        "local_team": team_map.get(int(match["local_team_id"])),
                        "away_team": team_map.get(int(match["away_team_id"])),
                    },
                    "winner_team": team_map.get(item["winner_team_id"]) if item["winner_team_id"] is not None else None,
                }
            )

        enriched_global_prediction = None
        if global_prediction is not None:
            enriched_global_prediction = {
                **global_prediction,
                "winner_team": team_map.get(global_prediction["winner_team_id"]),
                "runner_up_team": team_map.get(global_prediction["runner_up_team_id"]),
                "third_place_team": team_map.get(global_prediction["third_place_team_id"]),
                "fourth_place_team": team_map.get(global_prediction["fourth_place_team_id"]),
                "revelation_team": team_map.get(global_prediction["revelation_team_id"]),
                "disappointment_team": team_map.get(global_prediction["disappointment_team_id"]),
                "best_player": player_map.get(global_prediction["best_player_player_id"]),
                "best_gk_player": player_map.get(global_prediction["best_gk_player_id"]),
                "best_young_player": player_map.get(global_prediction["best_young_player_id"]),
                "max_scorer_player": player_map.get(global_prediction["max_scorer_player_id"]),
                "max_assister_player": player_map.get(global_prediction["max_assister_player_id"]),
                "max_yellow_cards_player": player_map.get(global_prediction["max_yellow_cards_player_id"]),
                "max_red_cards_player": player_map.get(global_prediction["max_red_cards_player_id"]),
                "revelation_player": player_map.get(global_prediction["revelation_player_id"]),
                "disappointment_player": player_map.get(global_prediction["disappointment_player_id"]),
            }

        predicted_groups = _build_predicted_groups(
            connection,
            match_predictions,
            match_map,
            team_map,
        )

    return {
        "prediction": prediction,
        "user": dict(user) if user is not None else None,
        "global_prediction": enriched_global_prediction,
        "match_predictions": enriched_match_predictions,
        "predicted_groups": predicted_groups,
    }
