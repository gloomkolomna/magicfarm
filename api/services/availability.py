from __future__ import annotations

from sqlalchemy.orm import Session


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
    if suitable and all((f.min_level or 0) > (user.level or 0) for f in suitable):
        return f"Локация откроется на {min(f.min_level for f in suitable)} уровне"
    return None
