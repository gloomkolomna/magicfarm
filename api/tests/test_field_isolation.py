import io
import tempfile

from PIL import Image

import config
from tests.conftest import make_user_client


def _img():
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (10, 120, 20)).save(buf, format="PNG")
    return buf.getvalue()


def _credit(c, amount):
    c.post(
        "/api/stitches/reports",
        data={"amount": str(amount)},
        files={"photo_after": ("r.png", io.BytesIO(_img()), "image/png")},
    )


def _plant_id(client, code="jackobob"):
    for p in client.get("/api/plants").json():
        if p["code"] == code:
            return p["id"]
    raise AssertionError(f"plant {code} not seeded")


def _make_garden_field(admin_client, monkeypatch, name="Огород"):
    tmp = tempfile.mkdtemp(prefix="farm_iso_")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp)
    fid = admin_client.post(
        "/api/admin/fields", json={"name": name, "cols": 3, "rows": 2}
    ).json()["id"]
    pid = _plant_id(admin_client)
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [pid]})
    cells = [{"col": c, "row": r} for r in range(2) for c in range(3)]
    admin_client.put(
        f"/api/admin/fields/{fid}/cells/blocked", json={"cells": cells, "kind": "bed"}
    )
    return fid, pid


def _cell(detail, col, row):
    return next(c for c in detail["cells"] if c["col"] == col and c["row"] == row)


# ===== Клетки: посадка изолирована между игроками =====

def test_other_player_does_not_see_my_plant(admin_client, monkeypatch):
    fid, pid = _make_garden_field(admin_client, monkeypatch)
    with make_user_client(1001, "player") as a:
        a.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid})
    with make_user_client(1002, "player") as b:
        detail = b.get(f"/api/fields/{fid}").json()
    cell = _cell(detail, 0, 0)
    assert cell["occupant_user_id"] is None
    assert cell["plant_id"] is None
    assert cell["plot"] is None


def test_two_players_plant_same_cell_independently(admin_client, monkeypatch):
    fid, pid = _make_garden_field(admin_client, monkeypatch)
    with make_user_client(1001, "player") as a:
        ra = a.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid})
        assert ra.status_code == 201
        assert ra.json()["occupant_user_id"] == 1001
    with make_user_client(1002, "player") as b:
        rb = b.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid})
        assert rb.status_code == 201
        assert rb.json()["occupant_user_id"] == 1002
        detail_b = b.get(f"/api/fields/{fid}").json()
    cell_b = _cell(detail_b, 0, 0)
    assert cell_b["occupant_user_id"] == 1002
    assert cell_b["plot"]["plant_id"] == pid
    with make_user_client(1001, "player") as a:
        detail_a = a.get(f"/api/fields/{fid}").json()
    cell_a = _cell(detail_a, 0, 0)
    assert cell_a["occupant_user_id"] == 1001


def test_invest_does_not_leak_to_other_player_plot(admin_client, monkeypatch):
    fid, pid = _make_garden_field(admin_client, monkeypatch)
    with make_user_client(1001, "player") as a:
        planted = a.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid}).json()
        a_required = planted["plot"]["required"]
        a_id = planted["plot"]["id"]
    with make_user_client(1002, "player") as b:
        planted = b.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid}).json()
        b_id = planted["plot"]["id"]
    assert a_id != b_id
    with make_user_client(1001, "player") as a:
        _credit(a, a_required)
        res = a.post(f"/api/farm/plots/{a_id}/invest", json={"amount": a_required})
        assert res.status_code == 200
        assert res.json()["status"] == "grown"
    with make_user_client(1002, "player") as b:
        detail = b.get(f"/api/fields/{fid}").json()
    cell_b = _cell(detail, 0, 0)
    assert cell_b["plot"]["status"] == "planted"
    assert cell_b["plot"]["accumulated"] == 0


# ===== Шатры: постройка изолирована между игроками =====

def _make_field_with_tent(admin_client, monkeypatch):
    tmp = tempfile.mkdtemp(prefix="farm_iso_tent_")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp)
    fid = admin_client.post(
        "/api/admin/fields", json={"name": "С шатром", "cols": 3, "rows": 2}
    ).json()["id"]
    res = admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "Стол", "kind": "alchemy", "col1": "1", "row1": "1", "col2": "2", "row2": "1"},
    )
    assert res.status_code == 201
    return fid, res.json()["id"]


def test_two_players_build_same_tent_independently(admin_client, monkeypatch):
    fid, tid = _make_field_with_tent(admin_client, monkeypatch)
    with make_user_client(2001, "player") as a:
        sa = a.post(f"/api/fields/{fid}/tents/{tid}/start-build")
        assert sa.status_code == 200
        assert sa.json()["builder_user_id"] == 2001
        a_required = sa.json()["required"]
    with make_user_client(2002, "player") as b:
        sb = b.post(f"/api/fields/{fid}/tents/{tid}/start-build")
        assert sb.status_code == 200
        assert sb.json()["builder_user_id"] == 2002
        b_required = sb.json()["required"]
    assert a_required > 0 and b_required > 0
    with make_user_client(2001, "player") as a:
        _credit(a, a_required)
        res = a.post(f"/api/fields/{fid}/tents/{tid}/build-invest", json={"amount": a_required})
        assert res.json()["build_status"] == "built"
    with make_user_client(2002, "player") as b:
        detail = b.get(f"/api/fields/{fid}").json()
    tent = next(t for t in detail["tents"] if t["id"] == tid)
    assert tent["build_status"] == "planted"
    assert tent["accumulated"] == 0
    assert tent["builder_user_id"] == 2002


# ===== Админ-просмотр: поле конкретного игрока =====

def test_admin_player_view_shows_only_that_player(admin_client, monkeypatch):
    fid, pid = _make_garden_field(admin_client, monkeypatch)
    with make_user_client(3001, "player") as a:
        a.post(f"/api/fields/{fid}/cells/0/0/plant", json={"plant_id": pid})
    with make_user_client(3002, "player") as b:
        b.post(f"/api/fields/{fid}/cells/1/0/plant", json={"plant_id": pid})
    detail_a = admin_client.get(f"/api/admin/players/3001/fields/{fid}").json()
    detail_b = admin_client.get(f"/api/admin/players/3002/fields/{fid}").json()
    a_cell00 = _cell(detail_a, 0, 0)
    a_cell10 = _cell(detail_a, 1, 0)
    b_cell00 = _cell(detail_b, 0, 0)
    b_cell10 = _cell(detail_b, 1, 0)
    assert a_cell00["occupant_user_id"] == 3001 and a_cell00["plot"] is not None
    assert a_cell10["occupant_user_id"] is None and a_cell10["plot"] is None
    assert b_cell10["occupant_user_id"] == 3002 and b_cell10["plot"] is not None
    assert b_cell00["occupant_user_id"] is None and b_cell00["plot"] is None
