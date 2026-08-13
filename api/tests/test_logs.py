import datetime

from tests.conftest import make_user_client


def test_admin_logs_requires_auth(client):
    assert client.get("/api/admin/logs").status_code == 401


def test_admin_logs_player_forbidden(player_client):
    assert player_client.get("/api/admin/logs").status_code == 403


def test_middleware_logs_successful_request(admin_client):
    admin_client.get("/api/me")
    rows = admin_client.get("/api/admin/logs").json()
    assert any(r["path"] == "/api/me" and r["source"] == "server" and r["status_code"] == 200 for r in rows)
    assert all(r["level"] == "info" for r in rows if r["status_code"] == 200 and r["path"] == "/api/me")


def test_middleware_logs_4xx_as_warn(admin_client):
    admin_client.get("/api/admin/fields/999999")
    rows = admin_client.get("/api/admin/logs", params={"level": "warn"}).json()
    assert any(r["status_code"] == 404 and r["source"] == "server" for r in rows)


def test_vk_log_requires_auth(client):
    assert client.post("/api/logs/vk", json={"level": "info", "event": "x"}).status_code == 401


def test_vk_log_creates_entry(admin_client):
    res = admin_client.post("/api/logs/vk", json={
        "level": "warn", "event": "launch", "message": "bridge timeout", "details": {"step": "launch_params"},
    })
    assert res.status_code == 201
    rows = admin_client.get("/api/admin/logs", params={"source": "vk"}).json()
    mine = [r for r in rows if r["event"] == "launch"]
    assert mine
    assert mine[0]["source"] == "vk"
    assert mine[0]["level"] == "warn"
    assert mine[0]["user_id"] == 400977
    assert "launch_params" in mine[0]["details"]


def test_vk_log_normalizes_unknown_level(admin_client):
    admin_client.post("/api/logs/vk", json={"level": "fatal", "event": "weird"})
    rows = admin_client.get("/api/admin/logs", params={"source": "vk", "level": "info"}).json()
    assert any(r["event"] == "weird" for r in rows)


def test_admin_logs_search_and_user_filter(admin_client):
    with make_user_client(77001, "player") as p:
        p.post("/api/logs/vk", json={"event": "player_event", "message": "special-token-xyz"})
    rows = admin_client.get("/api/admin/logs", params={"q": "special-token-xyz"}).json()
    assert rows and any(r["event"] == "player_event" for r in rows)
    by_user = admin_client.get("/api/admin/logs", params={"user_id": 77001}).json()
    assert all(r["user_id"] == 77001 for r in by_user)
    assert any(r["event"] == "player_event" for r in by_user)


def test_cleanup_old_logs(db):
    from models import Log
    from services.logging_svc import cleanup_old_logs

    old = Log(source="server", level="info", path="/old",
              created_at=datetime.datetime.utcnow() - datetime.timedelta(days=40))
    fresh = Log(source="server", level="info", path="/fresh",
                created_at=datetime.datetime.utcnow())
    db.add_all([old, fresh])
    db.commit()
    old_id = old.id
    fresh_id = fresh.id

    deleted = cleanup_old_logs(db, 30)
    assert deleted >= 1
    assert db.query(Log).filter(Log.id == old_id).first() is None
    assert db.query(Log).filter(Log.id == fresh_id).first() is not None


def test_admin_clear_logs(admin_client):
    admin_client.post("/api/logs/vk", json={"event": "to-be-cleared"})
    assert any(r["event"] == "to-be-cleared" for r in admin_client.get("/api/admin/logs").json())
    res = admin_client.delete("/api/admin/logs")
    assert res.status_code == 204
    assert all(r["event"] != "to-be-cleared" for r in admin_client.get("/api/admin/logs").json())
