from __future__ import annotations
import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_role
from models import StitchReport, User
from routes.settings import get_auto_credit
from services.achievements import check_and_award
from services.pet_bonuses import apply_pet_bonus_animal_product, apply_pet_bonus_craft
from services.uploads import remove_upload, save_upload

router = APIRouter(prefix="/api/stitches", tags=["stitches"])

MIN_AMOUNT = 1
MAX_AMOUNT = 100000

DEDUP_WINDOW_SECONDS = 10


def _credit(user: User, amount: int) -> None:
    user.crosses_balance = (user.crosses_balance or 0) + amount
    user.crosses_total = (user.crosses_total or 0) + amount


def _process_context(report: "StitchReport", db: Session) -> None:
    if report.context_type == "plant_grow" and report.context_id is not None:
        from models import Plot
        plot = db.query(Plot).filter(Plot.id == report.context_id, Plot.user_id == report.user_id).first()
        if plot is not None:
            plot.accumulated = (plot.accumulated or 0) + report.amount
            if plot.accumulated >= plot.required:
                plot.status = "grown"
                plot.completed_at = datetime.datetime.utcnow()
            db.commit()
    elif report.context_type == "recipe_study" and report.context_id is not None:
        from routes.library import complete_study
        complete_study(report.user_id, report.context_id, db)
        check_and_award(report.user_id, "first_recipe", db)
    elif report.context_type == "production" and report.context_id is not None:
        from models import CraftSession, Inventory
        cs = db.query(CraftSession).filter(CraftSession.id == report.context_id).first()
        if cs is not None and cs.status == "pending":
            cs.status = "completed"
            if cs.source_product_id is not None:
                source_inv = db.query(Inventory).filter(
                    Inventory.user_id == cs.user_id, Inventory.product_id == cs.source_product_id
                ).first()
                if source_inv:
                    source_inv.qty = (source_inv.qty or 0) - cs.qty
            else:
                plant_inv = db.query(Inventory).filter(
                    Inventory.user_id == cs.user_id, Inventory.plant_id == cs.plant_id
                ).first()
                if plant_inv:
                    plant_inv.qty = (plant_inv.qty or 0) - cs.qty
            prod_inv = db.query(Inventory).filter(
                Inventory.user_id == cs.user_id, Inventory.product_id == cs.product_id
            ).first()
            if prod_inv is None:
                prod_inv = Inventory(user_id=cs.user_id, product_id=cs.product_id, qty=0)
                db.add(prod_inv)
            prod_inv.qty = (prod_inv.qty or 0) + cs.qty
            bonus = apply_pet_bonus_craft(cs.user_id, db)
            if bonus > 0:
                prod_inv.qty = (prod_inv.qty or 0) + bonus
            db.commit()
    elif report.context_type == "animal_produce" and report.context_id is not None:
        from models import Animal, BarnyardSlot
        slot = db.query(BarnyardSlot).filter(BarnyardSlot.id == report.context_id).first()
        if slot is not None:
            bonus = apply_pet_bonus_animal_product(report.user_id, db)
            die = slot.last_die or 1
            qty = die + bonus
            animal = db.query(Animal).filter(Animal.id == slot.animal_id).first()
            if animal:
                pass
            db.commit()
    elif report.context_type == "tent_build" and report.context_id is not None:
        from models import PRODUCTION_NAMES, Production, Tent, TentBuild
        tb = db.query(TentBuild).filter(
            TentBuild.user_id == report.user_id, TentBuild.tent_id == report.context_id
        ).first()
        if tb is not None and tb.build_status == "planted":
            tb.accumulated = (tb.accumulated or 0) + report.amount
            if tb.accumulated >= (tb.required or 0):
                tb.build_status = "built"
                t = db.query(Tent).filter(Tent.id == tb.tent_id).first()
                if t is not None:
                    from routes.settings import get_production_required
                    exists = db.query(Production).filter(
                        Production.user_id == report.user_id, Production.tent_id == t.id
                    ).first()
                    if exists is None:
                        db.add(Production(
                            user_id=report.user_id, kind=t.kind,
                            name=PRODUCTION_NAMES.get(t.kind, t.kind),
                            status="installed", accumulated=0,
                            required=get_production_required(db), tent_id=t.id,
                        ))
            db.commit()
            check_and_award(report.user_id, "tents_count", db)
    elif report.context_type == "house_material" and report.context_id is not None:
        from routes.house import complete_material
        complete_material(report.user_id, report.context_id, db)
    elif report.context_type == "house_build" and report.context_id is not None:
        from routes.house import complete_build
        complete_build(report.user_id, report.context_id, db)
    elif report.context_type == "animal_build" and report.context_id is not None:
        from models import BarnyardSlot
        slot = db.query(BarnyardSlot).filter(
            BarnyardSlot.id == report.context_id, BarnyardSlot.user_id == report.user_id
        ).first()
        if slot is not None and slot.status == "building":
            slot.accumulated = (slot.accumulated or 0) + report.amount
            if slot.accumulated >= (slot.required or 0):
                slot.status = "ready"
            db.commit()
            check_and_award(report.user_id, "animals_count", db)
    elif report.context_type == "pet_settle" and report.context_id is not None:
        from models import UserPet
        existing = db.query(UserPet).filter(
            UserPet.user_id == report.user_id, UserPet.pet_id == report.context_id
        ).first()
        if existing is None:
            db.add(UserPet(user_id=report.user_id, pet_id=report.context_id, cell_id=report.cell_id))
            db.commit()
            check_and_award(report.user_id, "pets_count", db)


class StitchReportOut(BaseModel):
    id: int
    user_id: int
    amount: int
    photo_before_url: str | None
    photo_after_url: str
    note: str | None
    context_type: str | None
    context_id: int | None
    status: str
    reviewer_id: int | None
    reviewed_at: datetime.datetime | None
    created_at: datetime.datetime | None


def _to_out(r: StitchReport) -> StitchReportOut:
    return StitchReportOut(
        id=r.id, user_id=r.user_id, amount=r.amount,
        photo_before_url=r.photo_before_url, photo_after_url=r.photo_after_url,
        note=r.note, context_type=r.context_type, context_id=r.context_id,
        status=r.status, reviewer_id=r.reviewer_id,
        reviewed_at=r.reviewed_at, created_at=r.created_at,
    )


@router.post("/reports", response_model=StitchReportOut, status_code=status.HTTP_201_CREATED)
def create_report(
    photo_after: UploadFile = File(...),
    amount: int = Form(...),
    photo_before: UploadFile | None = File(default=None),
    note: str | None = Form(default=None),
    context_type: str | None = Form(default=None),
    context_id: int | None = Form(default=None),
    cell_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if amount < MIN_AMOUNT or amount > MAX_AMOUNT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Количество крестиков должно быть от {MIN_AMOUNT} до {MAX_AMOUNT}",
        )

    if context_type == "plant_grow" and context_id is not None:
        from models import Plot
        plot = db.query(Plot).filter(Plot.id == context_id, Plot.user_id == user.vk_id).first()
        if plot is not None:
            if plot.status == "await_replant":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Растение собрано — укажите новое количество и посадите заново",
                )
            if amount < (plot.required - plot.accumulated):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Недостаточно крестиков. Норма грядки: {plot.required - plot.accumulated}, вы указали {amount}",
                )

    if context_type == "production" and context_id is not None:
        from models import CraftSession
        cs = db.query(CraftSession).filter(
            CraftSession.id == context_id, CraftSession.user_id == user.vk_id
        ).first()
        if cs is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Крафт не найден")
        if cs.status != "pending":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Крафт уже завершён")
        if amount < (cs.required or 0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Недостаточно крестиков. Норма крафта: {cs.required}, вы указали {amount}",
            )

    if context_type == "house_material" and context_id is not None:
        from models import HouseBuild
        hb = db.query(HouseBuild).filter(
            HouseBuild.id == context_id, HouseBuild.user_id == user.vk_id
        ).first()
        if hb is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Стройка дома не найдена")
        if hb.phase != "materials" or hb.current_material is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Нет стройматериала, ожидающего вышивки",
            )
        if amount < (hb.current_required or 0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Недостаточно крестиков. Норма материала: {hb.current_required}, вы указали {amount}",
            )

    if context_type == "house_build" and context_id is not None:
        from models import HouseBuild
        hb = db.query(HouseBuild).filter(
            HouseBuild.id == context_id, HouseBuild.user_id == user.vk_id
        ).first()
        if hb is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Стройка дома не найдена")
        if hb.phase != "materials" or (hb.required or 0) <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Норма на постройку дома ещё не назначена",
            )
        if amount < (hb.required or 0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Недостаточно крестиков. Норма на дом: {hb.required}, вы указали {amount}",
            )

    if context_type is not None and context_type not in (
        "plant_grow", "recipe_study", "production",
        "animal_build", "animal_produce", "tent_build", "pet_settle",
        "house_material", "house_build",
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неверный тип контекста: {context_type}",
        )

    recent_cutoff = datetime.datetime.utcnow() - datetime.timedelta(seconds=DEDUP_WINDOW_SECONDS)
    duplicate = db.query(StitchReport).filter(
        StitchReport.user_id == user.vk_id,
        StitchReport.amount == amount,
        StitchReport.created_at >= recent_cutoff,
    ).first()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Такой отчёт уже отправлен недавно — подождите {DEDUP_WINDOW_SECONDS} секунд",
        )

    after_url = save_upload(photo_after, f"stitch_{user.vk_id}_after", max_size=1280)
    before_url = save_upload(photo_before, f"stitch_{user.vk_id}_before", max_size=1280) if photo_before else None
    r = StitchReport(
        user_id=user.vk_id, amount=amount,
        photo_before_url=before_url, photo_after_url=after_url,
        note=note, context_type=context_type, context_id=context_id,
        cell_id=cell_id,
        status="pending",
    )

    if get_auto_credit(db):
        u = db.query(User).filter(User.vk_id == user.vk_id).first()
        _credit(u, amount)
        r.status = "accepted"
        r.reviewed_at = datetime.datetime.utcnow()

    db.add(r)
    db.commit()
    db.refresh(r)

    if r.status == "accepted":
        _process_context(r, db)

    return _to_out(r)


@router.get("/reports", response_model=list[StitchReportOut])
def list_reports(
    status_filter: str | None = Query(default=None, alias="status"),
    mine: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(StitchReport)
    if status_filter is not None:
        q = q.filter(StitchReport.status == status_filter)
    if mine or user.role != "admin":
        # Игрок видит только свои отчёты; admin — все (если не запрошено mine).
        if user.role != "admin" or mine:
            q = q.filter(StitchReport.user_id == user.vk_id)
    rows = q.order_by(StitchReport.created_at.desc()).limit(200).all()
    return [_to_out(r) for r in rows]


def _get_pending_or_404(report_id: int, db: Session) -> StitchReport:
    r = db.query(StitchReport).filter(StitchReport.id == report_id).first()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отчёт не найден")
    if r.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Отчёт уже рассмотрен")
    return r


@router.post("/reports/{report_id}/accept", response_model=StitchReportOut)
def accept_report(
    report_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    r = _get_pending_or_404(report_id, db)
    author = db.query(User).filter(User.vk_id == r.user_id).first()
    if author is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Автор отчёта не найден")

    _credit(author, r.amount)
    r.status = "accepted"
    r.reviewer_id = user.vk_id
    r.reviewed_at = datetime.datetime.utcnow()

    db.commit()
    db.refresh(r)

    _process_context(r, db)

    return _to_out(r)


@router.post("/reports/{report_id}/reject", response_model=StitchReportOut)
def reject_report(
    report_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    r = _get_pending_or_404(report_id, db)
    r.status = "rejected"
    r.reviewer_id = user.vk_id
    r.reviewed_at = datetime.datetime.utcnow()

    db.commit()
    db.refresh(r)
    return _to_out(r)


@router.delete(
    "/reports/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("admin"))],
)
def delete_report(report_id: int, db: Session = Depends(get_db)):
    r = db.query(StitchReport).filter(StitchReport.id == report_id).first()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отчёт не найден")
    remove_upload(r.photo_before_url)
    remove_upload(r.photo_after_url)
    db.delete(r)
    db.commit()
    return None
