from tests.conftest import TestingSessionLocal, make_user_client
from models import BoardHold, BoardPost, Ingredient, Inventory, User, UserIngredient


def _add_user(vk_id, hidden=False):
    s = TestingSessionLocal()
    try:
        if s.query(User).filter(User.vk_id == vk_id).first() is None:
            s.add(User(vk_id=vk_id, role="player", display_name=f"Игрок{vk_id}", hidden=hidden))
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
        ing = s.query(Ingredient).filter(Ingredient.code == "board_ing").first()
        if ing is None:
            ing = Ingredient(code="board_ing", name="Досочный ингредиент")
            s.add(ing)
            s.commit()
            s.refresh(ing)
        return ing.id
    finally:
        s.close()


def _payload(items, message=None):
    return {"message": message, "items": items}


def test_board_requires_auth(client):
    assert client.get("/api/board").status_code == 401
    assert client.get("/api/board/mine").status_code == 401
    assert client.get("/api/board/history").status_code == 401
    assert client.post("/api/board", json=_payload([{"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"}])).status_code == 401


def test_create_board_validation(player_client):
    bad_cases = [
        _payload([], "пусто"),
        _payload([{"kind": "plant", "item_id": 1, "qty": 0, "direction": "give"}], "qty 0"),
        _payload([{"kind": "plant", "item_id": 1, "qty": 1, "direction": "want"}], "нет give"),
        _payload([{"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"}], "нет want"),
        _payload([{"kind": "unknown", "item_id": 1, "qty": 1, "direction": "give"}], "неизвестный вид"),
        _payload([{"kind": "plant", "item_id": 1, "qty": 1, "direction": "wrong"}], "неизвестное направление"),
    ]
    for payload in bad_cases:
        assert player_client.post("/api/board", json=payload).status_code == 400


def test_create_board_message_too_long(player_client):
    _give_plant(123, 1, 1)
    r = player_client.post("/api/board", json=_payload(
        [
            {"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"},
            {"kind": "plant", "item_id": 2, "qty": 1, "direction": "want"},
        ],
        message="x" * 1001,
    ))
    assert r.status_code == 400
    assert "символов" in r.json()["detail"]


def test_create_board_reserves_give_items(player_client):
    _give_plant(123, 1, 3)
    r = player_client.post("/api/board", json=_payload([
        {"kind": "plant", "item_id": 1, "qty": 2, "direction": "give"},
        {"kind": "plant", "item_id": 2, "qty": 1, "direction": "want"},
    ]))
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    s = TestingSessionLocal()
    try:
        row = s.query(Inventory).filter(Inventory.user_id == 123, Inventory.plant_id == 1).first()
        assert row is not None and row.qty == 1
        hold = s.query(BoardHold).filter(BoardHold.post_id == pid).first()
        assert hold is not None and hold.qty == 2 and hold.kind == "plant"
    finally:
        s.close()


def test_board_hides_posts_viewer_cannot_fulfill():
    _add_user(7001)
    ing_id = _make_ingredient()
    _give_plant(7001, 1, 1)
    _give_plant(7001, 2, 1)
    with make_user_client(7001, "player") as a:
        r = a.post("/api/board", json=_payload([
            {"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"},
            {"kind": "ingredient", "item_id": ing_id, "qty": 1, "direction": "want"},
        ]))
        assert r.status_code == 201, r.text
        pid = r.json()["id"]

    _add_user(7002)
    with make_user_client(7002, "player") as b:
        posts = b.get("/api/board").json()
        assert all(p["id"] != pid for p in posts)

    _give_ingredient(7002, ing_id, 1)
    with make_user_client(7002, "player") as b:
        posts = b.get("/api/board").json()
        assert any(p["id"] == pid for p in posts)
        post = next(p for p in posts if p["id"] == pid)
        assert post["can_respond"] is True


def test_board_excludes_own_posts(player_client):
    _give_plant(123, 1, 2)
    r = player_client.post("/api/board", json=_payload([
        {"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"},
        {"kind": "plant", "item_id": 2, "qty": 1, "direction": "want"},
    ]))
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert all(p["id"] != pid for p in player_client.get("/api/board").json())
    mine = player_client.get("/api/board/mine").json()
    assert any(p["id"] == pid for p in mine)


def test_respond_first_wins_and_transfers():
    _add_user(7001)
    _add_user(7002)
    _add_user(7003)
    ing_id = _make_ingredient()
    _give_plant(7001, 1, 2)
    _give_ingredient(7002, ing_id, 1)
    _give_ingredient(7003, ing_id, 1)

    with make_user_client(7001, "player") as a:
        r = a.post("/api/board", json=_payload([
            {"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"},
            {"kind": "ingredient", "item_id": ing_id, "qty": 1, "direction": "want"},
        ]))
        assert r.status_code == 201, r.text
        pid = r.json()["id"]

    with make_user_client(7002, "player") as b:
        res = b.post(f"/api/board/{pid}/respond")
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "fulfilled"

    with make_user_client(7003, "player") as c:
        assert c.post(f"/api/board/{pid}/respond").status_code == 409

    s = TestingSessionLocal()
    try:
        assert s.query(Inventory).filter(Inventory.user_id == 7001, Inventory.plant_id == 1).first().qty == 1
        assert s.query(Inventory).filter(Inventory.user_id == 7002, Inventory.plant_id == 1).first().qty == 1
        assert s.query(UserIngredient).filter(UserIngredient.user_id == 7001, UserIngredient.ingredient_id == ing_id).first().qty == 1
        assert s.query(UserIngredient).filter(UserIngredient.user_id == 7002, UserIngredient.ingredient_id == ing_id).first() is None
        assert s.query(BoardHold).filter(BoardHold.post_id == pid).count() == 0
    finally:
        s.close()


def test_respond_requires_want_items():
    _add_user(7001)
    _add_user(7002)
    ing_id = _make_ingredient()
    _give_plant(7001, 1, 1)
    with make_user_client(7001, "player") as a:
        r = a.post("/api/board", json=_payload([
            {"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"},
            {"kind": "ingredient", "item_id": ing_id, "qty": 1, "direction": "want"},
        ]))
        pid = r.json()["id"]
    with make_user_client(7002, "player") as b:
        res = b.post(f"/api/board/{pid}/respond")
        assert res.status_code == 400
        assert "недостаточно" in res.json()["detail"].lower()


def test_respond_own_post_400(player_client):
    _give_plant(123, 1, 1)
    _give_ingredient(123, _make_ingredient(), 1)
    r = player_client.post("/api/board", json=_payload([
        {"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"},
        {"kind": "plant", "item_id": 2, "qty": 1, "direction": "want"},
    ]))
    pid = r.json()["id"]
    assert player_client.post(f"/api/board/{pid}/respond").status_code == 400


def test_cancel_restores_reserved_items(player_client):
    _give_plant(123, 1, 3)
    r = player_client.post("/api/board", json=_payload([
        {"kind": "plant", "item_id": 1, "qty": 2, "direction": "give"},
        {"kind": "plant", "item_id": 2, "qty": 1, "direction": "want"},
    ]))
    pid = r.json()["id"]
    assert player_client.post(f"/api/board/{pid}/cancel").status_code == 200
    s = TestingSessionLocal()
    try:
        row = s.query(Inventory).filter(Inventory.user_id == 123, Inventory.plant_id == 1).first()
        assert row is not None and row.qty == 3
        assert s.query(BoardHold).filter(BoardHold.post_id == pid).count() == 0
    finally:
        s.close()


def test_cancel_only_author(player_client):
    _add_user(7001)
    _give_plant(123, 1, 2)
    r = player_client.post("/api/board", json=_payload([
        {"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"},
        {"kind": "plant", "item_id": 2, "qty": 1, "direction": "want"},
    ]))
    pid = r.json()["id"]
    with make_user_client(7001, "player") as b:
        assert b.post(f"/api/board/{pid}/cancel").status_code == 403


def test_expire_restores_holds():
    import datetime

    _add_user(7001)
    _give_plant(7001, 1, 2)
    with make_user_client(7001, "player") as a:
        r = a.post("/api/board", json=_payload([
            {"kind": "plant", "item_id": 1, "qty": 1, "direction": "give"},
            {"kind": "plant", "item_id": 2, "qty": 1, "direction": "want"},
        ]))
        pid = r.json()["id"]

    s = TestingSessionLocal()
    try:
        post = s.query(BoardPost).filter(BoardPost.id == pid).first()
        post.expires_at = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        s.commit()
    finally:
        s.close()

    with make_user_client(7001, "player") as a:
        assert a.get("/api/board/mine").json() == []
        hist = a.get("/api/board/history").json()
        assert any(p["id"] == pid and p["status"] == "expired" for p in hist)

    s = TestingSessionLocal()
    try:
        row = s.query(Inventory).filter(Inventory.user_id == 7001, Inventory.plant_id == 1).first()
        assert row is not None and row.qty == 2
        assert s.query(BoardHold).filter(BoardHold.post_id == pid).count() == 0
    finally:
        s.close()
