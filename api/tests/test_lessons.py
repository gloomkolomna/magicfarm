import io

from tests.conftest import make_user_client


def _fake_video():
    return io.BytesIO(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")


def test_lessons_empty_for_player(player_client):
    assert player_client.get("/api/lessons").json() == []


def test_lessons_requires_auth(client):
    assert client.get("/api/lessons").status_code == 401


def test_admin_creates_and_orders_lessons(admin_client):
    a = admin_client.post("/api/admin/lessons", json={"title": "Урок 2", "sort_order": 2})
    b = admin_client.post("/api/admin/lessons", json={"title": "Урок 1", "sort_order": 1})
    assert a.status_code == 201 and b.status_code == 201
    with make_user_client(123, "player") as c:
        ids = [l["id"] for l in c.get("/api/lessons").json()]
    assert ids == [b.json()["id"], a.json()["id"]]


def test_admin_lesson_title_required(admin_client):
    assert admin_client.post("/api/admin/lessons", json={"title": "   "}).status_code == 400
    assert admin_client.post("/api/admin/lessons", json={"title": ""}).status_code == 400


def test_admin_upload_lesson_video(admin_client, uploads_tmp):
    lesson = admin_client.post("/api/admin/lessons", json={"title": "Видео-урок"}).json()
    res = admin_client.put(
        f"/api/admin/lessons/{lesson['id']}/video",
        files={"file": ("lesson.mp4", _fake_video(), "video/mp4")},
    )
    assert res.status_code == 200
    url = res.json()["video_url"]
    assert url and url.startswith("/api/uploads/")
    with make_user_client(123, "player") as c:
        listed = c.get("/api/lessons").json()
    assert listed[0]["video_url"] == url
    assert listed[0]["title"] == "Видео-урок"


def test_admin_update_and_delete_lesson(admin_client):
    lesson = admin_client.post("/api/admin/lessons", json={"title": "Старый", "sort_order": 0}).json()
    lid = lesson["id"]
    up = admin_client.put(f"/api/admin/lessons/{lid}", json={"title": "Новый", "description": "Описание", "sort_order": 7})
    assert up.status_code == 200
    assert up.json()["title"] == "Новый"
    assert up.json()["description"] == "Описание"
    with make_user_client(123, "player") as c:
        assert c.get("/api/lessons").json()[0]["title"] == "Новый"
    assert admin_client.delete(f"/api/admin/lessons/{lid}").status_code == 204
    with make_user_client(123, "player") as c:
        assert c.get("/api/lessons").json() == []


def test_admin_lessons_require_admin(player_client):
    assert player_client.post("/api/admin/lessons", json={"title": "x"}).status_code == 403
    assert player_client.get("/api/admin/lessons").status_code == 403


def test_admin_lesson_404(admin_client):
    assert admin_client.put("/api/admin/lessons/999", json={"title": "x"}).status_code == 404
    assert admin_client.delete("/api/admin/lessons/999").status_code == 404
