from __future__ import annotations

import re
import time
from urllib.parse import urlparse

import requests

VK_TIMEOUT = 8
VK_API_VERSION = "5.199"
_NAME_CACHE: dict[int, dict] = {}
_NAME_MISS_CACHE: dict[int, float] = {}
_NAME_MISS_TTL = 300.0


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


def _vk_users_get(user_ids: str) -> list[dict] | None:
    import config
    from services.logging_svc import record_log
    if not config.VK_SERVICE_TOKEN or not user_ids:
        return None
    try:
        resp = requests.post(
            f"https://api.vk.ru/method/users.get",
            data={
                "user_ids": user_ids,
                "fields": "first_name,last_name",
                "lang": "ru",
                "access_token": config.VK_SERVICE_TOKEN,
                "v": VK_API_VERSION,
            },
            timeout=VK_TIMEOUT,
        )
    except requests.RequestException as e:
        record_log("vk", "error", event="vk_api", message=f"users.get failed: {e}")
        return None
    if resp.status_code != 200:
        record_log("vk", "error", event="vk_api", message=f"users.get http {resp.status_code}")
        return None
    try:
        body = resp.json()
    except ValueError:
        record_log("vk", "error", event="vk_api", message="users.get bad json")
        return None
    if "error" in body:
        record_log("vk", "error", event="vk_api", message=body["error"].get("error_msg", "vk error"))
        return None
    return body.get("response") or []


def resolve_vk_screen_name(name: str) -> dict | None:
    users = _vk_users_get(name)
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

    now = time.monotonic()
    ids_to_request = []
    for x in vk_ids[:1000]:
        x = int(x)
        if x in _NAME_CACHE:
            continue
        miss_at = _NAME_MISS_CACHE.get(x)
        if miss_at is not None and now - miss_at < _NAME_MISS_TTL:
            continue
        ids_to_request.append(x)
    if not ids_to_request:
        return {k: dict(v) for k, v in _NAME_CACHE.items()}

    resolved: dict[int, dict] = {}
    for start in range(0, len(ids_to_request), 100):
        chunk = ids_to_request[start:start + 100]
        ids_str = ",".join(str(x) for x in chunk)
        users = None
        for attempt in (1, 2):
            users = _vk_users_get(ids_str)
            if users is not None:
                break
            record_log(
                "vk", "error" if attempt == 2 else "warn", event="vk_api",
                message="users.get failed or timed out", details={"attempt": attempt, "count": len(chunk)},
            )
            if attempt == 1:
                time.sleep(0.4)
        if users is None:
            continue
        returned = set()
        for u in users:
            uid = int(u["id"])
            returned.add(uid)
            resolved[uid] = {
                "first_name": u.get("first_name", ""),
                "last_name": u.get("last_name", ""),
            }
        for uid in chunk:
            if uid not in returned:
                _NAME_MISS_CACHE[uid] = now

    _NAME_CACHE.update(resolved)
    out = {k: dict(v) for k, v in _NAME_CACHE.items()}
    record_log(
        "vk", "info", event="vk_api", message="users.get ok",
        details={"requested": len(ids_to_request), "resolved": len(resolved), "cached": len(_NAME_CACHE)},
    )
    return out


def vk_display_name(user) -> str:
    if user.display_name:
        return user.display_name
    full = ""
    try:
        nm = resolve_vk_names([user.vk_id]).get(user.vk_id, {})
        full = f"{nm.get('first_name', '')} {nm.get('last_name', '')}".strip()
    except Exception:
        full = ""
    return full or f"Игрок {user.vk_id}"
