def test_resolve_vk_names_passes_lang_ru():
    from services.vk_names import resolve_vk_names

    captured = {}

    class _Users:
        def get(self, **kwargs):
            captured.update(kwargs)
            return [{"id": 100, "first_name": "Иван", "last_name": "Иванов"}]

    class _FakeApi:
        def __init__(self):
            self.users = _Users()

    class _FakeVkApi:
        def __init__(self, *args, **kwargs):
            pass

        def get_api(self):
            return _FakeApi()

    import config
    config.VK_SERVICE_TOKEN = "fake_token"

    import vk_api as real_vk_api
    saved = real_vk_api.VkApi
    real_vk_api.VkApi = _FakeVkApi
    try:
        result = resolve_vk_names([100])
    finally:
        real_vk_api.VkApi = saved
        config.VK_SERVICE_TOKEN = ""

    assert result[100]["first_name"] == "Иван"
    assert result[100]["last_name"] == "Иванов"
    assert captured.get("lang") == "ru"
    assert captured.get("fields") == "first_name,last_name"


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
