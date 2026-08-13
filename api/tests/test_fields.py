import io

from PIL import Image

import config


def _img_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (10, 120, 20)).save(buf, format="PNG")
    return buf.getvalue()


def _make_field(admin_client, name="Огород", cols=4, rows=3):
    return admin_client.post("/api/admin/fields", json={"name": name, "cols": cols, "rows": rows}).json()["id"]


def _plant_id(client, code="jackobob"):
    for p in client.get("/api/plants").json():
        if p["code"] == code:
            return p["id"]
    raise AssertionError(f"plant {code} not seeded")


def _setup_field_with_plants(admin_client, monkeypatch):
    """Создаёт локацию 4×3, разрешает растения, делает клетки грядками. Возвращает (field_id, plant_id)."""
    import tempfile
    tmp = tempfile.mkdtemp(prefix="farm_field_up_")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp)
    fid = _make_field(admin_client)
    pid = _plant_id(admin_client)
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [pid]})
    # Новые клетки по умолчанию = bed; подтверждаем, что все грядки.
    cells = [{"col": c, "row": r} for r in range(3) for c in range(4)]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={"cells": cells, "kind": "bed"})
    return fid, pid


# Все игровые тесты используют make_user_client, т.к. admin_client и player_client
# как две фикстуры в одном тесте конфликтуют на общем app.dependency_overrides.
def _player():
    from tests.conftest import make_user_client
    return make_user_client(123, "player")


# ===== Список / детали =====

def test_list_fields(admin_client):
    _make_field(admin_client, "Огород")
    _make_field(admin_client, "Сад")
    with _player() as c:
        rows = c.get("/api/fields").json()
    assert len(rows) == 2
    assert {r["name"] for r in rows} == {"Огород", "Сад"}


def test_list_requires_auth(client):
    assert client.get("/api/fields").status_code == 401


def test_get_field_detail(admin_client, monkeypatch):
    fid, pid = _setup_field_with_plants(admin_client, monkeypatch)
    with _player() as c:
        res = c.get(f"/api/fields/{fid}")
    assert res.status_code == 200
    d = res.json()
    assert d["cols"] == 4 and d["rows"] == 3
    assert len(d["cells"]) == 12
    assert any(p["id"] == pid for p in d["plants"])


def test_get_field_not_found(admin_client):
    with _player() as c:
        assert c.get("/api/fields/9999").status_code == 404


# ===== Посадка на клетку =====

def test_plant_on_cell(admin_client, monkeypatch):
    fid, pid = _setup_field_with_plants(admin_client, monkeypatch)
    with _player() as c:
        res = c.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid})
    assert res.status_code == 201
    cc = res.json()
    assert cc["kind"] == "bed"
    assert cc["plant_id"] == pid
    assert cc["occupant_user_id"] == 123
    assert cc["plot"] is not None
    assert cc["plot"]["status"] == "planted"
    assert cc["plot"]["required"] > 0
    assert cc["plant_name"] is not None


def test_plant_on_cell_not_found(admin_client, monkeypatch):
    fid, _ = _setup_field_with_plants(admin_client, monkeypatch)
    with _player() as c:
        res = c.post(f"/api/fields/{fid}/cells/9/9/plant", json={"plant_id": 1})
    assert res.status_code == 404


def test_plant_on_occupied(admin_client, monkeypatch):
    fid, pid = _setup_field_with_plants(admin_client, monkeypatch)
    with _player() as c:
        c.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid})
        res = c.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid})
    assert res.status_code == 409


def test_plant_on_pet_cell_refused(admin_client, monkeypatch):
    import tempfile
    tmp = tempfile.mkdtemp(prefix="farm_field_pet_")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp)
    fid = _make_field(admin_client)
    pid = _plant_id(admin_client)
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [pid]})
    admin_client.put(
        f"/api/admin/fields/{fid}/cells/blocked",
        json={"cells": [{"col": 0, "row": 0}], "kind": "pet"},
    )
    with _player() as c:
        res = c.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid})
    assert res.status_code == 400


def test_plant_on_tent_cell(admin_client, monkeypatch):
    fid, pid = _setup_field_with_plants(admin_client, monkeypatch)
    admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "T", "kind": "alchemy", "col1": "1", "row1": "1", "col2": "2", "row2": "2"},
    )
    with _player() as c:
        res = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": pid})
    assert res.status_code == 400


def test_plant_not_in_field_list(admin_client, monkeypatch):
    fid, _ = _setup_field_with_plants(admin_client, monkeypatch)
    other_pid = _plant_id(admin_client, "khlebozlak")  # не разрешён в локации
    with _player() as c:
        res = c.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": other_pid})
    assert res.status_code == 400


# ===== Полный цикл: посадка → invest → grown → harvest =====

def test_full_cycle_plant_grow_harvest(admin_client, monkeypatch):
    fid, pid = _setup_field_with_plants(admin_client, monkeypatch)
    import tempfile
    tmp = tempfile.mkdtemp(prefix="farm_field_credit_")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp)

    with _player() as c:
        _credit_client(c, 1000)
        # 1. Посадка.
        planted = c.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid}).json()
        plot_id = planted["plot"]["id"]
        required = planted["plot"]["required"]
        # 2. Инвестируем крестики до grown.
        res = c.post(f"/api/farm/plots/{plot_id}/invest", json={"amount": required})
        assert res.status_code == 200
        assert res.json()["status"] == "grown"
        # 3. Собираем урожай — клетка не освобождается, plot сбрасывается в planted.
        res = c.post(f"/api/fields/{fid}/cells/0/0/harvest")
        assert res.status_code == 200
        cc = res.json()
        assert cc["plant_id"] is not None
        assert cc["occupant_user_id"] is not None
        assert cc["plot"] is not None
        assert cc["plot"]["status"] == "planted"
        assert cc["plot"]["accumulated"] == 0
        assert cc["plot"]["required"] > 0
        # 4. Клетка занята — повторная посадка невозможна.
        res = c.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid})
        assert res.status_code == 409


def _credit_client(c, amount):
    c.post(
        "/api/stitches/reports",
        data={"amount": str(amount)},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )


def test_harvest_not_grown(admin_client, monkeypatch):
    fid, pid = _setup_field_with_plants(admin_client, monkeypatch)
    with _player() as c:
        c.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid})
        res = c.post(f"/api/fields/{fid}/cells/0/0/harvest")
    assert res.status_code == 400


def test_harvest_not_owner(admin_client, monkeypatch):
    fid, pid = _setup_field_with_plants(admin_client, monkeypatch)
    with _player() as c:
        c.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid})
    from tests.conftest import make_user_client
    with make_user_client(999, "player") as other:
        res = other.post(f"/api/fields/{fid}/cells/0/0/harvest")
    assert res.status_code == 404


def test_harvest_empty_cell(admin_client, monkeypatch):
    fid, _ = _setup_field_with_plants(admin_client, monkeypatch)
    with _player() as c:
        res = c.post(f"/api/fields/{fid}/cells/0/0/harvest")
    assert res.status_code == 404


def test_harvest_not_found(admin_client, monkeypatch):
    fid, _ = _setup_field_with_plants(admin_client, monkeypatch)
    with _player() as c:
        res = c.post(f"/api/fields/{fid}/cells/9/9/harvest")
    assert res.status_code == 404
