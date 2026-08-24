from __future__ import annotations

from sqlalchemy.orm import Session


def has_installed_kassa(user, db: Session) -> bool:
    """Построена ли у игрока шатёр-касса (Production kind=kassa)."""
    from models import KASSA_KIND, Production

    return (
        db.query(Production)
        .filter(Production.user_id == user.vk_id, Production.kind == KASSA_KIND)
        .first()
        is not None
    )


def user_dlc_codes(user, db: Session) -> set[str]:
    from models import UserDlcUnlock

    rows = (
        db.query(UserDlcUnlock.location_code)
        .filter(UserDlcUnlock.user_id == user.vk_id)
        .all()
    )
    return {r[0] for r in rows}


def location_lock_reason(code: str, user, db: Session) -> str | None:
    """Причина закрытости локации для игрока: глобальный замок минус доступ игрока.

    None — локация доступна. Админам всё доступно всегда.
    Доступ: вечная разблокировка ИЛИ активная подписка с ДЛС в составе.
    """
    from routes.settings import get_locked_locations

    if user is not None and user.role == "admin":
        return None
    if code not in get_locked_locations(db):
        return None
    if code in user_dlc_codes(user, db):
        return None
    if user is not None:
        from services.subscription import is_subscription_active, parse_dlc_codes

        if is_subscription_active(user) and code in parse_dlc_codes(user.subscription_dlc_codes):
            return None
    from models import LOCATION_NAMES

    return f"{LOCATION_NAMES.get(code, code)} пока закрыта"


def locked_locations_for(user, db: Session) -> list[str]:
    """Список кодов локаций, закрытых лично для этого игрока (админу — пусто)."""
    from models import LOCATION_CODES
    from routes.settings import get_locked_locations

    if user is not None and user.role == "admin":
        return []
    locked = get_locked_locations(db)
    if not locked:
        return []
    owned = user_dlc_codes(user, db)
    if user is not None:
        from services.subscription import is_subscription_active, parse_dlc_codes

        if is_subscription_active(user):
            owned = owned | set(parse_dlc_codes(user.subscription_dlc_codes))
    return sorted(c for c in LOCATION_CODES if c in locked and c not in owned)


def product_lock_reason(product, user, db: Session) -> str | None:
    """Причина недоступности товара для игрока: уровень растения или закрытые локации.

    None — товар доступен. Товары без растения (продукция животных, зелья) доступны всегда.
    """
    from models import Field, FieldPlant, Plant

    if product is None or product.plant_id is None:
        return None
    plant = db.query(Plant).filter(Plant.id == product.plant_id).first()
    if plant is None:
        return None
    if plant.category == "garden_beds" and plant.level > (user.unlocked_plot_level or 1):
        return f"Нужны грядки {plant.level} уровня"
    if plant.category == "orchard" and plant.level > (user.unlocked_garden_level or 0):
        return f"Нужны сады {plant.level} уровня"
    fields = (
        db.query(Field)
        .join(FieldPlant, FieldPlant.field_id == Field.id)
        .filter(FieldPlant.plant_id == plant.id)
        .all()
    )
    suitable = [f for f in fields if f.plant_category is None or f.plant_category == plant.category]

    def _blocked_by_level(f) -> bool:
        if (f.min_level or 0) <= (user.level or 0):
            return False
        if f.field_kind == "garden_beds" and (user.unlocked_plot_level or 1) >= 3:
            return False
        if f.field_kind == "orchard" and (user.unlocked_garden_level or 0) >= 3:
            return False
        return True

    if suitable and all(_blocked_by_level(f) for f in suitable):
        return f"Локация откроется на {min(f.min_level for f in suitable)} уровне"
    return None
