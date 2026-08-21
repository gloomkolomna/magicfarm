import json


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def test_resolve_vk_names_passes_lang_ru(monkeypatch):
    from services import vk_names
    from services.vk_names import resolve_vk_names

    captured = {}

    def _fake_post(url, data=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["data"] = data
        captured["timeout"] = timeout
        return _FakeResponse({"response": [{"id": 100, "first_name": "Иван", "last_name": "Иванов"}]})

    monkeypatch.setattr(vk_names.requests, "post", _fake_post)
    monkeypatch.setattr(vk_names, "_NAME_CACHE", {})
    monkeypatch.setattr(vk_names, "_NAME_MISS_CACHE", {})
    monkeypatch.setattr("config.VK_SERVICE_TOKEN", "fake_token", raising=False)

    import config
    saved = config.VK_SERVICE_TOKEN
    config.VK_SERVICE_TOKEN = "fake_token"
    try:
        result = resolve_vk_names([100])
    finally:
        config.VK_SERVICE_TOKEN = saved

    assert result[100]["first_name"] == "Иван"
    assert result[100]["last_name"] == "Иванов"
    assert "users.get" in captured["url"]
    assert captured["data"]["lang"] == "ru"
    assert captured["data"]["fields"] == "first_name,last_name"
    assert captured["timeout"] == vk_names.VK_TIMEOUT


def test_resolve_vk_names_negative_cache(monkeypatch):
    from services import vk_names
    from services.vk_names import resolve_vk_names

    calls = []

    def _fake_post(url, data=None, timeout=None, **kwargs):
        calls.append(data["user_ids"])
        return _FakeResponse({"response": [{"id": 100, "first_name": "Иван", "last_name": "Иванов"}]})

    monkeypatch.setattr(vk_names.requests, "post", _fake_post)
    monkeypatch.setattr(vk_names, "_NAME_CACHE", {})
    monkeypatch.setattr(vk_names, "_NAME_MISS_CACHE", {})
    import config
    saved = config.VK_SERVICE_TOKEN
    config.VK_SERVICE_TOKEN = "fake_token"
    try:
        resolve_vk_names([100, 555])
        resolve_vk_names([100, 555])
    finally:
        config.VK_SERVICE_TOKEN = saved

    assert len(calls) == 1
    assert "555" in calls[0]


def test_resolve_vk_names_network_error(monkeypatch):
    import requests as real_requests
    from services import vk_names
    from services.vk_names import resolve_vk_names

    def _fake_post(url, data=None, timeout=None, **kwargs):
        raise real_requests.ConnectionError("boom")

    monkeypatch.setattr(vk_names.requests, "post", _fake_post)
    monkeypatch.setattr(vk_names, "_NAME_CACHE", {})
    monkeypatch.setattr(vk_names, "_NAME_MISS_CACHE", {})
    import config
    saved = config.VK_SERVICE_TOKEN
    config.VK_SERVICE_TOKEN = "fake_token"
    try:
        result = resolve_vk_names([100])
    finally:
        config.VK_SERVICE_TOKEN = saved

    assert result == {}


def test_vk_display_name_fallback_on_error(monkeypatch):
    from services.vk_names import vk_display_name

    class _User:
        vk_id = 777
        display_name = None

    def _boom(vk_ids):
        raise RuntimeError("vk down")

    monkeypatch.setattr("services.vk_names.resolve_vk_names", _boom)
    assert vk_display_name(_User()) == "Игрок 777"


def test_resolve_vk_names_no_token():
    from services.vk_names import resolve_vk_names

    import config
    saved = config.VK_SERVICE_TOKEN
    config.VK_SERVICE_TOKEN = ""
    try:
        result = resolve_vk_names([100])
    finally:
        config.VK_SERVICE_TOKEN = saved

    assert result == {}
