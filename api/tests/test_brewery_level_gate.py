from tests.conftest import TestingSessionLocal, make_user_client


def _create_brewery_field(admin_client, min_level: int):
    r = admin_client.post("/api/admin/fields", json={
        "name": "Зельеварня уровня", "cols": 6, "rows": 4,
        "field_kind": "brewery", "min_level": min_level,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _set_level(vk_id: int, level: int):
    from models import User
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == vk_id).first()
        assert u is not None
        u.level = level
        s.commit()
    finally:
        s.close()


def test_brewery_field_locked_by_min_level(admin_client):
    fid = _create_brewery_field(admin_client, min_level=3)
    with make_user_client(123, "player") as c:
        r = c.get(f"/api/fields/{fid}")
        assert r.status_code == 403
        assert "недоступна" in r.json()["detail"]


def test_brewery_field_open_after_reaching_level(admin_client):
    fid = _create_brewery_field(admin_client, min_level=3)
    with make_user_client(123, "player") as c:
        c.get("/api/me")
        _set_level(123, 3)
        r = c.get(f"/api/fields/{fid}")
        assert r.status_code == 200
        assert r.json()["min_level"] == 3


def test_regular_field_not_affected_by_brewery_gate(admin_client):
    r = admin_client.post("/api/admin/fields", json={
        "name": "Поле грядок", "cols": 3, "rows": 2, "min_level": 3,
    })
    fid = r.json()["id"]
    with make_user_client(123, "player") as c:
        rr = c.get(f"/api/fields/{fid}")
        assert rr.status_code == 200
