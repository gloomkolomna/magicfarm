from tests.conftest import make_user_client, make_user_client_no_onboarding


def _full_norms():
    return {
        "green": {"1": 11, "2": 22, "3": 33, "4": 44, "5": 55},
        "blue": {"1": 22, "2": 44, "3": 66, "4": 88, "5": 110},
        "violet": {"1": 33, "2": 66, "3": 99, "4": 132, "5": 165},
    }


# ===== Пресеты =====

def test_list_presets(player_client):
    res = player_client.get("/api/crystal-norms/presets")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 8
    assert {r["variant"] for r in rows} == {1, 2, 3, 4, 5, 6, 7, 8}
    for r in rows:
        assert set(r["norms"].keys()) == {"green", "blue", "violet"}
        for color in ("green", "blue", "violet"):
            assert set(r["norms"][color].keys()) == {"1", "2", "3", "4", "5"}


def test_presets_require_auth(client):
    assert client.get("/api/crystal-norms/presets").status_code == 401


# ===== Стандарт =====

def test_get_standard_default(player_client):
    res = player_client.get("/api/crystal-norms/standard")
    assert res.status_code == 200
    norms = res.json()["norms"]
    # По умолчанию — пресет 1.
    from routes.settings import VARIANT_TABLES
    assert norms["green"]["1"] == VARIANT_TABLES[1]["green"][1]


def test_set_standard_admin(admin_client):
    res = admin_client.put("/api/crystal-norms/admin/standard", json={"norms": _full_norms()})
    assert res.status_code == 200
    assert res.json()["norms"]["blue"]["3"] == 66

    res2 = admin_client.get("/api/crystal-norms/standard")
    assert res2.json()["norms"]["blue"]["3"] == 66


def test_set_standard_player_forbidden(player_client):
    res = player_client.put("/api/crystal-norms/admin/standard", json={"norms": _full_norms()})
    assert res.status_code == 403


def test_set_standard_by_preset(admin_client):
    res = admin_client.put("/api/crystal-norms/admin/standard", json={"preset": 3})
    assert res.status_code == 200
    from routes.settings import VARIANT_TABLES
    assert res.json()["norms"]["violet"]["5"] == VARIANT_TABLES[3]["violet"][5]


def test_set_standard_requires_body(admin_client):
    res = admin_client.put("/api/crystal-norms/admin/standard", json={})
    assert res.status_code == 400


def test_set_standard_invalid_preset(admin_client):
    res = admin_client.put("/api/crystal-norms/admin/standard", json={"preset": 99})
    assert res.status_code == 400


def test_set_standard_missing_color(admin_client):
    bad = _full_norms()
    del bad["violet"]
    res = admin_client.put("/api/crystal-norms/admin/standard", json={"norms": bad})
    assert res.status_code == 422


# ===== Мои нормы =====

def test_get_my_norms_new_player_returns_standard():
    with make_user_client_no_onboarding(555, "player") as c:
        res = c.get("/api/crystal-norms/mine")
    assert res.status_code == 200
    data = res.json()
    assert data["onboarding_done"] is False
    # Нет персональных норм → отдаётся стандарт (пресет 1).
    assert "green" in data["norms"]


def test_set_my_norms(player_client):
    res = player_client.put("/api/crystal-norms/mine", json={"norms": _full_norms()})
    assert res.status_code == 200
    data = res.json()
    assert data["onboarding_done"] is True
    assert data["norms"]["blue"]["3"] == 66

    me = player_client.get("/api/me").json()
    assert me["onboarding_done"] is True

    res2 = player_client.get("/api/crystal-norms/mine")
    assert res2.json()["onboarding_done"] is True
    assert res2.json()["norms"]["blue"]["3"] == 66


def test_set_my_norms_invalid_value(player_client):
    bad = _full_norms()
    bad["green"]["2"] = 0
    res = player_client.put("/api/crystal-norms/mine", json={"norms": bad})
    assert res.status_code == 400


def test_set_my_norms_missing_count(player_client):
    bad = {
        "green": {"1": 10, "2": 20, "3": 30, "4": 40, "5": 50},
        "blue": {"1": 20, "2": 40, "3": 60, "4": 80},
        "violet": {"1": 30, "2": 60, "3": 90, "4": 120, "5": 150},
    }
    res = player_client.put("/api/crystal-norms/mine", json={"norms": bad})
    assert res.status_code == 400


def test_set_my_norms_missing_color(player_client):
    bad = _full_norms()
    del bad["blue"]
    res = player_client.put("/api/crystal-norms/mine", json={"norms": bad})
    assert res.status_code == 422


def test_apply_preset(player_client):
    res = player_client.post("/api/crystal-norms/mine/preset/4")
    assert res.status_code == 200
    data = res.json()
    assert data["onboarding_done"] is True
    from routes.settings import VARIANT_TABLES
    assert data["norms"]["violet"]["5"] == VARIANT_TABLES[4]["violet"][5]


def test_apply_preset_invalid(player_client):
    assert player_client.post("/api/crystal-norms/mine/preset/99").status_code == 400


# ===== Онбординг-блокировка =====

def _setup_field(admin_client, monkeypatch):
    import io
    import tempfile
    from PIL import Image
    import config

    tmp = tempfile.mkdtemp(prefix="farm_norm_ob_")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp)
    fid = admin_client.post("/api/admin/fields", json={"name": "Огород", "cols": 4, "rows": 3}).json()["id"]
    pid = None
    for p in admin_client.get("/api/plants").json():
        if p["code"] == "jackobob":
            pid = p["id"]
            break
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [pid]})
    # По умолчанию новые клетки = empty; сделаем клетку (0,0) грядкой.
    admin_client.put(
        f"/api/admin/fields/{fid}/cells/blocked",
        json={"cells": [{"col": 0, "row": 0}], "kind": "bed"},
    )
    return fid, pid


def test_plant_on_cell_blocked_without_onboarding(admin_client, monkeypatch):
    fid, pid = _setup_field(admin_client, monkeypatch)
    with make_user_client_no_onboarding(777, "player") as c:
        res = c.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid})
    assert res.status_code == 403
    assert "онбординг" in res.json()["detail"].lower()


def test_plant_on_cell_allowed_after_onboarding(admin_client, monkeypatch):
    fid, pid = _setup_field(admin_client, monkeypatch)
    with make_user_client_no_onboarding(778, "player") as c:
        # Проходим онбординг пресетом.
        assert c.post("/api/crystal-norms/mine/preset/2").status_code == 200
        res = c.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid})
    assert res.status_code == 201


def test_start_build_blocked_without_onboarding_impl(admin_client, monkeypatch):
    # Блокировка онбординга проверяется и на постройке шатра (требует require_onboarding).
    fid = admin_client.post("/api/admin/fields", json={"name": "О", "cols": 4, "rows": 3}).json()["id"]
    tid = admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "С", "kind": "alchemy", "col1": "1", "row1": "1", "col2": "2", "row2": "2"},
    ).json()["id"]
    with make_user_client_no_onboarding(779, "player") as c:
        res = c.post(f"/api/fields/{fid}/tents/{tid}/start-build")
    assert res.status_code == 403


# ===== crystal_norm использует персональное значение =====

def test_crystal_norm_uses_personal():
    """crystal_norm возвращает персональное значение × count; без норм — стандарт."""
    from routes.settings import crystal_norm, VARIANT_TABLES, DEFAULT_VARIANT
    from models import User, UserCrystalNorm
    from tests.conftest import TestingSessionLocal

    s = TestingSessionLocal()
    try:
        u = User(vk_id=9000, role="player")
        s.add(u)
        s.commit()
        s.refresh(u)

        # Без персональных норм — стандарт (пресет 1).
        baseline = crystal_norm(s, u, "green", 3)
        assert baseline == VARIANT_TABLES[DEFAULT_VARIANT]["green"][3] * 3

        # Задаём свою норму green×1 = 999.
        s.add(UserCrystalNorm(user_id=u.vk_id, color="green", count=1, value=999))
        s.commit()
        assert crystal_norm(s, u, "green", 1) == 999

        # Другой цвет/количество остаётся стандартным.
        assert crystal_norm(s, u, "blue", 2) == VARIANT_TABLES[DEFAULT_VARIANT]["blue"][2] * 2
    finally:
        s.close()


# ===== Treasure =====

def test_set_standard_with_treasure(admin_client):
    norms = _full_norms()
    norms["green"]["0"] = 500
    norms["blue"]["0"] = 600
    norms["violet"]["0"] = 700
    res = admin_client.put("/api/crystal-norms/admin/standard", json={"norms": norms})
    assert res.status_code == 200
    data = res.json()["norms"]
    assert data["green"]["0"] == 500
    assert data["blue"]["0"] == 600
    assert data["violet"]["0"] == 700
    assert data["green"]["1"] == 11


def test_treasure_defaults_to_zero(player_client):
    norms = _full_norms()
    res = player_client.put("/api/crystal-norms/mine", json={"norms": norms})
    assert res.status_code == 200
    assert res.json()["norms"]["green"]["0"] == 0


# ===== Norm images =====

def test_norm_images_empty(admin_client):
    res = admin_client.get("/api/crystal-norms/admin/images")
    assert res.status_code == 200
    assert res.json() == []


def test_upload_norm_image(admin_client, uploads_tmp):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), (100, 200, 50)).save(buf, format="PNG")
    res = admin_client.put(
        "/api/crystal-norms/admin/images/green/1",
        files={"image": ("n.png", buf.getvalue(), "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["color"] == "green"
    assert data["count"] == 1
    assert data["image_url"] is not None

    images = admin_client.get("/api/crystal-norms/admin/images").json()
    assert len(images) == 1
    assert images[0]["image_url"] == data["image_url"]


def test_upload_norm_image_replaces(admin_client, uploads_tmp):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), (100, 200, 50)).save(buf, format="PNG")
    r1 = admin_client.put(
        "/api/crystal-norms/admin/images/blue/3",
        files={"image": ("a.png", buf.getvalue(), "image/png")},
    )
    buf2 = io.BytesIO()
    Image.new("RGB", (20, 20), (200, 100, 50)).save(buf2, format="PNG")
    r2 = admin_client.put(
        "/api/crystal-norms/admin/images/blue/3",
        files={"image": ("b.png", buf2.getvalue(), "image/png")},
    )
    assert r2.status_code == 200
    images = admin_client.get("/api/crystal-norms/admin/images").json()
    assert len(images) == 1
    assert images[0]["image_url"] == r2.json()["image_url"]


def test_upload_norm_image_requires_admin(player_client, uploads_tmp):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), (100, 200, 50)).save(buf, format="PNG")
    res = player_client.put(
        "/api/crystal-norms/admin/images/green/1",
        files={"image": ("n.png", buf.getvalue(), "image/png")},
    )
    assert res.status_code == 403
