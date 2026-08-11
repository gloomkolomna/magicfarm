import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_role
from models import Setting, User, UserCrystalNorm

router = APIRouter(prefix="/api", tags=["settings"])


# Ключи настроек и их ограничения.
CRYSTAL_RATE_VARIANT_KEY = "crystal_rate_variant"
MIN_VARIANT = 1
MAX_VARIANT = 8
DEFAULT_VARIANT = 1

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

PRODUCTION_NORM_L1_KEY = "production_norm_lvl1"
PRODUCTION_NORM_L2_KEY = "production_norm_lvl2"
PRODUCTION_NORM_L3_KEY = "production_norm_lvl3"
MIN_PROD_NORM = 1
MAX_PROD_NORM = 100000
DEFAULT_PROD_NORM_L1 = 100
DEFAULT_PROD_NORM_L2 = 200
DEFAULT_PROD_NORM_L3 = 300

STUDY_NORM_L1_KEY = "study_norm_lvl1"
STUDY_NORM_L2_KEY = "study_norm_lvl2"
STUDY_NORM_L3_KEY = "study_norm_lvl3"
MIN_STUDY_NORM = 1
MAX_STUDY_NORM = 100000
DEFAULT_STUDY_NORM_L1 = 500
DEFAULT_STUDY_NORM_L2 = 1000
DEFAULT_STUDY_NORM_L3 = 1500

ANIMAL_BUILD_NORM_KEY = "animal_build_norm"
ANIMAL_PRODUCTION_NORM_KEY = "animal_production_norm"
DEFAULT_ANIMAL_BUILD = 1000
DEFAULT_ANIMAL_PROD = 200

SALE_PRICE_RATIO_KEY = "sale_price_ratio"
DEFAULT_SALE_RATIO = 0.5

DEFAULT_BG_KEY = "default_background_url"


# Нормы для одного кристалла по варианту (из таблиц правил Фермы, слайды 21–22).
# Структура: variant -> {color -> {count -> норма}}.
VARIANT_TABLES: dict[int, dict[str, dict[int, int]]] = {
    1: {
        "green": {1: 10, 2: 20, 3: 30, 4: 40, 5: 50},
        "blue": {1: 20, 2: 40, 3: 60, 4: 80, 5: 100},
        "violet": {1: 30, 2: 60, 3: 90, 4: 120, 5: 150},
    },
    2: {
        "green": {1: 20, 2: 40, 3: 60, 4: 80, 5: 100},
        "blue": {1: 30, 2: 60, 3: 90, 4: 120, 5: 150},
        "violet": {1: 40, 2: 80, 3: 120, 4: 160, 5: 200},
    },
    3: {
        "green": {1: 30, 2: 60, 3: 90, 4: 120, 5: 150},
        "blue": {1: 40, 2: 80, 3: 120, 4: 160, 5: 200},
        "violet": {1: 50, 2: 100, 3: 150, 4: 200, 5: 250},
    },
    4: {
        "green": {1: 40, 2: 80, 3: 120, 4: 160, 5: 200},
        "blue": {1: 50, 2: 100, 3: 150, 4: 200, 5: 250},
        "violet": {1: 60, 2: 120, 3: 180, 4: 240, 5: 300},
    },
    5: {
        "green": {1: 50, 2: 100, 3: 150, 4: 200, 5: 250},
        "blue": {1: 60, 2: 120, 3: 180, 4: 240, 5: 300},
        "violet": {1: 70, 2: 140, 3: 210, 4: 280, 5: 350},
    },
    6: {
        "green": {1: 60, 2: 120, 3: 180, 4: 240, 5: 300},
        "blue": {1: 70, 2: 140, 3: 210, 4: 280, 5: 350},
        "violet": {1: 80, 2: 160, 3: 240, 4: 320, 5: 400},
    },
    7: {
        "green": {1: 70, 2: 140, 3: 180, 4: 280, 5: 350},
        "blue": {1: 80, 2: 160, 3: 240, 4: 320, 5: 400},
        "violet": {1: 90, 2: 180, 3: 270, 4: 360, 5: 450},
    },
    8: {
        "green": {1: 80, 2: 160, 3: 240, 4: 320, 5: 400},
        "blue": {1: 90, 2: 180, 3: 270, 4: 360, 5: 450},
        "violet": {1: 100, 2: 200, 3: 300, 4: 400, 5: 500},
    },
}

CRYSTAL_COLORS = ("green", "blue", "violet")
CRYSTAL_COUNTS = (0, 1, 2, 3, 4, 5)
CRYSTAL_COUNT_LABELS = {0: "💎", 1: "×1", 2: "×2", 3: "×3", 4: "×4", 5: "×5"}


# Стандарт норм кристаллов, задаваемый админом (JSON в настройке crystal_standard).
# Структура: {color -> {count -> норма за 1 кристалл}}. Фолбэк — пресет 1.
CRYSTAL_STANDARD_KEY = "crystal_standard"


def _preset_to_norms(variant: int) -> dict[str, dict[int, int]]:
    table = VARIANT_TABLES.get(variant, VARIANT_TABLES[DEFAULT_VARIANT])
    return {color: {cnt: val for cnt, val in per_color.items()} for color, per_color in table.items()}


def _default_standard() -> dict[str, dict[int, int]]:
    norms = _preset_to_norms(DEFAULT_VARIANT)
    for color in CRYSTAL_COLORS:
        if 0 not in norms[color]:
            norms[color][0] = 0
    return norms


def get_crystal_standard(db: Session) -> dict[str, dict[int, int]]:
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
        result[color] = {}
        for cnt in CRYSTAL_COUNTS:
            val = per_color.get(str(cnt), per_color.get(cnt))
            if cnt == 0:
                if val is None:
                    result[color][0] = 0
                else:
                    result[color][0] = int(val) if isinstance(val, (int, str)) and str(val).lstrip("-").isdigit() else 0
                continue
            if not isinstance(val, int) or val < 1:
                return _default_standard()
            result[color][cnt] = val
    return result


def set_crystal_standard(db: Session, norms: dict[str, dict[int, int]]) -> None:
    serializable = {}
    for color, per_color in norms.items():
        serializable[color] = {}
        for cnt, val in per_color.items():
            serializable[color][str(cnt)] = int(val)
    s = db.query(Setting).filter(Setting.key == CRYSTAL_STANDARD_KEY).first()
    if s is None:
        s = Setting(key=CRYSTAL_STANDARD_KEY, value=json.dumps(serializable))
        db.add(s)
    else:
        s.value = json.dumps(serializable)


def get_crystal_rate_variant(db: Session) -> int:
    s = db.query(Setting).filter(Setting.key == CRYSTAL_RATE_VARIANT_KEY).first()
    if s is None:
        return DEFAULT_VARIANT
    try:
        return max(MIN_VARIANT, min(MAX_VARIANT, int(s.value)))
    except (TypeError, ValueError):
        return DEFAULT_VARIANT


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


_PRODUCTION_NORM_KEYS = {
    1: (PRODUCTION_NORM_L1_KEY, DEFAULT_PROD_NORM_L1),
    2: (PRODUCTION_NORM_L2_KEY, DEFAULT_PROD_NORM_L2),
    3: (PRODUCTION_NORM_L3_KEY, DEFAULT_PROD_NORM_L3),
}


def get_production_norm(db: Session, level: int) -> int:
    key_info = _PRODUCTION_NORM_KEYS.get(level)
    if key_info is None:
        return DEFAULT_PROD_NORM_L1
    key, default = key_info
    s = db.query(Setting).filter(Setting.key == key).first()
    if s is None:
        return default
    try:
        return max(MIN_PROD_NORM, min(MAX_PROD_NORM, int(s.value)))
    except (TypeError, ValueError):
        return default


_STUDY_NORM_KEYS = {
    1: (STUDY_NORM_L1_KEY, DEFAULT_STUDY_NORM_L1),
    2: (STUDY_NORM_L2_KEY, DEFAULT_STUDY_NORM_L2),
    3: (STUDY_NORM_L3_KEY, DEFAULT_STUDY_NORM_L3),
}


def get_study_norm(db: Session, level: int) -> int:
    key_info = _STUDY_NORM_KEYS.get(level)
    if key_info is None:
        return DEFAULT_STUDY_NORM_L1
    key, default = key_info
    s = db.query(Setting).filter(Setting.key == key).first()
    if s is None:
        return default
    try:
        return max(MIN_STUDY_NORM, min(MAX_STUDY_NORM, int(s.value)))
    except (TypeError, ValueError):
        return default


def get_animal_build_norm(db: Session) -> int:
    s = db.query(Setting).filter(Setting.key == ANIMAL_BUILD_NORM_KEY).first()
    if s is None:
        return DEFAULT_ANIMAL_BUILD
    try:
        return max(1, min(100000, int(s.value)))
    except (TypeError, ValueError):
        return DEFAULT_ANIMAL_BUILD


def get_animal_production_norm(db: Session) -> int:
    s = db.query(Setting).filter(Setting.key == ANIMAL_PRODUCTION_NORM_KEY).first()
    if s is None:
        return DEFAULT_ANIMAL_PROD
    try:
        return max(1, min(100000, int(s.value)))
    except (TypeError, ValueError):
        return DEFAULT_ANIMAL_PROD


def get_sale_price_ratio(db: Session) -> float:
    s = db.query(Setting).filter(Setting.key == SALE_PRICE_RATIO_KEY).first()
    if s is None:
        return DEFAULT_SALE_RATIO
    try:
        return max(0.01, min(1.0, float(s.value)))
    except (TypeError, ValueError):
        return DEFAULT_SALE_RATIO


def crystal_norm(db: Session, user: User, color: str, count: int) -> int:
    norm_row = db.query(UserCrystalNorm).filter(
        UserCrystalNorm.user_id == user.vk_id,
        UserCrystalNorm.color == color,
        UserCrystalNorm.count == count,
    ).first()
    if norm_row is not None:
        return norm_row.value * (1 if count == 0 else count)

    standard = get_crystal_standard(db)
    color_table = standard.get(color)
    if color_table is None:
        color_table = _default_standard()[color]
    val = color_table.get(count)
    if val is None:
        val = color_table.get(5, 0)
    return val * (1 if count == 0 else count)


class SettingOut(BaseModel):
    key: str
    value: str


class BackgroundUpdate(BaseModel):
    url: str


@router.get("/settings/background")
def get_background(db: Session = Depends(get_db)):
    s = db.query(Setting).filter(Setting.key == DEFAULT_BG_KEY).first()
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
    CRYSTAL_RATE_VARIANT_KEY: (MIN_VARIANT, MAX_VARIANT, DEFAULT_VARIANT),
    PLANT_QTY_KEY: (MIN_QTY, MAX_QTY, DEFAULT_QTY),
    PRODUCTION_REQUIRED_KEY: (MIN_PROD_REQ, MAX_PROD_REQ, DEFAULT_PROD_REQ),
    ORDER_REWARD_KEY: (MIN_REWARD, MAX_REWARD, DEFAULT_REWARD),
    AUTO_CREDIT_KEY: (0, 1, 1 if DEFAULT_AUTO_CREDIT else 0),
    PRODUCTION_NORM_L1_KEY: (MIN_PROD_NORM, MAX_PROD_NORM, DEFAULT_PROD_NORM_L1),
    PRODUCTION_NORM_L2_KEY: (MIN_PROD_NORM, MAX_PROD_NORM, DEFAULT_PROD_NORM_L2),
    PRODUCTION_NORM_L3_KEY: (MIN_PROD_NORM, MAX_PROD_NORM, DEFAULT_PROD_NORM_L3),
    STUDY_NORM_L1_KEY: (MIN_STUDY_NORM, MAX_STUDY_NORM, DEFAULT_STUDY_NORM_L1),
    STUDY_NORM_L2_KEY: (MIN_STUDY_NORM, MAX_STUDY_NORM, DEFAULT_STUDY_NORM_L2),
    STUDY_NORM_L3_KEY: (MIN_STUDY_NORM, MAX_STUDY_NORM, DEFAULT_STUDY_NORM_L3),
    ANIMAL_BUILD_NORM_KEY: (1, 100000, DEFAULT_ANIMAL_BUILD),
    ANIMAL_PRODUCTION_NORM_KEY: (1, 100000, DEFAULT_ANIMAL_PROD),
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
    if key == CRYSTAL_RATE_VARIANT_KEY:
        return SettingOut(key=key, value=str(get_crystal_rate_variant(db)))
    if key == PLANT_QTY_KEY:
        return SettingOut(key=key, value=str(get_default_plant_qty(db)))
    if key == PRODUCTION_REQUIRED_KEY:
        return SettingOut(key=key, value=str(get_production_required(db)))
    if key == ORDER_REWARD_KEY:
        return SettingOut(key=key, value=str(get_order_reward(db)))
    if key == PRODUCTION_NORM_L1_KEY:
        return SettingOut(key=key, value=str(get_production_norm(db, 1)))
    if key == PRODUCTION_NORM_L2_KEY:
        return SettingOut(key=key, value=str(get_production_norm(db, 2)))
    if key == PRODUCTION_NORM_L3_KEY:
        return SettingOut(key=key, value=str(get_production_norm(db, 3)))
    if key == STUDY_NORM_L1_KEY:
        return SettingOut(key=key, value=str(get_study_norm(db, 1)))
    if key == STUDY_NORM_L2_KEY:
        return SettingOut(key=key, value=str(get_study_norm(db, 2)))
    if key == STUDY_NORM_L3_KEY:
        return SettingOut(key=key, value=str(get_study_norm(db, 3)))
    if key == ANIMAL_PRODUCTION_NORM_KEY:
        return SettingOut(key=key, value=str(get_animal_production_norm(db)))
    if key == SALE_PRICE_RATIO_KEY:
        return SettingOut(key=key, value=str(get_sale_price_ratio(db)))
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
