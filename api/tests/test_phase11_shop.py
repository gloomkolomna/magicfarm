from tests.conftest import TestingSessionLocal, make_user_client


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


def _seed_shop_field() -> int:
    from models import Field
    s = TestingSessionLocal()
    try:
        f = Field(code="shop_test", name="Городская лавка", cols=3, rows=2,
                  field_kind="shop", min_level=0)
        s.add(f)
        s.commit()
        s.refresh(f)
        return f.id
    finally:
        s.close()


def _seed_trade_cell(field_id: int, col: int, row: int, ingredient_ids: list[int]) -> int:
    from models import FieldCell, TradeCell, TradeCellIngredient
    s = TestingSessionLocal()
    try:
        tc = TradeCell(field_id=field_id, col=col, row=row)
        s.add(tc)
        s.flush()
        for iid in ingredient_ids:
            s.add(TradeCellIngredient(trade_cell_id=tc.id, ingredient_id=iid))
        s.add(FieldCell(field_id=field_id, col=col, row=row, kind="trade"))
        s.commit()
        s.refresh(tc)
        return tc.id
    finally:
        s.close()


def _seed_user_ingredient(vk_id: int, ingredient_id: int, qty: int) -> None:
    from models import UserIngredient
    s = TestingSessionLocal()
    try:
        s.add(UserIngredient(user_id=vk_id, ingredient_id=ingredient_id, qty=qty))
        s.commit()
    finally:
        s.close()


def test_shop_get_cells(admin_client):
    iid = _seed_ingredient("Роса")
    fid = _seed_shop_field()
    _seed_trade_cell(fid, 0, 0, [iid])
    with make_user_client(123, "player") as c:
        r = c.get(f"/api/shop/{fid}")
        assert r.status_code == 200
        data = r.json()
        assert data["field_id"] == fid
        assert len(data["cells"]) == 1
        assert data["cells"][0]["ingredients"][0]["id"] == iid
        assert data["apothecary"] == []


def test_shop_wrong_field_kind(admin_client):
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
        assert c.get(f"/api/shop/{fid}").status_code == 400


def test_shop_field_gate(admin_client):
    from models import Field
    s = TestingSessionLocal()
    try:
        f = Field(code="shop_gate", name="Лавка", cols=2, rows=1,
                  field_kind="shop", min_level=3)
        s.add(f)
        s.commit()
        s.refresh(f)
        fid = f.id
    finally:
        s.close()
    with make_user_client(123, "player") as c:
        assert c.get(f"/api/shop/{fid}").status_code == 403


def test_shop_requires_auth(client):
    assert client.get("/api/shop/1").status_code == 401


def test_barter_happy_path(admin_client):
    want_iid = _seed_ingredient("Роса")
    give_iid = _seed_ingredient("Вода")
    fid = _seed_shop_field()
    tc_id = _seed_trade_cell(fid, 0, 0, [want_iid])
    _seed_user_ingredient(123, give_iid, 5)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/shop/cells/{tc_id}/barter", json={
            "want_ingredient_id": want_iid,
            "give_kind": "ingredient",
            "give_item_id": give_iid,
            "qty": 2,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["qty"] == 2
        assert data["want"]["id"] == want_iid
        assert data["give"]["id"] == give_iid
        apo = {i["ingredient_id"]: i["qty"] for i in data["apothecary"]}
        assert apo[give_iid] == 3
        assert apo[want_iid] == 2


def test_barter_want_not_in_cell(admin_client):
    want_iid = _seed_ingredient("Роса")
    give_iid = _seed_ingredient("Вода")
    other_iid = _seed_ingredient("Папоротник")
    fid = _seed_shop_field()
    tc_id = _seed_trade_cell(fid, 0, 0, [other_iid])
    _seed_user_ingredient(123, give_iid, 5)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/shop/cells/{tc_id}/barter", json={
            "want_ingredient_id": want_iid,
            "give_kind": "ingredient",
            "give_item_id": give_iid,
            "qty": 1,
        })
        assert r.status_code == 400


def test_barter_insufficient_give(admin_client):
    want_iid = _seed_ingredient("Роса")
    give_iid = _seed_ingredient("Вода")
    fid = _seed_shop_field()
    tc_id = _seed_trade_cell(fid, 0, 0, [want_iid])
    _seed_user_ingredient(123, give_iid, 1)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/shop/cells/{tc_id}/barter", json={
            "want_ingredient_id": want_iid,
            "give_kind": "ingredient",
            "give_item_id": give_iid,
            "qty": 2,
        })
        assert r.status_code == 400


def test_barter_no_give_in_storage(admin_client):
    want_iid = _seed_ingredient("Роса")
    give_iid = _seed_ingredient("Вода")
    fid = _seed_shop_field()
    tc_id = _seed_trade_cell(fid, 0, 0, [want_iid])
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/shop/cells/{tc_id}/barter", json={
            "want_ingredient_id": want_iid,
            "give_kind": "ingredient",
            "give_item_id": give_iid,
            "qty": 1,
        })
        assert r.status_code == 400


def test_barter_qty_lt_one(admin_client):
    want_iid = _seed_ingredient("Роса")
    give_iid = _seed_ingredient("Вода")
    fid = _seed_shop_field()
    tc_id = _seed_trade_cell(fid, 0, 0, [want_iid])
    _seed_user_ingredient(123, give_iid, 5)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/shop/cells/{tc_id}/barter", json={
            "want_ingredient_id": want_iid,
            "give_kind": "ingredient",
            "give_item_id": give_iid,
            "qty": 0,
        })
        assert r.status_code == 400


def test_barter_unknown_cell_404(admin_client):
    want_iid = _seed_ingredient("Роса")
    give_iid = _seed_ingredient("Вода")
    _seed_user_ingredient(123, give_iid, 5)
    with make_user_client(123, "player") as c:
        r = c.post("/api/shop/cells/9999/barter", json={
            "want_ingredient_id": want_iid,
            "give_kind": "ingredient",
            "give_item_id": give_iid,
            "qty": 1,
        })
        assert r.status_code == 404


def test_barter_requires_auth(client):
    assert client.post("/api/shop/cells/1/barter", json={
        "want_ingredient_id": 1, "give_kind": "ingredient", "give_item_id": 2, "qty": 1,
    }).status_code == 401


def test_barter_from_inventory_plant(admin_client):
    """Можно отдать растение со склада игрока (Inventory), а не только ингредиент."""
    want_iid = _seed_ingredient("Роса")
    fid = _seed_shop_field()
    tc_id = _seed_trade_cell(fid, 0, 0, [want_iid])
    plant = next(p for p in admin_client.get("/api/plants").json() if p["code"] == "jackobob")

    from models import Inventory
    s = TestingSessionLocal()
    try:
        s.add(Inventory(user_id=123, plant_id=plant["id"], qty=4))
        s.commit()
    finally:
        s.close()

    with make_user_client(123, "player") as c:
        r = c.post(f"/api/shop/cells/{tc_id}/barter", json={
            "want_ingredient_id": want_iid,
            "give_kind": "plant",
            "give_item_id": plant["id"],
            "qty": 3,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["give"]["kind"] == "plant"
        assert data["give"]["id"] == plant["id"]
        assert data["qty"] == 3

    s = TestingSessionLocal()
    try:
        inv = s.query(Inventory).filter(Inventory.user_id == 123, Inventory.plant_id == plant["id"]).first()
        assert inv.qty == 1
    finally:
        s.close()
