#!/usr/bin/env sh
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-finveille}"
POSTGRES_USER="${POSTGRES_USER:-finveille}"

mkdir -p "$BACKUP_DIR"

STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="$BACKUP_DIR/finveille-$STAMP.sql.gz"

pg_dump -h "$POSTGRES_HOST" -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$FILE"
find "$BACKUP_DIR" -type f -name "finveille-*.sql.gz" -mtime +"$RETENTION_DAYS" -delete

echo "Backup created: $FILE"
