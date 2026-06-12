from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import api.media as media
import database.init_db as init_db
import database.predictions.global_predictions as global_predictions
from api.app import app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DEBUG_DB_TOKEN", "test-admin-token")
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "test-admin-token")

    db_path = tmp_path / "test.db"
    monkeypatch.setattr(init_db, "DB_PATH", db_path)

    media_dir = tmp_path / "media"
    monkeypatch.setattr(media, "MEDIA_DIR", media_dir)
    monkeypatch.setattr(media, "USER_MEDIA_DIR", media_dir / "users")
    monkeypatch.setattr(media, "MEDIA_BACKUP_DIR", media_dir / "backups" / "users")

    future_deadline = datetime.now(timezone.utc) + timedelta(days=30)
    monkeypatch.setattr(global_predictions, "GLOBAL_PREDICTION_DEADLINE", future_deadline)

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def registered_user(client: TestClient) -> dict[str, object]:
    response = client.post("/auth/register", json={"name": "alice", "password": "secret123"})
    assert response.status_code == 201
    user = response.json()

    login_response = client.post("/auth/login", json={"name": "alice", "password": "secret123"})
    assert login_response.status_code == 200
    token = login_response.json()["token"]

    return {
        "user": user,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


def set_future_match_kickoff(match_id: int = 1) -> None:
    with init_db.get_connection() as connection:
        connection.execute(
            "UPDATE matches SET kickoff_at = ? WHERE id = ?",
            ("2099-06-11T13:00:00+00:00", match_id),
        )
        connection.commit()
