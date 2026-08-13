from __future__ import annotations
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
    ids_to_request = [int(x) for x in vk_ids[:1000]]
    vk = vk_api.VkApi(token=config.VK_SERVICE_TOKEN, api_version="5.199").get_api()
    resolved: dict[int, dict] = {}
    for start in range(0, len(ids_to_request), 100):
        chunk = ids_to_request[start:start + 100]
        ids_str = ",".join(str(x) for x in chunk)
        users = None
        for attempt in (1, 2):
            try:
                users = vk.users.get(user_ids=ids_str, fields="first_name,last_name")
                break
            except Exception as e:
                record_log(
                    "vk", "error" if attempt == 2 else "warn", event="vk_api",
                    message=f"users.get failed: {e}", details={"attempt": attempt, "count": len(chunk)},
                )
                if attempt == 1:
                    import time
                    time.sleep(0.4)
        if users is None:
            continue
        for u in users:
            resolved[u["id"]] = {
                "first_name": u.get("first_name", ""),
                "last_name": u.get("last_name", ""),
            }
    record_log(
        "vk", "info", event="vk_api", message="users.get ok",
        details={"requested": len(ids_to_request), "resolved": len(resolved)},
    )
    return resolved
