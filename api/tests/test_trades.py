from tests.conftest import TestingSessionLocal, make_user_client
from models import Ingredient, Inventory, User, UserIngredient


def _add_user(vk_id):
    s = TestingSessionLocal()
    try:
        if s.query(User).filter(User.vk_id == vk_id).first() is None:
            s.add(User(vk_id=vk_id, role="player", display_name=f"Игрок{vk_id}"))
            s.commit()
    finally:
        s.close()


def _give_plant(vk_id, plant_id, qty):
    s = TestingSessionLocal()
    try:
        row = s.query(Inventory).filter(Inventory.user_id == vk_id, Inventory.plant_id == plant_id).first()
        if row is None:
            row = Inventory(user_id=vk_id, plant_id=plant_id, qty=0)
            s.add(row)
        row.qty += qty
        s.commit()
    finally:
        s.close()


def _give_product(vk_id, product_id, qty):
    s = TestingSessionLocal()
    try:
        row = s.query(Inventory).filter(Inventory.user_id == vk_id, Inventory.product_id == product_id).first()
        if row is None:
            row = Inventory(user_id=vk_id, product_id=product_id, qty=0)
            s.add(row)
        row.qty += qty
        s.commit()
    finally:
        s.close()


def _give_ingredient(vk_id, ingredient_id, qty):
    s = TestingSessionLocal()
    try:
        row = s.query(UserIngredient).filter(
            UserIngredient.user_id == vk_id, UserIngredient.ingredient_id == ingredient_id
        ).first()
        if row is None:
            row = UserIngredient(user_id=vk_id, ingredient_id=ingredient_id, qty=0)
            s.add(row)
        row.qty += qty
        s.commit()
    finally:
        s.close()


def _make_ingredient():
    s = TestingSessionLocal()
    try:
        ing = s.query(Ingredient).filter(Ingredient.code == "test_ing").first()
        if ing is None:
            ing = Ingredient(code="test_ing", name="Тест-ингредиент")
            s.add(ing)
            s.commit()
            s.refresh(ing)
        return ing.id
    finally:
        s.close()


def _offer_payload(to_user_id, items, message=None):
    return {"to_user_id": to_user_id, "message": message, "items": items}


def test_trades_requires_auth(client):
    assert client.get("/api/trades/incoming").status_code == 401
    assert client.get("/api/trades/outgoing").status_code == 401
    assert client.get("/api/trades/history").status_code == 401


def test_create_trade_validation(player_client):
    _add_user(7001)
    bad_cases = [
        _offer_payload(7001, [], "пусто"),
        _offer_payload(7001, [{"kind": "plant", "item_id": 1, "qty": 0, "direction": "give"}], "qty 0"),
        _offer_payload(7001, [{"kind": "plant", "item_id": 1, "qty": 1, "direction": "want"}], "нет give"),
        _offer_payload(7001, [{"kind": "unknown", "item_id": 1, "qty": 1, "direction": "give"}], "неизвестный вид"),
        _offer_payload(7001, [{"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"}, {"kind": "plant", "item_id": 1, "qty": 1, "direction": "wrong"}], "неизвестное направление"),
    ]
    for payload in bad_cases:
        assert player_client.post("/api/trades", json=payload).status_code == 400


def test_create_trade_self_and_target(player_client):
    assert player_client.post("/api/trades", json=_offer_payload(123, [{"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"}])).status_code == 400
    assert player_client.post("/api/trades", json=_offer_payload(999999, [{"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"}])).status_code == 404
    _add_user(7002)
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == 7002).first()
        u.status = "blocked"
        s.commit()
    finally:
        s.close()
    assert player_client.post("/api/trades", json=_offer_payload(7002, [{"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"}])).status_code == 400


def test_create_trade_insufficient_stock(player_client):
    _add_user(7003)
    _give_plant(7003, 1, 2)
    res = player_client.post("/api/trades", json=_offer_payload(
        7003, [{"kind": "plant", "item_id": 1, "qty": 5, "direction": "give"}],
    ))
    assert res.status_code == 400
    res = player_client.post("/api/trades", json=_offer_payload(
        7003, [{"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"},
               {"kind": "ingredient", "item_id": 1, "qty": 1, "direction": "want"}],
    ))
    assert res.status_code == 400


def test_trade_flow_accept_transfers():
    _add_user(7001)
    _add_user(7002)
    ing_id = _make_ingredient()
    _give_plant(7001, 1, 5)
    _give_product(7001, 1, 2)
    _give_plant(7002, 1, 1)
    _give_ingredient(7002, ing_id, 3)

    with make_user_client(7001, "player") as a:
        created = a.post("/api/trades", json=_offer_payload(
            7002, [
                {"kind": "plant", "item_id": 1, "qty": 2, "direction": "give"},
                {"kind": "product", "item_id": 1, "qty": 1, "direction": "give"},
                {"kind": "ingredient", "item_id": ing_id, "qty": 1, "direction": "want"},
            ],
            message="Меняемся?",
        ))
        assert created.status_code == 201
        oid = created.json()["id"]
        assert created.json()["message"] == "Меняемся?"
        assert [o["id"] for o in a.get("/api/trades/outgoing").json()] == [oid]
        give_items = [i for i in created.json()["items"] if i["direction"] == "give"]
        assert len(give_items) == 2 and all(i["reserved"] for i in give_items)

    s = TestingSessionLocal()
    try:
        assert s.query(Inventory).filter(Inventory.user_id == 7001, Inventory.plant_id == 1).first().qty == 3
        assert s.query(Inventory).filter(Inventory.user_id == 7001, Inventory.product_id == 1).first().qty == 1
    finally:
        s.close()

    with make_user_client(7002, "player") as b:
        assert [o["id"] for o in b.get("/api/trades/incoming").json()] == [oid]
        acc = b.post(f"/api/trades/{oid}/accept")
        assert acc.status_code == 200
        assert acc.json()["status"] == "accepted"

    s = TestingSessionLocal()
    try:
        assert s.query(Inventory).filter(Inventory.user_id == 7001, Inventory.plant_id == 1).first().qty == 3
        assert s.query(Inventory).filter(Inventory.user_id == 7001, Inventory.product_id == 1).first().qty == 1
        assert s.query(UserIngredient).filter(UserIngredient.user_id == 7001, UserIngredient.ingredient_id == ing_id).first().qty == 1
        assert s.query(Inventory).filter(Inventory.user_id == 7002, Inventory.plant_id == 1).first().qty == 3
        assert s.query(UserIngredient).filter(UserIngredient.user_id == 7002, UserIngredient.ingredient_id == ing_id).first().qty == 2
    finally:
        s.close()


def test_accept_requires_recipient():
    _add_user(7001)
    _add_user(7002)
    _give_plant(7001, 1, 2)
    with make_user_client(7001, "player") as a:
        oid = a.post("/api/trades", json=_offer_payload(
            7002, [{"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"}],
        )).json()["id"]
        assert a.post(f"/api/trades/{oid}/accept").status_code == 403
        assert a.post(f"/api/trades/{oid}/reject").status_code == 403
    with make_user_client(7002, "player") as b:
        assert b.post(f"/api/trades/{oid}/cancel").status_code == 403
        assert b.post(f"/api/trades/{oid}/reject").status_code == 200
        assert b.post(f"/api/trades/{oid}/accept").status_code == 400


def test_cancel_by_offerer():
    _add_user(7001)
    _add_user(7002)
    _give_plant(7001, 1, 2)
    with make_user_client(7001, "player") as a:
        oid = a.post("/api/trades", json=_offer_payload(
            7002, [{"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"}],
        )).json()["id"]
        assert a.post(f"/api/trades/{oid}/cancel").status_code == 200
        assert a.get("/api/trades/outgoing").json() == []
        hist = a.get("/api/trades/history").json()
        assert any(o["id"] == oid and o["status"] == "cancelled" for o in hist)


def test_accept_fails_when_recipient_want_gone():
    from models import TradeHold

    _add_user(7001)
    _add_user(7002)
    ing_id = _make_ingredient()
    _give_plant(7001, 1, 2)
    _give_ingredient(7002, ing_id, 1)
    with make_user_client(7001, "player") as a:
        oid = a.post("/api/trades", json=_offer_payload(
            7002, [
                {"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"},
                {"kind": "ingredient", "item_id": ing_id, "qty": 1, "direction": "want"},
            ],
        )).json()["id"]
    s = TestingSessionLocal()
    try:
        row = s.query(UserIngredient).filter(
            UserIngredient.user_id == 7002, UserIngredient.ingredient_id == ing_id
        ).first()
        row.qty = 0
        s.commit()
    finally:
        s.close()
    with make_user_client(7002, "player") as b:
        res = b.post(f"/api/trades/{oid}/accept")
        assert res.status_code == 400
    s = TestingSessionLocal()
    try:
        assert s.query(TradeHold).filter(TradeHold.offer_id == oid).count() == 1
        assert s.query(Inventory).filter(Inventory.user_id == 7001, Inventory.plant_id == 1).first().qty == 1
    finally:
        s.close()


def test_create_reserves_give_items():
    from models import TradeHold

    _add_user(7001)
    _add_user(7002)
    _give_plant(7001, 1, 3)
    with make_user_client(7001, "player") as a:
        oid = a.post("/api/trades", json=_offer_payload(
            7002, [{"kind": "plant", "item_id": 1, "qty": 2, "direction": "give"}],
        )).json()["id"]
    s = TestingSessionLocal()
    try:
        row = s.query(Inventory).filter(Inventory.user_id == 7001, Inventory.plant_id == 1).first()
        assert row is not None and row.qty == 1
        hold = s.query(TradeHold).filter(TradeHold.offer_id == oid).first()
        assert hold is not None and hold.qty == 2 and hold.kind == "plant"
    finally:
        s.close()


def test_cancel_restores_reserved_items():
    from models import TradeHold

    _add_user(7001)
    _add_user(7002)
    _give_plant(7001, 1, 3)
    with make_user_client(7001, "player") as a:
        oid = a.post("/api/trades", json=_offer_payload(
            7002, [{"kind": "plant", "item_id": 1, "qty": 2, "direction": "give"}],
        )).json()["id"]
        assert a.post(f"/api/trades/{oid}/cancel").status_code == 200
    s = TestingSessionLocal()
    try:
        row = s.query(Inventory).filter(Inventory.user_id == 7001, Inventory.plant_id == 1).first()
        assert row is not None and row.qty == 3
        assert s.query(TradeHold).filter(TradeHold.offer_id == oid).count() == 0
    finally:
        s.close()


def test_reject_restores_reserved_items():
    from models import TradeHold

    _add_user(7001)
    _add_user(7002)
    _give_plant(7001, 1, 3)
    with make_user_client(7001, "player") as a:
        oid = a.post("/api/trades", json=_offer_payload(
            7002, [{"kind": "plant", "item_id": 1, "qty": 2, "direction": "give"}],
        )).json()["id"]
    with make_user_client(7002, "player") as b:
        assert b.post(f"/api/trades/{oid}/reject").status_code == 200
    s = TestingSessionLocal()
    try:
        row = s.query(Inventory).filter(Inventory.user_id == 7001, Inventory.plant_id == 1).first()
        assert row is not None and row.qty == 3
        assert s.query(TradeHold).filter(TradeHold.offer_id == oid).count() == 0
    finally:
        s.close()


def test_create_trade_merges_duplicate_items():
    from models import TradeHold, TradeOfferItem

    _add_user(7001)
    _add_user(7002)
    _give_plant(7001, 1, 3)
    _give_product(7002, 1, 2)
    with make_user_client(7001, "player") as a:
        r = a.post("/api/trades", json=_offer_payload(
            7002,
            [
                {"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"},
                {"kind": "plant", "item_id": 1, "qty": 2, "direction": "give"},
                {"kind": "product", "item_id": 1, "qty": 1, "direction": "want"},
                {"kind": "product", "item_id": 1, "qty": 1, "direction": "want"},
            ],
        ))
        assert r.status_code == 201, r.text
        body = r.json()
        give = [i for i in body["items"] if i["direction"] == "give"]
        want = [i for i in body["items"] if i["direction"] == "want"]
        assert len(give) == 1 and give[0]["qty"] == 3
        assert len(want) == 1 and want[0]["qty"] == 2
        oid = body["id"]

    s = TestingSessionLocal()
    try:
        row = s.query(Inventory).filter(Inventory.user_id == 7001, Inventory.plant_id == 1).first()
        assert row is None
        items = s.query(TradeOfferItem).filter(TradeOfferItem.offer_id == oid).all()
        assert sorted(i.qty for i in items) == [2, 3]
        holds = s.query(TradeHold).filter(TradeHold.offer_id == oid).all()
        assert len(holds) == 1 and holds[0].qty == 3
    finally:
        s.close()


def test_create_trade_merged_duplicates_insufficient():
    _add_user(7001)
    _add_user(7002)
    _give_plant(7001, 1, 3)
    with make_user_client(7001, "player") as a:
        r = a.post("/api/trades", json=_offer_payload(
            7002,
            [
                {"kind": "plant", "item_id": 1, "qty": 2, "direction": "give"},
                {"kind": "plant", "item_id": 1, "qty": 2, "direction": "give"},
            ],
        ))
        assert r.status_code == 400
        assert "Недостаточно" in r.json()["detail"]
    s = TestingSessionLocal()
    try:
        row = s.query(Inventory).filter(Inventory.user_id == 7001, Inventory.plant_id == 1).first()
        assert row is not None and row.qty == 3
    finally:
        s.close()


def test_create_trade_message_too_long(player_client):
    _add_user(7001)
    with make_user_client(123, "player") as a:
        r = a.post("/api/trades", json=_offer_payload(
            7001,
            [{"kind": "plant", "item_id": 1, "qty": 1, "direction": "want"},
             {"kind": "plant", "item_id": 2, "qty": 1, "direction": "give"}],
            message="x" * 1001,
        ))
        assert r.status_code == 400
        assert "символов" in r.json()["detail"]
