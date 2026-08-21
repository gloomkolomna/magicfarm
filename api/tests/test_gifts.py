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


def test_gifts_require_auth(client):
    assert client.get("/api/gifts/received").status_code == 401
    assert client.post("/api/gifts", json={"to_user_id": 1, "kind": "plant", "item_id": 1, "qty": 1}).status_code == 401


def test_send_gift_validation(player_client):
    _add_user(7001)
    _give_plant(123, 1, 2)
    assert player_client.post("/api/gifts", json={"to_user_id": 123, "kind": "plant", "item_id": 1, "qty": 1}).status_code == 400
    assert player_client.post("/api/gifts", json={"to_user_id": 999999, "kind": "plant", "item_id": 1, "qty": 1}).status_code == 404
    assert player_client.post("/api/gifts", json={"to_user_id": 7001, "kind": "bogus", "item_id": 1, "qty": 1}).status_code == 400
    assert player_client.post("/api/gifts", json={"to_user_id": 7001, "kind": "plant", "item_id": 1, "qty": 5}).status_code == 400
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == 7001).first()
        u.status = "blocked"
        s.commit()
    finally:
        s.close()
    assert player_client.post("/api/gifts", json={"to_user_id": 7001, "kind": "plant", "item_id": 1, "qty": 1}).status_code == 400


def test_send_gift_deducts_and_creates_chat_message():
    from models import ChatMessage, Gift

    _add_user(7001)
    _give_plant(123, 1, 3)
    with make_user_client(123, "player") as a:
        res = a.post("/api/gifts", json={"to_user_id": 7001, "kind": "plant", "item_id": 1, "qty": 2})
        assert res.status_code == 201
        g = res.json()
        assert g["item_name"] == "Джекобоб"
        assert g["qty"] == 2
        assert g["claimed"] is False
    s = TestingSessionLocal()
    try:
        assert s.query(Inventory).filter(Inventory.user_id == 123, Inventory.plant_id == 1).first().qty == 1
        msg = s.query(ChatMessage).filter(ChatMessage.gift_id == g["id"]).first()
        assert msg is not None and msg.kind == "gift"
        assert s.query(Gift).filter(Gift.id == g["id"]).first().to_user_id == 7001
    finally:
        s.close()
    with make_user_client(7001, "player") as b:
        thread = b.get("/api/chat/with/123").json()
        assert any(m["kind"] == "gift" and m["gift_id"] == g["id"] for m in thread)
        assert [x["id"] for x in b.get("/api/gifts/received").json()] == [g["id"]]


def test_claim_gift_adds_to_recipient_stock():
    _add_user(7001)
    _give_plant(123, 1, 2)
    with make_user_client(123, "player") as a:
        gid = a.post("/api/gifts", json={"to_user_id": 7001, "kind": "plant", "item_id": 1, "qty": 1}).json()["id"]
    with make_user_client(7001, "player") as b:
        res = b.post(f"/api/gifts/{gid}/claim")
        assert res.status_code == 200
        assert res.json()["claimed"] is True
    s = TestingSessionLocal()
    try:
        row = s.query(Inventory).filter(Inventory.user_id == 7001, Inventory.plant_id == 1).first()
        assert row is not None and row.qty == 1
    finally:
        s.close()
    with make_user_client(7001, "player") as b:
        assert b.post(f"/api/gifts/{gid}/claim").status_code == 400
        assert b.get("/api/gifts/received").json() == []


def test_claim_gift_requires_recipient():
    _add_user(7001)
    _add_user(7002)
    _give_plant(123, 1, 2)
    with make_user_client(123, "player") as a:
        gid = a.post("/api/gifts", json={"to_user_id": 7001, "kind": "plant", "item_id": 1, "qty": 1}).json()["id"]
        assert a.get(f"/api/gifts/{gid}").status_code == 403
        assert a.post(f"/api/gifts/{gid}/claim").status_code == 403
    with make_user_client(7002, "player") as c:
        assert c.post(f"/api/gifts/{gid}/claim").status_code == 403
        assert c.get(f"/api/gifts/{gid}").status_code == 403
    with make_user_client(7001, "player") as b:
        assert b.get(f"/api/gifts/{gid}").status_code == 200


def test_gift_plant_uses_grown_image():
    from models import Plant

    _add_user(7001)
    s = TestingSessionLocal()
    try:
        p = s.query(Plant).filter(Plant.id == 1).first()
        p.image_url = "/api/uploads/main.png"
        p.image_grown_url = "/api/uploads/grown.png"
        p.image_harvested_url = "/api/uploads/harvested.png"
        s.commit()
    finally:
        s.close()
    _give_plant(123, 1, 1)
    with make_user_client(123, "player") as a:
        res = a.post("/api/gifts", json={"to_user_id": 7001, "kind": "plant", "item_id": 1, "qty": 1})
        assert res.status_code == 201
        assert res.json()["item_image_url"] == "/api/uploads/harvested.png"

    s = TestingSessionLocal()
    try:
        p = s.query(Plant).filter(Plant.id == 1).first()
        p.image_harvested_url = None
        s.commit()
    finally:
        s.close()
    _give_plant(123, 1, 1)
    with make_user_client(123, "player") as a:
        res = a.post("/api/gifts", json={"to_user_id": 7001, "kind": "plant", "item_id": 1, "qty": 1})
        assert res.json()["item_image_url"] == "/api/uploads/grown.png"


def test_gift_product_and_ingredient():
    _add_user(7001)
    _give_product(123, 1, 2)
    with make_user_client(123, "player") as a:
        res = a.post("/api/gifts", json={"to_user_id": 7001, "kind": "product", "item_id": 1, "qty": 1})
        assert res.status_code == 201
        assert res.json()["item_name"] == "Яд"
    with make_user_client(7001, "player") as b:
        gid = b.get("/api/gifts/received").json()[0]["id"]
        assert b.post(f"/api/gifts/{gid}/claim").status_code == 200
    s = TestingSessionLocal()
    try:
        row = s.query(Inventory).filter(Inventory.user_id == 7001, Inventory.product_id == 1).first()
        assert row is not None and row.qty == 1
    finally:
        s.close()

    _add_user(7002)
    ing_id = _make_ingredient()
    _give_ingredient(123, ing_id, 2)
    with make_user_client(123, "player") as a:
        res = a.post("/api/gifts", json={"to_user_id": 7002, "kind": "ingredient", "item_id": ing_id, "qty": 1})
        assert res.status_code == 201
        assert res.json()["item_name"] == "Тест-ингредиент"
    with make_user_client(7002, "player") as b:
        gid2 = b.get("/api/gifts/received").json()[0]["id"]
        assert b.post(f"/api/gifts/{gid2}/claim").status_code == 200
    s = TestingSessionLocal()
    try:
        row = s.query(UserIngredient).filter(
            UserIngredient.user_id == 7002, UserIngredient.ingredient_id == ing_id
        ).first()
        assert row is not None and row.qty == 1
    finally:
        s.close()


def test_cancel_gift_returns_items_to_sender():
    from models import ChatMessage, Gift

    _add_user(7001)
    _add_user(7002)
    _give_plant(7001, 1, 2)
    with make_user_client(7001, "player") as a:
        r = a.post("/api/gifts", json={"to_user_id": 7002, "kind": "plant", "item_id": 1, "qty": 2})
        assert r.status_code == 201, r.text
        gid = r.json()["id"]
        assert a.post(f"/api/gifts/{gid}/cancel").status_code == 200

    s = TestingSessionLocal()
    try:
        row = s.query(Inventory).filter(Inventory.user_id == 7001, Inventory.plant_id == 1).first()
        assert row is not None and row.qty == 2
        g = s.query(Gift).filter(Gift.id == gid).first()
        assert g.claimed_at is not None
        assert s.query(ChatMessage).filter(ChatMessage.gift_id == gid).count() == 0
    finally:
        s.close()

    with make_user_client(7002, "player") as b:
        assert b.get("/api/gifts/received").json() == []
        assert b.post(f"/api/gifts/{gid}/claim").status_code == 400


def test_cancel_gift_only_sender():
    _add_user(7001)
    _add_user(7002)
    _give_plant(7001, 1, 1)
    with make_user_client(7001, "player") as a:
        gid = a.post("/api/gifts", json={"to_user_id": 7002, "kind": "plant", "item_id": 1, "qty": 1}).json()["id"]
    with make_user_client(7002, "player") as b:
        assert b.post(f"/api/gifts/{gid}/cancel").status_code == 403


def test_cancel_claimed_gift_rejected():
    _add_user(7001)
    _add_user(7002)
    _give_plant(7001, 1, 1)
    with make_user_client(7001, "player") as a:
        gid = a.post("/api/gifts", json={"to_user_id": 7002, "kind": "plant", "item_id": 1, "qty": 1}).json()["id"]
    with make_user_client(7002, "player") as b:
        assert b.post(f"/api/gifts/{gid}/claim").status_code == 200
    with make_user_client(7001, "player") as a:
        assert a.post(f"/api/gifts/{gid}/cancel").status_code == 400


def test_second_claim_rejected():
    _add_user(7001)
    _add_user(7002)
    _give_plant(7001, 1, 2)
    with make_user_client(7001, "player") as a:
        gid = a.post("/api/gifts", json={"to_user_id": 7002, "kind": "plant", "item_id": 1, "qty": 1}).json()["id"]
    with make_user_client(7002, "player") as b:
        assert b.post(f"/api/gifts/{gid}/claim").status_code == 200
        assert b.post(f"/api/gifts/{gid}/claim").status_code == 400
