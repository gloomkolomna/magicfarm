from __future__ import annotations
import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_role
from models import Inventory, OrderReq, Product, User, OrderTemplate
from routes.settings import get_default_plant_qty
from services.achievements import check_and_award
from services.pet_bonuses import apply_pet_bonus_fulfill
from services.uploads import remove_upload, save_upload

router = APIRouter(prefix="/api/orders", tags=["orders"])

CUSTOMER_NAMES = (
    "Леди Бейлин", "Иллюзионист Мерлин", "Крестьянка Бэт", "Крестьянин Том",
    "Травница Свентана", "Профессор Дамболдор", "Волшебница Альвева", "Палач Мор",
    "Ведьма Бригида", "Волшебник Рандольф", "Ученица Гильда", "Профессор Рон",
    "Господин Иоханн", "Поэт Вальтер", "Цветочница Колетта", "Маг Годвин",
    "Ведьма Груда", "Ведьма Доротея", "Водяная Акварис", "Тролль Гослин",
    "Воин Стасий", "Водяной Дионисий", "Болотная Иса", "Прокажённый Гус",
    "Хамон", "Разбойница Томасина", "Эльф Эверард", "Бусли",
    "Разбойник Гольём", "Библиотекарь Летард", "Книжница Элоиза", "Циркач Белкс",
    "Старец Эдрик", "Изобретатель Нигель", "Розамунда", "Гуннильда",
    "Фей Алан", "Прометеус", "Гном Дремотун", "Гном Гром",
    "Гном Плясун", "Султан Арагим", "Султан Эфиос", "Красавица Ева",
    "Художница Стефания", "Сэр Аорон", "Фея Аврора", "Король Артур",
    "Оборотень Рандус", "Старец Симонус", "Эльф Анарендил", "Эльфийка Хиварра",
    "Эльф Фараун", "Астроном Сириус", "Русалка Марин", "Профессор Сусанна",
    "Гадалка Сванекильда", "Ученица Холли", "Русалка Оресия", "Русалка Эделина",
    "Профессор Гилотта", "Иллюзионист Сфериус", "Волшебница Идонея", "Учёный Томас",
    "Профессор Кларисса", "Оборотень Уолк", "Мышиный воин Осборт", "Ледяная Сванекильда",
)

MIN_QTY = 1
MAX_QTY = 20


def _get_order_or_404(order_id: int, db: Session) -> OrderReq:
    o = db.query(OrderReq).filter(OrderReq.id == order_id).first()
    if o is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")
    return o


def _get_user_order(order_id: int, user: User, db: Session) -> OrderReq:
    o = _get_order_or_404(order_id, db)
    if o.user_id != user.vk_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваш заказ")
    return o


def _calc_order_reward(db: Session, product: Product, qty: int) -> int:
    from services.pricing import calculate_product_price
    from models import Plant

    plant_level = 1
    if product.plant_id is not None:
        plant = db.query(Plant).filter(Plant.id == product.plant_id).first()
        if plant is not None:
            plant_level = plant.level
    prod_kind = product.production_kind or "alchemy"
    return calculate_product_price(plant_level, prod_kind, qty, db)


class OrderOut(BaseModel):
    id: int
    product_id: int
    product_code: str
    product_name: str
    product_emoji: str | None
    qty: int
    reward_coins: int
    customer: str | None
    status: str
    name: str | None = None
    image_url: str | None = None
    created_at: datetime.datetime | None
    fulfilled_at: datetime.datetime | None


def _to_out(o: OrderReq) -> OrderOut:
    return OrderOut(
        id=o.id, product_id=o.product_id, product_code=o.product.code,
        product_name=o.product.name, product_emoji=o.product.emoji,
        qty=o.qty, reward_coins=o.reward_coins,
        customer=o.customer,
        status=o.status, name=o.name, image_url=o.image_url,
        created_at=o.created_at, fulfilled_at=o.fulfilled_at,
    )


@router.get("/customers", response_model=list[str])
def list_customer_names(
    user: User = Depends(get_current_user),
):
    return list(CUSTOMER_NAMES)


@router.get("", response_model=list[OrderOut])
def list_orders(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(OrderReq).filter(OrderReq.user_id == user.vk_id)
    if status_filter is not None:
        q = q.filter(OrderReq.status == status_filter)
    rows = q.order_by(OrderReq.created_at.desc()).limit(200).all()
    return [_to_out(o) for o in rows]


@router.get("/available", response_model=list[OrderOut])
def list_available_orders(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(OrderReq).filter(
        OrderReq.user_id == None, OrderReq.status == "open"
    ).order_by(OrderReq.created_at.desc()).limit(200).all()
    return [_to_out(o) for o in rows]


@router.post("/{order_id}/take", response_model=OrderOut)
def take_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    o = _get_order_or_404(order_id, db)
    if o.user_id is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Заказ уже взят")
    if o.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Заказ уже выполнен или отменён")
    o.user_id = user.vk_id
    db.commit()
    db.refresh(o)
    return _to_out(o)


class GenerateRequest(BaseModel):
    product_id: int
    qty: int | None = None
    customer: str | None = None


@router.post("/generate", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def generate_order(
    req: GenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Создаёт NPC-заказ для игрока.

    В правилах Фермы заказ приходит из игры (карточка). В цифре заказ генерируется
    по запросу: заказчик выбирается из списка, награда = цена товара
    (база уровня растения + надбавка шатра) × qty.
    """
    product = db.query(Product).filter(Product.id == req.product_id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")
    qty = req.qty if req.qty is not None else get_default_plant_qty(db)
    if qty < MIN_QTY or qty > MAX_QTY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Количество должно быть от {MIN_QTY} до {MAX_QTY}",
        )

    reward = _calc_order_reward(db, product, qty)
    o = OrderReq(
        user_id=user.vk_id, product_id=product.id, qty=qty,
        reward_coins=reward, customer=req.customer,
        status="open",
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return _to_out(o)


@router.post("/{order_id}/image", response_model=OrderOut)
def upload_own_order_image(
    order_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    o = _get_user_order(order_id, user, db)
    remove_upload(o.image_url)
    o.image_url = save_upload(image, f"order_{order_id}", max_size=800)
    db.commit()
    db.refresh(o)
    return _to_out(o)


@router.post("/{order_id}/fulfill", response_model=OrderOut)
def fulfill_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    o = _get_user_order(order_id, user, db)
    if o.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Заказ уже выполнен или отменён")

    inv = db.query(Inventory).filter(
        Inventory.user_id == user.vk_id, Inventory.product_id == o.product_id
    ).first()
    if inv is None or (inv.qty or 0) < o.qty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недостаточно товара на складе",
        )

    u = db.query(User).filter(User.vk_id == user.vk_id).first()
    inv.qty = (inv.qty or 0) - o.qty
    u.coins = (u.coins or 0) + o.reward_coins

    bonus = apply_pet_bonus_fulfill(user.vk_id, db)
    if bonus > 0:
        u.coins = (u.coins or 0) + bonus

    o.status = "fulfilled"
    o.fulfilled_at = datetime.datetime.utcnow()

    db.commit()
    db.refresh(o)

    check_and_award(user.vk_id, "first_order", db)
    check_and_award(user.vk_id, "coins_reached", db)

    from services.leveling import check_level_up
    check_level_up(db, u)

    return _to_out(o)


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    o = _get_user_order(order_id, user, db)
    if o.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Заказ уже выполнен или отменён")
    o.status = "cancelled"
    db.commit()
    db.refresh(o)
    return _to_out(o)


# ── Admin ──

admin_router = APIRouter(prefix="/api/admin/orders", tags=["admin-orders"])

class AdminOrderOut(OrderOut):
    user_id: int | None = None

def _admin_to_out(o: OrderReq) -> AdminOrderOut:
    d = _to_out(o).model_dump()
    d["user_id"] = o.user_id
    return AdminOrderOut(**d)

@admin_router.get("", response_model=list[AdminOrderOut])
def admin_list_orders(
    user_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    q = db.query(OrderReq).order_by(OrderReq.id.desc())
    if user_id is not None:
        q = q.filter(OrderReq.user_id == user_id)
    return [_admin_to_out(o) for o in q.limit(200).all()]

class AdminGenerateRequest(BaseModel):
    product_id: int
    qty: int | None = None
    customer: str | None = None


@admin_router.post("/generate", response_model=AdminOrderOut, status_code=status.HTTP_201_CREATED)
def admin_generate_order(
    req: AdminGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    product = db.query(Product).filter(Product.id == req.product_id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")
    qty = req.qty if req.qty is not None else get_default_plant_qty(db)
    if qty < MIN_QTY or qty > MAX_QTY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Количество должно быть от {MIN_QTY} до {MAX_QTY}",
        )
    reward = _calc_order_reward(db, product, qty)
    customer = req.customer
    o = OrderReq(
        user_id=None, product_id=product.id, qty=qty,
        reward_coins=reward, customer=customer,
        status="open",
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return _admin_to_out(o)


class AdminUpdateOrder(BaseModel):
    product_id: int | None = None
    qty: int | None = None
    reward_coins: int | None = None
    customer: str | None = None
    status: str | None = None
    name: str | None = None


@admin_router.put("/{order_id}", response_model=AdminOrderOut)
def admin_update_order(
    order_id: int,
    data: AdminUpdateOrder,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    o = _get_order_or_404(order_id, db)
    if data.product_id is not None:
        o.product_id = data.product_id
    if data.qty is not None:
        if data.qty < MIN_QTY or data.qty > MAX_QTY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Количество должно быть от {MIN_QTY} до {MAX_QTY}",
            )
        o.qty = data.qty
    if data.reward_coins is not None:
        o.reward_coins = data.reward_coins
    if data.customer is not None:
        o.customer = data.customer
    if data.status is not None:
        if data.status not in ("open", "fulfilled", "cancelled"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Статус должен быть open, fulfilled или cancelled",
            )
        o.status = data.status
        if data.status == "fulfilled" and o.fulfilled_at is None:
            o.fulfilled_at = datetime.datetime.utcnow()
    if data.name is not None:
        o.name = data.name
    db.commit()
    db.refresh(o)
    return _admin_to_out(o)


@admin_router.post("/{order_id}/cancel", response_model=AdminOrderOut)
def admin_cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    o = _get_order_or_404(order_id, db)
    if o.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Заказ уже выполнен или отменён")
    o.status = "cancelled"
    db.commit()
    db.refresh(o)
    return _admin_to_out(o)


@admin_router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    o = _get_order_or_404(order_id, db)
    db.delete(o)
    db.commit()
    return None


@admin_router.put("/{order_id}/image", response_model=AdminOrderOut)
def upload_order_image(
    order_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    o = _get_order_or_404(order_id, db)
    remove_upload(o.image_url)
    o.image_url = save_upload(image, f"order_{order_id}", max_size=800)
    db.commit()
    db.refresh(o)
    return _admin_to_out(o)


# ── Order Templates (admin) ──

template_router = APIRouter(prefix="/api/admin/order-templates", tags=["admin-order-templates"])


class OrderTemplateOut(BaseModel):
    id: int
    source_kind: str
    source_id: int
    product_id: int
    qty: int
    reward_coins: int
    customer: str | None
    name: str | None
    image_url: str | None


def _tpl_out(t: OrderTemplate) -> OrderTemplateOut:
    return OrderTemplateOut(
        id=t.id, source_kind=t.source_kind, source_id=t.source_id,
        product_id=t.product_id, qty=t.qty, reward_coins=t.reward_coins,
        customer=t.customer, name=t.name, image_url=t.image_url,
    )


class OrderTemplateCreate(BaseModel):
    source_kind: str
    source_id: int
    product_id: int
    qty: int
    reward_coins: int = 0
    customer: str | None = None
    name: str | None = None


@template_router.get("", response_model=list[OrderTemplateOut])
def list_templates(
    source_kind: str | None = None,
    source_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    q = db.query(OrderTemplate).order_by(OrderTemplate.id.asc())
    if source_kind is not None:
        q = q.filter(OrderTemplate.source_kind == source_kind)
    if source_id is not None:
        q = q.filter(OrderTemplate.source_id == source_id)
    return [_tpl_out(t) for t in q.limit(200).all()]


@template_router.post("", response_model=OrderTemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    req: OrderTemplateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if req.source_kind not in ("plant", "animal", "product", "potion"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source_kind: plant/animal/product/potion")
    if req.qty < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="qty >= 1")
    product = db.query(Product).filter(Product.id == req.product_id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")
    t = OrderTemplate(
        source_kind=req.source_kind, source_id=req.source_id,
        product_id=req.product_id, qty=req.qty, reward_coins=req.reward_coins,
        customer=req.customer, name=req.name,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _tpl_out(t)


@template_router.put("/{template_id}", response_model=OrderTemplateOut)
def update_template(
    template_id: int,
    req: OrderTemplateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    t = db.query(OrderTemplate).filter(OrderTemplate.id == template_id).first()
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаблон не найден")
    if req.source_kind not in ("plant", "animal", "product", "potion"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source_kind: plant/animal/product/potion")
    if req.qty < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="qty >= 1")
    t.source_kind = req.source_kind
    t.source_id = req.source_id
    t.product_id = req.product_id
    t.qty = req.qty
    t.reward_coins = req.reward_coins
    t.customer = req.customer
    t.name = req.name
    db.commit()
    db.refresh(t)
    return _tpl_out(t)


@template_router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    t = db.query(OrderTemplate).filter(OrderTemplate.id == template_id).first()
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаблон не найден")
    db.delete(t)
    db.commit()
    return None


@template_router.put("/{template_id}/image", response_model=OrderTemplateOut)
def upload_template_image(
    template_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    t = db.query(OrderTemplate).filter(OrderTemplate.id == template_id).first()
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаблон не найден")
    remove_upload(t.image_url)
    t.image_url = save_upload(image, f"order_template_{template_id}", max_size=800)
    db.commit()
    db.refresh(t)
    return _tpl_out(t)
