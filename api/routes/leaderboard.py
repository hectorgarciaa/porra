from fastapi import APIRouter

from database.info.leaderboard import getLeaderboard, getLeaderboardEvolution
from database.types import JsonList

router = APIRouter(tags=["leaderboard"])


@router.get("/leaderboard")
def get_leaderboard() -> JsonList:
    return getLeaderboard()


@router.get("/leaderboard/evolution")
def get_leaderboard_evolution() -> JsonList:
    return getLeaderboardEvolution()
