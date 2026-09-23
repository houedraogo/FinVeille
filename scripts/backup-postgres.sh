#!/usr/bin/env sh
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-finveille}"
POSTGRES_USER="${POSTGRES_USER:-finveille}"
PGPORT="${POSTGRES_PORT:-${PGPORT:-5432}}"
export PGPORT
if [ -n "${POSTGRES_PASSWORD:-}" ]; then
    PGPASSWORD="$POSTGRES_PASSWORD"
    export PGPASSWORD
fi
: "${PGPASSWORD:?POSTGRES_PASSWORD or PGPASSWORD is required}"

mkdir -p "$BACKUP_DIR"

STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="$BACKUP_DIR/finveille-$STAMP.dump"
TEMP_FILE="$(mktemp "$BACKUP_DIR/.finveille-$STAMP.XXXXXX")"
trap 'rm -f "$TEMP_FILE"' EXIT HUP INT TERM

pg_dump -Fc -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -f "$TEMP_FILE" "$POSTGRES_DB"
test -s "$TEMP_FILE"
pg_restore --list "$TEMP_FILE" > /dev/null
mv "$TEMP_FILE" "$FILE"
find "$BACKUP_DIR" -type f \( -name "finveille-*.dump" -o -name "finveille-*.sql.gz" \) -mtime +"$RETENTION_DAYS" -delete

echo "Backup created: $FILE"
