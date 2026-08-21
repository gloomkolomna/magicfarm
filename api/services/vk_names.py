from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from urllib.parse import urlparse

VK_TIMEOUT = 8
_NAME_CACHE: dict[int, dict] = {}


def parse_vk_input(raw: str) -> tuple[str, object] | None:
    raw = (raw or "").strip().rstrip("/")
    if not raw:
        return None
    token = raw
    if "/" in raw or raw.lower().startswith(("http://", "https://", "vk.")):
        url = raw if "://" in raw else f"https://{raw}"
        segments = [s for s in urlparse(url).path.split("/") if s]
        if not segments:
            return None
        token = segments[0]
    if token.isdigit():
        return ("id", int(token))
    m = re.fullmatch(r"id(\d+)", token, flags=re.IGNORECASE)
    if m:
        return ("id", int(m.group(1)))
    if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.]{0,31}", token):
        return ("screen_name", token)
    return None


def resolve_vk_screen_name(name: str) -> dict | None:
    import config
    from services.logging_svc import record_log
    if not config.VK_SERVICE_TOKEN or not name:
        return None
    try:
        import vk_api
    except ImportError:
        record_log("vk", "error", event="vk_api", message="vk_api not installed")
        return None
    vk = vk_api.VkApi(token=config.VK_SERVICE_TOKEN, api_version="5.199").get_api()
    try:
        users = vk.users.get(user_ids=name, fields="first_name,last_name", lang="ru")
    except Exception as e:
        record_log("vk", "error", event="vk_api", message=f"users.get failed: {e}")
        return None
    if not users:
        return None
    u = users[0]
    if u.get("deactivated"):
        return None
    return {
        "id": u["id"],
        "first_name": u.get("first_name", ""),
        "last_name": u.get("last_name", ""),
    }


def resolve_vk_names(vk_ids: list[int]) -> dict[int, dict]:
    import config
    from services.logging_svc import record_log
    if not config.VK_SERVICE_TOKEN or not vk_ids:
        return {}
    try:
        import vk_api
    except ImportError:
        record_log("vk", "error", event="vk_api", message="vk_api not installed")
        return {}

    ids_to_request = [int(x) for x in vk_ids[:1000] if int(x) not in _NAME_CACHE]
    if not ids_to_request:
        return {k: dict(v) for k, v in _NAME_CACHE.items()}

    vk = vk_api.VkApi(token=config.VK_SERVICE_TOKEN, api_version="5.199").get_api()
    resolved: dict[int, dict] = {}

    def _fetch(ids_str: str):
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(vk.users.get, user_ids=ids_str, fields="first_name,last_name", lang="ru")
            try:
                return fut.result(timeout=VK_TIMEOUT)
            except FutureTimeout:
                return None

    for start in range(0, len(ids_to_request), 100):
        chunk = ids_to_request[start:start + 100]
        ids_str = ",".join(str(x) for x in chunk)
        users = None
        for attempt in (1, 2):
            users = _fetch(ids_str)
            if users is not None:
                break
            record_log(
                "vk", "error" if attempt == 2 else "warn", event="vk_api",
                message=f"users.get failed or timed out", details={"attempt": attempt, "count": len(chunk)},
            )
            if attempt == 1:
                import time
                time.sleep(0.4)
        if not users:
            continue
        for u in users:
            resolved[int(u["id"])] = {
                "first_name": u.get("first_name", ""),
                "last_name": u.get("last_name", ""),
            }

    _NAME_CACHE.update(resolved)
    out = {k: dict(v) for k, v in _NAME_CACHE.items()}
    record_log(
        "vk", "info", event="vk_api", message="users.get ok",
        details={"requested": len(ids_to_request), "resolved": len(resolved), "cached": len(_NAME_CACHE)},
    )
    return out
