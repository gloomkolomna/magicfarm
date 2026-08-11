import io

from tests.conftest import make_user_client


def _real_img():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (50, 100, 150)).save(buf, format="PNG")
    return buf.getvalue()


def _credit(client, amount):
    img = _real_img()
    r = client.post("/api/stitches/reports", data={"amount": str(amount)}, files=[
        ("photo_after", ("a.png", img, "image/png")),
    ])
    assert r.status_code == 201, f"Credit: {r.status_code}"


def test_list_pets_empty(admin_client):
    with make_user_client(123, "player") as c:
        r = c.get("/api/pets")
        assert r.status_code == 200
        assert r.json() == []


def test_settle_pet_returns_cards(admin_client):
    with make_user_client(123, "player") as c:
        r = c.post("/api/pets/settle", json={"pet_id": 1})
        assert r.status_code == 201
        data = r.json()
        assert data["pet_id"] == 1
        assert data["pet_name"] == "Дракон Эфир"
        assert len(data["drawn_cards"]) == 10
        assert data["required"] > 0


def test_settle_duplicate_pet(admin_client):
    with make_user_client(123, "player") as c:
        r = c.post("/api/pets/settle", json={"pet_id": 1})
        assert r.status_code == 201
        required = r.json()["required"]
        img = _real_img()
        c.post("/api/stitches/reports", data={
            "amount": str(required),
            "context_type": "pet_settle", "context_id": "1",
        }, files=[("photo_after", ("a.png", img, "image/png"))])

        r = c.post("/api/pets/settle", json={"pet_id": 1})
        assert r.status_code == 409


def test_settle_unknown_pet(admin_client):
    with make_user_client(123, "player") as c:
        r = c.post("/api/pets/settle", json={"pet_id": 999})
        assert r.status_code == 404


def test_pet_settled_on_report_accept(admin_client):
    with make_user_client(123, "player") as c:
        r = c.post("/api/pets/settle", json={"pet_id": 1})
        assert r.status_code == 201
        required = r.json()["required"]

        img = _real_img()
        r = c.post("/api/stitches/reports", data={
            "amount": str(required),
            "context_type": "pet_settle",
            "context_id": "1",
        }, files=[
            ("photo_after", ("after.png", img, "image/png")),
        ])
        assert r.status_code == 201
        assert r.json()["status"] == "accepted"

        pets = c.get("/api/pets").json()
        assert len(pets) == 1
        assert pets[0]["pet_id"] == 1
        assert pets[0]["pet_name"] == "Дракон Эфир"
