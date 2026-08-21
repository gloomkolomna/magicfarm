import io
import os

import pytest
from PIL import Image

from tests.conftest import make_user_client


def _img_bytes(w=800, h=600, fmt="PNG"):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (90, 160, 70)).save(buf, format=fmt)
    return buf.getvalue()


def _plant_id(client, code="jackobob"):
    for p in client.get("/api/plants").json():
        if p["code"] == code:
            return p["id"]
    raise AssertionError(f"plant {code} not seeded")


# ===== Права =====

def test_list_requires_admin(player_client):
    assert player_client.get("/api/admin/fields").status_code == 403


def test_list_requires_auth(client):
    assert client.get("/api/admin/fields").status_code == 401


# ===== CRUD локаций =====

def test_create_field(admin_client):
    res = admin_client.post("/api/admin/fields", json={"name": "Огород", "cols": 6, "rows": 4})
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Огород"
    assert data["cols"] == 6 and data["rows"] == 4
    assert data["map_url"] is None
    fid = data["id"]
    # Проверим, что сетка клеток создалась.
    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    assert len(detail["cells"]) == 24
    assert all(c["kind"] == "empty" for c in detail["cells"])


def test_create_field_invalid_dim(admin_client):
    res = admin_client.post("/api/admin/fields", json={"name": "X", "cols": 0, "rows": 4})
    assert res.status_code == 400
    res = admin_client.post("/api/admin/fields", json={"name": "X", "cols": 6, "rows": 99})
    assert res.status_code == 400


def test_create_field_empty_name(admin_client):
    assert admin_client.post("/api/admin/fields", json={"name": "  "}).status_code == 400


def test_list_fields(admin_client):
    admin_client.post("/api/admin/fields", json={"name": "Garden"})
    admin_client.post("/api/admin/fields", json={"name": "Orchard"})
    rows = admin_client.get("/api/admin/fields").json()
    assert len(rows) == 2
    assert {r["name"] for r in rows} == {"Garden", "Orchard"}


def test_get_field_detail(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Огород"}).json()["id"]
    res = admin_client.get(f"/api/admin/fields/{fid}")
    assert res.status_code == 200
    d = res.json()
    assert d["id"] == fid
    assert d["cells"] == [] or len(d["cells"]) > 0
    assert d["tents"] == []
    assert d["plants"] == []


def test_get_field_not_found(admin_client):
    assert admin_client.get("/api/admin/fields/9999").status_code == 404


def test_update_field_name_and_dims(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Огород", "cols": 4, "rows": 4}).json()["id"]
    res = admin_client.put(f"/api/admin/fields/{fid}", json={"name": "Большой огород", "cols": 6})
    assert res.status_code == 200
    assert res.json()["name"] == "Большой огород"
    # Сетка пересоздалась под новые размеры: 6×4=24 клетки.
    assert len(admin_client.get(f"/api/admin/fields/{fid}").json()["cells"]) == 24


def test_update_field_shrink_removes_cells(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "О", "cols": 6, "rows": 4}).json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}", json={"cols": 3, "rows": 2})
    cells = admin_client.get(f"/api/admin/fields/{fid}").json()["cells"]
    assert len(cells) == 6  # 3×2


def test_shrink_field_trims_pet_zone(admin_client):
    fid = admin_client.post(
        "/api/admin/fields", json={"name": "Лужайка", "cols": 4, "rows": 4, "field_kind": "lawn"}
    ).json()["id"]
    r = admin_client.post(f"/api/admin/fields/{fid}/pet-zones", data={"col1": 2, "row1": 2, "col2": 3, "row2": 3})
    assert r.status_code == 201

    admin_client.put(f"/api/admin/fields/{fid}", json={"cols": 2, "rows": 2})
    d = admin_client.get(f"/api/admin/fields/{fid}").json()
    assert d["pet_zones"] == []
    assert len(d["cells"]) == 4
    assert all(c["kind"] == "empty" for c in d["cells"])


def test_shrink_field_keeps_inner_pet_zone(admin_client):
    fid = admin_client.post(
        "/api/admin/fields", json={"name": "Лужайка", "cols": 4, "rows": 4, "field_kind": "lawn"}
    ).json()["id"]
    assert admin_client.post(
        f"/api/admin/fields/{fid}/pet-zones", data={"col1": 0, "row1": 0, "col2": 1, "row2": 1}
    ).status_code == 201

    admin_client.put(f"/api/admin/fields/{fid}", json={"cols": 2, "rows": 2})
    d = admin_client.get(f"/api/admin/fields/{fid}").json()
    assert len(d["pet_zones"]) == 1
    assert d["pet_zones"][0]["col2"] == 1 and d["pet_zones"][0]["row2"] == 1


def test_shrink_field_trims_tent(admin_client, uploads_tmp):
    fid = admin_client.post("/api/admin/fields", json={"name": "О", "cols": 4, "rows": 4}).json()["id"]
    assert admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "T", "col1": "2", "row1": "2", "col2": "3", "row2": "3"},
    ).status_code == 201

    admin_client.put(f"/api/admin/fields/{fid}", json={"cols": 2, "rows": 2})
    d = admin_client.get(f"/api/admin/fields/{fid}").json()
    assert d["tents"] == []
    assert len(d["cells"]) == 4
    assert all(c["kind"] == "empty" for c in d["cells"])


def test_update_field_grid_color(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "О"}).json()["id"]
    res = admin_client.put(f"/api/admin/fields/{fid}", json={"grid_color": "#aabbcc"})
    assert res.json()["grid_color"] == "#aabbcc"
    res = admin_client.put(f"/api/admin/fields/{fid}", json={"grid_color": "bad"})
    assert res.status_code == 400


def test_delete_field(admin_client, uploads_tmp):
    fid = admin_client.post("/api/admin/fields", json={"name": "О"}).json()["id"]
    assert admin_client.delete(f"/api/admin/fields/{fid}").status_code == 204
    assert admin_client.get(f"/api/admin/fields/{fid}").status_code == 404


def test_delete_field_player_forbidden(player_client):
    assert player_client.delete("/api/admin/fields/1").status_code == 403


# ===== Загрузка картинки карты =====

def test_upload_map(admin_client, uploads_tmp):
    fid = admin_client.post("/api/admin/fields", json={"name": "О"}).json()["id"]
    res = admin_client.put(
        f"/api/admin/fields/{fid}/map",
        files={"map_image": ("m.png", io.BytesIO(_img_bytes(1200, 800)), "image/png")},
    )
    assert res.status_code == 200
    assert res.json()["map_url"].startswith("/api/uploads/field_")
    # Старая картинка удаляется при замене.
    old = res.json()["map_url"]
    res2 = admin_client.put(
        f"/api/admin/fields/{fid}/map",
        files={"map_image": ("m.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res2.json()["map_url"] != old


def test_upload_map_not_image(admin_client, uploads_tmp):
    fid = admin_client.post("/api/admin/fields", json={"name": "О"}).json()["id"]
    res = admin_client.put(
        f"/api/admin/fields/{fid}/map",
        files={"map_image": ("x.txt", io.BytesIO(b"nope"), "text/plain")},
    )
    assert res.status_code == 400


def test_upload_map_not_found(admin_client, uploads_tmp):
    res = admin_client.put(
        "/api/admin/fields/9999/map",
        files={"map_image": ("m.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 404


# ===== Кисти клеток =====

def test_set_blocked_bad_coords(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "О"}).json()["id"]
    res = admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={"cells": [{"col": "x"}]})
    assert res.status_code == 400


def test_set_pet_cells(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "П", "cols": 3, "rows": 3}).json()["id"]
    res = admin_client.put(
        f"/api/admin/fields/{fid}/cells/blocked",
        json={"cells": [{"col": 0, "row": 0}, {"col": 1, "row": 1}], "kind": "pet"},
    )
    assert res.status_code == 200
    kinds = {(c["col"], c["row"]): c["kind"] for c in res.json()["cells"]}
    assert kinds[(0, 0)] == "pet"
    assert kinds[(1, 1)] == "pet"
    assert kinds[(2, 2)] == "empty"

    # Сброс → все pet обратно в empty.
    res = admin_client.put(
        f"/api/admin/fields/{fid}/cells/blocked",
        json={"cells": [], "kind": "pet"},
    )
    kinds = {(c["col"], c["row"]): c["kind"] for c in res.json()["cells"]}
    assert all(k == "empty" for k in kinds.values())


def test_set_barnyard_cells(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "С", "cols": 3, "rows": 3}).json()["id"]
    res = admin_client.put(
        f"/api/admin/fields/{fid}/cells/blocked",
        json={"cells": [{"col": 2, "row": 0}, {"col": 2, "row": 1}], "kind": "barnyard"},
    )
    assert res.status_code == 200
    kinds = {(c["col"], c["row"]): c["kind"] for c in res.json()["cells"]}
    assert kinds[(2, 0)] == "barnyard"
    assert kinds[(2, 1)] == "barnyard"
    assert kinds[(0, 0)] == "empty"


def test_set_cells_invalid_kind(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Т"}).json()["id"]
    res = admin_client.put(
        f"/api/admin/fields/{fid}/cells/blocked",
        json={"cells": [{"col": 0, "row": 0}], "kind": "dragon"},
    )
    assert res.status_code == 400


def test_set_cells_kinds_independent(admin_client):
    """Сохранение одного вида НЕ сбрасывает другие (взаимное исключение — на фронтенде)."""
    fid = admin_client.post("/api/admin/fields", json={"name": "М", "cols": 3, "rows": 3}).json()["id"]
    admin_client.put(
        f"/api/admin/fields/{fid}/cells/blocked",
        json={"cells": [{"col": 0, "row": 0}], "kind": "pet"},
    )
    admin_client.put(
        f"/api/admin/fields/{fid}/cells/blocked",
        json={"cells": [{"col": 1, "row": 1}], "kind": "barnyard"},
    )
    res = admin_client.get(f"/api/admin/fields/{fid}")
    kinds = {(c["col"], c["row"]): c["kind"] for c in res.json()["cells"]}
    assert kinds[(0, 0)] == "pet"
    assert kinds[(1, 1)] == "barnyard"
    assert kinds[(2, 2)] == "empty"


# ===== Растения локации =====

def test_set_field_plants(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "О"}).json()["id"]
    pid = _plant_id(admin_client)
    res = admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [pid, 9999]})
    assert res.status_code == 200
    ids = {p["id"] for p in res.json()}
    assert pid in ids
    assert 9999 not in ids  # несуществующее отфильтровано


def test_set_field_plants_replace(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "О"}).json()["id"]
    p1 = _plant_id(admin_client, "jackobob")
    p2 = _plant_id(admin_client, "khlebozlak")
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [p1, p2]})
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [p1]})
    ids = {p["id"] for p in admin_client.get(f"/api/admin/fields/{fid}").json()["plants"]}
    assert ids == {p1}


# ===== Привязка животных/питомцев к локации =====

def test_set_field_animals(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Скотный", "field_kind": "barnyard"}).json()["id"]
    res = admin_client.put(f"/api/admin/fields/{fid}/animals", json={"animal_ids": [1, 9999]})
    assert res.status_code == 200
    ids = set(res.json())
    assert 1 in ids
    assert 9999 not in ids
    assert set(admin_client.get(f"/api/admin/fields/{fid}").json()["animal_ids"]) == {1}


def test_set_field_pets(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Лужайка", "field_kind": "lawn"}).json()["id"]
    res = admin_client.put(f"/api/admin/fields/{fid}/pets", json={"pet_ids": [1, 9999]})
    assert res.status_code == 200
    ids = set(res.json())
    assert 1 in ids
    assert 9999 not in ids
    assert set(admin_client.get(f"/api/admin/fields/{fid}").json()["pet_ids"]) == {1}


def test_set_field_animals_requires_admin(player_client):
    assert player_client.put("/api/admin/fields/1/animals", json={"animal_ids": [1]}).status_code == 403


def test_set_field_pets_requires_admin(player_client):
    assert player_client.put("/api/admin/fields/1/pets", json={"pet_ids": [1]}).status_code == 403


# ===== Публичные списки животных/питомцев из локаций =====

def test_available_animals_fallback(player_client):
    animals = player_client.get("/api/animals").json()
    assert len(animals) == 2


def test_available_pets_fallback(player_client):
    pets = player_client.get("/api/pets/catalog").json()
    assert len(pets) == 2


def test_available_animals_from_barnyard_binding(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Скотный", "field_kind": "barnyard"}).json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/animals", json={"animal_ids": [1]})
    with make_user_client(4001, "player") as c:
        bound = c.get("/api/animals").json()
    assert [a["id"] for a in bound] == [1]


def test_available_pets_from_lawn_binding(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "Лужайка", "field_kind": "lawn"}).json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/pets", json={"pet_ids": [2]})
    with make_user_client(4002, "player") as c:
        bound = c.get("/api/pets/catalog").json()
    assert [p["id"] for p in bound] == [2]


def test_available_animals_requires_auth(client):
    assert client.get("/api/animals").status_code == 401


def test_available_pets_requires_auth(client):
    assert client.get("/api/pets/catalog").status_code == 401


# ===== Шатры-прямоугольники =====

def test_create_tent(admin_client, uploads_tmp):
    fid = admin_client.post("/api/admin/fields", json={"name": "О", "cols": 6, "rows": 4}).json()["id"]
    res = admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "Стол зельеварения", "kind": "alchemy", "col1": "1", "row1": "1", "col2": "2", "row2": "2"},
        files={"image": ("t.png", io.BytesIO(_img_bytes(200, 200)), "image/png")},
    )
    assert res.status_code == 201
    t = res.json()
    assert t["name"] == "Стол зельеварения"
    assert t["kind"] == "alchemy"
    assert t["image_url"].startswith("/api/uploads/tent_")
    assert (t["col1"], t["row1"], t["col2"], t["row2"]) == (1, 1, 2, 2)

    # Клетки прямоугольника помечены tent.
    cells = {(c["col"], c["row"]): c for c in admin_client.get(f"/api/admin/fields/{fid}").json()["cells"]}
    for (c, r) in [(1, 1), (1, 2), (2, 1), (2, 2)]:
        assert cells[(c, r)]["kind"] == "tent"
        assert cells[(c, r)]["tent_id"] == t["id"]
    assert cells[(0, 0)]["kind"] == "empty"


def test_create_tent_normalized_rect(admin_client, uploads_tmp):
    """Координаты в любом порядке приводятся к canon-виду."""
    fid = admin_client.post("/api/admin/fields", json={"name": "О", "cols": 6, "rows": 4}).json()["id"]
    res = admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "T", "col1": "2", "row1": "2", "col2": "1", "row2": "1"},
    )
    assert res.status_code == 201
    assert (res.json()["col1"], res.json()["row1"], res.json()["col2"], res.json()["row2"]) == (1, 1, 2, 2)


def test_create_tent_out_of_bounds(admin_client, uploads_tmp):
    fid = admin_client.post("/api/admin/fields", json={"name": "О", "cols": 4, "rows": 4}).json()["id"]
    res = admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "T", "col1": "3", "row1": "0", "col2": "5", "row2": "1"},
    )
    assert res.status_code == 400


def test_create_tent_overlap(admin_client, uploads_tmp):
    fid = admin_client.post("/api/admin/fields", json={"name": "О", "cols": 6, "rows": 4}).json()["id"]
    admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "T1", "col1": "1", "row1": "1", "col2": "2", "row2": "2"},
    )
    res = admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "T2", "col1": "2", "row1": "2", "col2": "3", "row2": "3"},
    )
    assert res.status_code == 409


def test_create_tent_invalid_kind(admin_client, uploads_tmp):
    fid = admin_client.post("/api/admin/fields", json={"name": "О"}).json()["id"]
    res = admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "T", "kind": "bogus", "col1": "0", "row1": "0", "col2": "0", "row2": "0"},
    )
    assert res.status_code == 400


def test_create_tent_empty_name(admin_client, uploads_tmp):
    fid = admin_client.post("/api/admin/fields", json={"name": "О"}).json()["id"]
    res = admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "  ", "col1": "0", "row1": "0", "col2": "0", "row2": "0"},
    )
    assert res.status_code == 400


def test_delete_tent_frees_cells(admin_client, uploads_tmp):
    fid = admin_client.post("/api/admin/fields", json={"name": "О", "cols": 6, "rows": 4}).json()["id"]
    tid = admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "T", "col1": "1", "row1": "1", "col2": "2", "row2": "2"},
        files={"image": ("t.png", io.BytesIO(_img_bytes()), "image/png")},
    ).json()["id"]

    assert admin_client.delete(f"/api/admin/fields/{fid}/tents/{tid}").status_code == 204
    cells = admin_client.get(f"/api/admin/fields/{fid}").json()["cells"]
    tent_cells = [c for c in cells if c["col"] in (1, 2) and c["row"] in (1, 2)]
    assert all(c["kind"] == "empty" for c in tent_cells)
    assert all(c["tent_id"] is None for c in cells)


def test_delete_tent_not_found(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "О"}).json()["id"]
    assert admin_client.delete(f"/api/admin/fields/{fid}/tents/9999").status_code == 404


# ===== Точечное изменение kind клетки (автосохранение) =====

def test_set_cell_kind_bed_toggle(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "О", "cols": 3, "rows": 3}).json()["id"]
    res = admin_client.put(f"/api/admin/fields/{fid}/cell/0/0", json={"kind": "bed"})
    assert res.status_code == 200
    assert res.json()["kind"] == "bed"
    res = admin_client.put(f"/api/admin/fields/{fid}/cell/0/0", json={"kind": "bed"})
    assert res.json()["kind"] == "empty"


def test_set_cell_kind_pet_barnyard(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "О", "cols": 3, "rows": 3}).json()["id"]
    assert admin_client.put(f"/api/admin/fields/{fid}/cell/1/1", json={"kind": "pet"}).json()["kind"] == "pet"
    assert admin_client.put(f"/api/admin/fields/{fid}/cell/2/2", json={"kind": "barnyard"}).json()["kind"] == "barnyard"


def test_set_cell_kind_invalid(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "О"}).json()["id"]
    assert admin_client.put(f"/api/admin/fields/{fid}/cell/0/0", json={"kind": "dragon"}).status_code == 400


def test_set_cell_kind_out_of_bounds(admin_client):
    fid = admin_client.post("/api/admin/fields", json={"name": "О", "cols": 3, "rows": 3}).json()["id"]
    assert admin_client.put(f"/api/admin/fields/{fid}/cell/9/9", json={"kind": "bed"}).status_code == 400


def test_set_cell_kind_tent_immune(admin_client, uploads_tmp):
    fid = admin_client.post("/api/admin/fields", json={"name": "О", "cols": 4, "rows": 4}).json()["id"]
    admin_client.post(
        f"/api/admin/fields/{fid}/tents",
        data={"name": "T", "col1": "1", "row1": "1", "col2": "2", "row2": "2"},
    )
    assert admin_client.put(f"/api/admin/fields/{fid}/cell/1/1", json={"kind": "bed"}).status_code == 409
