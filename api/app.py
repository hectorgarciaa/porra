from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.media import MEDIA_DIR, ensure_media_dirs
from api.routes.admin import router as admin_router
from api.routes.auth import router as auth_router
from api.routes.chat import router as chat_router
from api.routes.debug import router as debug_router
from api.routes.info import router as info_router
from api.routes.leaderboard import router as leaderboard_router
from api.routes.pages import router as pages_router
from api.routes.predictions import router as predictions_router
from api.routes.stats import router as stats_router
from api.routes.users import router as users_router
from database.info.groups import GroupNotFoundError
from database.info.matches import MatchNotFoundError
from database.info.teams import TeamNotFoundError
from database.info.users import (
    ForbiddenError,
    InvalidCredentialsError,
    InvalidSessionError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from database.init_db import init_db
from database.predictions.predictions import PredictionNotFoundError

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    ensure_media_dirs()
    yield


app = FastAPI(
    title="Porra Mundial 2026 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(UserAlreadyExistsError)
async def handle_user_exists(_: Request, exc: UserAlreadyExistsError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(UserNotFoundError)
async def handle_user_not_found(_: Request, exc: UserNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(GroupNotFoundError)
async def handle_group_not_found(_: Request, exc: GroupNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(MatchNotFoundError)
async def handle_match_not_found(_: Request, exc: MatchNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(TeamNotFoundError)
async def handle_team_not_found(_: Request, exc: TeamNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(PredictionNotFoundError)
async def handle_prediction_not_found(_: Request, exc: PredictionNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(InvalidCredentialsError)
async def handle_invalid_credentials(_: Request, exc: InvalidCredentialsError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(InvalidSessionError)
async def handle_invalid_session(_: Request, exc: InvalidSessionError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(ForbiddenError)
async def handle_forbidden(_: Request, exc: ForbiddenError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def handle_value_error(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


app.include_router(pages_router)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(debug_router)
app.include_router(info_router)
app.include_router(leaderboard_router)
app.include_router(predictions_router)
app.include_router(stats_router)
app.include_router(users_router)
