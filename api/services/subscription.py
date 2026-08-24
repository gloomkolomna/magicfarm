from __future__ import annotations

import datetime

from sqlalchemy.orm import Session


TRIAL_DAYS_KEY = "trial_days"
BASE_PRICE_KEY = "subscription_price_rub"
DLC_CHANGE_IMMEDIATE_KEY = "dlc_change_immediate"
DEFAULT_TRIAL_DAYS = 7
DEFAULT_BASE_PRICE_RUB = 300
DEFAULT_DLC_PRICE_RUB = 50
PERIOD_DAYS = 30


def dlc_price_key(code: str) -> str:
    return f"subscription_price_rub_{code}"


def _get_int_setting(db: Session, key: str, default: int) -> int:
    from models import Setting

    s = db.query(Setting).filter(Setting.key == key).first()
    if s is None:
        return default
    try:
        return int(float(s.value))
    except (TypeError, ValueError):
        return default


def get_trial_days(db: Session) -> int:
    return _get_int_setting(db, TRIAL_DAYS_KEY, DEFAULT_TRIAL_DAYS)


def get_base_price_rub(db: Session) -> int:
    return _get_int_setting(db, BASE_PRICE_KEY, DEFAULT_BASE_PRICE_RUB)


def get_dlc_price_rub(db: Session, code: str) -> int:
    return _get_int_setting(db, dlc_price_key(code), DEFAULT_DLC_PRICE_RUB)


def get_dlc_change_immediate(db: Session) -> bool:
    return _get_int_setting(db, DLC_CHANGE_IMMEDIATE_KEY, 0) == 1


def dlc_catalog(db: Session) -> list[dict]:
    from models import LOCATION_CODES, LOCATION_NAMES

    return [
        {"code": c, "name": LOCATION_NAMES.get(c, c), "price_rub": get_dlc_price_rub(db, c)}
        for c in LOCATION_CODES
    ]


def price_rub_for(db: Session, dlc_codes: list[str]) -> int:
    return get_base_price_rub(db) + sum(get_dlc_price_rub(db, c) for c in dlc_codes)


def is_trial_active(user) -> bool:
    return user.trial_until is not None and user.trial_until > datetime.datetime.utcnow()


def is_subscription_active(user) -> bool:
    return user.subscription_until is not None and user.subscription_until > datetime.datetime.utcnow()


def is_access_active(user) -> bool:
    return is_trial_active(user) or is_subscription_active(user)


def access_until(user) -> datetime.datetime | None:
    candidates = [u for u in (user.trial_until, user.subscription_until) if u is not None]
    return max(candidates) if candidates else None


def days_left(until: datetime.datetime | None) -> int | None:
    if until is None:
        return None
    delta = until - datetime.datetime.utcnow()
    if delta.total_seconds() <= 0:
        return 0
    return delta.days + (1 if delta.seconds > 0 else 0)


def parse_dlc_codes(raw: str | None) -> list[str]:
    return [c for c in (raw or "").split(",") if c]


def dlc_codes_to_str(codes: list[str]) -> str:
    return ",".join(codes)


def extend_subscription(db: Session, user, days: int, dlc_codes: list[str]) -> None:
    base = max(datetime.datetime.utcnow(), user.subscription_until or datetime.datetime.utcnow())
    user.subscription_until = base + datetime.timedelta(days=days)
    user.subscription_dlc_codes = dlc_codes_to_str(dlc_codes)
    db.commit()


def set_trial_days(db: Session, user, days: int) -> None:
    user.trial_until = datetime.datetime.utcnow() + datetime.timedelta(days=days)
    db.commit()
