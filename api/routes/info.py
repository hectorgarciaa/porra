from fastapi import APIRouter, Depends

from api.dependencies import require_admin_token
from api.schemas.matches import SetMatchResultRequest
from database.info.world_cup import (
    getGroupsOverview,
    getMatchesOverview,
    getMatchOverviewById,
    getTeamOverviewById,
)
from database.info.matches import getMatchPredictionsSummary
from database.info.players import getPlayersOverview
from database.predictions.prediction_service import processMatchResult
from database.types import JsonDict, JsonList


router = APIRouter(tags=["info"])


@router.get("/groups")
def get_groups() -> JsonList:
    return getGroupsOverview()


@router.get("/matches")
def get_matches() -> JsonList:
    return getMatchesOverview()


@router.get("/matches/{match_id}")
def get_match_by_id(match_id: int) -> JsonDict:
    return getMatchOverviewById(match_id)


@router.get("/matches/{match_id}/predictions")
def get_match_predictions(match_id: int) -> JsonDict:
    return getMatchPredictionsSummary(match_id)


@router.put("/matches/{match_id}/result")
def set_match_result(
    match_id: int,
    payload: SetMatchResultRequest,
    _: str = Depends(require_admin_token),
) -> JsonDict:
    match = processMatchResult(
        match_id,
        local_goals=payload.local_goals,
        away_goals=payload.away_goals,
        winner_id=payload.winner_id,
        scorer_ids=payload.scorer_ids if payload.scorer_ids else None,
        assists_ids=payload.assists_ids if payload.assists_ids else None,
        yellow_card_ids=payload.yellow_card_ids if payload.yellow_card_ids else None,
        red_card_ids=payload.red_card_ids if payload.red_card_ids else None,
        has_extra_time=payload.has_extra_time,
        has_penalties=payload.has_penalties,
        local_penalties=payload.local_penalties,
        away_penalties=payload.away_penalties,
    )
    return {"match": match}


@router.get("/teams/{team_id}")
def get_team_by_id(team_id: int) -> JsonDict:
    return getTeamOverviewById(team_id)


@router.get("/players")
def get_players() -> JsonList:
    return getPlayersOverview()
