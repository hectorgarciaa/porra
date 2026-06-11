from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_current_user
from api.schemas.predictions import (
    UpsertGlobalPredictionRequest,
    UpsertMatchPredictionRequest,
)
from database.predictions.global_predictions import upsertGlobalPrediction
from database.predictions.match_predictions import upsertMatchPrediction
from database.predictions.prediction_service import (
    createEmptyPrediction,
    getFullPredictionById,
)
from database.predictions.predictions import (
    PredictionAlreadyExistsError,
    getPredictionByPlayerId,
)
from database.types import JsonDict, RowDict

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_my_prediction(current_user: RowDict = Depends(get_current_user)) -> JsonDict:
    user_id = int(current_user["id"])
    try:
        prediction = createEmptyPrediction(user_id)
    except PredictionAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return {"prediction": prediction}


@router.get("/me")
def get_my_prediction(current_user: RowDict = Depends(get_current_user)) -> JsonDict:
    user_id = int(current_user["id"])
    prediction = getPredictionByPlayerId(user_id)
    return getFullPredictionById(int(prediction["id"]))


@router.get("/{prediction_id}")
def get_prediction_by_id(
    prediction_id: int,
    current_user: RowDict = Depends(get_current_user),
) -> JsonDict:
    user_id = int(current_user["id"])
    prediction = getPredictionByPlayerId(user_id)
    if int(prediction["id"]) != prediction_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para ver esta prediccion.",
        )
    return getFullPredictionById(prediction_id)


@router.post("/global")
def upsert_my_global_prediction(
    payload: UpsertGlobalPredictionRequest,
    current_user: RowDict = Depends(get_current_user),
) -> JsonDict:
    user_id = int(current_user["id"])
    prediction = getPredictionByPlayerId(user_id)

    global_prediction = upsertGlobalPrediction(
        int(prediction["id"]),
        winner_team_id=payload.winner_team_id,
        runner_up_team_id=payload.runner_up_team_id,
        third_place_team_id=payload.third_place_team_id,
        fourth_place_team_id=payload.fourth_place_team_id,
        best_player_player_id=payload.best_player_player_id,
        max_scorer_player_id=payload.max_scorer_player_id,
        max_assister_player_id=payload.max_assister_player_id,
        max_yellow_cards_player_id=payload.max_yellow_cards_player_id,
        max_red_cards_player_id=payload.max_red_cards_player_id,
    )
    return {"global_prediction": global_prediction}


@router.post("/matches/{match_id}")
def upsert_my_match_prediction(
    match_id: int,
    payload: UpsertMatchPredictionRequest,
    current_user: RowDict = Depends(get_current_user),
) -> JsonDict:
    user_id = int(current_user["id"])
    prediction = getPredictionByPlayerId(user_id)

    match_prediction = upsertMatchPrediction(
        int(prediction["id"]),
        match_id,
        local_goals=payload.local_goals,
        away_goals=payload.away_goals,
        winner_team_id=payload.winner_team_id,
        has_extra_time=payload.has_extra_time,
        has_penalties=payload.has_penalties,
    )
    return {"match_prediction": match_prediction}
