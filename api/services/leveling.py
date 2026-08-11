from sqlalchemy.orm import Session
from models import LevelGate, Plot, User


def check_level_up(db: Session, user: User) -> int | None:
    if user.route_variant is None:
        return None

    current = user.level or 0
    next_level = current + 1
    gate = db.query(LevelGate).filter(
        LevelGate.variant == user.route_variant, LevelGate.level == next_level
    ).first()
    if gate is None:
        return None

    if (user.coins or 0) < gate.coins_required:
        return None

    plot_count = db.query(Plot).filter(
        Plot.user_id == user.vk_id, Plot.cell_id.isnot(None)
    ).count()
    if plot_count < gate.plots_required:
        return None

    user.level = next_level

    if user.round < next_level:
        user.round = next_level

    db.commit()
    return next_level
