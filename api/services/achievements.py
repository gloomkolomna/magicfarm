from __future__ import annotations
from sqlalchemy.orm import Session
from models import Achievement, Plot, UserAchievement


ACHIEVEMENT_KINDS = [
    {"kind": "first_plant", "label": "Первое растение", "hint": "первая грядка посажена"},
    {"kind": "plots_count", "label": "Грядки", "hint": "сколько грядок у игрока"},
    {"kind": "first_order", "label": "Первый заказ", "hint": "выполнено заказов"},
    {"kind": "coins_reached", "label": "Монеты", "hint": "всего монет у игрока"},
    {"kind": "animals_count", "label": "Животные", "hint": "животных в стойле"},
    {"kind": "pets_count", "label": "Питомцы", "hint": "питомцев у игрока"},
    {"kind": "potions_count", "label": "Зелья", "hint": "зелий у игрока"},
    {"kind": "tents_count", "label": "Шатры", "hint": "построено шатров"},
    {"kind": "house_built", "label": "Дом ведьмы", "hint": "построен дом ведьмы"},
    {"kind": "level_reached", "label": "Уровень", "hint": "достигнут уровень"},
    {"kind": "healed_count", "label": "Излечено животных", "hint": "вылечено пациентов в лечебнице"},
    {"kind": "infirmary_level_complete", "label": "Уровень лечебницы", "hint": "пройден уровень лечебницы (production_code = 1/2/3)"},
    {"kind": "full_collection", "label": "Полная коллекция", "hint": "вылечены все животные лечебницы"},
]


def known_kinds() -> set[str]:
    return {k["kind"] for k in ACHIEVEMENT_KINDS}


def check_and_award(user_id: int, condition_kind: str, db: Session) -> int:
    achievements = db.query(Achievement).filter(
        Achievement.condition_kind == condition_kind
    ).all()
    awarded = 0
    for a in achievements:
        existing = db.query(UserAchievement).filter(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == a.id,
        ).first()
        if existing is not None:
            continue
        if _meets_condition(user_id, a, db):
            db.add(UserAchievement(user_id=user_id, achievement_id=a.id))
            awarded += 1
    if awarded:
        db.commit()
    return awarded


def _meets_condition(user_id: int, a: Achievement, db: Session) -> bool:
    if a.condition_kind == "first_plant":
        count = db.query(Plot).filter(Plot.user_id == user_id, Plot.cell_id.isnot(None)).count()
        return count >= a.condition_value
    if a.condition_kind == "plots_count":
        count = db.query(Plot).filter(Plot.user_id == user_id, Plot.cell_id.isnot(None)).count()
        return count >= a.condition_value
    if a.condition_kind == "first_order":
        from models import UserOrder
        count = db.query(UserOrder).filter(
            UserOrder.user_id == user_id, UserOrder.fulfilled_at.isnot(None)
        ).count()
        return count >= a.condition_value
    if a.condition_kind == "coins_reached":
        from models import User
        u = db.query(User).filter(User.vk_id == user_id).first()
        return (u.coins or 0) >= a.condition_value
    if a.condition_kind == "animals_count":
        from models import BarnyardSlot
        count = db.query(BarnyardSlot).filter(
            BarnyardSlot.user_id == user_id, BarnyardSlot.animal_id.isnot(None)
        ).count()
        return count >= a.condition_value
    if a.condition_kind == "pets_count":
        from models import UserPet
        count = db.query(UserPet).filter(UserPet.user_id == user_id).count()
        return count >= a.condition_value
    if a.condition_kind == "potions_count":
        from models import UserPotion
        count = db.query(UserPotion).filter(UserPotion.user_id == user_id).count()
        return count >= a.condition_value
    if a.condition_kind == "tents_count":
        from models import Tent, TentBuild
        q = db.query(TentBuild).join(Tent, TentBuild.tent_id == Tent.id).filter(
            TentBuild.user_id == user_id, TentBuild.build_status == "built"
        )
        if a.production_code:
            q = q.filter(Tent.kind == a.production_code)
        return q.count() >= a.condition_value
    if a.condition_kind == "house_built":
        from models import HouseBuild
        count = db.query(HouseBuild).filter(
            HouseBuild.user_id == user_id, HouseBuild.phase == "built"
        ).count()
        return count >= a.condition_value
    if a.condition_kind == "level_reached":
        from models import User
        u = db.query(User).filter(User.vk_id == user_id).first()
        return (u.level or 0) >= a.condition_value
    if a.condition_kind == "healed_count":
        from models import UserPatientState
        count = db.query(UserPatientState).filter(
            UserPatientState.user_id == user_id, UserPatientState.status.in_(["treated", "released"])
        ).count()
        return count >= a.condition_value
    if a.condition_kind == "infirmary_level_complete":
        from models import PatientAnimal, UserPatientState
        try:
            level = int(a.production_code or 0)
        except (TypeError, ValueError):
            return False
        patients = [p.id for p in db.query(PatientAnimal).filter(PatientAnimal.level == level).all()]
        if not patients:
            return False
        healed = db.query(UserPatientState).filter(
            UserPatientState.user_id == user_id, UserPatientState.status.in_(["treated", "released"]),
            UserPatientState.patient_id.in_(patients),
        ).count()
        return healed >= len(patients)
    if a.condition_kind == "full_collection":
        from models import PatientAnimal, UserPatientState
        total = db.query(PatientAnimal).count()
        if total == 0:
            return False
        healed = db.query(UserPatientState).filter(
            UserPatientState.user_id == user_id, UserPatientState.status.in_(["treated", "released"])
        ).count()
        return healed >= total
    return False
