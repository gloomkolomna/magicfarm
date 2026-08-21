import datetime

from tests.conftest import TestingSessionLocal, make_user_client
from models import ChatMessage, User


def _add_user(vk_id):
    s = TestingSessionLocal()
    try:
        if s.query(User).filter(User.vk_id == vk_id).first() is None:
            s.add(User(vk_id=vk_id, role="player", display_name=f"Игрок{vk_id}"))
            s.commit()
    finally:
        s.close()


def _seed_message(from_id, to_id, text, read=None):
    s = TestingSessionLocal()
    try:
        s.add(ChatMessage(from_user_id=from_id, to_user_id=to_id, text=text, read_at=read))
        s.commit()
    finally:
        s.close()


def test_chat_requires_auth(client):
    assert client.get("/api/chat/conversations").status_code == 401
    assert client.get("/api/chat/with/1").status_code == 401
    assert client.post("/api/chat/with/1", json={"text": "x"}).status_code == 401


def test_send_message_validation(player_client):
    _add_user(7001)
    assert player_client.post("/api/chat/with/123", json={"text": "x"}).status_code == 400
    assert player_client.post("/api/chat/with/999999", json={"text": "x"}).status_code == 404
    assert player_client.post("/api/chat/with/7001", json={"text": ""}).status_code == 400
    assert player_client.post("/api/chat/with/7001", json={"text": "   "}).status_code == 400
    assert player_client.post("/api/chat/with/7001", json={"text": "x" * 2001}).status_code == 400
    s = TestingSessionLocal()
    try:
        u = s.query(User).filter(User.vk_id == 7001).first()
        u.status = "blocked"
        s.commit()
    finally:
        s.close()
    assert player_client.post("/api/chat/with/7001", json={"text": "x"}).status_code == 400


def test_send_and_read_thread():
    _add_user(7002)
    with make_user_client(123, "player") as a:
        assert a.post("/api/chat/with/7002", json={"text": "Привет!"}).status_code == 201
    with make_user_client(7002, "player") as b:
        convs = b.get("/api/chat/conversations").json()
        conv = next(c for c in convs if c["vk_id"] == 123)
        assert conv["unread_count"] == 1
        thread = b.get("/api/chat/with/123").json()
        assert [m["text"] for m in thread] == ["Привет!"]
        assert thread[0]["read"] is True
        assert b.post("/api/chat/with/123", json={"text": "Здравствуй!"}).status_code == 201
        convs2 = b.get("/api/chat/conversations").json()
        conv2 = next(c for c in convs2 if c["vk_id"] == 123)
        assert conv2["unread_count"] == 0
        assert conv2["last_message"] == "Здравствуй!"
    with make_user_client(123, "player") as a:
        thread2 = a.get("/api/chat/with/7002").json()
        assert [m["text"] for m in thread2] == ["Привет!", "Здравствуй!"]
        assert thread2[0]["read"] is True and thread2[1]["read"] is True
        assert a.post("/api/chat/with/7002", json={"text": "Второе"}).status_code == 201
    with make_user_client(7002, "player") as b:
        convs3 = b.get("/api/chat/conversations").json()
        conv3 = next(c for c in convs3 if c["vk_id"] == 123)
        assert conv3["unread_count"] == 1
        assert conv3["last_message"] == "Второе"


def test_conversations_lists_peers():
    _add_user(7003)
    _add_user(7004)
    _seed_message(7003, 123, "старт")
    _seed_message(7003, 123, "второе", read=datetime.datetime.utcnow())
    _seed_message(7004, 123, "другое")

    with make_user_client(123, "player") as a:
        convs = a.get("/api/chat/conversations").json()
        by_id = {c["vk_id"]: c for c in convs}
        assert set(by_id.keys()) == {7003, 7004}
        assert by_id[7003]["unread_count"] == 1
        assert by_id[7004]["unread_count"] == 1
        assert by_id[7003]["display_name"] == "Игрок7003"
        assert by_id[7004]["last_message"] == "другое"
