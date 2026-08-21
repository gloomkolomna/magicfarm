from __future__ import annotations
import datetime

from sqlalchemy.orm import Session

import config


def cleanup_expired_stitch_photos(db: Session) -> dict:
    from models import StitchReport
    from services import s3_storage

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=config.STITCH_PHOTO_TTL_DAYS)
    reports = db.query(StitchReport).filter(
        StitchReport.created_at <= cutoff,
        StitchReport.status != "pending",
        StitchReport.photo_after_url.isnot(None),
    ).all()
    cleaned = 0
    objects_deleted = 0
    delete_failed = 0
    skipped = 0
    pending_deletes: list[str] = []
    for r in reports:
        if not r.photo_after_thumb_url:
            skipped += 1
            continue
        changed = False
        after_key = s3_storage.s3_key_from_url(r.photo_after_url)
        if after_key:
            pending_deletes.append(after_key)
            r.photo_after_url = None
            changed = True
        if r.photo_before_url and r.photo_before_thumb_url:
            before_key = s3_storage.s3_key_from_url(r.photo_before_url)
            if before_key:
                pending_deletes.append(before_key)
                r.photo_before_url = None
                changed = True
        if changed:
            cleaned += 1
    if cleaned:
        db.commit()
    for key in pending_deletes:
        try:
            s3_storage.delete_object(key)
            objects_deleted += 1
        except Exception:
            delete_failed += 1
    return {
        "scanned": len(reports),
        "cleaned": cleaned,
        "objects_deleted": objects_deleted,
        "skipped_no_thumb": skipped,
        "delete_failed": delete_failed,
    }
