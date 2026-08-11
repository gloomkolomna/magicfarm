import io
import os

import pytest


def create_test_image():
    from PIL import Image
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    buf.name = "test.jpg"
    return buf


class TestGameMediaAdmin:
    def test_list_empty(self, admin_client):
        r = admin_client.get("/api/admin/game-media")
        assert r.status_code == 200
        assert r.json() == []

    def test_create(self, admin_client):
        r = admin_client.post("/api/admin/game-media", json={"code": "card_shuffle", "kind": "video"})
        assert r.status_code == 201
        data = r.json()
        assert data["code"] == "card_shuffle"
        assert data["kind"] == "video"
        assert data["url"] is None

    def test_create_duplicate_code(self, admin_client):
        admin_client.post("/api/admin/game-media", json={"code": "unique_video", "kind": "video"})
        r = admin_client.post("/api/admin/game-media", json={"code": "unique_video", "kind": "video"})
        assert r.status_code == 409

    def test_create_empty_code(self, admin_client):
        r = admin_client.post("/api/admin/game-media", json={"code": "   ", "kind": "video"})
        assert r.status_code == 400

    def test_update(self, admin_client):
        admin_client.post("/api/admin/game-media", json={"code": "to_update", "kind": "video"})
        r = admin_client.put("/api/admin/game-media/1", json={"code": "updated_code", "kind": "image"})
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == "updated_code"
        assert data["kind"] == "image"

    def test_update_duplicate_code(self, admin_client):
        admin_client.post("/api/admin/game-media", json={"code": "first", "kind": "video"})
        admin_client.post("/api/admin/game-media", json={"code": "second", "kind": "video"})
        r = admin_client.put("/api/admin/game-media/1", json={"code": "second"})
        assert r.status_code == 409

    def test_update_not_found(self, admin_client):
        r = admin_client.put("/api/admin/game-media/999", json={"code": "x"})
        assert r.status_code == 404

    def test_delete(self, admin_client):
        admin_client.post("/api/admin/game-media", json={"code": "to_delete", "kind": "video"})
        r = admin_client.delete("/api/admin/game-media/1")
        assert r.status_code == 204
        r2 = admin_client.get("/api/admin/game-media")
        assert r2.json() == []

    def test_upload_file(self, admin_client, uploads_tmp):
        admin_client.post("/api/admin/game-media", json={"code": "card_shuffle", "kind": "video"})
        img = create_test_image()
        r = admin_client.put("/api/admin/game-media/1/upload", files={"file": ("test.jpg", img, "image/jpeg")})
        assert r.status_code == 200
        data = r.json()
        assert data["url"] is not None
        assert data["url"].startswith("/api/uploads/")

    def test_upload_video(self, admin_client, uploads_tmp):
        admin_client.post("/api/admin/game-media", json={"code": "dice_roll", "kind": "video"})
        fake_video = io.BytesIO(b"fake mp4 data")
        fake_video.name = "test.mp4"
        r = admin_client.put("/api/admin/game-media/1/upload", files={"file": ("test.mp4", fake_video, "video/mp4")})
        assert r.status_code == 200
        data = r.json()
        assert data["url"] is not None
        assert ".mp4" in data["url"]

    def test_list_multiple(self, admin_client):
        for i in range(3):
            admin_client.post("/api/admin/game-media", json={"code": f"media_{i}", "kind": "video"})
        r = admin_client.get("/api/admin/game-media")
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_player_cannot_access_admin(self, player_client):
        r = player_client.get("/api/admin/game-media")
        assert r.status_code == 403


class TestGameMediaPublic:
    def test_list_public(self, admin_client):
        admin_client.post("/api/admin/game-media", json={"code": "card_shuffle", "kind": "video"})
        r = admin_client.get("/api/game-media")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["code"] == "card_shuffle"

    def test_get_by_code(self, admin_client):
        admin_client.post("/api/admin/game-media", json={"code": "dice_roll", "kind": "video"})
        r = admin_client.get("/api/game-media/dice_roll")
        assert r.status_code == 200
        assert r.json()["code"] == "dice_roll"

    def test_get_by_code_not_found(self, admin_client):
        r = admin_client.get("/api/game-media/nonexistent")
        assert r.status_code == 404

    def test_public_accessible_without_auth(self, client):
        from db import get_db
        from fastapi.testclient import TestClient
        r = client.get("/api/game-media")
        assert r.status_code == 200


class TestCrystalCardImage:
    def test_list_cards(self, admin_client):
        r = admin_client.get("/api/admin/catalog/crystal-cards")
        assert r.status_code == 200
        cards = r.json()
        assert len(cards) == 18
        colors = {c["color"] for c in cards}
        assert colors == {"green", "blue", "violet"}

    def test_upload_card_image(self, admin_client, uploads_tmp):
        img = create_test_image()
        r = admin_client.put("/api/admin/catalog/crystal-cards/1/image", files={"image": ("test.jpg", img, "image/jpeg")})
        assert r.status_code == 200
        data = r.json()
        assert data["image_url"] is not None
        assert data["image_url"].startswith("/api/uploads/")

    def test_upload_card_image_not_found(self, admin_client):
        img = create_test_image()
        r = admin_client.put("/api/admin/catalog/crystal-cards/999/image", files={"image": ("test.jpg", img, "image/jpeg")})
        assert r.status_code == 404

    def test_player_cannot_upload_card(self, player_client):
        img = create_test_image()
        r = player_client.put("/api/admin/catalog/crystal-cards/1/image", files={"image": ("test.jpg", img, "image/jpeg")})
        assert r.status_code == 403


class TestProductPlantUniqueness:
    def test_duplicate_plant_product_rejected(self, admin_client):
        plants = admin_client.get("/api/admin/catalog/plants").json()
        plant_id = plants[0]["id"]
        admin_client.post("/api/admin/catalog/products", json={
            "name": "Товар А", "plant_id": plant_id, "stars": 1, "production_kind": "alchemy",
        })
        r = admin_client.post("/api/admin/catalog/products", json={
            "name": "Товар Б", "plant_id": plant_id, "stars": 2, "production_kind": "sewing",
        })
        assert r.status_code == 409

    def test_different_plants_ok(self, admin_client):
        plants = admin_client.get("/api/admin/catalog/plants").json()
        r1 = admin_client.post("/api/admin/catalog/products", json={
            "name": "Товар А", "plant_id": plants[0]["id"], "stars": 1,
        })
        assert r1.status_code == 201
        r2 = admin_client.post("/api/admin/catalog/products", json={
            "name": "Товар Б", "plant_id": plants[1]["id"], "stars": 1,
        })
        assert r2.status_code == 201

    def test_product_without_plant_ok(self, admin_client):
        r = admin_client.post("/api/admin/catalog/products", json={
            "name": "Без растения", "stars": 1,
        })
        assert r.status_code == 201


class TestRecipePlantUniqueness:
    def test_duplicate_recipe_plant_rejected(self, db):
        from models import Recipe
        from sqlalchemy.exc import IntegrityError
        plants = db.query(__import__("models").Plant).order_by(__import__("models").Plant.id).all()
        products = db.query(__import__("models").Product).order_by(__import__("models").Product.id).all()
        plant_id = plants[0].id
        product_id = products[0].id
        r1 = Recipe(plant_id=plant_id, product_id=product_id, level=1)
        db.add(r1)
        db.commit()
        r2 = Recipe(plant_id=plant_id, product_id=product_id, level=2)
        db.add(r2)
        try:
            db.commit()
            assert False
        except IntegrityError:
            db.rollback()
