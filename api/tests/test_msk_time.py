from datetime import date, datetime, timedelta, timezone

from services.msk_time import WINDOW_KINDS, MSK, next_open_at, now_msk, window_active


def _msk_dt(hour: int, minute: int = 0, day: int = 18) -> datetime:
    return datetime(2026, 8, day, hour, minute, tzinfo=MSK)


def test_windows_kinds():
    assert WINDOW_KINDS == ("morning", "day", "night", "always")


def test_window_active_morning():
    assert window_active("morning", _msk_dt(4)) is True
    assert window_active("morning", _msk_dt(9, 59)) is True
    assert window_active("morning", _msk_dt(10)) is False
    assert window_active("morning", _msk_dt(11)) is False


def test_window_active_day():
    assert window_active("day", _msk_dt(12)) is True
    assert window_active("day", _msk_dt(14, 59)) is True
    assert window_active("day", _msk_dt(15)) is False
    assert window_active("day", _msk_dt(11)) is False


def test_window_active_night_crosses_midnight():
    assert window_active("night", _msk_dt(21)) is True
    assert window_active("night", _msk_dt(23, 30)) is True
    assert window_active("night", _msk_dt(2, 59)) is True
    assert window_active("night", _msk_dt(3)) is False
    assert window_active("night", _msk_dt(20, 59)) is False


def test_window_active_always():
    assert window_active("always", _msk_dt(3)) is True
    assert window_active("always", _msk_dt(12)) is True


def test_window_active_unknown_kind():
    assert window_active("lunch", _msk_dt(12)) is False


def test_next_open_at_morning_from_afternoon():
    nxt = next_open_at("morning", _msk_dt(12))
    assert nxt is not None
    assert nxt.date() == date(2026, 8, 19)
    assert nxt.hour == 4


def test_next_open_at_morning_from_early_night():
    nxt = next_open_at("morning", _msk_dt(2))
    assert nxt is not None
    assert nxt.date() == date(2026, 8, 18)
    assert nxt.hour == 4


def test_next_open_at_night_from_afternoon():
    nxt = next_open_at("night", _msk_dt(15))
    assert nxt is not None
    assert nxt.date() == date(2026, 8, 18)
    assert nxt.hour == 21


def test_next_open_at_night_from_morning_after_end():
    nxt = next_open_at("night", _msk_dt(5))
    assert nxt is not None
    assert nxt.date() == date(2026, 8, 18)
    assert nxt.hour == 21


def test_next_open_at_always_is_none():
    assert next_open_at("always", _msk_dt(12)) is None


def test_now_msk_offset():
    now = now_msk()
    assert now.utcoffset() == timedelta(hours=3)


def test_window_active_rejects_naive_now():
    from datetime import datetime as dt
    assert window_active("always", dt(2026, 8, 18, 12, 0)) is True


def test_window_active_astimezone_handles_utc_now():
    utc = timezone.utc
    now_utc = datetime(2026, 8, 18, 9, 0, tzinfo=utc)
    assert window_active("day", now_utc) is True
