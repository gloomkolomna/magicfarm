from __future__ import annotations
import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_role
from models import Customer, Inventory, OrderReq, Product, User
from routes.settings import get_default_plant_qty
from services.achievements import check_and_award
from services.availability import has_installed_kassa
from services.pet_bonuses import apply_pet_bonus_fulfill
from services.potion_bonuses import consume_potion, is_potion_active
from services.uploads import remove_upload, save_upload

router = APIRouter(prefix="/api/orders", tags=["orders"])

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


def _order_lock_reason(o: OrderReq, user: User, db: Session) -> str | None:
    from services.availability import product_lock_reason

    return product_lock_reason(o.product, user, db)


class OrderOut(BaseModel):
    id: int
    product_id: int | None
    product_code: str
    product_name: str
    product_emoji: str | None
    product_image_url: str | None = None
    potion_recipe_id: int | None = None
    potion_name: str | None = None
    potion_image_url: str | None = None
    qty: int
    reward_coins: int
    customer: str | None
    customer_phrase: str | None = None
    customer_image_url: str | None = None
    status: str
    name: str | None = None
    image_url: str | None = None
    created_at: datetime.datetime | None
    fulfilled_at: datetime.datetime | None
    available: bool = True
    lock_reason: str | None = None


def _customer_images(db: Session) -> dict[str, str]:
    rows = db.query(Customer).filter(Customer.image_url.isnot(None)).all()
    return {c.name: c.image_url for c in rows}


def _to_out(o: OrderReq, customer_images: dict[str, str] | None = None, lock_reason: str | None = None) -> OrderOut:
    if o.product is not None:
        product_code = o.product.code
        product_name = o.product.name
        product_emoji = o.product.emoji
        product_image_url = o.product.image_url
    else:
        product_code = ""
        product_name = o.potion_recipe.name if o.potion_recipe else "Зелье"
        product_emoji = "🧪"
        product_image_url = None
    return OrderOut(
        id=o.id, product_id=o.product_id, product_code=product_code,
        product_name=product_name, product_emoji=product_emoji,
        product_image_url=product_image_url,
        potion_recipe_id=o.potion_recipe_id,
        potion_name=o.potion_recipe.name if o.potion_recipe else None,
        potion_image_url=(o.potion_recipe.image_url if o.potion_recipe else None),
        qty=o.qty, reward_coins=o.reward_coins,
        customer=o.customer,
        customer_phrase=o.customer_phrase,
        customer_image_url=(customer_images or {}).get(o.customer) if o.customer else None,
        status=o.status, name=o.name, image_url=o.image_url,
        created_at=o.created_at, fulfilled_at=o.fulfilled_at,
        available=lock_reason is None, lock_reason=lock_reason,
    )


@router.get("/customers", response_model=list[str])
def list_customer_names(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return [c.name for c in db.query(Customer).order_by(Customer.id.asc()).all()]


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
    imgs = _customer_images(db)
    return [_to_out(o, imgs) for o in rows]


@router.get("/available", response_model=list[OrderOut])
def list_available_orders(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not has_installed_kassa(user, db):
        return []
    rows = db.query(OrderReq).filter(
        OrderReq.user_id == None, OrderReq.status == "open",
        (OrderReq.fulfilled_by == None) | (OrderReq.fulfilled_by != user.vk_id),
    ).order_by(OrderReq.created_at.desc()).limit(200).all()
    imgs = _customer_images(db)
    visible = [o for o in rows if _order_lock_reason(o, user, db) is None]
    return [_to_out(o, imgs) for o in visible]


@router.post("/{order_id}/take", response_model=OrderOut)
def take_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not has_installed_kassa(user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Установите шатёр-кассу, чтобы брать заказы",
        )
    o = _get_order_or_404(order_id, db)
    if o.fulfilled_by == user.vk_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Вы уже выполняли этот заказ")
    if o.user_id is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Заказ уже взят")
    if o.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Заказ уже выполнен или отменён")
    lock_reason = _order_lock_reason(o, user, db)
    if lock_reason is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=lock_reason)
    o.user_id = user.vk_id
    db.commit()
    db.refresh(o)
    return _to_out(o, _customer_images(db))


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
    if not has_installed_kassa(user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Установите шатёр-кассу, чтобы брать заказы",
        )
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
    return _to_out(o, _customer_images(db))


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
    return _to_out(o, _customer_images(db))


@router.post("/{order_id}/fulfill", response_model=OrderOut)
def fulfill_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    o = _get_user_order(order_id, user, db)
    if o.fulfilled_by == user.vk_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Вы уже выполняли этот заказ")
    if o.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Заказ уже выполнен или отменён")

    double_reward = is_potion_active(user.vk_id, "double_order_reward", db)

    if o.potion_recipe_id is not None:
        from models import UserPotion
        up = db.query(UserPotion).filter(
            UserPotion.user_id == user.vk_id,
            UserPotion.potion_recipe_id == o.potion_recipe_id,
            UserPotion.used.is_(False),
        ).first()
        if up is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нет такого зелья — сварите его в котле",
            )
        up.used = True

        u = db.query(User).filter(User.vk_id == user.vk_id).first()
        reward = o.reward_coins * 2 if double_reward else o.reward_coins
        u.coins = (u.coins or 0) + reward

        bonus = apply_pet_bonus_fulfill(user.vk_id, db)
        if bonus > 0:
            u.coins = (u.coins or 0) + bonus

        if double_reward:
            consume_potion(user.vk_id, "double_order_reward", db)

        o.status = "fulfilled"
        o.fulfilled_by = user.vk_id
        o.fulfilled_at = datetime.datetime.utcnow()

        db.commit()
        db.refresh(o)

        check_and_award(user.vk_id, "first_order", db)
        check_and_award(user.vk_id, "coins_reached", db)

        from services.leveling import check_level_up
        check_level_up(db, u)

        return _to_out(o, _customer_images(db))

    inv = db.query(Inventory).filter(
        Inventory.user_id == user.vk_id, Inventory.product_id == o.product_id
    ).first()

    partial = is_potion_active(user.vk_id, "partial_order", db)

    if partial:
        if inv is None or (inv.qty or 0) < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недостаточно товара на складе",
            )
        spent = min(inv.qty or 0, o.qty)
    else:
        if inv is None or (inv.qty or 0) < o.qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недостаточно товара на складе",
            )
        spent = o.qty

    u = db.query(User).filter(User.vk_id == user.vk_id).first()
    inv.qty = (inv.qty or 0) - spent
    reward = o.reward_coins * 2 if double_reward else o.reward_coins
    u.coins = (u.coins or 0) + reward

    bonus = apply_pet_bonus_fulfill(user.vk_id, db)
    if bonus > 0:
        u.coins = (u.coins or 0) + bonus

    if partial:
        consume_potion(user.vk_id, "partial_order", db)
    if double_reward:
        consume_potion(user.vk_id, "double_order_reward", db)

    o.status = "fulfilled"
    o.fulfilled_by = user.vk_id
    o.fulfilled_at = datetime.datetime.utcnow()

    db.commit()
    db.refresh(o)

    check_and_award(user.vk_id, "first_order", db)
    check_and_award(user.vk_id, "coins_reached", db)

    from services.leveling import check_level_up
    check_level_up(db, u)

    return _to_out(o, _customer_images(db))


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    o = _get_user_order(order_id, user, db)
    if o.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Заказ уже выполнен или отменён")
    o.user_id = None
    db.commit()
    db.refresh(o)
    return _to_out(o, _customer_images(db))


# ── Admin ──

admin_router = APIRouter(prefix="/api/admin/orders", tags=["admin-orders"])

class AdminOrderOut(OrderOut):
    user_id: int | None = None

def _admin_to_out(o: OrderReq, customer_images: dict[str, str] | None = None) -> AdminOrderOut:
    d = _to_out(o, customer_images).model_dump()
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
    imgs = _customer_images(db)
    return [_admin_to_out(o, imgs) for o in q.limit(200).all()]

class AdminGenerateRequest(BaseModel):
    product_id: int | None = None
    potion_recipe_id: int | None = None
    qty: int | None = None
    customer: str | None = None
    customer_phrase: str | None = None


@admin_router.post("/generate", response_model=AdminOrderOut, status_code=status.HTTP_201_CREATED)
def admin_generate_order(
    req: AdminGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if (req.product_id is None) == (req.potion_recipe_id is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите либо product_id, либо potion_recipe_id (ровно одно)",
        )
    if req.potion_recipe_id is not None:
        from models import PotionRecipe
        recipe = db.query(PotionRecipe).filter(PotionRecipe.id == req.potion_recipe_id).first()
        if recipe is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рецепт зелья не найден")
        o = OrderReq(
            user_id=None, product_id=None, potion_recipe_id=recipe.id, qty=1,
            reward_coins=recipe.reward_coins, customer=req.customer,
            customer_phrase=req.customer_phrase,
            status="open",
        )
        db.add(o)
        db.commit()
        db.refresh(o)
        return _admin_to_out(o, _customer_images(db))

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
        customer_phrase=req.customer_phrase,
        status="open",
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return _admin_to_out(o, _customer_images(db))


class AdminUpdateOrder(BaseModel):
    product_id: int | None = None
    qty: int | None = None
    reward_coins: int | None = None
    customer: str | None = None
    customer_phrase: str | None = None
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
        if o.potion_recipe_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Это заказ на зелье — сменить на товар нельзя",
            )
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
    if data.customer_phrase is not None:
        o.customer_phrase = data.customer_phrase or None
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
    return _admin_to_out(o, _customer_images(db))


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
    return _admin_to_out(o, _customer_images(db))


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
    return _admin_to_out(o, _customer_images(db))


# ── Customers (admin) ──

customer_router = APIRouter(prefix="/api/admin/customers", tags=["admin-customers"])


class CustomerOut(BaseModel):
    id: int
    name: str
    image_url: str | None
    open_orders_count: int = 0


def _customer_out(c: Customer, open_orders_count: int = 0) -> CustomerOut:
    return CustomerOut(id=c.id, name=c.name, image_url=c.image_url, open_orders_count=open_orders_count)


class CustomerCreate(BaseModel):
    name: str


def _get_customer_or_404(customer_id: int, db: Session) -> Customer:
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказчик не найден")
    return c


def _ensure_name_free(name: str, db: Session, exclude_id: int | None = None):
    q = db.query(Customer).filter(Customer.name == name)
    if exclude_id is not None:
        q = q.filter(Customer.id != exclude_id)
    if q.first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Заказчик с таким именем уже есть")


@customer_router.get("", response_model=list[CustomerOut])
def list_customers(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    counts = dict(
        db.query(OrderReq.customer, func.count(OrderReq.id))
        .filter(OrderReq.status == "open", OrderReq.customer.isnot(None))
        .group_by(OrderReq.customer)
        .all()
    )
    return [
        _customer_out(c, counts.get(c.name, 0))
        for c in db.query(Customer).order_by(Customer.id.asc()).all()
    ]


@customer_router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    req: CustomerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Имя не может быть пустым")
    _ensure_name_free(name, db)
    c = Customer(name=name)
    db.add(c)
    db.commit()
    db.refresh(c)
    return _customer_out(c)


@customer_router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int,
    req: CustomerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    c = _get_customer_or_404(customer_id, db)
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Имя не может быть пустым")
    _ensure_name_free(name, db, exclude_id=c.id)
    c.name = name
    db.commit()
    db.refresh(c)
    return _customer_out(c)


@customer_router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    c = _get_customer_or_404(customer_id, db)
    remove_upload(c.image_url)
    db.delete(c)
    db.commit()
    return None


@customer_router.put("/{customer_id}/image", response_model=CustomerOut)
def upload_customer_image(
    customer_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    c = _get_customer_or_404(customer_id, db)
    remove_upload(c.image_url)
    c.image_url = save_upload(image, f"customer_{customer_id}", max_size=400)
    db.commit()
    db.refresh(c)
    return _customer_out(c)
