from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg
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
    monkeypatch.setenv("DEBUG_DB_TOKEN", "test-admin-token")
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "test-admin-token")

    test_backend = os.getenv("TEST_DATABASE_BACKEND", "sqlite").strip().lower()

    schema_name: str | None = None
    base_database_url: str | None = None
    if test_backend == "postgres":
        base_database_url = os.getenv("DATABASE_URL")
        if not base_database_url:
            pytest.skip("DATABASE_URL no esta configurada para tests con Postgres.")

        schema_name = f"test_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
        with psycopg.connect(base_database_url) as setup_connection:
            setup_connection.execute(f'CREATE SCHEMA "{schema_name}"')
            setup_connection.commit()

        split_url = urlsplit(base_database_url)
        query = dict(parse_qsl(split_url.query, keep_blank_values=True))
        query["options"] = f"-csearch_path={schema_name}"
        postgres_test_url = urlunsplit(
            (split_url.scheme, split_url.netloc, split_url.path, urlencode(query), split_url.fragment)
        )
        monkeypatch.setenv("DATABASE_URL", postgres_test_url)
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        db_path = tmp_path / "test.db"
        monkeypatch.setattr(init_db, "DB_PATH", db_path)

    media_dir = tmp_path / "media"
    monkeypatch.setattr(media, "MEDIA_DIR", media_dir)
    monkeypatch.setattr(media, "USER_MEDIA_DIR", media_dir / "users")
    monkeypatch.setattr(media, "MEDIA_BACKUP_DIR", media_dir / "backups" / "users")

    future_deadline = datetime.now(timezone.utc) + timedelta(days=30)
    monkeypatch.setattr(global_predictions, "GLOBAL_PREDICTION_DEADLINE", future_deadline)

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        if schema_name is not None:
            if base_database_url:
                with psycopg.connect(base_database_url) as cleanup_connection:
                    cleanup_connection.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
                    cleanup_connection.commit()


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
