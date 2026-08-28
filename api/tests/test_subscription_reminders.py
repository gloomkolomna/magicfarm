import datetime
from datetime import timedelta

from models import Notification, SubscriptionReminder, User
from services.subscription_tasks import send_due_reminders
from tests.conftest import TestingSessionLocal


def _utcnow():
    return datetime.datetime.utcnow()


def _add_user(db, vk_id, *, sub_days=None, trial_days=None, block=False, role="player"):
    u = User(
        vk_id=vk_id, role=role, block_after_expiry=block,
        subscription_until=_utcnow() + timedelta(days=sub_days) if sub_days is not None else None,
        trial_until=_utcnow() + timedelta(days=trial_days) if trial_days is not None else None,
    )
    db.add(u)
    db.commit()
    return u


def _notifications(db, vk_id):
    return db.query(Notification).filter(Notification.user_id == vk_id).all()


def test_reminder_sent_at_5_days(db):
    _add_user(db, 601, sub_days=5)
    assert send_due_reminders(db) == 1
    notes = _notifications(db, 601)
    assert len(notes) == 1
    assert notes[0].kind == "subscription"
    assert "5 дн." in notes[0].text


def test_reminder_not_duplicated_on_rerun(db):
    _add_user(db, 602, sub_days=5)
    assert send_due_reminders(db) == 1
    assert send_due_reminders(db) == 0
    assert len(_notifications(db, 602)) == 1
    assert db.query(SubscriptionReminder).filter(SubscriptionReminder.user_id == 602).count() == 1


def test_reminders_at_3_and_1_days(db):
    _add_user(db, 603, sub_days=3)
    _add_user(db, 604, sub_days=1)
    assert send_due_reminders(db) == 2
    assert "3 дн." in _notifications(db, 603)[0].text
    assert "1 дн." in _notifications(db, 604)[0].text


def test_no_reminder_at_4_days(db):
    _add_user(db, 605, sub_days=4)
    assert send_due_reminders(db) == 0
    assert _notifications(db, 605) == []


def test_no_reminder_for_expired_or_missing_subscription(db):
    _add_user(db, 606, sub_days=-1)
    _add_user(db, 607)
    assert send_due_reminders(db) == 0


def test_no_reminder_for_blocked_or_admin(db):
    _add_user(db, 608, sub_days=5, block=True)
    _add_user(db, 609, sub_days=5, role="admin")
    assert send_due_reminders(db) == 0


def test_reminder_fires_again_after_renewal(db):
    u = _add_user(db, 610, sub_days=3)
    assert send_due_reminders(db) == 1
    u.subscription_until = _utcnow() + timedelta(days=5)
    db.commit()
    assert send_due_reminders(db) == 1
    assert len(_notifications(db, 610)) == 2


def test_trial_reminder_sent_at_5_days(db):
    _add_user(db, 611, trial_days=5)
    assert send_due_reminders(db) == 1
    notes = _notifications(db, 611)
    assert len(notes) == 1
    assert notes[0].kind == "trial"
    assert "Пробный период" in notes[0].text
    assert "5 дн." in notes[0].text


def test_trial_reminder_not_duplicated_on_rerun(db):
    _add_user(db, 612, trial_days=3)
    assert send_due_reminders(db) == 1
    assert send_due_reminders(db) == 0
    assert len(_notifications(db, 612)) == 1


def test_no_trial_reminder_at_4_days(db):
    _add_user(db, 613, trial_days=4)
    assert send_due_reminders(db) == 0


def test_no_trial_reminder_after_expiry(db):
    _add_user(db, 614, trial_days=-1)
    assert send_due_reminders(db) == 0


def test_trial_reminder_skipped_when_subscription_extends_beyond(db):
    _add_user(db, 615, trial_days=5, sub_days=20)
    assert send_due_reminders(db) == 0
    assert _notifications(db, 615) == []


def test_trial_and_subscription_reminders_both_sent(db):
    _add_user(db, 616, trial_days=5, sub_days=3)
    assert send_due_reminders(db) == 2
    kinds = sorted(n.kind for n in _notifications(db, 616))
    assert kinds == ["subscription", "trial"]


def test_no_trial_reminder_for_blocked_or_admin(db):
    _add_user(db, 617, trial_days=5, block=True)
    _add_user(db, 618, trial_days=5, role="admin")
    assert send_due_reminders(db) == 0


def test_trial_reminder_fires_again_after_admin_extends_trial(db):
    u = _add_user(db, 619, trial_days=3)
    assert send_due_reminders(db) == 1
    u.trial_until = _utcnow() + timedelta(days=5)
    db.commit()
    assert send_due_reminders(db) == 1
    assert len(_notifications(db, 619)) == 2
