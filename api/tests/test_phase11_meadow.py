from datetime import datetime, timezone

from tests.conftest import TestingSessionLocal, make_user_client


def _msk_dt(hour: int, minute: int = 0) -> datetime:
    from services.msk_time import MSK
    return datetime(2026, 8, 18, hour, minute, tzinfo=MSK)


def _seed_ingredient(name: str) -> int:
    from models import Ingredient
    from routes.admin_catalog import _auto_code, _unique_code
    s = TestingSessionLocal()
    try:
        code = _unique_code(_auto_code(name, "ingredient"), Ingredient, s)
        ing = Ingredient(code=code, name=name)
        s.add(ing)
        s.commit()
        s.refresh(ing)
        return ing.id
    finally:
        s.close()


def _seed_meadow_field() -> int:
    from models import Field
    s = TestingSessionLocal()
    try:
        f = Field(code="meadow_test", name="Лесная поляна", cols=3, rows=2,
                  field_kind="meadow", min_level=0)
        s.add(f)
        s.commit()
        s.refresh(f)
        return f.id
    finally:
        s.close()


def _seed_gather_cell(field_id: int, col: int, row: int, window: str, ingredient_ids: list[int]) -> int:
    from models import FieldCell, GatherCell, GatherCellIngredient
    s = TestingSessionLocal()
    try:
        gc = GatherCell(field_id=field_id, col=col, row=row, window=window)
        s.add(gc)
        s.flush()
        for iid in ingredient_ids:
            s.add(GatherCellIngredient(gather_cell_id=gc.id, ingredient_id=iid))
        s.add(FieldCell(field_id=field_id, col=col, row=row, kind="gather"))
        s.commit()
        s.refresh(gc)
        return gc.id
    finally:
        s.close()


def test_meadow_get_cells(monkeypatch, admin_client):
    iid1 = _seed_ingredient("Роса")
    iid2 = _seed_ingredient("Вода")
    fid = _seed_meadow_field()
    _seed_gather_cell(fid, 0, 0, "morning", [iid1, iid2])
    monkeypatch.setattr("services.msk_time.now_msk", lambda: _msk_dt(6))
    with make_user_client(123, "player") as c:
        r = c.get(f"/api/meadow/{fid}")
        assert r.status_code == 200
        data = r.json()
        assert data["field_id"] == fid
        assert data["now_msk"]
        assert len(data["cells"]) == 1
        cell = data["cells"][0]
        assert cell["window"] == "morning"
        assert cell["available"] is True
        assert cell["collected_today"] is False
        assert cell["next_open_at"] is None
        assert {i["id"] for i in cell["ingredients"]} == {iid1, iid2}


def test_meadow_cell_sleeping_shows_next_open(monkeypatch, admin_client):
    iid = _seed_ingredient("Роса")
    fid = _seed_meadow_field()
    _seed_gather_cell(fid, 0, 0, "morning", [iid])
    monkeypatch.setattr("services.msk_time.now_msk", lambda: _msk_dt(12))
    with make_user_client(123, "player") as c:
        r = c.get(f"/api/meadow/{fid}")
        assert r.status_code == 200
        cell = r.json()["cells"][0]
        assert cell["available"] is False
        assert cell["next_open_at"]


def test_meadow_cell_collected_today(monkeypatch, admin_client):
    iid = _seed_ingredient("Роса")
    fid = _seed_meadow_field()
    gc_id = _seed_gather_cell(fid, 0, 0, "always", [iid])
    monkeypatch.setattr("services.msk_time.now_msk", lambda: _msk_dt(12))
    with make_user_client(123, "player") as c:
        c.post(f"/api/meadow/cells/{gc_id}/gather")
        r = c.get(f"/api/meadow/{fid}")
        cell = r.json()["cells"][0]
        assert cell["collected_today"] is True
        assert cell["available"] is False


def test_meadow_wrong_field_kind(admin_client):
    from models import Field
    s = TestingSessionLocal()
    try:
        f = Field(code="beds_test", name="Грядки", cols=2, rows=1, field_kind="garden_beds")
        s.add(f)
        s.commit()
        s.refresh(f)
        fid = f.id
    finally:
        s.close()
    with make_user_client(123, "player") as c:
        assert c.get(f"/api/meadow/{fid}").status_code == 400


def test_meadow_field_gate(monkeypatch, admin_client):
    from models import Field
    s = TestingSessionLocal()
    try:
        f = Field(code="meadow_l3", name="Поляна 3 ур", cols=2, rows=1,
                  field_kind="meadow", min_level=3)
        s.add(f)
        s.commit()
        s.refresh(f)
        fid = f.id
    finally:
        s.close()
    monkeypatch.setattr("services.msk_time.now_msk", lambda: _msk_dt(6))
    with make_user_client(123, "player") as c:
        assert c.get(f"/api/meadow/{fid}").status_code == 403


def test_meadow_requires_auth(client):
    assert client.get("/api/meadow/1").status_code == 401


def test_gather_success(monkeypatch, admin_client):
    iid = _seed_ingredient("Роса")
    fid = _seed_meadow_field()
    gc_id = _seed_gather_cell(fid, 0, 0, "always", [iid])
    monkeypatch.setattr("services.msk_time.now_msk", lambda: _msk_dt(12))
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/meadow/cells/{gc_id}/gather")
        assert r.status_code == 200
        data = r.json()
        assert data["cell_id"] == gc_id
        assert data["ingredient"]["id"] == iid
        assert data["apothecary_qty"] == 1
        apo = c.get("/api/apothecary").json()
        assert apo[0]["ingredient_id"] == iid
        assert apo[0]["qty"] == 1


def test_gather_accumulates_on_repeat_day(monkeypatch, admin_client):
    iid = _seed_ingredient("Роса")
    fid = _seed_meadow_field()
    gc1 = _seed_gather_cell(fid, 0, 0, "always", [iid])
    gc2 = _seed_gather_cell(fid, 1, 0, "always", [iid])
    monkeypatch.setattr("services.msk_time.now_msk", lambda: _msk_dt(12))
    with make_user_client(123, "player") as c:
        c.post(f"/api/meadow/cells/{gc1}/gather")
        r = c.post(f"/api/meadow/cells/{gc2}/gather")
        assert r.status_code == 200
        assert r.json()["apothecary_qty"] == 2
        apo = c.get("/api/apothecary").json()
        assert apo[0]["qty"] == 2


def test_gather_daily_limit_429(monkeypatch, admin_client):
    iid = _seed_ingredient("Роса")
    fid = _seed_meadow_field()
    gc_id = _seed_gather_cell(fid, 0, 0, "always", [iid])
    monkeypatch.setattr("services.msk_time.now_msk", lambda: _msk_dt(12))
    with make_user_client(123, "player") as c:
        assert c.post(f"/api/meadow/cells/{gc_id}/gather").status_code == 200
        r = c.post(f"/api/meadow/cells/{gc_id}/gather")
        assert r.status_code == 429


def test_gather_outside_window_400(monkeypatch, admin_client):
    iid = _seed_ingredient("Роса")
    fid = _seed_meadow_field()
    gc_id = _seed_gather_cell(fid, 0, 0, "morning", [iid])
    monkeypatch.setattr("services.msk_time.now_msk", lambda: _msk_dt(12))
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/meadow/cells/{gc_id}/gather")
        assert r.status_code == 400
        assert "Вернитесь" in r.json()["detail"]


def test_gather_random_within_cell_list(monkeypatch, admin_client):
    iid1 = _seed_ingredient("Роса")
    iid2 = _seed_ingredient("Вода")
    fid = _seed_meadow_field()
    gc_id = _seed_gather_cell(fid, 0, 0, "always", [iid1, iid2])
    monkeypatch.setattr("services.msk_time.now_msk", lambda: _msk_dt(12))
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/meadow/cells/{gc_id}/gather")
        assert r.status_code == 200
        assert r.json()["ingredient"]["id"] in (iid1, iid2)


def test_gather_empty_cell_list_400(monkeypatch, admin_client):
    fid = _seed_meadow_field()
    gc_id = _seed_gather_cell(fid, 0, 0, "always", [])
    monkeypatch.setattr("services.msk_time.now_msk", lambda: _msk_dt(12))
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/meadow/cells/{gc_id}/gather")
        assert r.status_code == 400


def test_gather_unknown_cell_404(admin_client):
    with make_user_client(123, "player") as c:
        assert c.post("/api/meadow/cells/9999/gather").status_code == 404


def test_gather_field_gate_403(monkeypatch, admin_client):
    from models import Field
    s = TestingSessionLocal()
    try:
        f = Field(code="meadow_gate", name="Поляна", cols=2, rows=1,
                  field_kind="meadow", min_level=3)
        s.add(f)
        s.commit()
        s.refresh(f)
        gc_id = _seed_gather_cell(f.id, 0, 0, "always", [])
    finally:
        s.close()
    monkeypatch.setattr("services.msk_time.now_msk", lambda: _msk_dt(12))
    with make_user_client(123, "player") as c:
        assert c.post(f"/api/meadow/cells/{gc_id}/gather").status_code == 403


def test_gather_requires_auth(client):
    assert client.post("/api/meadow/cells/1/gather").status_code == 401
