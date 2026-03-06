#!/usr/bin/env bash
# Database backup script — run manually or add to cron
# Usage: ./scripts/backup.sh [output-dir]
set -euo pipefail

BACKUP_DIR="${1:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="aiwebgen_${TIMESTAMP}.sql.gz"

source .env 2>/dev/null || true

mkdir -p "$BACKUP_DIR"

echo "Creating database backup: $FILENAME"

docker exec aiwebgen-postgres pg_dump \
  -U "${POSTGRES_USER:-aiwebgen}" \
  "${POSTGRES_DB:-ai_web_gen}" | \
  gzip > "${BACKUP_DIR}/${FILENAME}"

SIZE=$(du -h "${BACKUP_DIR}/${FILENAME}" | cut -f1)
echo "Backup saved: ${BACKUP_DIR}/${FILENAME} (${SIZE})"

# Keep only last 7 daily backups
find "$BACKUP_DIR" -name "aiwebgen_*.sql.gz" -mtime +7 -delete
echo "Old backups cleaned (kept last 7 days)"
