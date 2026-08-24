import io

from PIL import Image

from tests.conftest import make_user_client


def _fake_video():
    return io.BytesIO(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")


def _img_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (80, 140, 200)).save(buf, format="PNG")
    return buf.getvalue()


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


def test_admin_upload_lesson_image(admin_client, uploads_tmp):
    lesson = admin_client.post("/api/admin/lessons", json={"title": "С картинкой"}).json()
    res = admin_client.put(
        f"/api/admin/lessons/{lesson['id']}/image",
        files={"file": ("img.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 200
    url = res.json()["image_url"]
    assert url and url.startswith("/api/uploads/")
    with make_user_client(123, "player") as c:
        listed = c.get("/api/lessons").json()
    assert listed[0]["image_url"] == url


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


def test_admin_lesson_category_default_and_validation(admin_client):
    a = admin_client.post("/api/admin/lessons", json={"title": "Ферма", "sort_order": 0})
    assert a.status_code == 201
    assert a.json()["category"] == "farm"

    b = admin_client.post("/api/admin/lessons", json={"title": "Зельеварение", "sort_order": 0, "category": "brewery"})
    assert b.status_code == 201
    assert b.json()["category"] == "brewery"

    bad = admin_client.post("/api/admin/lessons", json={"title": "Бад", "category": "nope"})
    assert bad.status_code == 400


def test_admin_lesson_update_category(admin_client):
    lesson = admin_client.post("/api/admin/lessons", json={"title": "Урок", "sort_order": 0}).json()
    up = admin_client.put(f"/api/admin/lessons/{lesson['id']}", json={"category": "infirmary"})
    assert up.status_code == 200
    assert up.json()["category"] == "infirmary"
    with make_user_client(123, "player") as c:
        listed = c.get("/api/lessons").json()
    assert listed[0]["category"] == "infirmary"


def test_admin_upload_lesson_video_to_s3(admin_client, monkeypatch):
    import config
    from services import uploads as uploads_mod

    class _FakeS3:
        def __init__(self):
            self.base = "https://s3.example.com/bucket"
            self.uploaded = {}
            self.deleted = []

        def upload_stream(self, key, fileobj, content_type="video/mp4"):
            self.uploaded[key] = (fileobj.read(), content_type)
            return f"{self.base}/{key}"

        def delete_object(self, key):
            self.deleted.append(key)

    fake = _FakeS3()
    monkeypatch.setattr(config, "S3_PUBLIC_URL", fake.base)
    monkeypatch.setattr(uploads_mod, "_S3", fake)

    lesson = admin_client.post("/api/admin/lessons", json={"title": "S3 урок"}).json()
    res = admin_client.put(
        f"/api/admin/lessons/{lesson['id']}/video",
        files={"file": ("lesson.mp4", _fake_video(), "video/mp4")},
    )
    assert res.status_code == 200
    url = res.json()["video_url"]
    assert url.startswith(fake.base + "/videos/lesson_")
    key = url[len(fake.base) + 1:]
    assert fake.uploaded[key][0] == _fake_video().getvalue()
    assert fake.uploaded[key][1] == "video/mp4"

    with make_user_client(123, "player") as c:
        assert c.get("/api/lessons").json()[0]["video_url"] == url

    assert admin_client.delete(f"/api/admin/lessons/{lesson['id']}").status_code == 204
    assert fake.deleted == [key]


def test_admin_lesson_404(admin_client):
    assert admin_client.put("/api/admin/lessons/999", json={"title": "x"}).status_code == 404
    assert admin_client.delete("/api/admin/lessons/999").status_code == 404


def test_upload_video_failure_keeps_old_file(admin_client, monkeypatch):
    from routes import lessons as routes_lessons
    from services.uploads import remove_upload as real_remove
    from models import Lesson
    from tests.conftest import TestingSessionLocal

    r = admin_client.post("/api/admin/lessons", json={"title": "Урок медиа"})
    assert r.status_code == 201, r.text
    lid = r.json()["id"]

    s = TestingSessionLocal()
    try:
        lesson = s.query(Lesson).filter(Lesson.id == lid).first()
        lesson.video_url = "/api/uploads/old_lesson.mp4"
        s.commit()
    finally:
        s.close()

    removed = []

    def _fake_remove(url):
        removed.append(url)
        return real_remove(url)

    def _bad_save(file, name, **kwargs):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Файл слишком большой")

    monkeypatch.setattr(routes_lessons, "remove_upload", _fake_remove)
    monkeypatch.setattr(routes_lessons, "save_upload", _bad_save)

    res = admin_client.put(f"/api/admin/lessons/{lid}/video", files={
        "file": ("v.mp4", b"xxxx", "video/mp4"),
    })
    assert res.status_code == 400
    assert removed == []

    s = TestingSessionLocal()
    try:
        lesson = s.query(Lesson).filter(Lesson.id == lid).first()
        assert lesson.video_url == "/api/uploads/old_lesson.mp4"
    finally:
        s.close()
