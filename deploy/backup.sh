#!/bin/bash
# Daily DB backup script — «Ферма».
# В cron, например: 0 3 * * * /opt/farm/deploy/backup.sh
DB_FILE="/opt/farm/api/farm.db"
BACKUP_DIR="/opt/farm/api/backups"
RETENTION_DAYS=7

mkdir -p "$BACKUP_DIR"
BACKUP_PATH="$BACKUP_DIR/farm.db.bak.$(date '+%Y%m%d_%H%M%S')"
cp "$DB_FILE" "$BACKUP_PATH"

find "$BACKUP_DIR" -name "farm.db.bak.*" -type f -mtime +$RETENTION_DAYS -delete
