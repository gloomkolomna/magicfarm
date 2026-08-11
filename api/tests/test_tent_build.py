import io
import tempfile

from PIL import Image

import config
from tests.conftest import make_user_client, make_user_client_no_onboarding


def _img_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (10, 120, 20)).save(buf, format="PNG")
    return buf.getvalue()


def _credit(c, amount):
    tmp = tempfile.mkdtemp(prefix="farm_tentbuild_")
    import importlib
    importlib.reload(config)
    config.UPLOADS_DIR = tmp
    c.post(
        "/api/stitches/reports",
        data={"amount": str(amount)},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )


def _make_field_with_slot(admin_client):
    """Создаёт локацию 4×3 и слот-шатёр alchemy в (1,1)-(2,2)."""
    fid = admin_client.post("/api/admin/fields", json={"name": "Огород", "cols": 4, "rows": 3}).json()["id"]
    res = admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "Стол", "kind": "alchemy", "col1": "1", "row1": "1", "col2": "2", "row2": "2"},
    )
    assert res.status_code == 201
    tent = res.json()
    assert tent["build_status"] == "slot"
    assert tent["required"] == 500
    return fid, tent["id"]


# ===== start-build =====

def test_create_tent_is_slot(admin_client):
    fid, tid = _make_field_with_slot(admin_client)
    t = admin_client.get(f"/api/admin/fields/{fid}").json()
    tent = [x for x in t["tents"] if x["id"] == tid][0]
    assert tent["build_status"] == "slot"
    assert tent["builder_user_id"] is None


def test_start_build_success(admin_client, monkeypatch):
    fid, tid = _make_field_with_slot(admin_client)
    with make_user_client(1001, "player") as c:
        res = c.post(f"/api/fields/{fid}/tents/{tid}/start-build")
    assert res.status_code == 200
    data = res.json()
    assert data["build_status"] == "planted"
    assert data["builder_user_id"] == 1001
    assert data["required"] > 0
    assert data["crystal_color"] is None
    assert data["crystal_count"] is None
    assert data["accumulated"] == 0


def test_start_build_not_slot(admin_client, monkeypatch):
    fid, tid = _make_field_with_slot(admin_client)
    with make_user_client(1002, "player") as c:
        c.post(f"/api/fields/{fid}/tents/{tid}/start-build")
        # Повторный start-build тем же игроком → уже planted.
        res = c.post(f"/api/fields/{fid}/tents/{tid}/start-build")
    assert res.status_code == 409


def test_start_build_tent_not_found(admin_client):
    fid, _ = _make_field_with_slot(admin_client)
    with make_user_client(1003, "player") as c:
        res = c.post(f"/api/fields/{fid}/tents/9999/start-build")
    assert res.status_code == 404


def test_start_build_field_not_found(admin_client):
    fid, tid = _make_field_with_slot(admin_client)
    with make_user_client(1004, "player") as c:
        res = c.post(f"/api/fields/9999/tents/{tid}/start-build")
    assert res.status_code == 404


def test_start_build_requires_onboarding(admin_client, monkeypatch):
    fid, tid = _make_field_with_slot(admin_client)
    with make_user_client_no_onboarding(1005, "player") as c:
        res = c.post(f"/api/fields/{fid}/tents/{tid}/start-build")
    assert res.status_code == 403


def test_start_build_requires_auth(client):
    assert client.post("/api/fields/1/tents/1/start-build").status_code == 401


# ===== build-invest =====

def test_build_invest_completes(admin_client, monkeypatch):
    fid, tid = _make_field_with_slot(admin_client)
    with make_user_client(1006, "player") as c:
        started = c.post(f"/api/fields/{fid}/tents/{tid}/start-build").json()
        required = started["required"]
        _credit(c, required)

        res = c.post(f"/api/fields/{fid}/tents/{tid}/build-invest", json={"amount": required})
        assert res.status_code == 200
        data = res.json()
        assert data["build_status"] == "built"
        assert data["accumulated"] >= required

        # Production создан и доступен через крафт-эндпоинт.
        prods = c.get("/api/farm/productions").json()
    assert any(p["kind"] == "alchemy" for p in prods)


def test_build_invest_partial_then_complete(admin_client, monkeypatch):
    fid, tid = _make_field_with_slot(admin_client)
    with make_user_client(1007, "player") as c:
        started = c.post(f"/api/fields/{fid}/tents/{tid}/start-build").json()
        required = started["required"]
        _credit(c, required)

        half = required // 2
        r1 = c.post(f"/api/fields/{fid}/tents/{tid}/build-invest", json={"amount": half}).json()
        assert r1["build_status"] == "planted"
        assert r1["accumulated"] == half

        r2 = c.post(f"/api/fields/{fid}/tents/{tid}/build-invest", json={"amount": required - half}).json()
        assert r2["build_status"] == "built"


def test_build_invest_other_user_forbidden(admin_client, monkeypatch):
    fid, tid = _make_field_with_slot(admin_client)
    with make_user_client(1008, "player") as c:
        c.post(f"/api/fields/{fid}/tents/{tid}/start-build")
    with make_user_client(1009, "player") as other:
        res = other.post(f"/api/fields/{fid}/tents/{tid}/build-invest", json={"amount": 1})
    assert res.status_code == 403


def test_build_invest_slot_not_started(admin_client):
    fid, tid = _make_field_with_slot(admin_client)
    with make_user_client(1010, "player") as c:
        res = c.post(f"/api/fields/{fid}/tents/{tid}/build-invest", json={"amount": 1})
    assert res.status_code == 409


def test_build_invest_insufficient_balance(admin_client, monkeypatch):
    fid, tid = _make_field_with_slot(admin_client)
    with make_user_client(1011, "player") as c:
        started = c.post(f"/api/fields/{fid}/tents/{tid}/start-build").json()
        res = c.post(f"/api/fields/{fid}/tents/{tid}/build-invest", json={"amount": started["required"]})
    assert res.status_code == 400


def test_build_invest_invalid_amount(admin_client, monkeypatch):
    fid, tid = _make_field_with_slot(admin_client)
    with make_user_client(1012, "player") as c:
        c.post(f"/api/fields/{fid}/tents/{tid}/start-build")
        res = c.post(f"/api/fields/{fid}/tents/{tid}/build-invest", json={"amount": 0})
    assert res.status_code == 400


def test_build_invest_requires_auth(client):
    assert client.post("/api/fields/1/tents/1/build-invest", json={"amount": 1}).status_code == 401


# ===== FieldDetail отдаёт build-поля =====

def test_field_detail_has_build_fields(admin_client, monkeypatch):
    fid, tid = _make_field_with_slot(admin_client)
    with make_user_client(1013, "player") as c:
        c.post(f"/api/fields/{fid}/tents/{tid}/start-build")
        detail = c.get(f"/api/fields/{fid}").json()
    tent = [t for t in detail["tents"] if t["id"] == tid][0]
    assert tent["build_status"] == "planted"
    assert tent["required"] > 0
