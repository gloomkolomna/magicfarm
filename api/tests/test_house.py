import io
import json

from PIL import Image

from tests.conftest import make_user_client, make_user_client_no_onboarding

MATERIALS = {"glass", "wood", "nails", "pipes", "bricks", "paint"}


def _img_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (10, 120, 20)).save(buf, format="PNG")
    return buf.getvalue()


def _make_field_with_house(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Поляна ведьмы", "cols": 4, "rows": 3}).json()["id"]
    res = admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "Дом ведьмы", "kind": "witch_house", "col1": "1", "row1": "1", "col2": "2", "row2": "2"},
    )
    assert res.status_code == 201, res.text
    return fid, res.json()["id"]


def _report(c, amount, context_type, context_id):
    return c.post(
        "/api/stitches/reports",
        data={"amount": str(amount), "context_type": context_type, "context_id": str(context_id)},
        files=[("photo_after", ("a.png", io.BytesIO(_img_bytes()), "image/png"))],
    )


# ===== размещение дома админом =====

def test_create_witch_house_tent(admin_client):
    fid, tid = _make_field_with_house(admin_client)
    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    tent = [t for t in detail["tents"] if t["id"] == tid][0]
    assert tent["kind"] == "witch_house"
    assert tent["required"] == 0


def test_create_tent_invalid_kind_lists_witch_house(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Поле", "cols": 4, "rows": 3}).json()["id"]
    res = admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "Х", "kind": "unknown_kind", "col1": "0", "row1": "0", "col2": "1", "row2": "1"},
    )
    assert res.status_code == 400
    assert "witch_house" in res.json()["detail"]


def test_create_tent_requires_admin(player_client):
    res = player_client.post(
        "/api/admin/fields/1/tents",
        data={"name": "Дом", "kind": "witch_house", "col1": "0", "row1": "0", "col2": "1", "row2": "1"},
    )
    assert res.status_code == 403


# ===== состояние дома =====

def test_house_state_default(admin_client):
    fid, tid = _make_field_with_house(admin_client)
    with make_user_client(2001, "player") as c:
        res = c.get(f"/api/fields/{fid}/house/{tid}")
    assert res.status_code == 200
    data = res.json()
    assert data["phase"] == "materials"
    assert data["collected"] == []
    assert data["current_material"] is None
    assert data["required"] == 0


def test_house_state_wrong_kind(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Огород", "cols": 4, "rows": 3}).json()["id"]
    tid = admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "Стол", "kind": "alchemy", "col1": "0", "row1": "0", "col2": "1", "row2": "1"},
    ).json()["id"]
    with make_user_client(2002, "player") as c:
        res = c.get(f"/api/fields/{fid}/house/{tid}")
    assert res.status_code == 400


def test_house_state_not_found(admin_client):
    fid, _ = _make_field_with_house(admin_client)
    with make_user_client(2003, "player") as c:
        assert c.get(f"/api/fields/{fid}/house/9999").status_code == 404
        assert c.get(f"/api/fields/9999/house/1").status_code == 404


def test_house_state_requires_auth(client):
    assert client.get("/api/fields/1/house/1").status_code == 401


# ===== request-material =====

def test_request_material_success(admin_client):
    fid, tid = _make_field_with_house(admin_client)
    with make_user_client(2004, "player") as c:
        res = c.post(f"/api/fields/{fid}/house/{tid}/request-material")
    assert res.status_code == 200
    data = res.json()
    assert data["current_material"] in MATERIALS
    assert 1 <= data["current_die"] <= 6
    assert data["current_required"] == 200 * data["current_die"]


def test_request_material_repeat_while_pending(admin_client):
    fid, tid = _make_field_with_house(admin_client)
    with make_user_client(2005, "player") as c:
        c.post(f"/api/fields/{fid}/house/{tid}/request-material")
        res = c.post(f"/api/fields/{fid}/house/{tid}/request-material")
    assert res.status_code == 409


def test_request_material_requires_onboarding(admin_client):
    fid, tid = _make_field_with_house(admin_client)
    with make_user_client_no_onboarding(2006, "player") as c:
        res = c.post(f"/api/fields/{fid}/house/{tid}/request-material")
    assert res.status_code == 403


def test_request_material_requires_auth(client):
    assert client.post("/api/fields/1/house/1/request-material").status_code == 401


def test_start_tent_build_blocked_for_witch_house(admin_client):
    fid, tid = _make_field_with_house(admin_client)
    with make_user_client(2007, "player") as c:
        res = c.post(f"/api/fields/{fid}/tents/{tid}/start-build")
    assert res.status_code == 400


# ===== зачёт материала через фото-отчёт =====

def test_material_report_insufficient_amount(admin_client):
    fid, tid = _make_field_with_house(admin_client)
    with make_user_client(2008, "player") as c:
        st = c.post(f"/api/fields/{fid}/house/{tid}/request-material").json()
        res = _report(c, st["current_required"] - 1, "house_material", st["id"])
    assert res.status_code == 400


def test_material_report_without_request(admin_client):
    fid, tid = _make_field_with_house(admin_client)
    with make_user_client(2009, "player") as c:
        st = c.get(f"/api/fields/{fid}/house/{tid}").json()
        res = _report(c, 500, "house_material", 1)
        assert res.status_code in (404, 409)
        assert st["current_material"] is None


def test_material_report_collects_material(admin_client):
    fid, tid = _make_field_with_house(admin_client)
    with make_user_client(2010, "player") as c:
        st = c.post(f"/api/fields/{fid}/house/{tid}/request-material").json()
        rep = _report(c, st["current_required"], "house_material", st["id"])
        assert rep.status_code == 201, rep.text
        st2 = c.get(f"/api/fields/{fid}/house/{tid}").json()
        assert st2["collected"] == [st["current_material"]]
        assert st2["current_material"] is None


def test_all_materials_without_repeats(admin_client):
    fid, tid = _make_field_with_house(admin_client)
    with make_user_client(2011, "player") as c:
        for i in range(6):
            st = c.post(f"/api/fields/{fid}/house/{tid}/request-material").json()
            rep = _report(c, st["current_required"] + i * 3, "house_material", st["id"])
            assert rep.status_code == 201, rep.text
        st = c.get(f"/api/fields/{fid}/house/{tid}").json()
        assert set(st["collected"]) == MATERIALS
        assert len(st["collected"]) == 6
        res = c.post(f"/api/fields/{fid}/house/{tid}/request-material")
        assert res.status_code == 409


# ===== постройка дома =====

def test_build_before_materials_collected(admin_client):
    fid, tid = _make_field_with_house(admin_client)
    with make_user_client(2012, "player") as c:
        res = c.post(f"/api/fields/{fid}/house/{tid}/build")
    assert res.status_code == 409


def test_build_draws_cards(admin_client):
    fid, tid = _make_field_with_house(admin_client)
    with make_user_client(2013, "player") as c:
        for i in range(6):
            st = c.post(f"/api/fields/{fid}/house/{tid}/request-material").json()
            _report(c, st["current_required"] + i * 3, "house_material", st["id"])
        res = c.post(f"/api/fields/{fid}/house/{tid}/build")
        assert res.status_code == 200
        data = res.json()
        assert data["required"] > 0
        cards = json.loads(data["cards_json"])
        assert len(cards) == 5
        res2 = c.post(f"/api/fields/{fid}/house/{tid}/build")
        assert res2.status_code == 409


def test_build_with_pending_material(admin_client):
    fid, tid = _make_field_with_house(admin_client)
    with make_user_client(2014, "player") as c:
        for i in range(5):
            st = c.post(f"/api/fields/{fid}/house/{tid}/request-material").json()
            _report(c, st["current_required"] + i * 3, "house_material", st["id"])
        c.post(f"/api/fields/{fid}/house/{tid}/request-material")
        res = c.post(f"/api/fields/{fid}/house/{tid}/build")
        assert res.status_code == 409


def test_build_requires_auth(client):
    assert client.post("/api/fields/1/house/1/build").status_code == 401


# ===== финал: дом построен, подарки, достижение =====

def _build_house(c, fid, tid):
    for i in range(6):
        st = c.post(f"/api/fields/{fid}/house/{tid}/request-material").json()
        rep = _report(c, st["current_required"] + i * 3, "house_material", st["id"])
        assert rep.status_code == 201, rep.text
    st = c.post(f"/api/fields/{fid}/house/{tid}/build").json()
    return st


def test_complete_house_full_flow(admin_client):
    fid, tid = _make_field_with_house(admin_client)
    admin_client.post("/api/admin/achievements", json={
        "name": "Построить дом", "condition_kind": "house_built", "condition_value": 1,
    })
    with make_user_client(2015, "player") as c:
        st = _build_house(c, fid, tid)
        rep = _report(c, st["required"] + 4242, "house_build", st["id"])
        assert rep.status_code == 201, rep.text

        st2 = c.get(f"/api/fields/{fid}/house/{tid}").json()
        assert st2["phase"] == "built"

        res = c.post(f"/api/fields/{fid}/house/{tid}/request-material")
        assert res.status_code == 409

        detail = c.get(f"/api/fields/{fid}").json()
        tent = [t for t in detail["tents"] if t["id"] == tid][0]
        assert tent["build_status"] == "built"

        inv = c.get("/api/farm/inventory").json()
        assert any(i["item_kind"] == "plant" and i["qty"] >= 5 for i in inv)
        assert any(i["item_kind"] == "product" and i["qty"] >= 5 for i in inv)

        achs = c.get("/api/achievements").json()
        house_ach = [a for a in achs if a["condition_kind"] == "house_built"]
        assert house_ach and house_ach[0]["earned"] is True


def test_house_report_insufficient_amount(admin_client):
    fid, tid = _make_field_with_house(admin_client)
    with make_user_client(2016, "player") as c:
        st = _build_house(c, fid, tid)
        res = _report(c, st["required"] - 1, "house_build", st["id"])
    assert res.status_code == 400


def test_other_player_house_independent(admin_client):
    fid, tid = _make_field_with_house(admin_client)
    with make_user_client(2017, "player") as c:
        _build_house(c, fid, tid)
    with make_user_client(2018, "player") as other:
        rep = _report(other, 100000, "house_build", 1)
        assert rep.status_code == 404
        st = other.get(f"/api/fields/{fid}/house/{tid}").json()
        assert st["phase"] == "materials"
        assert st["collected"] == []
        assert st["id"] is None
