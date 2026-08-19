from __future__ import annotations
import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_role
from models import Setting, User, UserCrystalNorm

router = APIRouter(prefix="/api", tags=["settings"])


# Ключи настроек и их ограничения.
AUTO_CREDIT_KEY = "auto_credit"
DEFAULT_AUTO_CREDIT = True

PLANT_QTY_KEY = "default_plant_qty"
MIN_QTY = 1
MAX_QTY = 50
DEFAULT_QTY = 7

PRODUCTION_REQUIRED_KEY = "production_required"
MIN_PROD_REQ = 100
MAX_PROD_REQ = 100000
DEFAULT_PROD_REQ = 500

ORDER_REWARD_KEY = "order_reward_per_unit"
MIN_REWARD = 1
MAX_REWARD = 1000
DEFAULT_REWARD = 5

ANIMAL_BUILD_NORM_KEY = "animal_build_norm"
DEFAULT_ANIMAL_BUILD = 1000

CUSTOMER_MAX_ORDERS_KEY = "customer_max_orders"
MIN_CUSTOMER_ORDERS = 0
MAX_CUSTOMER_ORDERS = 50
DEFAULT_CUSTOMER_ORDERS = 3

SALE_PRICE_RATIO_KEY = "sale_price_ratio"
DEFAULT_SALE_RATIO = 0.5

DEFAULT_BG_KEY = "default_background_url"
INFIRMARY_BG_KEY = "infirmary_background_url"


CRYSTAL_COLORS = ("green", "blue", "violet")

# Базовые нормы за 1 кристалл (значение по умолчанию для стандарта).
DEFAULT_CARD_NORMS: dict[str, int] = {"green": 10, "blue": 20, "violet": 30}

# Личная норма кубика игрока (за 1 точку); фолбэк, если не задана.
DEFAULT_DICE_NORM = 200

# Личная норма продукции скотного двора (крестиков за 1 единицу при заборе со склада шатра); фолбэк, если не задана.
DEFAULT_ANIMAL_PRODUCT_NORM = 100


# Стандарт норм кристаллов, задаваемый админом (JSON в настройке crystal_standard).
# Структура: {color -> {"norm": база за 1 кристалл, "treasure": норма сокровища}}.
CRYSTAL_STANDARD_KEY = "crystal_standard"


def _default_standard() -> dict[str, dict[str, int]]:
    return {color: {"norm": val, "treasure": 0} for color, val in DEFAULT_CARD_NORMS.items()}


def get_crystal_standard(db: Session) -> dict[str, dict[str, int]]:
    s = db.query(Setting).filter(Setting.key == CRYSTAL_STANDARD_KEY).first()
    if s is None:
        return _default_standard()
    try:
        data = json.loads(s.value)
    except (TypeError, ValueError):
        return _default_standard()
    if not isinstance(data, dict) or set(data.keys()) != set(CRYSTAL_COLORS):
        return _default_standard()
    result = {}
    for color in CRYSTAL_COLORS:
        per_color = data.get(color)
        if not isinstance(per_color, dict):
            return _default_standard()
        norm = per_color.get("norm")
        treasure = per_color.get("treasure", 0)
        if not isinstance(norm, int) or norm < 1:
            return _default_standard()
        if not isinstance(treasure, int) or treasure < 0:
            treasure = 0
        result[color] = {"norm": norm, "treasure": treasure}
    return result


def set_crystal_standard(db: Session, norms: dict[str, dict[str, int]]) -> None:
    serializable = {
        color: {"norm": int(per_color["norm"]), "treasure": int(per_color.get("treasure", 0))}
        for color, per_color in norms.items()
    }
    s = db.query(Setting).filter(Setting.key == CRYSTAL_STANDARD_KEY).first()
    if s is None:
        s = Setting(key=CRYSTAL_STANDARD_KEY, value=json.dumps(serializable))
        db.add(s)
    else:
        s.value = json.dumps(serializable)


def get_auto_credit(db: Session) -> bool:
    s = db.query(Setting).filter(Setting.key == AUTO_CREDIT_KEY).first()
    if s is None:
        return DEFAULT_AUTO_CREDIT
    return str(s.value).strip().lower() in ("1", "true", "yes", "on")


def get_default_plant_qty(db: Session) -> int:
    s = db.query(Setting).filter(Setting.key == PLANT_QTY_KEY).first()
    if s is None:
        return DEFAULT_QTY
    try:
        return max(MIN_QTY, min(MAX_QTY, int(s.value)))
    except (TypeError, ValueError):
        return DEFAULT_QTY


def get_production_required(db: Session) -> int:
    s = db.query(Setting).filter(Setting.key == PRODUCTION_REQUIRED_KEY).first()
    if s is None:
        return DEFAULT_PROD_REQ
    try:
        return max(MIN_PROD_REQ, min(MAX_PROD_REQ, int(s.value)))
    except (TypeError, ValueError):
        return DEFAULT_PROD_REQ


def get_order_reward(db: Session) -> int:
    s = db.query(Setting).filter(Setting.key == ORDER_REWARD_KEY).first()
    if s is None:
        return DEFAULT_REWARD
    try:
        return max(MIN_REWARD, min(MAX_REWARD, int(s.value)))
    except (TypeError, ValueError):
        return DEFAULT_REWARD


def get_animal_build_norm(db: Session) -> int:
    s = db.query(Setting).filter(Setting.key == ANIMAL_BUILD_NORM_KEY).first()
    if s is None:
        return DEFAULT_ANIMAL_BUILD
    try:
        return max(1, min(100000, int(s.value)))
    except (TypeError, ValueError):
        return DEFAULT_ANIMAL_BUILD


def get_customer_max_orders(db: Session) -> int:
    s = db.query(Setting).filter(Setting.key == CUSTOMER_MAX_ORDERS_KEY).first()
    if s is None:
        return DEFAULT_CUSTOMER_ORDERS
    try:
        return max(MIN_CUSTOMER_ORDERS, min(MAX_CUSTOMER_ORDERS, int(s.value)))
    except (TypeError, ValueError):
        return DEFAULT_CUSTOMER_ORDERS


def get_sale_price_ratio(db: Session) -> float:
    s = db.query(Setting).filter(Setting.key == SALE_PRICE_RATIO_KEY).first()
    if s is None:
        return DEFAULT_SALE_RATIO
    try:
        return max(0.01, min(1.0, float(s.value)))
    except (TypeError, ValueError):
        return DEFAULT_SALE_RATIO


def crystal_norm(db: Session, user: User, color: str) -> int:
    """База за 1 кристалл: личная норма игрока либо стандарт админа."""
    norm_row = db.query(UserCrystalNorm).filter(
        UserCrystalNorm.user_id == user.vk_id,
        UserCrystalNorm.color == color,
        UserCrystalNorm.count == 1,
    ).first()
    if norm_row is not None:
        return norm_row.value

    standard = get_crystal_standard(db)
    per_color = standard.get(color)
    if per_color is None:
        return DEFAULT_CARD_NORMS.get(color, 1)
    return per_color["norm"]


def get_dice_norm(user: User) -> int:
    """Личная норма кубика игрока (за 1 точку)."""
    if user.dice_norm is None:
        return DEFAULT_DICE_NORM
    return max(1, min(100000, int(user.dice_norm)))


def get_animal_product_norm(user: User) -> int:
    """Личная норма продукции скотного двора (крестиков за 1 единицу при заборе со склада шатра)."""
    if user.animal_product_norm is None:
        return DEFAULT_ANIMAL_PRODUCT_NORM
    return max(1, min(100000, int(user.animal_product_norm)))


_STUDY_NORM_ATTRS = {1: "study_norm_l1", 2: "study_norm_l2", 3: "study_norm_l3"}
_PRODUCTION_NORM_ATTRS = {1: "production_norm_l1", 2: "production_norm_l2", 3: "production_norm_l3"}


def get_user_study_norm(user: User, level: int) -> int | None:
    """Личная норма изучения рецепта уровня; None — игрок ещё не задал."""
    attr = _STUDY_NORM_ATTRS.get(level, "study_norm_l1")
    val = getattr(user, attr, None)
    if val is None:
        return None
    return max(1, min(100000, int(val)))


def get_user_production_norm(user: User, level: int) -> int | None:
    """Личная норма производства товара уровня; None — игрок ещё не задал."""
    attr = _PRODUCTION_NORM_ATTRS.get(level, "production_norm_l1")
    val = getattr(user, attr, None)
    if val is None:
        return None
    return max(1, min(100000, int(val)))


class SettingOut(BaseModel):
    key: str
    value: str


class BackgroundUpdate(BaseModel):
    url: str


@router.get("/settings/background")
def get_background(db: Session = Depends(get_db)):
    s = db.query(Setting).filter(Setting.key == DEFAULT_BG_KEY).first()
    return {"url": s.value if s else ""}


@router.get("/settings/infirmary-background")
def get_infirmary_background(db: Session = Depends(get_db)):
    s = db.query(Setting).filter(Setting.key == INFIRMARY_BG_KEY).first()
    return {"url": s.value if s else ""}


@router.put("/settings/background")
def set_background(
    req: BackgroundUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    s = db.query(Setting).filter(Setting.key == DEFAULT_BG_KEY).first()
    if s is None:
        s = Setting(key=DEFAULT_BG_KEY, value=req.url)
        db.add(s)
    else:
        s.value = req.url
    db.commit()
    return {"url": req.url}


_SETTING_META = {
    PLANT_QTY_KEY: (MIN_QTY, MAX_QTY, DEFAULT_QTY),
    PRODUCTION_REQUIRED_KEY: (MIN_PROD_REQ, MAX_PROD_REQ, DEFAULT_PROD_REQ),
    ORDER_REWARD_KEY: (MIN_REWARD, MAX_REWARD, DEFAULT_REWARD),
    AUTO_CREDIT_KEY: (0, 1, 1 if DEFAULT_AUTO_CREDIT else 0),
    ANIMAL_BUILD_NORM_KEY: (1, 100000, DEFAULT_ANIMAL_BUILD),
    CUSTOMER_MAX_ORDERS_KEY: (MIN_CUSTOMER_ORDERS, MAX_CUSTOMER_ORDERS, DEFAULT_CUSTOMER_ORDERS),
}


def _get_setting_or_404(key: str, db: Session) -> Setting:
    s = db.query(Setting).filter(Setting.key == key).first()
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Настройка не найдена")
    return s


@router.get("/settings/{key}", response_model=SettingOut)
def get_setting(key: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if key == AUTO_CREDIT_KEY:
        return SettingOut(key=key, value=str(int(get_auto_credit(db))))
    if key == PLANT_QTY_KEY:
        return SettingOut(key=key, value=str(get_default_plant_qty(db)))
    if key == PRODUCTION_REQUIRED_KEY:
        return SettingOut(key=key, value=str(get_production_required(db)))
    if key == ORDER_REWARD_KEY:
        return SettingOut(key=key, value=str(get_order_reward(db)))
    if key == SALE_PRICE_RATIO_KEY:
        return SettingOut(key=key, value=str(get_sale_price_ratio(db)))
    if key == CUSTOMER_MAX_ORDERS_KEY:
        return SettingOut(key=key, value=str(get_customer_max_orders(db)))
    s = _get_setting_or_404(key, db)
    return SettingOut(key=s.key, value=s.value)


class SettingUpdate(BaseModel):
    value: str


@router.put("/admin/settings/{key}", response_model=SettingOut)
def update_setting(
    key: str,
    req: SettingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if key not in _SETTING_META:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Настройка не найдена")

    lo, hi, default = _SETTING_META[key]
    raw = (req.value or "").strip()
    try:
        num = int(float(raw))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Значение должно быть числом")
    num = max(lo, min(hi, num))

    s = db.query(Setting).filter(Setting.key == key).first()
    if s is None:
        s = Setting(key=key, value=str(num))
        db.add(s)
    else:
        s.value = str(num)
    db.commit()
    db.refresh(s)
    return SettingOut(key=s.key, value=s.value)
