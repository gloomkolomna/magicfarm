from sqlalchemy.orm import Session
from models import LevelGate, Plot, User

UNLOCK_PARSERS = {
    "Животноводство +1": ("barnyard", 1),
    "Животноводство +2": ("barnyard", 2),
    "Питомец-помощник +1": ("pets", 1),
    "Сад 1 уровня": ("garden_level", 1),
    "Сад 2 уровня": ("garden_level", 2),
    "Сад 3 уровня": ("garden_level", 3),
    "Грядка 2 уровня": ("plot_level", 2),
    "Грядка 3 уровня": ("plot_level", 3),
}


def _apply_unlock(user: User, unlock_type: str | None) -> None:
    if unlock_type is None:
        return
    parsed = UNLOCK_PARSERS.get(unlock_type)
    if parsed is None:
        return
    kind, value = parsed
    if kind == "barnyard":
        user.unlocked_barnyard = (user.unlocked_barnyard or 0) + value
    elif kind == "pets":
        user.unlocked_pets = (user.unlocked_pets or 0) + value
    elif kind == "garden_level":
        if value > (user.unlocked_garden_level or 0):
            user.unlocked_garden_level = value
    elif kind == "plot_level":
        if value > (user.unlocked_plot_level or 0):
            user.unlocked_plot_level = value


def check_level_up(db: Session, user: User) -> int | None:
    current = user.level or 0
    next_level = current + 1
    gate = db.query(LevelGate).filter(LevelGate.level == next_level).first()
    if gate is None:
        return None

    u = db.query(User).filter(User.vk_id == user.vk_id).first()
    if u is None:
        return None

    if (u.coins or 0) < gate.coins_required:
        return None

    plot_count = db.query(Plot).filter(
        Plot.user_id == user.vk_id, Plot.cell_id.isnot(None)
    ).count()
    if plot_count < gate.plots_required:
        return None

    u.level = next_level

    if u.round < next_level:
        u.round = next_level

    _apply_unlock(u, gate.unlock_type)

    db.commit()
    return next_level
