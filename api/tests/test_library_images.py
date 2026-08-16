import io

from tests.conftest import TestingSessionLocal, make_user_client


def _img_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (24, 24), (60, 180, 90)).save(buf, format="PNG")
    return buf.getvalue()


def _seed_animal_recipe() -> int:
    from models import Product, Recipe
    s = TestingSessionLocal()
    try:
        src = Product(code="test_wool", name="Тестовая шерсть", emoji="🧶", stars=1, production_kind="barnyard", animal_id=1)
        dst = Product(code="test_yarn", name="Тестовая пряжа", emoji="🧶", stars=1, production_kind="sewing")
        s.add(src)
        s.add(dst)
        s.commit()
        s.refresh(src)
        s.refresh(dst)
        r = Recipe(source_product_id=src.id, product_id=dst.id, level=1)
        s.add(r)
        s.commit()
        s.refresh(r)
        return r.id
    finally:
        s.close()


def test_library_images_empty_by_default(admin_client):
    with make_user_client(123, "player") as c:
        rows = c.get("/api/library").json()
        r = next(x for x in rows if x["plant_id"] is not None)
        assert r["plant_image"] is None
        assert r["source_product_image"] is None
        assert r["product_image"] is None


def test_library_plant_image(admin_client, uploads_tmp):
    r = admin_client.put(
        "/api/admin/catalog/plants/4/image",
        files={"image": ("p.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert r.status_code == 200
    with make_user_client(123, "player") as c:
        rows = c.get("/api/library").json()
        rec = next(x for x in rows if x["plant_id"] == 4)
        assert rec["plant_image"] is not None


def test_library_prefers_harvested_plant_image(admin_client, uploads_tmp):
    admin_client.put(
        "/api/admin/catalog/plants/4/image",
        files={"image": ("p.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    r = admin_client.put(
        "/api/admin/catalog/plants/4/image-harvested",
        files={"image": ("h.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert r.status_code == 200
    harvested_url = r.json()["image_harvested_url"]
    with make_user_client(123, "player") as c:
        rows = c.get("/api/library").json()
        rec = next(x for x in rows if x["plant_id"] == 4)
        assert rec["plant_image"] == harvested_url


def test_library_product_image(admin_client, uploads_tmp):
    r = admin_client.put(
        "/api/admin/catalog/products/1/image",
        files={"image": ("pr.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert r.status_code == 200
    expected = r.json()["image_url"]
    with make_user_client(123, "player") as c:
        rows = c.get("/api/library").json()
        rec = next(x for x in rows if x["product_id"] == 1)
        assert rec["product_image"] == expected


def test_library_source_product_image(admin_client, uploads_tmp):
    rid = _seed_animal_recipe()
    with make_user_client(123, "player") as c:
        rows = c.get("/api/library").json()
        rec = next(x for x in rows if x["id"] == rid)
        assert rec["source_kind"] == "animal_product"
        assert rec["source_product_image"] is None

    from models import Recipe
    s = TestingSessionLocal()
    try:
        r = s.query(Recipe).filter(Recipe.id == rid).first()
        src_id = r.source_product_id
    finally:
        s.close()

    resp = admin_client.put(
        f"/api/admin/catalog/products/{src_id}/image",
        files={"image": ("sp.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert resp.status_code == 200
    with make_user_client(123, "player") as c:
        rows = c.get("/api/library").json()
        rec = next(x for x in rows if x["id"] == rid)
        assert rec["source_product_image"] is not None
