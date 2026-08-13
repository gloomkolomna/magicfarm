import io

import pytest


# ── Plants CRUD ──

def test_list_plants_admin(admin_client):
    res = admin_client.get("/api/admin/catalog/plants")
    assert res.status_code == 200
    assert len(res.json()) >= 4  # seed plants


def test_create_plant(admin_client):
    res = admin_client.post("/api/admin/catalog/plants", json={"name": "Тест", "emoji": "🧪"})
    assert res.status_code == 201
    d = res.json()
    assert d["code"] and d["code"][0].isalpha()
    assert d["name"] == "Тест"


def test_create_plant_duplicate_code(admin_client):
    c1 = admin_client.post("/api/admin/catalog/plants", json={"name": "Цветок"}).json()["code"]
    c2 = admin_client.post("/api/admin/catalog/plants", json={"name": "Цветок"}).json()["code"]
    assert c1 != c2


def test_create_plant_empty_name(admin_client):
    res = admin_client.post("/api/admin/catalog/plants", json={"name": "  "})
    assert res.status_code == 400


def test_create_plant_autocode(admin_client):
    res = admin_client.post("/api/admin/catalog/plants", json={"name": "Волшебный боб", "emoji": "🫘"})
    assert res.status_code == 201
    code = res.json()["code"]
    assert code and code[0].isalpha()


def test_create_plant_autocode_unique(admin_client):
    c1 = admin_client.post("/api/admin/catalog/plants", json={"name": "Трава"}).json()["code"]
    c2 = admin_client.post("/api/admin/catalog/plants", json={"name": "Трава"}).json()["code"]
    assert c1 != c2


def test_create_plant_category_default(admin_client):
    res = admin_client.post("/api/admin/catalog/plants", json={"name": "Куст"})
    assert res.json()["category"] == "garden"


def test_update_plant(admin_client):
    r = admin_client.post("/api/admin/catalog/plants", json={"name": "A", "emoji": "🌿"})
    pid = r.json()["id"]
    res = admin_client.put(f"/api/admin/catalog/plants/{pid}", json={"name": "B", "level": 5})
    assert res.status_code == 200
    d = res.json()
    assert d["name"] == "B"
    assert d["level"] == 5
    assert d["emoji"] == "🌿"


def test_update_plant_not_found(admin_client):
    res = admin_client.put("/api/admin/catalog/plants/9999", json={"name": "X"})
    assert res.status_code == 404


def test_delete_plant(admin_client):
    r = admin_client.post("/api/admin/catalog/plants", json={"name": "D"})
    pid = r.json()["id"]
    assert admin_client.delete(f"/api/admin/catalog/plants/{pid}").status_code == 204
    names = [p["code"] for p in admin_client.get("/api/admin/catalog/plants").json()]
    assert "del" not in names


def test_plant_catalog_requires_admin(player_client):
    assert player_client.get("/api/admin/catalog/plants").status_code == 403
    assert player_client.post("/api/admin/catalog/plants", json={"code": "x", "name": "X"}).status_code == 403


# ── Animals CRUD ──

def test_list_animals_empty(admin_client):
    res = admin_client.get("/api/admin/catalog/animals")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_create_animal(admin_client):
    res = admin_client.post("/api/admin/catalog/animals", json={
        "name": "Дракон", "emoji": "🐉", "product_name": "Чешуя", "sort_order": 4,
    })
    assert res.status_code == 201
    d = res.json()
    assert d["code"] and d["code"][0].isalpha()
    assert d["product_name"] == "Чешуя"
    assert d["sort_order"] == 4


def test_update_animal(admin_client):
    r = admin_client.post("/api/admin/catalog/animals", json={"name": "Овечка"})
    aid = r.json()["id"]
    res = admin_client.put(f"/api/admin/catalog/animals/{aid}", json={"product_name": "Шерсть", "sort_order": 1})
    assert res.status_code == 200
    d = res.json()
    assert d["product_name"] == "Шерсть"
    assert d["sort_order"] == 1


def test_delete_animal(admin_client):
    r = admin_client.post("/api/admin/catalog/animals", json={"name": "X"})
    aid = r.json()["id"]
    assert admin_client.delete(f"/api/admin/catalog/animals/{aid}").status_code == 204
    assert len(admin_client.get("/api/admin/catalog/animals").json()) == 2


# ── Pets CRUD ──

def test_list_pets_empty(admin_client):
    res = admin_client.get("/api/admin/catalog/pets")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_create_pet(admin_client):
    res = admin_client.post("/api/admin/catalog/pets", json={
        "name": "Лис", "emoji": "🦊", "bonus_kind": "harvest_orchard", "bonus_description": "+1 дерево",
    })
    assert res.status_code == 201
    d = res.json()
    assert d["code"] and d["code"][0].isalpha()
    assert d["bonus_kind"] == "harvest_orchard"
    assert d["bonus_description"] == "+1 дерево"


def test_update_pet(admin_client):
    r = admin_client.post("/api/admin/catalog/pets", json={"name": "Кот"})
    pid = r.json()["id"]
    res = admin_client.put(f"/api/admin/catalog/pets/{pid}", json={
        "emoji": "🐱", "bonus_kind": "animal_product", "bonus_description": "+1 продукция",
    })
    assert res.status_code == 200
    d = res.json()
    assert d["emoji"] == "🐱"
    assert d["bonus_kind"] == "animal_product"
    assert d["bonus_description"] == "+1 продукция"


def test_delete_pet(admin_client):
    r = admin_client.post("/api/admin/catalog/pets", json={"name": "X"})
    pid = r.json()["id"]
    assert admin_client.delete(f"/api/admin/catalog/pets/{pid}").status_code == 204
    assert len(admin_client.get("/api/admin/catalog/pets").json()) == 2


# ── Image upload ──

def _img_bytes(w: int = 80, h: int = 60) -> bytes:
    from PIL import Image
    import io
    img = Image.new("RGB", (w, h), (100, 180, 50))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_upload_plant_image(admin_client, uploads_tmp):
    r = admin_client.post("/api/admin/catalog/plants", json={"code": "img_test", "name": "T"})
    pid = r.json()["id"]
    res = admin_client.put(
        f"/api/admin/catalog/plants/{pid}/image",
        files={"image": ("p.png", _img_bytes(), "image/png")},
    )
    assert res.status_code == 200
    assert res.json()["image_url"] is not None
    assert "/api/uploads/" in res.json()["image_url"] or "http" in res.json()["image_url"]


def test_upload_animal_image(admin_client, uploads_tmp):
    r = admin_client.post("/api/admin/catalog/animals", json={"code": "a_img", "name": "A"})
    aid = r.json()["id"]
    res = admin_client.put(
        f"/api/admin/catalog/animals/{aid}/image",
        files={"image": ("a.png", _img_bytes(), "image/png")},
    )
    assert res.status_code == 200
    assert res.json()["image_url"] is not None


def test_upload_pet_image(admin_client, uploads_tmp):
    r = admin_client.post("/api/admin/catalog/pets", json={"code": "p_img", "name": "P"})
    pid = r.json()["id"]
    res = admin_client.put(
        f"/api/admin/catalog/pets/{pid}/image",
        files={"image": ("p.png", _img_bytes(), "image/png")},
    )
    assert res.status_code == 200
    assert res.json()["image_url"] is not None


def test_upload_image_not_found(admin_client, uploads_tmp):
    res = admin_client.put(
        "/api/admin/catalog/plants/9999/image",
        files={"image": ("r.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 404


# ═══════════════════════════════════════════════════════════════
# Products CRUD
# ═══════════════════════════════════════════════════════════════


def test_list_products_admin(admin_client):
    res = admin_client.get("/api/admin/catalog/products")
    assert res.status_code == 200
    data = res.json()
    assert any(p["code"] == "poison" for p in data)


def test_create_product(admin_client):
    res = admin_client.post(
        "/api/admin/catalog/products",
        json={"name": "Зелье здоровья", "emoji": "🧪", "stars": 2, "production_kind": "alchemy"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["code"] and data["code"][0].isalpha()
    assert data["name"] == "Зелье здоровья"
    assert data["stars"] == 2
    assert data["production_kind"] == "alchemy"


def test_create_product_with_animal(admin_client):
    res = admin_client.post(
        "/api/admin/catalog/products",
        json={"name": "Радужная шерсть", "animal_id": 1, "stars": 1, "production_kind": "sewing"},
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["animal_id"] == 1


def test_create_product_with_pet(admin_client):
    res = admin_client.post(
        "/api/admin/catalog/products",
        json={"name": "Бонус питомца", "pet_id": 1, "stars": 1},
    )
    assert res.status_code == 201, res.text
    assert res.json()["pet_id"] == 1


def test_create_product_invalid_animal(admin_client):
    res = admin_client.post(
        "/api/admin/catalog/products",
        json={"name": "X", "animal_id": 999},
    )
    assert res.status_code == 404


def test_create_product_invalid_pet(admin_client):
    res = admin_client.post(
        "/api/admin/catalog/products",
        json={"name": "Y", "pet_id": 999},
    )
    assert res.status_code == 404


def test_create_product_duplicate_code(admin_client):
    c1 = admin_client.post("/api/admin/catalog/products", json={"name": "Товар"}).json()["code"]
    c2 = admin_client.post("/api/admin/catalog/products", json={"name": "Товар"}).json()["code"]
    assert c1 != c2


def test_create_product_empty_name(admin_client):
    res = admin_client.post(
        "/api/admin/catalog/products",
        json={"name": ""},
    )
    assert res.status_code == 400


def test_update_product(admin_client):
    res = admin_client.post(
        "/api/admin/catalog/products",
        json={"name": "Исходное", "stars": 1},
    )
    pid = res.json()["id"]
    res2 = admin_client.put(
        f"/api/admin/catalog/products/{pid}",
        json={"name": "Обновлённое", "stars": 3},
    )
    assert res2.status_code == 200
    assert res2.json()["name"] == "Обновлённое"
    assert res2.json()["stars"] == 3


def test_update_product_not_found(admin_client):
    res = admin_client.put("/api/admin/catalog/products/9999", json={"name": "X"})
    assert res.status_code == 404


def test_delete_product(admin_client):
    res = admin_client.post(
        "/api/admin/catalog/products",
        json={"name": "Удаляемый"},
    )
    pid = res.json()["id"]
    del_res = admin_client.delete(f"/api/admin/catalog/products/{pid}")
    assert del_res.status_code == 204
    get_res = admin_client.get("/api/admin/catalog/products")
    assert not any(p["id"] == pid for p in get_res.json())


def test_product_catalog_requires_admin(player_client):
    res = player_client.get("/api/admin/catalog/products")
    assert res.status_code == 403


def test_upload_animal_image_harvested(admin_client, uploads_tmp):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (200, 200), (120, 80, 40)).save(buf, format="PNG")
    res = admin_client.put(
        "/api/admin/catalog/animals/1/image-harvested",
        files={"image": ("h.png", io.BytesIO(buf.getvalue()), "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["image_harvested_url"] is not None
    assert data["image_harvested_url"].startswith("/api/uploads/animal_")


# ═══════════════════════════════════════════════════════════════
# Production Templates CRUD
# ═══════════════════════════════════════════════════════════════


def test_list_production_templates(admin_client):
    res = admin_client.get("/api/admin/catalog/production-templates")
    assert res.status_code == 200
    data = res.json()
    codes = [p["code"] for p in data]
    assert "alchemy" in codes
    assert "sewing" in codes
    assert "workshop" in codes


def test_create_production_template(admin_client):
    res = admin_client.post(
        "/api/admin/catalog/production-templates",
        json={"code": "forge", "name": "Кузница", "required": 800},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["code"] == "forge"
    assert data["name"] == "Кузница"
    assert data["required"] == 800


def test_create_production_template_duplicate_kind(admin_client):
    admin_client.post("/api/admin/catalog/production-templates", json={"code": "test_kind", "name": "X"})
    res = admin_client.post("/api/admin/catalog/production-templates", json={"code": "test_kind", "name": "Y"})
    assert res.status_code == 409


def test_update_production_template(admin_client):
    r = admin_client.post("/api/admin/catalog/production-templates", json={"code": "bakery", "name": "Пекарня", "required": 300})
    pid = r.json()["id"]
    res = admin_client.put(f"/api/admin/catalog/production-templates/{pid}", json={"name": "Булочная", "required": 400})
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Булочная"
    assert data["required"] == 400


def test_delete_production_template(admin_client):
    r = admin_client.post("/api/admin/catalog/production-templates", json={"code": "del_pt", "name": "X"})
    pid = r.json()["id"]
    assert admin_client.delete(f"/api/admin/catalog/production-templates/{pid}").status_code == 204
    assert not any(p["id"] == pid for p in admin_client.get("/api/admin/catalog/production-templates").json())


def test_production_template_requires_admin(player_client):
    res = player_client.get("/api/admin/catalog/production-templates")
    assert res.status_code == 403
