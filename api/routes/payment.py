from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

import config
from db import get_db
from deps import get_current_user, require_role
from models import LOCATION_NAMES, PaymentLog, PaymentOrder, User
from services.subscription import (
    PERIOD_DAYS,
    apply_dlc_topup,
    dlc_catalog,
    days_left,
    extend_subscription,
    get_base_price_rub,
    is_subscription_active,
    parse_dlc_codes,
    price_rub_for,
    topup_price_rub,
)

router = APIRouter(prefix="/api/payment", tags=["payment"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin-payment"])
public_router = APIRouter(prefix="/api/public", tags=["public"])

PENDING_TTL = datetime.timedelta(hours=1)
LAZY_POLL_AFTER = datetime.timedelta(seconds=45)


def _log(vk_id, order_id, action, detail="", txn_id="", db: Session = None) -> None:
    try:
        own = db is None
        if own:
            from db import SessionLocal
            db = SessionLocal()
        db.add(PaymentLog(vk_id=vk_id, order_id=order_id, txn_id=txn_id,
                          action=action, detail=str(detail)[:2000]))
        db.commit()
    except Exception:
        pass


def _order_description(dlc_codes: list[str], kind: str = "subscription") -> str:
    names = [LOCATION_NAMES.get(c, c) for c in dlc_codes]
    if kind == "dlc_topup":
        return "Дополнение подписки «Ферма»: " + ", ".join(names)
    parts = ["Подписка «Ферма» 30 дней"]
    if names:
        parts.append(" + " + ", ".join(names))
    return "".join(parts)


EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class CreateOrderRequest(BaseModel):
    dlc_codes: list[str] = []
    receipt_email: str


class CreateOrderResponse(BaseModel):
    order_id: int
    transaction_id: str
    payment_url: str
    amount_kop: int
    amount_rub: int
    period_days: int
    kind: str
    dlc_codes: list[str]


class OrderStatusResponse(BaseModel):
    id: int
    status: str
    amount_kop: int
    period_days: int
    kind: str
    dlc_codes: list[str]
    created_at: str


class PriceDlcItem(BaseModel):
    code: str
    name: str
    price_rub: int
    topup_rub: int | None = None


class PriceResponse(BaseModel):
    period_days: int
    base_rub: int
    dlc: list[PriceDlcItem]
    topup_days_left: int | None = None


def _cancel_expired_pending(db: Session, vk_id: int) -> None:
    now = datetime.datetime.utcnow()
    stale = (
        db.query(PaymentOrder)
        .filter(
            PaymentOrder.vk_id == vk_id,
            PaymentOrder.status == "pending",
            PaymentOrder.created_at <= now - PENDING_TTL,
        )
        .all()
    )
    for o in stale:
        o.status = "cancelled"
    if stale:
        db.commit()


def _validate_dlc_codes(codes: list[str]) -> list[str]:
    from models import LOCATION_CODES

    valid = list(dict.fromkeys(codes))
    unknown = [c for c in valid if c not in LOCATION_CODES]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неизвестные ДЛС: {', '.join(unknown)}",
        )
    return valid


@router.get("/price", response_model=PriceResponse)
def get_price(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    topup_days = None
    current: set[str] = set()
    if is_subscription_active(user):
        topup_days = days_left(user.subscription_until)
        current = set(parse_dlc_codes(user.subscription_dlc_codes))
    items = []
    for d in dlc_catalog(db):
        topup_rub = None
        if topup_days is not None and d["code"] not in current:
            topup_rub = topup_price_rub(db, [d["code"]], topup_days)
        items.append(PriceDlcItem(**d, topup_rub=topup_rub))
    return PriceResponse(
        period_days=PERIOD_DAYS,
        base_rub=get_base_price_rub(db),
        dlc=items,
        topup_days_left=topup_days,
    )


@public_router.get("/pricing", response_model=PriceResponse)
def public_pricing(db: Session = Depends(get_db)):
    return PriceResponse(
        period_days=PERIOD_DAYS,
        base_rub=get_base_price_rub(db),
        dlc=[PriceDlcItem(**d) for d in dlc_catalog(db)],
    )


@router.post("/create-order", response_model=CreateOrderResponse)
def create_subscription_order(
    req: CreateOrderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from routes.settings import get_game_open

    if get_game_open(db):
        from services.donor import can_renew_subscription

        if not can_renew_subscription(db, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Продление доступно только действующим донам группы «Крестики от Корги»",
            )

    if not config.PAY_GATEWAY_ENABLED:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Оплата не настроена")

    dlc_codes = _validate_dlc_codes(req.dlc_codes or [])
    email = (req.receipt_email or "").strip().lower()
    if not EMAIL_RE.fullmatch(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите корректный email — на него придёт электронный чек",
        )

    kind = "subscription"
    amount_rub = price_rub_for(db, dlc_codes)
    period_days = PERIOD_DAYS

    if is_subscription_active(user):
        current = set(parse_dlc_codes(user.subscription_dlc_codes))
        requested = set(dlc_codes)
        if requested != current:
            if not requested.issuperset(current):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="До конца текущего периода состав можно только дополнять ДЛС. Полная стоимость — со следующего платежа",
                )
            new_codes = [c for c in dlc_codes if c not in current]
            period_days = days_left(user.subscription_until)
            amount_rub = topup_price_rub(db, new_codes, period_days)
            kind = "dlc_topup"
            dlc_codes = new_codes

    amount_kop = amount_rub * 100

    _cancel_expired_pending(db, user.vk_id)

    order = PaymentOrder(
        vk_id=user.vk_id,
        amount_kop=amount_kop,
        period_days=period_days,
        dlc_codes=",".join(dlc_codes),
        kind=kind,
        status="pending",
        receipt_email=email,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    from services.pay_gateway_client import create_order as gateway_create_order
    from services.pay_gateway_client import PayGatewayBlocked, PayGatewayError

    try:
        info = gateway_create_order(
            vk_id=user.vk_id,
            amount_kop=amount_kop,
            description=_order_description(dlc_codes, kind),
            receipt_email=order.receipt_email,
        )
    except PayGatewayBlocked:
        order.status = "cancelled"
        db.commit()
        _log(user.vk_id, order.id, "gateway_test_blocked", "", db=db)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Оплата временно недоступна")
    except PayGatewayError as exc:
        order.status = "fail"
        db.commit()
        _log(user.vk_id, order.id, "gateway_error", str(exc), db=db)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Платёжный шлюз недоступен")

    order.gateway_txn_id = str(info.get("transaction_id") or "")
    db.commit()
    _log(user.vk_id, order.id, "order_created",
         f"amount_kop={amount_kop} dlc={order.dlc_codes}", txn_id=order.gateway_txn_id, db=db)

    return CreateOrderResponse(
        order_id=order.id,
        transaction_id=order.gateway_txn_id,
        payment_url=info.get("payment_url") or "",
        amount_kop=amount_kop,
        amount_rub=amount_rub,
        period_days=period_days,
        kind=kind,
        dlc_codes=dlc_codes,
    )


def _claim_success(db: Session, order: PaymentOrder) -> bool:
    updated = (
        db.query(PaymentOrder)
        .filter(PaymentOrder.id == order.id, PaymentOrder.status.in_(("pending", "cancelled")))
        .update({"status": "success", "completed_at": datetime.datetime.utcnow()},
                synchronize_session=False)
    )
    db.commit()
    if updated:
        db.refresh(order)
    return bool(updated)


def _fulfill(db: Session, order: PaymentOrder, source: str, operation_id: str = "") -> None:
    user = db.query(User).filter(User.vk_id == order.vk_id).first()
    action = "subscription_extended"
    if user is not None:
        if order.kind == "dlc_topup":
            apply_dlc_topup(db, user, parse_dlc_codes(order.dlc_codes))
            action = "dlc_topup_applied"
        else:
            extend_subscription(db, user, order.period_days, parse_dlc_codes(order.dlc_codes))
    _log(order.vk_id, order.id, f"{action}_{source}",
         f"kind={order.kind} days={order.period_days} dlc={order.dlc_codes} moneta_operation_id={operation_id}",
         txn_id=order.gateway_txn_id or "", db=db)


@router.get("/orders/{order_id}", response_model=OrderStatusResponse)
def get_order_status(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = db.query(PaymentOrder).filter(PaymentOrder.id == order_id).first()
    if order is None or order.vk_id != user.vk_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")

    if (
        order.status == "pending"
        and order.gateway_txn_id
        and order.created_at <= datetime.datetime.utcnow() - LAZY_POLL_AFTER
        and config.PAY_GATEWAY_ENABLED
    ):
        from services.pay_gateway_client import get_order as gateway_get_order
        from services.pay_gateway_client import PayGatewayError

        try:
            info = gateway_get_order(order.gateway_txn_id)
            if info.get("status") == "success" and int(info.get("amount_kop") or -1) == order.amount_kop:
                if _claim_success(db, order):
                    _fulfill(db, order, "lazy_poll")
            elif info.get("status") in ("cancelled", "failed"):
                order.status = info.get("status")
                db.commit()
        except PayGatewayError as exc:
            _log(order.vk_id, order.id, "lazy_poll_error", str(exc), txn_id=order.gateway_txn_id or "", db=db)

    return OrderStatusResponse(
        id=order.id,
        status=order.status,
        amount_kop=order.amount_kop,
        period_days=order.period_days,
        kind=order.kind,
        dlc_codes=parse_dlc_codes(order.dlc_codes),
        created_at=order.created_at.isoformat(),
    )


def _verify_webhook_signature(body: bytes, signature: str) -> bool:
    secret = config.PAY_GATEWAY_WEBHOOK_SECRET
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


@router.post("/webhook")
async def payment_webhook(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    signature = request.headers.get("x-pay-signature", "")
    if not config.PAY_GATEWAY_WEBHOOK_SECRET:
        _log(0, 0, "webhook_not_configured", "secret empty", db=db)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="webhook secret not configured")
    if not _verify_webhook_signature(raw, signature):
        _log(0, 0, "webhook_bad_sig", raw[:200].decode("utf-8", "replace"), db=db)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad signature")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad payload")

    txn = str(payload.get("transaction_id") or "")
    game_id = payload.get("game_id")
    vk_id = payload.get("vk_id")
    amount_kop = payload.get("amount_kop")
    if not txn:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing transaction_id")
    if game_id != config.PAY_GATEWAY_GAME_ID:
        _log(0, 0, "webhook_game_mismatch", f"got={game_id}", txn_id=txn, db=db)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="game mismatch")

    order = db.query(PaymentOrder).filter(PaymentOrder.gateway_txn_id == txn).first()
    if order is None:
        _log(0, 0, "webhook_order_not_found", "no local order for txn", txn_id=txn, db=db)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")

    if order.status == "success":
        return {"ok": True}

    try:
        got_vk = int(vk_id)
    except (TypeError, ValueError):
        got_vk = None
    if got_vk is not None and got_vk != order.vk_id:
        _log(order.vk_id, order.id, "webhook_vk_mismatch", f"expected={order.vk_id} got={vk_id}", txn_id=txn, db=db)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="vk_id mismatch")
    try:
        paid = int(amount_kop)
    except (TypeError, ValueError):
        paid = -1
    if paid != order.amount_kop:
        _log(order.vk_id, order.id, "webhook_amount_mismatch",
             f"expected={order.amount_kop} got={amount_kop}", txn_id=txn, db=db)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="amount mismatch")

    if order.status not in ("pending", "cancelled"):
        _log(order.vk_id, order.id, "webhook_skipped", f"local status={order.status}", txn_id=txn, db=db)
        return {"ok": True}

    if not _claim_success(db, order):
        return {"ok": True}

    _fulfill(db, order, "webhook", str(payload.get("moneta_operation_id") or ""))
    return PlainTextResponse("SUCCESS")


class AdminPaymentOrderOut(BaseModel):
    id: int
    vk_id: int
    amount_kop: int
    amount_rub: float
    period_days: int
    kind: str
    dlc_codes: list[str]
    status: str
    gateway_txn_id: str | None
    created_at: str
    completed_at: str | None


class AdminPaymentLogOut(BaseModel):
    id: int
    vk_id: int | None
    order_id: int | None
    txn_id: str | None
    action: str
    detail: str | None
    created_at: str


@admin_router.get("/payment-orders", response_model=list[AdminPaymentOrderOut])
def list_payment_orders(
    status_filter: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    q = db.query(PaymentOrder)
    if status_filter:
        q = q.filter(PaymentOrder.status == status_filter)
    orders = q.order_by(PaymentOrder.created_at.desc()).limit(200).all()
    return [
        AdminPaymentOrderOut(
            id=o.id, vk_id=o.vk_id, amount_kop=o.amount_kop,
            amount_rub=round(o.amount_kop / 100, 2), period_days=o.period_days,
            kind=o.kind, dlc_codes=parse_dlc_codes(o.dlc_codes), status=o.status,
            gateway_txn_id=o.gateway_txn_id,
            created_at=o.created_at.isoformat(), completed_at=o.completed_at.isoformat() if o.completed_at else None,
        )
        for o in orders
    ]


@admin_router.post("/payment-orders/{order_id}/cancel", response_model=AdminPaymentOrderOut)
def cancel_payment_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    order = db.query(PaymentOrder).filter(PaymentOrder.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")
    if order.status == "pending":
        order.status = "cancelled"
        db.commit()
        _log(order.vk_id, order.id, "cancelled_by_admin", "", txn_id=order.gateway_txn_id or "", db=db)
    db.refresh(order)
    return AdminPaymentOrderOut(
        id=order.id, vk_id=order.vk_id, amount_kop=order.amount_kop,
        amount_rub=round(order.amount_kop / 100, 2), period_days=order.period_days,
        kind=order.kind, dlc_codes=parse_dlc_codes(order.dlc_codes), status=order.status,
        gateway_txn_id=order.gateway_txn_id,
        created_at=order.created_at.isoformat(), completed_at=order.completed_at.isoformat() if order.completed_at else None,
    )


@admin_router.get("/payment-logs", response_model=list[AdminPaymentLogOut])
def list_payment_logs(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    logs = db.query(PaymentLog).order_by(PaymentLog.created_at.desc()).limit(200).all()
    return [
        AdminPaymentLogOut(
            id=l.id, vk_id=l.vk_id, order_id=l.order_id, txn_id=l.txn_id,
            action=l.action, detail=l.detail, created_at=l.created_at.isoformat(),
        )
        for l in logs
    ]
