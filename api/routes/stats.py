from fastapi import APIRouter, Query

from database.info.stats import getAssisters, getReds, getScorers, getYellows
from database.types import JsonDict

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/scorers")
def get_scorers(
    start: int = Query(default=1, ge=1),
    end: int = Query(default=20, ge=1),
) -> JsonDict:
    return getScorers(start=start, end=end)


@router.get("/assisters")
def get_assisters(
    start: int = Query(default=1, ge=1),
    end: int = Query(default=20, ge=1),
) -> JsonDict:
    return getAssisters(start=start, end=end)


@router.get("/yellows")
def get_yellows(
    start: int = Query(default=1, ge=1),
    end: int = Query(default=20, ge=1),
) -> JsonDict:
    return getYellows(start=start, end=end)


@router.get("/reds")
def get_reds(
    start: int = Query(default=1, ge=1),
    end: int = Query(default=20, ge=1),
) -> JsonDict:
    return getReds(start=start, end=end)
