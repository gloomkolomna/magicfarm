from tests.conftest import TestingSessionLocal, make_user_client

PLAYER_VK = 123


def _make_barnyard_field(admin_client, cells_count=3):
    paint = [(i, 0) for i in range(cells_count)]
    fid = admin_client.post(
        "/api/admin/fields", json={"name": "Скотный", "cols": cells_count, "rows": 1, "field_kind": "barnyard"}
    ).json()["id"]
    admin_client.put(
        f"/api/admin/fields/{fid}/cells/blocked",
        json={"cells": [{"col": c, "row": r} for c, r in paint], "kind": "barnyard"},
    )
    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    cells = sorted((c["id"] for c in detail["cells"]), )
    return cells


def _animal_id(admin_client, code):
    return next(a["id"] for a in admin_client.get("/api/admin/catalog/animals").json() if a["code"] == code)


def _make_animal_product(admin_client, animal_id, kind="sewing"):
    return admin_client.post("/api/admin/catalog/products", json={
        "name": f"Продукция {animal_id}", "animal_id": animal_id, "stars": 1, "production_kind": kind,
    }).json()["id"]


def _seed_inventory(vk_id, product_id, qty):
    from models import Inventory
    s = TestingSessionLocal()
    try:
        s.add(Inventory(user_id=vk_id, product_id=product_id, qty=qty))
        s.commit()
    finally:
        s.close()


def _seed_tent_storage(vk_id, product_id, qty):
    from models import BarnyardStorage
    s = TestingSessionLocal()
    try:
        s.add(BarnyardStorage(user_id=vk_id, product_id=product_id, qty=qty))
        s.commit()
    finally:
        s.close()


def _install_orders(pc, cells, animal_ids):
    slots = []
    for cell_id, animal_id in zip(cells, animal_ids):
        res = pc.post(f"/api/animals/cells/{cell_id}/install", json={"animal_id": animal_id})
        assert res.status_code == 200, res.text
        slots.append(res.json())
    return slots


def _openings(vk_id):
    from models import UserAnimalOpening
    s = TestingSessionLocal()
    try:
        rows = s.query(UserAnimalOpening).filter(UserAnimalOpening.user_id == vk_id).all()
        return {r.animal_id: r.opening_order for r in rows}
    finally:
        s.close()


def _sell(pc, product_id, qty):
    return pc.post("/api/farm/sell-surplus", json={
        "item_kind": "product", "item_id": product_id, "qty": qty,
    })


# sewing: (5 база + 30 наценка) × 0.5 = 17 за 1 ед.; далее +5 за каждое последующее животное
BASE_UNIT = 17


def test_install_assigns_sequential_opening_orders(admin_client):
    cells = _make_barnyard_field(admin_client)
    sheep, bunny = _animal_id(admin_client, "wool_sheep"), _animal_id(admin_client, "easter_bunny")

    with make_user_client(PLAYER_VK, "player") as pc:
        slots = _install_orders(pc, cells, [sheep, bunny])

    assert [s["opening_order"] for s in slots] == [1, 2]
    assert _openings(PLAYER_VK) == {sheep: 1, bunny: 2}


def test_reinstall_same_animal_keeps_opening_order(admin_client):
    cells = _make_barnyard_field(admin_client)
    sheep, bunny = _animal_id(admin_client, "wool_sheep"), _animal_id(admin_client, "easter_bunny")

    with make_user_client(PLAYER_VK, "player") as pc:
        first, second = _install_orders(pc, cells[:2], [sheep, bunny])

        res = pc.delete(f"/api/animals/pens/{first['id']}")
        assert res.status_code == 204

        again = pc.post(f"/api/animals/cells/{cells[0]}/install", json={"animal_id": sheep}).json()

    assert again["opening_order"] == 1
    assert _openings(PLAYER_VK) == {sheep: 1, bunny: 2}


def test_new_animal_gets_next_order_after_reinstall(admin_client):
    cells = _make_barnyard_field(admin_client)
    sheep, bunny = _animal_id(admin_client, "wool_sheep"), _animal_id(admin_client, "easter_bunny")
    bat = admin_client.post("/api/admin/catalog/animals", json={
        "name": "Летучая мышь", "emoji": "🦇", "product_name": "Шерсть летучей мыши", "sort_order": 3,
    }).json()["id"]

    with make_user_client(PLAYER_VK, "player") as pc:
        first, second = _install_orders(pc, cells[:2], [sheep, bunny])
        pc.delete(f"/api/animals/pens/{first['id']}")
        pc.post(f"/api/animals/cells/{cells[0]}/install", json={"animal_id": sheep})

        third = pc.post(f"/api/animals/cells/{cells[2]}/install", json={"animal_id": bat}).json()

    assert third["opening_order"] == 3
    assert _openings(PLAYER_VK) == {sheep: 1, bunny: 2, bat: 3}


def test_sell_first_animal_product_no_bonus(admin_client):
    cells = _make_barnyard_field(admin_client, cells_count=1)
    sheep = _animal_id(admin_client, "wool_sheep")
    wool_id = _make_animal_product(admin_client, sheep)

    with make_user_client(PLAYER_VK, "player") as pc:
        _install_orders(pc, cells, [sheep])

    _seed_inventory(PLAYER_VK, wool_id, 5)
    with make_user_client(PLAYER_VK, "player") as pc:
        res = _sell(pc, wool_id, 2)
        assert res.status_code == 200, res.text
        assert res.json()["coins_earned"] == 35


def test_sell_second_animal_product_plus_five(admin_client):
    cells = _make_barnyard_field(admin_client)
    sheep, bunny = _animal_id(admin_client, "wool_sheep"), _animal_id(admin_client, "easter_bunny")
    egg_id = _make_animal_product(admin_client, bunny)

    with make_user_client(PLAYER_VK, "player") as pc:
        _install_orders(pc, cells, [sheep, bunny])

    _seed_inventory(PLAYER_VK, egg_id, 5)
    with make_user_client(PLAYER_VK, "player") as pc:
        res = _sell(pc, egg_id, 1)
        assert res.status_code == 200, res.text
        assert res.json()["coins_earned"] == BASE_UNIT + 5

        res = _sell(pc, egg_id, 3)
        assert res.status_code == 200, res.text
        assert res.json()["coins_earned"] == 52 + 15


def test_sell_third_animal_product_plus_ten(admin_client):
    cells = _make_barnyard_field(admin_client)
    sheep, bunny = _animal_id(admin_client, "wool_sheep"), _animal_id(admin_client, "easter_bunny")
    bat = admin_client.post("/api/admin/catalog/animals", json={
        "name": "Летучая мышь", "emoji": "🦇", "product_name": "Шерсть летучей мыши", "sort_order": 3,
    }).json()["id"]
    fur_id = _make_animal_product(admin_client, bat)

    with make_user_client(PLAYER_VK, "player") as pc:
        _install_orders(pc, cells, [sheep, bunny, bat])

    _seed_inventory(PLAYER_VK, fur_id, 2)
    with make_user_client(PLAYER_VK, "player") as pc:
        res = _sell(pc, fur_id, 1)
        assert res.status_code == 200, res.text
        assert res.json()["coins_earned"] == BASE_UNIT + 10


def _set_sale_ratio(value):
    from models import Setting
    s = TestingSessionLocal()
    try:
        row = s.query(Setting).filter(Setting.key == "sale_price_ratio").first()
        row.value = str(value)
        s.commit()
    finally:
        s.close()


def test_bonus_not_cut_by_sale_ratio(admin_client):
    cells = _make_barnyard_field(admin_client)
    sheep, bunny = _animal_id(admin_client, "wool_sheep"), _animal_id(admin_client, "easter_bunny")
    egg_id = _make_animal_product(admin_client, bunny)

    with make_user_client(PLAYER_VK, "player") as pc:
        _install_orders(pc, cells, [sheep, bunny])

    _set_sale_ratio(0.1)
    _seed_inventory(PLAYER_VK, egg_id, 2)

    with make_user_client(PLAYER_VK, "player") as pc:
        res = _sell(pc, egg_id, 1)
        assert res.status_code == 200, res.text
        assert res.json()["coins_earned"] == 3 + 5


def test_sell_after_release_keeps_bonus(admin_client):
    cells = _make_barnyard_field(admin_client)
    sheep, bunny = _animal_id(admin_client, "wool_sheep"), _animal_id(admin_client, "easter_bunny")
    egg_id = _make_animal_product(admin_client, bunny)

    with make_user_client(PLAYER_VK, "player") as pc:
        slots = _install_orders(pc, cells, [sheep, bunny])
        res = pc.delete(f"/api/animals/pens/{slots[1]['id']}")
        assert res.status_code == 204

    _seed_inventory(PLAYER_VK, egg_id, 1)
    with make_user_client(PLAYER_VK, "player") as pc:
        res = _sell(pc, egg_id, 1)
        assert res.status_code == 200, res.text
        assert res.json()["coins_earned"] == BASE_UNIT + 5


def test_legacy_product_without_opening_costs_base(admin_client):
    sheep = _animal_id(admin_client, "wool_sheep")
    wool_id = _make_animal_product(admin_client, sheep)

    _seed_inventory(PLAYER_VK, wool_id, 1)
    with make_user_client(PLAYER_VK, "player") as pc:
        res = _sell(pc, wool_id, 1)
        assert res.status_code == 200, res.text
        assert res.json()["coins_earned"] == BASE_UNIT


def test_inventory_sell_price_for_animal_products(admin_client):
    cells = _make_barnyard_field(admin_client)
    sheep, bunny = _animal_id(admin_client, "wool_sheep"), _animal_id(admin_client, "easter_bunny")
    wool_id = _make_animal_product(admin_client, sheep)
    egg_id = _make_animal_product(admin_client, bunny)
    poison = next(p for p in admin_client.get("/api/admin/catalog/products").json() if p["code"] == "poison")

    with make_user_client(PLAYER_VK, "player") as pc:
        _install_orders(pc, cells, [sheep, bunny])

    _seed_inventory(PLAYER_VK, wool_id, 1)
    _seed_inventory(PLAYER_VK, egg_id, 1)
    _seed_inventory(PLAYER_VK, poison["id"], 1)

    with make_user_client(PLAYER_VK, "player") as pc:
        inv = pc.get("/api/farm/inventory").json()

    by_id = {i["item_id"]: i for i in inv if i["item_kind"] == "product"}
    assert by_id[wool_id]["sell_price"] == BASE_UNIT
    assert by_id[egg_id]["sell_price"] == BASE_UNIT + 5
    assert by_id[poison["id"]]["sell_price"] is None


def test_field_detail_shows_opening_order(admin_client):
    cells = _make_barnyard_field(admin_client)
    sheep, bunny = _animal_id(admin_client, "wool_sheep"), _animal_id(admin_client, "easter_bunny")

    with make_user_client(PLAYER_VK, "player") as pc:
        _install_orders(pc, cells, [sheep, bunny])
        detail = pc.get("/api/fields").json()
        fid = next(f["id"] for f in detail if f.get("field_kind") == "barnyard")
        cells_out = pc.get(f"/api/fields/{fid}").json()["cells"]

    orders = sorted(
        c["barnyard"]["opening_order"] for c in cells_out
        if c.get("barnyard") and c["barnyard"]["animal_id"] is not None
    )
    assert orders == [1, 2]


def test_tent_storage_price_per_unit(admin_client):
    cells = _make_barnyard_field(admin_client)
    sheep, bunny = _animal_id(admin_client, "wool_sheep"), _animal_id(admin_client, "easter_bunny")
    wool_id = _make_animal_product(admin_client, sheep)
    egg_id = _make_animal_product(admin_client, bunny)

    with make_user_client(PLAYER_VK, "player") as pc:
        _install_orders(pc, cells, [sheep, bunny])

    _seed_tent_storage(PLAYER_VK, wool_id, 4)
    _seed_tent_storage(PLAYER_VK, egg_id, 2)

    with make_user_client(PLAYER_VK, "player") as pc:
        res = pc.get("/api/animals/tents/storage")
        assert res.status_code == 200, res.text
        items = {i["product_id"]: i for i in res.json()["items"]}

    assert items[wool_id]["price_per_unit"] == BASE_UNIT
    assert items[egg_id]["price_per_unit"] == BASE_UNIT + 5
