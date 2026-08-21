import io

from PIL import Image

from tests.conftest import make_user_client


def _img_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (120, 80, 200)).save(buf, format="PNG")
    return buf.getvalue()


def test_story_slides_empty_for_player(player_client):
    assert player_client.get("/api/story/slides").json() == []


def test_story_slides_requires_auth(client):
    assert client.get("/api/story/slides").status_code == 401
    assert client.post("/api/story/seen").status_code == 401


def test_mark_story_seen(player_client):
    assert player_client.get("/api/me").json()["story_seen"] is False
    res = player_client.post("/api/story/seen")
    assert res.status_code == 200
    assert player_client.get("/api/me").json()["story_seen"] is True


def test_admin_creates_and_orders_slides(admin_client):
    a = admin_client.post("/api/admin/story/slides", json={"text": "Первый", "sort_order": 2})
    b = admin_client.post("/api/admin/story/slides", json={"text": "Второй", "sort_order": 1})
    assert a.status_code == 201 and b.status_code == 201
    with make_user_client(123, "player") as c:
        ids = [s["id"] for s in c.get("/api/story/slides").json()]
    assert ids == [b.json()["id"], a.json()["id"]]


def test_admin_upload_slide_image(admin_client, uploads_tmp):
    slide = admin_client.post("/api/admin/story/slides", json={"text": "Слайд"}).json()
    res = admin_client.put(
        f"/api/admin/story/slides/{slide['id']}/image",
        files={"file": ("img.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 200
    url = res.json()["image_url"]
    assert url and url.startswith("/api/uploads/")
    with make_user_client(123, "player") as c:
        listed = c.get("/api/story/slides").json()
    assert listed[0]["image_url"] == url


def test_admin_update_and_delete_slide(admin_client):
    slide = admin_client.post("/api/admin/story/slides", json={"text": "Старый", "sort_order": 0}).json()
    sid = slide["id"]
    up = admin_client.put(f"/api/admin/story/slides/{sid}", json={"text": "Новый", "sort_order": 5})
    assert up.status_code == 200
    assert up.json()["text"] == "Новый"
    assert up.json()["sort_order"] == 5
    with make_user_client(123, "player") as c:
        assert c.get("/api/story/slides").json()[0]["text"] == "Новый"
    assert admin_client.delete(f"/api/admin/story/slides/{sid}").status_code == 204
    with make_user_client(123, "player") as c:
        assert c.get("/api/story/slides").json() == []


def test_admin_story_slides_require_admin(player_client):
    assert player_client.post("/api/admin/story/slides", json={"text": "x"}).status_code == 403


def test_admin_slide_404(admin_client):
    assert admin_client.put("/api/admin/story/slides/999", json={"text": "x"}).status_code == 404
    assert admin_client.delete("/api/admin/story/slides/999").status_code == 404


def test_admin_dlc_locations(admin_client):
    res = admin_client.get("/api/admin/story/dlc-locations")
    assert res.status_code == 200
    codes = {c["code"] for c in res.json()}
    assert "infirmary" in codes and "brewery" in codes


def test_dlc_slide_excluded_from_general(admin_client):
    admin_client.post("/api/admin/story/slides", json={"text": "Общая"})
    admin_client.post("/api/admin/story/slides", json={"text": "Для лечебницы", "location_code": "infirmary"})
    with make_user_client(123, "player") as c:
        general = [s["text"] for s in c.get("/api/story/slides").json()]
        assert general == ["Общая"]
        dlc = c.get("/api/story/dlc/infirmary").json()
        assert [s["text"] for s in dlc["slides"]] == ["Для лечебницы"]
        assert dlc["seen"] is False


def test_dlc_story_seen_flag(player_client):
    assert player_client.get("/api/story/dlc/brewery").json()["seen"] is False
    assert player_client.post("/api/story/dlc/brewery/seen").status_code == 200
    assert player_client.get("/api/story/dlc/brewery").json()["seen"] is True


def test_dlc_story_unknown_location_400(player_client):
    assert player_client.get("/api/story/dlc/wrong").status_code == 400
    assert player_client.post("/api/story/dlc/wrong/seen").status_code == 400


def test_admin_dlc_slide_invalid_location_400(admin_client):
    assert admin_client.post("/api/admin/story/slides", json={"text": "x", "location_code": "wrong"}).status_code == 400



def test_dlc_story_locked_without_unlock(player_client):
    from routes.settings import set_locked_locations
    from tests.conftest import TestingSessionLocal

    s = TestingSessionLocal()
    try:
        set_locked_locations(s, ["brewery"])
    finally:
        s.close()
    try:
        assert player_client.get("/api/story/dlc/brewery").status_code == 403
        assert player_client.post("/api/story/dlc/brewery/seen").status_code == 403
        assert player_client.get("/api/story/dlc/infirmary").status_code == 200
    finally:
        s = TestingSessionLocal()
        try:
            set_locked_locations(s, [])
        finally:
            s.close()


def test_dlc_story_unlocked_with_dlc(player_client):
    from models import UserDlcUnlock
    from routes.settings import set_locked_locations
    from tests.conftest import TestingSessionLocal

    s = TestingSessionLocal()
    try:
        set_locked_locations(s, ["brewery"])
        s.add(UserDlcUnlock(user_id=123, location_code="brewery"))
        s.commit()
    finally:
        s.close()
    try:
        assert player_client.get("/api/story/dlc/brewery").status_code == 200
        assert player_client.post("/api/story/dlc/brewery/seen").status_code == 200
    finally:
        s = TestingSessionLocal()
        try:
            set_locked_locations(s, [])
        finally:
            s.close()


def test_upload_slide_image_failure_keeps_old_file(admin_client, monkeypatch):
    from routes import story as routes_story
    from services.uploads import remove_upload as real_remove
    from models import StorySlide
    from tests.conftest import TestingSessionLocal

    r = admin_client.post("/api/admin/story/slides", json={"text": "слайд"})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]

    s = TestingSessionLocal()
    try:
        slide = s.query(StorySlide).filter(StorySlide.id == sid).first()
        slide.image_url = "/api/uploads/old_story.jpg"
        s.commit()
    finally:
        s.close()

    removed = []

    def _fake_remove(url):
        removed.append(url)
        return real_remove(url)

    def _bad_save(file, name, **kwargs):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Файл должен быть изображением")

    monkeypatch.setattr(routes_story, "remove_upload", _fake_remove)
    monkeypatch.setattr(routes_story, "save_upload", _bad_save)

    res = admin_client.put(f"/api/admin/story/slides/{sid}/image", files={
        "file": ("x.png", b"notanimage", "image/png"),
    })
    assert res.status_code == 400
    assert removed == []

    s = TestingSessionLocal()
    try:
        slide = s.query(StorySlide).filter(StorySlide.id == sid).first()
        assert slide.image_url == "/api/uploads/old_story.jpg"
    finally:
        s.close()
