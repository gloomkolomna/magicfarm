from __future__ import annotations

from sqlalchemy.orm import Session


def production_display_name(db: Session, kind: str, stored: str | None = None) -> str:
    from models import PRODUCTION_NAMES, ProductionTemplate

    if kind:
        tmpl = db.query(ProductionTemplate).filter(ProductionTemplate.code == kind).first()
        if tmpl is not None and tmpl.name:
            return tmpl.name
        if kind in PRODUCTION_NAMES:
            return PRODUCTION_NAMES[kind]
    return stored or kind or ""
