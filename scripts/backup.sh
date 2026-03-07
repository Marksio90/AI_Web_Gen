#!/usr/bin/env bash
# Database backup script — run manually or add to cron
# Usage: ./scripts/backup.sh [output-dir]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="aiwebgen_${TIMESTAMP}.sql.gz"

source "$ROOT/.env" 2>/dev/null || true

BACKUP_DIR="${1:-$ROOT/backups}"
mkdir -p "$BACKUP_DIR"

echo "Creating database backup: $FILENAME"

docker exec aiwebgen-postgres pg_dump \
  -U "${POSTGRES_USER:-aiwebgen}" \
  "${POSTGRES_DB:-ai_web_gen}" | \
  gzip > "${BACKUP_DIR}/${FILENAME}"

# Verify backup integrity
gzip -t "${BACKUP_DIR}/${FILENAME}" || { echo "ERROR: Backup file is corrupt!"; exit 1; }
ACTUAL_SIZE=$(stat -c%s "${BACKUP_DIR}/${FILENAME}" 2>/dev/null || stat -f%z "${BACKUP_DIR}/${FILENAME}")
if [ "$ACTUAL_SIZE" -lt 1024 ]; then
  echo "ERROR: Backup too small (${ACTUAL_SIZE} bytes), likely empty or failed"
  exit 1
fi

SIZE=$(du -h "${BACKUP_DIR}/${FILENAME}" | cut -f1)
echo "Backup saved: ${BACKUP_DIR}/${FILENAME} (${SIZE})"

# Keep only last 7 daily backups
find "$BACKUP_DIR" -maxdepth 1 -name "aiwebgen_*.sql.gz" -mtime +7 -delete
echo "Old backups cleaned (kept last 7 days)"
