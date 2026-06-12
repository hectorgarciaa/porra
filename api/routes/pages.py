from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

router = APIRouter(tags=["pages"])


def _render(name: str, request: Request) -> HTMLResponse:
    template = env.get_template(name)
    return HTMLResponse(template.render(request=request))


# ── Páginas principales ──────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return _render("home.html", request)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    return _render("login.html", request)


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    return _render("register.html", request)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    return _render("dashboard.html", request)


@router.get("/world-cup", response_class=HTMLResponse)
async def world_cup(request: Request) -> HTMLResponse:
    return _render("world_cup.html", request)


@router.get("/classification", response_class=HTMLResponse)
async def leaderboard_page(request: Request) -> HTMLResponse:
    return _render("leaderboard.html", request)


@router.get("/my-predictions", response_class=HTMLResponse)
async def my_predictions(request: Request) -> HTMLResponse:
    return _render("my_predictions.html", request)


@router.get("/bar", response_class=HTMLResponse)
async def bar(request: Request) -> HTMLResponse:
    return _render("bar.html", request)


@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request) -> HTMLResponse:
    return _render("settings.html", request)


# ── Aliases en español ───────────────────────────────────────

@router.get("/inicio", response_class=HTMLResponse)
async def inicio(request: Request) -> HTMLResponse:
    return _render("dashboard.html", request)


@router.get("/clasificacion", response_class=HTMLResponse)
async def clasificacion(request: Request) -> HTMLResponse:
    return _render("leaderboard.html", request)


@router.get("/mi-porra", response_class=HTMLResponse)
async def mi_porra(request: Request) -> HTMLResponse:
    return _render("my_predictions.html", request)


@router.get("/mundial", response_class=HTMLResponse)
async def mundial(request: Request) -> HTMLResponse:
    return _render("world_cup.html", request)


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request) -> HTMLResponse:
    return _render("admin.html", request)


@router.get("/prediction/{prediction_id}", response_class=HTMLResponse)
async def view_prediction(request: Request) -> HTMLResponse:
    return _render("view_prediction.html", request)


@router.get("/rules", response_class=HTMLResponse)
async def rules(request: Request) -> HTMLResponse:
    return _render("rules.html", request)
