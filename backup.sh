#!/bin/bash
set -euo pipefail
BACKUP_DIR=/opt/quit-smoke-bot/backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
cd /opt/quit-smoke-bot

# Dump database
docker compose exec -T postgres pg_dump -U bot -d quit_smoke | gzip > "$BACKUP_DIR/quit_smoke_$TIMESTAMP.sql.gz"

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name '*.sql.gz' -mtime +7 -delete

echo "Backup completed: quit_smoke_$TIMESTAMP.sql.gz"
