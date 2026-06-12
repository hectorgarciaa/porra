from __future__ import annotations

from pathlib import Path

import api.media as media
from tests.conftest import set_future_match_kickoff


def test_pages_and_method_guards(client) -> None:
    assert client.get("/health").status_code == 200

    for path in (
        "/",
        "/login",
        "/register",
        "/dashboard",
        "/world-cup",
        "/classification",
        "/my-predictions",
        "/bar",
        "/settings",
        "/rules",
        "/inicio",
        "/clasificacion",
        "/mi-porra",
        "/mundial",
        "/admin",
    ):
        response = client.get(path)
        assert response.status_code == 200, path

    assert client.post("/groups").status_code == 405
    assert client.get("/auth/login").status_code == 405
    assert client.patch("/users/me", json={"name": "blocked"}).status_code == 401


def test_auth_users_chat_and_info_endpoints(client, registered_user) -> None:
    headers = registered_user["headers"]

    unlock_response = client.post("/auth/admin/unlock", json={"password": "test-admin-token"})
    assert unlock_response.status_code == 200
    assert unlock_response.json()["ok"] is True

    me_response = client.get("/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["name"] == "alice"

    update_response = client.patch("/users/me", json={"name": "alice-2"}, headers=headers)
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "alice-2"

    avatar_response = client.post(
        "/users/me/avatar",
        headers=headers,
        files={"image": ("avatar.png", b"fakepng", "image/png")},
    )
    assert avatar_response.status_code == 200
    assert avatar_response.json()["img"].startswith("/media/users/")

    groups_response = client.get("/groups")
    assert groups_response.status_code == 200
    groups = groups_response.json()
    assert len(groups) == 12

    matches_response = client.get("/matches")
    assert matches_response.status_code == 200
    matches = matches_response.json()
    assert len(matches) > 0

    match_response = client.get(f"/matches/{matches[0]['id']}")
    assert match_response.status_code == 200
    assert match_response.json()["id"] == matches[0]["id"]

    team_response = client.get(f"/teams/{matches[0]['local_team']['id']}")
    assert team_response.status_code == 200
    assert len(team_response.json()["players"]) > 0

    players_response = client.get("/players")
    assert players_response.status_code == 200
    assert len(players_response.json()) > 0

    for path in ("/stats/scorers", "/stats/assisters", "/stats/yellows", "/stats/reds"):
        response = client.get(f"{path}?start=1&end=20")
        assert response.status_code == 200, path

    leaderboard_response = client.get("/leaderboard")
    assert leaderboard_response.status_code == 200
    assert any(item["name"] == "alice-2" for item in leaderboard_response.json())

    evolution_response = client.get("/leaderboard/evolution")
    assert evolution_response.status_code == 200

    messages_response = client.get("/chat/messages")
    assert messages_response.status_code == 200
    assert messages_response.json() == []

    post_message_response = client.post("/chat/messages", headers=headers, data={"text": "hola"})
    assert post_message_response.status_code == 200
    assert post_message_response.json()["message"]["text"] == "hola"

    post_image_response = client.post(
        "/chat/messages/image",
        headers=headers,
        data={"text": "foto"},
        files={"image": ("chat.png", b"image-bytes", "image/png")},
    )
    assert post_image_response.status_code == 200
    assert post_image_response.json()["message"]["image_url"].startswith("/media/users/")

    latest_messages = client.get("/chat/messages?since=0")
    assert latest_messages.status_code == 200
    assert len(latest_messages.json()) == 2


def test_predictions_match_results_and_admin_tools(client, registered_user) -> None:
    headers = registered_user["headers"]
    admin_headers = {"X-Admin-Token": "test-admin-token"}

    set_future_match_kickoff(1)
    match_before = client.get("/matches/1")
    assert match_before.status_code == 200
    match_data = match_before.json()
    local_team_id = int(match_data["local_team"]["id"])
    away_team_id = int(match_data["away_team"]["id"])

    local_team = client.get(f"/teams/{local_team_id}")
    away_team = client.get(f"/teams/{away_team_id}")
    assert local_team.status_code == 200
    assert away_team.status_code == 200
    scorer_id = int(local_team.json()["players"][0]["id"])
    assist_id = int(away_team.json()["players"][0]["id"])

    prediction_missing = client.get("/predictions/me", headers=headers)
    assert prediction_missing.status_code == 404

    create_prediction = client.post("/predictions", headers=headers)
    assert create_prediction.status_code == 201
    prediction_id = create_prediction.json()["prediction"]["id"]

    duplicate_prediction = client.post("/predictions", headers=headers)
    assert duplicate_prediction.status_code == 409

    own_prediction = client.get("/predictions/me", headers=headers)
    assert own_prediction.status_code == 200
    assert own_prediction.json()["prediction"]["id"] == prediction_id

    match_prediction_response = client.post(
        "/predictions/matches/1",
        headers=headers,
        json={"local_goals": 1, "away_goals": 0, "winner_team_id": local_team_id},
    )
    assert match_prediction_response.status_code == 200

    global_prediction_response = client.post(
        "/predictions/global",
        headers=headers,
        json={
            "winner_team_id": 1,
            "runner_up_team_id": 2,
            "third_place_team_id": 3,
            "fourth_place_team_id": 4,
            "best_player_player_id": 1,
            "max_scorer_player_id": 2,
            "max_assister_player_id": 3,
            "max_yellow_cards_player_id": 4,
            "max_red_cards_player_id": 5,
        },
    )
    assert global_prediction_response.status_code == 200

    match_result_response = client.put(
        "/matches/1/result",
        headers=admin_headers,
        json={
            "local_goals": 1,
            "away_goals": 0,
            "winner_id": local_team_id,
            "scorer_ids": [scorer_id],
            "assists_ids": [assist_id],
            "yellow_card_ids": [],
            "red_card_ids": [],
            "has_extra_time": False,
            "has_penalties": False,
            "local_penalties": None,
            "away_penalties": None,
        },
    )
    assert match_result_response.status_code == 200
    assert match_result_response.json()["match"]["local_goals"] == 1

    leaderboard_response = client.get("/leaderboard")
    assert leaderboard_response.status_code == 200
    user_row = next(item for item in leaderboard_response.json() if item["name"] == "alice")
    assert user_row["points"] == 7

    prediction_by_id = client.get(f"/predictions/{prediction_id}", headers=headers)
    assert prediction_by_id.status_code == 200
    prediction_payload = prediction_by_id.json()
    assert "predicted_groups" in prediction_payload
    assert len(prediction_payload["predicted_groups"]) == 12
    group_a = next(group for group in prediction_payload["predicted_groups"] if group["letter"] == "A")
    assert "standings" in group_a
    assert len(group_a["standings"]) == 4

    avatar_response = client.post(
        "/users/me/avatar",
        headers=headers,
        files={"image": ("backup-avatar.png", b"backup-avatar", "image/png")},
    )
    assert avatar_response.status_code == 200

    debug_summary = client.get("/debug/db-summary?token=test-admin-token")
    assert debug_summary.status_code == 200
    assert debug_summary.json()["table_counts"]["groups"] == 12

    debug_groups = client.get("/debug/db-table/groups?token=test-admin-token&limit=3&offset=0")
    assert debug_groups.status_code == 200
    assert len(debug_groups.json()["items"]) == 3

    backup_response = client.post("/admin/media-users/backup", headers=admin_headers)
    assert backup_response.status_code == 200
    assert backup_response.headers["content-type"] == "application/zip"
    backup_zip_bytes = backup_response.content

    media_overview_response = client.get("/admin/media-files", headers=admin_headers)
    assert media_overview_response.status_code == 200
    media_overview = media_overview_response.json()
    assert "users" in media_overview
    assert "user_backups" in media_overview
    assert len(media_overview["users"]["files"]) >= 1
    assert any(file_item["relative_path"].endswith(".png") for file_item in media_overview["users"]["files"])
    assert any(file_item["name"].endswith(".zip") for file_item in media_overview["user_backups"]["files"])

    media_files = [path for path in media.USER_MEDIA_DIR.rglob("*") if path.is_file()]
    assert media_files
    for path in media_files:
        path.unlink()

    upload_restore_response = client.post(
        "/admin/media-users/restore/upload",
        headers=admin_headers,
        files={"file": ("users_backup_test.zip", backup_zip_bytes, "application/zip")},
    )
    assert upload_restore_response.status_code == 200
    assert upload_restore_response.json()["restored_files"] >= 1

    restored_from_upload_files = [path for path in media.USER_MEDIA_DIR.rglob("*") if path.is_file()]
    assert restored_from_upload_files
    for path in restored_from_upload_files:
        path.unlink()

    restore_response = client.post("/admin/media-users/restore", headers=admin_headers)
    assert restore_response.status_code == 200
    assert restore_response.json()["restored_files"] >= 1

    restored_files = [path for path in media.USER_MEDIA_DIR.rglob("*") if path.is_file()]
    assert restored_files


def test_frontend_contracts(client) -> None:
    app_js = Path("static/js/app.js").read_text(encoding="utf-8")
    dashboard_html = Path("templates/dashboard.html").read_text(encoding="utf-8")
    admin_html = Path("templates/admin.html").read_text(encoding="utf-8")

    assert "/admin" in app_js
    assert "/rules" in app_js
    assert "!['/', '/admin', '/rules'].includes(location.pathname)" in app_js
    assert 'href="/rules"' in dashboard_html
    assert "/auth/admin/unlock" in admin_html
    assert "/admin/media-users/backup" in admin_html
    assert "/admin/media-users/restore" in admin_html
    assert "/admin/media-files" in admin_html
    assert "media-explorer" in admin_html
    assert "DUPLICATE_EVENT_CATEGORIES" in admin_html
    assert "renderAllSelectedCategories" in admin_html
    assert "/matches/${matchId}" in admin_html
    assert "predicted_groups" in Path("database/predictions/prediction_service.py").read_text(encoding="utf-8")
    assert "predicted-groups-section" in Path("templates/view_prediction.html").read_text(encoding="utf-8")
