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


def _seed_field(field_kind: str, name: str) -> int:
    from models import Field
    s = TestingSessionLocal()
    try:
        f = Field(code=f"f_{field_kind}_{name}", name=name, cols=3, rows=2,
                  field_kind=field_kind, min_level=0)
        s.add(f)
        s.commit()
        s.refresh(f)
        return f.id
    finally:
        s.close()


def test_admin_create_gather_cell(admin_client):
    iid1 = _seed_ingredient("Роса")
    iid2 = _seed_ingredient("Вода")
    fid = _seed_field("meadow", "Поляна")
    r = admin_client.post(f"/api/admin/fields/{fid}/gather-cells", json={
        "col": 0, "row": 0, "window": "morning", "ingredient_ids": [iid1, iid2],
    })
    assert r.status_code == 201
    data = r.json()
    assert data["window"] == "morning"
    assert set(data["ingredient_ids"]) == {iid1, iid2}
    assert len(data["ingredient_names"]) == 2


def test_admin_create_gather_cell_marks_cell_kind(admin_client):
    iid = _seed_ingredient("Роса")
    fid = _seed_field("meadow", "Поляна")
    admin_client.post(f"/api/admin/fields/{fid}/gather-cells", json={
        "col": 1, "row": 1, "window": "always", "ingredient_ids": [iid],
    })
    r = admin_client.get(f"/api/admin/fields/{fid}")
    assert r.status_code == 200
    cells = {f"{c['col']},{c['row']}": c for c in r.json()["cells"]}
    assert cells["1,1"]["kind"] == "gather"


def test_admin_gather_cell_wrong_field_kind(admin_client):
    iid = _seed_ingredient("Роса")
    fid = _seed_field("garden_beds", "Грядки")
    r = admin_client.post(f"/api/admin/fields/{fid}/gather-cells", json={
        "col": 0, "row": 0, "window": "always", "ingredient_ids": [iid],
    })
    assert r.status_code == 400


def test_admin_gather_cell_invalid_window(admin_client):
    iid = _seed_ingredient("Роса")
    fid = _seed_field("meadow", "Поляна")
    r = admin_client.post(f"/api/admin/fields/{fid}/gather-cells", json={
        "col": 0, "row": 0, "window": "lunch", "ingredient_ids": [iid],
    })
    assert r.status_code == 400


def test_admin_gather_cell_duplicate_409(admin_client):
    iid = _seed_ingredient("Роса")
    fid = _seed_field("meadow", "Поляна")
    body = {"col": 0, "row": 0, "window": "always", "ingredient_ids": [iid]}
    assert admin_client.post(f"/api/admin/fields/{fid}/gather-cells", json=body).status_code == 201
    assert admin_client.post(f"/api/admin/fields/{fid}/gather-cells", json=body).status_code == 409


def test_admin_gather_cell_out_of_bounds(admin_client):
    fid = _seed_field("meadow", "Поляна")
    r = admin_client.post(f"/api/admin/fields/{fid}/gather-cells", json={
        "col": 99, "row": 0, "window": "always", "ingredient_ids": [],
    })
    assert r.status_code == 400


def test_admin_update_gather_cell(admin_client):
    iid1 = _seed_ingredient("Роса")
    iid2 = _seed_ingredient("Вода")
    fid = _seed_field("meadow", "Поляна")
    gc_id = admin_client.post(f"/api/admin/fields/{fid}/gather-cells", json={
        "col": 0, "row": 0, "window": "morning", "ingredient_ids": [iid1],
    }).json()["id"]
    r = admin_client.put(f"/api/admin/fields/{fid}/gather-cells/{gc_id}", json={
        "window": "night", "ingredient_ids": [iid2],
    })
    assert r.status_code == 200
    assert r.json()["window"] == "night"
    assert r.json()["ingredient_ids"] == [iid2]


def test_admin_delete_gather_cell_resets_cell_kind(admin_client):
    iid = _seed_ingredient("Роса")
    fid = _seed_field("meadow", "Поляна")
    gc_id = admin_client.post(f"/api/admin/fields/{fid}/gather-cells", json={
        "col": 1, "row": 1, "window": "always", "ingredient_ids": [iid],
    }).json()["id"]
    assert admin_client.delete(f"/api/admin/fields/{fid}/gather-cells/{gc_id}").status_code == 204
    r = admin_client.get(f"/api/admin/fields/{fid}")
    cells = {f"{c['col']},{c['row']}": c for c in r.json()["cells"]}
    assert cells["1,1"]["kind"] == "empty"
    assert len(r.json()["gather_cells"]) == 0


def test_admin_create_trade_cell(admin_client):
    iid = _seed_ingredient("Роса")
    fid = _seed_field("shop", "Лавка")
    r = admin_client.post(f"/api/admin/fields/{fid}/trade-cells", json={
        "col": 0, "row": 0, "ingredient_ids": [iid],
    })
    assert r.status_code == 201
    assert r.json()["ingredient_ids"] == [iid]


def test_admin_trade_cell_wrong_field_kind(admin_client):
    iid = _seed_ingredient("Роса")
    fid = _seed_field("meadow", "Поляна")
    r = admin_client.post(f"/api/admin/fields/{fid}/trade-cells", json={
        "col": 0, "row": 0, "ingredient_ids": [iid],
    })
    assert r.status_code == 400


def test_admin_update_trade_cell(admin_client):
    iid1 = _seed_ingredient("Роса")
    iid2 = _seed_ingredient("Вода")
    fid = _seed_field("shop", "Лавка")
    tc_id = admin_client.post(f"/api/admin/fields/{fid}/trade-cells", json={
        "col": 0, "row": 0, "ingredient_ids": [iid1],
    }).json()["id"]
    r = admin_client.put(f"/api/admin/fields/{fid}/trade-cells/{tc_id}", json={
        "ingredient_ids": [iid2],
    })
    assert r.status_code == 200
    assert r.json()["ingredient_ids"] == [iid2]


def test_admin_delete_trade_cell_resets_cell_kind(admin_client):
    iid = _seed_ingredient("Роса")
    fid = _seed_field("shop", "Лавка")
    tc_id = admin_client.post(f"/api/admin/fields/{fid}/trade-cells", json={
        "col": 1, "row": 1, "ingredient_ids": [iid],
    }).json()["id"]
    assert admin_client.delete(f"/api/admin/fields/{fid}/trade-cells/{tc_id}").status_code == 204
    r = admin_client.get(f"/api/admin/fields/{fid}")
    cells = {f"{c['col']},{c['row']}": c for c in r.json()["cells"]}
    assert cells["1,1"]["kind"] == "empty"


def test_player_forbidden_on_cell_config(player_client):
    with make_user_client(123, "player") as c:
        assert c.post("/api/admin/fields/1/gather-cells", json={
            "col": 0, "row": 0, "window": "always", "ingredient_ids": [],
        }).status_code == 403
        assert c.post("/api/admin/fields/1/trade-cells", json={
            "col": 0, "row": 0, "ingredient_ids": [],
        }).status_code == 403
