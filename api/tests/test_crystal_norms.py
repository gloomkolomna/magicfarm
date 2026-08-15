from tests.conftest import make_user_client, make_user_client_no_onboarding


def _full_norms():
    return {
        "green": {"norm": 11, "treasure": 0},
        "blue": {"norm": 22, "treasure": 0},
        "violet": {"norm": 33, "treasure": 0},
    }


# ===== Пресеты удалены =====

def test_presets_endpoint_removed(player_client):
    assert player_client.get("/api/crystal-norms/presets").status_code == 404


def test_apply_preset_endpoint_removed(player_client):
    assert player_client.post("/api/crystal-norms/mine/preset/2").status_code == 404


# ===== Стандарт =====

def test_get_standard_default(player_client):
    res = player_client.get("/api/crystal-norms/standard")
    assert res.status_code == 200
    norms = res.json()["norms"]
    from routes.settings import DEFAULT_CARD_NORMS
    for color in ("green", "blue", "violet"):
        assert norms[color]["norm"] == DEFAULT_CARD_NORMS[color]
        assert norms[color]["treasure"] == 0


def test_set_standard_admin(admin_client):
    res = admin_client.put("/api/crystal-norms/admin/standard", json={"norms": _full_norms()})
    assert res.status_code == 200
    assert res.json()["norms"]["blue"]["norm"] == 22

    res2 = admin_client.get("/api/crystal-norms/standard")
    assert res2.json()["norms"]["blue"]["norm"] == 22


def test_set_standard_player_forbidden(player_client):
    res = player_client.put("/api/crystal-norms/admin/standard", json={"norms": _full_norms()})
    assert res.status_code == 403


def test_set_standard_requires_body(admin_client):
    res = admin_client.put("/api/crystal-norms/admin/standard", json={})
    assert res.status_code == 422


def test_set_standard_invalid_value(admin_client):
    bad = _full_norms()
    bad["green"]["norm"] = 0
    res = admin_client.put("/api/crystal-norms/admin/standard", json={"norms": bad})
    assert res.status_code == 400


def test_set_standard_missing_color(admin_client):
    bad = _full_norms()
    del bad["violet"]
    res = admin_client.put("/api/crystal-norms/admin/standard", json={"norms": bad})
    assert res.status_code == 422


def test_set_standard_with_treasure(admin_client):
    norms = _full_norms()
    norms["green"]["treasure"] = 500
    norms["blue"]["treasure"] = 600
    norms["violet"]["treasure"] = 700
    res = admin_client.put("/api/crystal-norms/admin/standard", json={"norms": norms})
    assert res.status_code == 200
    data = res.json()["norms"]
    assert data["green"]["treasure"] == 500
    assert data["blue"]["treasure"] == 600
    assert data["violet"]["treasure"] == 700
    assert data["green"]["norm"] == 11


# ===== Мои нормы =====

def test_get_my_norms_new_player_returns_standard():
    with make_user_client_no_onboarding(555, "player") as c:
        res = c.get("/api/crystal-norms/mine")
    assert res.status_code == 200
    data = res.json()
    assert data["onboarding_done"] is False
    assert data["dice_norm"] == 200
    from routes.settings import DEFAULT_CARD_NORMS
    assert data["norms"]["green"]["norm"] == DEFAULT_CARD_NORMS["green"]


def test_set_my_norms(player_client):
    res = player_client.put(
        "/api/crystal-norms/mine",
        json={"norms": _full_norms(), "dice_norm": 150},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["onboarding_done"] is True
    assert data["norms"]["blue"]["norm"] == 22
    assert data["dice_norm"] == 150

    me = player_client.get("/api/me").json()
    assert me["onboarding_done"] is True

    res2 = player_client.get("/api/crystal-norms/mine")
    assert res2.json()["onboarding_done"] is True
    assert res2.json()["norms"]["blue"]["norm"] == 22
    assert res2.json()["dice_norm"] == 150


def test_set_my_norms_invalid_value(player_client):
    bad = _full_norms()
    bad["green"]["norm"] = 0
    res = player_client.put("/api/crystal-norms/mine", json={"norms": bad, "dice_norm": 150})
    assert res.status_code == 400


def test_set_my_norms_invalid_dice(player_client):
    res = player_client.put("/api/crystal-norms/mine", json={"norms": _full_norms(), "dice_norm": 0})
    assert res.status_code == 400


def test_set_my_norms_missing_color(player_client):
    bad = _full_norms()
    del bad["blue"]
    res = player_client.put("/api/crystal-norms/mine", json={"norms": bad, "dice_norm": 150})
    assert res.status_code == 422


def test_treasure_saved_and_returned(player_client):
    norms = _full_norms()
    norms["green"]["treasure"] = 400
    res = player_client.put("/api/crystal-norms/mine", json={"norms": norms, "dice_norm": 150})
    assert res.status_code == 200
    assert res.json()["norms"]["green"]["treasure"] == 400

    res2 = player_client.get("/api/crystal-norms/mine")
    assert res2.json()["norms"]["green"]["treasure"] == 400


def test_treasure_defaults_to_zero(player_client):
    res = player_client.put("/api/crystal-norms/mine", json={"norms": _full_norms(), "dice_norm": 150})
    assert res.status_code == 200
    assert res.json()["norms"]["green"]["treasure"] == 0


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
        assert c.put(
            "/api/crystal-norms/mine",
            json={"norms": _full_norms(), "dice_norm": 100},
        ).status_code == 200
        res = c.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid})
    assert res.status_code == 201


def test_start_build_blocked_without_onboarding_impl(admin_client, monkeypatch):
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
    """crystal_norm возвращает персональную базу за 1 кристалл; без норм — стандарт."""
    from routes.settings import crystal_norm, DEFAULT_CARD_NORMS
    from models import User, UserCrystalNorm
    from tests.conftest import TestingSessionLocal

    s = TestingSessionLocal()
    try:
        u = User(vk_id=9000, role="player")
        s.add(u)
        s.commit()
        s.refresh(u)

        assert crystal_norm(s, u, "green") == DEFAULT_CARD_NORMS["green"]

        s.add(UserCrystalNorm(user_id=u.vk_id, color="green", count=1, value=999))
        s.commit()
        assert crystal_norm(s, u, "green") == 999

        assert crystal_norm(s, u, "blue") == DEFAULT_CARD_NORMS["blue"]
    finally:
        s.close()


def test_treasure_norm_uses_personal_row():
    """calculate_norm для карты-сокровища берёт личную норму treasure_<color>."""
    from models import User, UserCrystalNorm
    from services.card_draw import calculate_norm
    from tests.conftest import TestingSessionLocal

    s = TestingSessionLocal()
    try:
        u = User(vk_id=9001, role="player")
        s.add(u)
        s.commit()
        s.refresh(u)

        s.add(UserCrystalNorm(user_id=u.vk_id, color="treasure_green", count=0, value=777))
        s.commit()

        cards = [{"color": "green", "value": 0, "is_treasure": True}]
        assert calculate_norm(s, u, cards) == 777
    finally:
        s.close()


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
