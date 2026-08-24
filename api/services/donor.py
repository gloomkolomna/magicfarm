from __future__ import annotations

import datetime
import threading
import time

import config


def _now_iso() -> str:
    return datetime.datetime.utcnow().isoformat()


def _fetch_remote(vk_id: int) -> dict | None:
    """Запрос к донат-боту; None — не настроен или недоступен."""
    if not config.DONUT_API_URL or not config.DONUT_API_KEY:
        return None
    import httpx

    try:
        resp = httpx.get(
            f"{config.DONUT_API_URL.rstrip('/')}/{vk_id}",
            headers={"X-API-Key": config.DONUT_API_KEY},
            timeout=config.DONUT_TIMEOUT_SECONDS,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def sync_user(db, vk_id: int) -> bool | None:
    """Live-проверка дон-статуса с обновлением кеша.

    Возвращает is_don (bool) или None, если донат-бот не настроен/недоступен
    (кеш при этом не трогается — решения принимаются по последнему значению).
    """
    from models import DonorCache

    data = _fetch_remote(vk_id)
    if data is None:
        return None
    is_don = bool(data.get("is_don"))

    row = db.query(DonorCache).filter(DonorCache.vk_id == vk_id).first()
    if row is None:
        row = DonorCache(vk_id=vk_id)
        db.add(row)
    row.is_don = is_don
    row.don_since = (str(data.get("don_since")) if data.get("don_since") else None)
    row.updated_at = (str(data.get("updated_at")) if data.get("updated_at") else None)
    row.last_synced_at = _now_iso()
    db.commit()
    return is_don


def is_donor(db, vk_id: int) -> bool:
    from models import DonorCache

    row = db.query(DonorCache).filter(DonorCache.vk_id == vk_id).first()
    return bool(row is not None and row.is_don)


def donor_flags(db, vk_ids: list[int]) -> dict[int, bool]:
    from models import DonorCache

    if not vk_ids:
        return {}
    rows = db.query(DonorCache).filter(DonorCache.vk_id.in_(vk_ids)).all()
    return {r.vk_id: bool(r.is_don) for r in rows}


def sync_all_users(db) -> int:
    """Синхронизирует кеш по всем игрокам (кроме админов); возвращает число успешных."""
    from models import User

    synced = 0
    for u in db.query(User).filter(User.role != "admin").all():
        if sync_user(db, u.vk_id) is not None:
            synced += 1
    return synced


def donor_loop() -> None:
    from db import SessionLocal

    while True:
        try:
            db = SessionLocal()
            try:
                sync_all_users(db)
            finally:
                db.close()
        except Exception:
            pass
        time.sleep(max(60, config.DONOR_SYNC_INTERVAL_MINUTES * 60))


def start_donor_sync_thread() -> threading.Thread | None:
    if not (config.DONUT_API_URL and config.DONUT_API_KEY):
        return None
    t = threading.Thread(target=donor_loop, daemon=True, name="donor-sync")
    t.start()
    return t


def can_play(db, user) -> tuple[bool, str | None]:
    """Право играть при открытом дон-гейте.

    - админ — всегда;
    - дон / donor_exempt — по обычным правилам (триал ∪ подписка);
    - не-дон — только доиграть оплаченную подписку (триал не считается).

    Возвращает (разрешено, причина): причина None | "subscription_expired" | "not_donor".
    """
    from services.subscription import is_subscription_active, is_trial_active

    if user.role == "admin":
        return True, None
    if user.donor_exempt or is_donor(db, user.vk_id):
        if is_trial_active(user) or is_subscription_active(user):
            return True, None
        return False, "subscription_expired"
    if is_subscription_active(user):
        return True, None
    return False, "not_donor"


def can_renew_subscription(db, user) -> bool:
    """Продление/покупка подписки — только дону или exempt."""
    if user.role == "admin":
        return True
    return bool(user.donor_exempt) or is_donor(db, user.vk_id)
