from database.predictions.scoring import (
    POINTS_CORRECT_GOAL_DIFFERENCE,
    POINTS_CORRECT_ONE_TEAM_GOALS,
    POINTS_CORRECT_SIGN,
    POINTS_EXACT_SCORE,
    calculate_match_prediction_points,
)


def test_exact_score_is_seven_points() -> None:
    assert POINTS_EXACT_SCORE == 7
    assert calculate_match_prediction_points(
        actual_local_goals=2,
        actual_away_goals=1,
        predicted_local_goals=2,
        predicted_away_goals=1,
    ) == 7


def test_non_exact_points_stack_as_3_plus_1() -> None:
    assert POINTS_CORRECT_SIGN == 3
    assert POINTS_CORRECT_GOAL_DIFFERENCE == 1
    assert POINTS_CORRECT_ONE_TEAM_GOALS == 1

    assert calculate_match_prediction_points(
        actual_local_goals=2,
        actual_away_goals=1,
        predicted_local_goals=1,
        predicted_away_goals=0,
    ) == 4


def test_non_exact_can_score_four_points_with_sign_and_one_team_goals() -> None:
    assert calculate_match_prediction_points(
        actual_local_goals=2,
        actual_away_goals=1,
        predicted_local_goals=2,
        predicted_away_goals=0,
    ) == 4


def test_wrong_sign_can_only_score_one_for_one_team_exact_goals() -> None:
    assert calculate_match_prediction_points(
        actual_local_goals=2,
        actual_away_goals=1,
        predicted_local_goals=0,
        predicted_away_goals=1,
    ) == 1


def test_unplayed_match_scores_zero() -> None:
    assert calculate_match_prediction_points(
        actual_local_goals=None,
        actual_away_goals=None,
        predicted_local_goals=1,
        predicted_away_goals=0,
    ) == 0
