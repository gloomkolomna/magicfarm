from __future__ import annotations
from datetime import datetime, time, timedelta, timezone

MSK = timezone(timedelta(hours=3))

WINDOW_KINDS = ("morning", "day", "night", "always")

WINDOW_RANGES = {
    "morning": (time(4, 0), time(10, 0)),
    "day": (time(12, 0), time(15, 0)),
    "night": (time(21, 0), time(3, 0)),
}


def now_msk() -> datetime:
    return datetime.now(MSK)


def window_active(kind: str, now: datetime | None = None) -> bool:
    if kind == "always":
        return True
    if kind not in WINDOW_RANGES:
        return False
    current = now_msk() if now is None else now.astimezone(MSK)
    start, end = WINDOW_RANGES[kind]
    current_time = current.time()
    if start <= end:
        return start <= current_time < end
    return current_time >= start or current_time < end


def next_open_at(kind: str, now: datetime | None = None) -> datetime | None:
    if kind == "always" or kind not in WINDOW_RANGES:
        return None
    current = now_msk() if now is None else now.astimezone(MSK)
    start, _ = WINDOW_RANGES[kind]
    candidate = datetime.combine(current.date(), start, tzinfo=MSK)
    while candidate <= current:
        candidate += timedelta(days=1)
    return candidate
