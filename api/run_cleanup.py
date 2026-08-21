from __future__ import annotations

from db import SessionLocal
from services.s3_cleanup import cleanup_expired_stitch_photos


def main() -> None:
    db = SessionLocal()
    try:
        stats = cleanup_expired_stitch_photos(db)
        print(
            "S3 cleanup: scanned={scanned} cleaned={cleaned} "
            "objects_deleted={objects_deleted} skipped_no_thumb={skipped_no_thumb}".format(**stats)
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
