from __future__ import annotations

import datetime
import threading
import time

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import config
from services.subscription import (
    REMINDER_DAYS, days_left, is_access_active, is_subscription_active, is_trial_active,
)

CHECK_INTERVAL_SECONDS = 30 * 60


def _send_once(db: Session, vk_id: int, key: str, kind: str, text: str) -> bool:
    from models import SubscriptionReminder
    from routes.notifications import notify

    exists = db.query(SubscriptionReminder).filter(
        SubscriptionReminder.user_id == vk_id,
        SubscriptionReminder.reminder_key == key,
    ).first()
    if exists is not None:
        return False
    notify(db, vk_id, text, kind=kind)
    db.add(SubscriptionReminder(user_id=vk_id, reminder_key=key))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True


def send_due_reminders(db: Session) -> int:
    from models import User

    sent = 0
    users = db.query(User).filter(User.role != "admin").all()
    for u in users:
        if u.block_after_expiry:
            continue
        due = []
        if is_subscription_active(u):
            d = days_left(u.subscription_until)
            if d in REMINDER_DAYS:
                until_str = u.subscription_until.strftime("%d.%m.%Y")
                due.append((
                    f"{u.subscription_until.isoformat()}|{d}",
                    "subscription",
                    f"⏳ Подписка заканчивается через {d} дн. (до {until_str}). Продлить можно уже сейчас.",
                ))
        if is_trial_active(u) and not (u.subscription_until and u.subscription_until > u.trial_until):
            d = days_left(u.trial_until)
            if d in REMINDER_DAYS:
                until_str = u.trial_until.strftime("%d.%m.%Y")
                due.append((
                    f"trial|{u.trial_until.isoformat()}|{d}",
                    "trial",
                    f"⏳ Пробный период заканчивается через {d} дн. (до {until_str}). "
                    "После его окончания можно оформить подписку — прогресс сохранится.",
                ))
        for key, kind, text in due:
            if _send_once(db, u.vk_id, key, kind, text):
                sent += 1
    return sent


def apply_future_blocks(db: Session) -> int:
    from models import User

    users = db.query(User).filter(
        User.role != "admin",
        User.block_after_expiry.is_(True),
        User.status == "active",
    ).all()
    changed = 0
    for u in users:
        if is_access_active(u):
            continue
        u.status = "readonly"
        changed += 1
    if changed:
        db.commit()
    return changed


def run_subscription_tasks(db: Session) -> dict:
    return {
        "reminders": send_due_reminders(db),
        "blocked": apply_future_blocks(db),
    }


def subscription_tasks_loop() -> None:
    from db import SessionLocal

    while True:
        try:
            db = SessionLocal()
            try:
                run_subscription_tasks(db)
            finally:
                db.close()
        except Exception:
            pass
        time.sleep(CHECK_INTERVAL_SECONDS)


def start_subscription_tasks_thread() -> threading.Thread | None:
    if not config.SUBSCRIPTION_TASKS_ENABLED:
        return None
    t = threading.Thread(target=subscription_tasks_loop, daemon=True, name="subscription-tasks")
    t.start()
    return t
