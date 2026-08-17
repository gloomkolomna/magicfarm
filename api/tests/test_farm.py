import io

from PIL import Image

import config


def _img_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (10, 120, 20)).save(buf, format="PNG")
    return buf.getvalue()


def _credit(player_client, monkeypatch, amount):
    tmp = __import__("tempfile").mkdtemp(prefix="farm_inv_")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp)
    player_client.post(
        "/api/stitches/reports",
        data={"amount": str(amount)},
        files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )


def _plant_id(player_client, code="jackobob"):
    for p in player_client.get("/api/plants").json():
        if p["code"] == code:
            return p["id"]
    raise AssertionError(f"plant {code} not seeded")


PLAYER_VK = 123


def _make_plot(user_id: int = PLAYER_VK, required: int = 500) -> int:
    """Создаёт Plot напрямую в БД (как это сделала бы посадка на клетку поля)."""
    from models import Plot
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        p = Plot(
            user_id=user_id, plant_id=1, qty=1,
            status="planted", accumulated=0, required=required,
            crystal_color="green", crystal_count=1,
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id
    finally:
        s.close()


def test_invest_insufficient_balance(player_client):
    plot_id = _make_plot()
    res = player_client.post(f"/api/farm/plots/{plot_id}/invest", json={"amount": 1})
    assert res.status_code == 400
    assert "недостаточно" in res.json()["detail"].lower()


def test_invest_grows_plot(player_client, monkeypatch):
    _credit(player_client, monkeypatch, 1000)
    plot_id = _make_plot(required=300)

    res = player_client.post(f"/api/farm/plots/{plot_id}/invest", json={"amount": 300})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "grown"
    assert data["accumulated"] == 300
    assert data["completed_at"] is not None

    me = player_client.get("/api/me").json()
    assert me["crosses_balance"] == 1000 - 300


def test_invest_partial_then_complete(player_client, monkeypatch):
    _credit(player_client, monkeypatch, 1000)
    plot_id = _make_plot(required=300)
    half = 300 // 2

    r1 = player_client.post(f"/api/farm/plots/{plot_id}/invest", json={"amount": half}).json()
    assert r1["status"] == "planted"
    assert r1["accumulated"] == half

    r2 = player_client.post(f"/api/farm/plots/{plot_id}/invest", json={"amount": 300 - half}).json()
    assert r2["status"] == "grown"


def test_invest_other_user_plot_forbidden(player_client):
    # Грядка принадлежит player_client (vk 123); чужой клиент 999 пытается инвестировать.
    plot_id = _make_plot(user_id=123)
    from tests.conftest import make_user_client
    with make_user_client(999, "player") as other:
        res = other.post(f"/api/farm/plots/{plot_id}/invest", json={"amount": 1})
        assert res.status_code == 403


def test_invest_already_grown(player_client, monkeypatch):
    _credit(player_client, monkeypatch, 1000)
    plot_id = _make_plot(required=300)
    player_client.post(f"/api/farm/plots/{plot_id}/invest", json={"amount": 300})
    res = player_client.post(f"/api/farm/plots/{plot_id}/invest", json={"amount": 1})
    assert res.status_code == 409


def test_invest_not_found(player_client):
    res = player_client.post("/api/farm/plots/9999/invest", json={"amount": 1})
    assert res.status_code == 404


def test_invest_invalid_amount(player_client, monkeypatch):
    _credit(player_client, monkeypatch, 1000)
    plot_id = _make_plot(required=300)
    res = player_client.post(f"/api/farm/plots/{plot_id}/invest", json={"amount": 0})
    assert res.status_code == 400


def test_inventory_hides_zero_qty(player_client):
    from models import Inventory
    from tests.conftest import TestingSessionLocal
    jack = _plant_id(player_client, "jackobob")
    khleb = _plant_id(player_client, "khlebozlak")
    poison = next(p for p in player_client.get("/api/farm/products").json() if p["code"] == "poison")
    s = TestingSessionLocal()
    try:
        s.add(Inventory(user_id=PLAYER_VK, plant_id=jack, qty=0))
        s.add(Inventory(user_id=PLAYER_VK, plant_id=khleb, qty=4))
        s.add(Inventory(user_id=PLAYER_VK, product_id=poison["id"], qty=0))
        s.commit()
    finally:
        s.close()

    items = player_client.get("/api/farm/inventory").json()
    assert all(i["qty"] > 0 for i in items)
    plant_ids = {i["item_id"] for i in items if i["item_kind"] == "plant"}
    assert jack not in plant_ids
    assert khleb in plant_ids
    assert not any(i["item_kind"] == "product" and i["item_id"] == poison["id"] for i in items)

    plants_only = player_client.get("/api/farm/inventory", params={"item_kind": "plant"}).json()
    assert all(i["qty"] > 0 for i in plants_only)
    assert {i["item_id"] for i in plants_only} == {khleb}
