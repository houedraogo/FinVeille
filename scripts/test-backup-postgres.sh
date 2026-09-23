#!/usr/bin/env sh
# Run only against an explicitly designated disposable PostgreSQL database.
set -eu
: "${LOT1_TEST_POSTGRES:?Set LOT1_TEST_POSTGRES=1 for a disposable database}"
[ "$LOT1_TEST_POSTGRES" = 1 ]
: "${POSTGRES_HOST:?}"
: "${POSTGRES_DB:?}"
: "${POSTGRES_USER:?}"
: "${POSTGRES_PASSWORD:?}"

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_DIR="$(mktemp -d)"
RESTORE_DB="lot1_restore_$$"
export PGPASSWORD="$POSTGRES_PASSWORD"
cleanup() {
    dropdb -h "$POSTGRES_HOST" -U "$POSTGRES_USER" --if-exists "$RESTORE_DB" > /dev/null 2>&1 || true
    rm -rf "$TEST_DIR"
}
trap cleanup EXIT

# A real dump can be listed and restored to a second disposable database.
BACKUP_DIR="$TEST_DIR/valid" sh "$SCRIPT_DIR/backup-postgres.sh"
VALID_DUMP="$(find "$TEST_DIR/valid" -name 'finveille-*.dump' -type f)"
[ -s "$VALID_DUMP" ]
pg_restore --list "$VALID_DUMP" > /dev/null
createdb -h "$POSTGRES_HOST" -U "$POSTGRES_USER" "$RESTORE_DB"
pg_restore -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$RESTORE_DB" "$VALID_DUMP"
psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$RESTORE_DB" -Atqc "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'" | grep -q '^[1-9]'

# Wrong credentials must fail, leaving no advertised backup.
if BACKUP_DIR="$TEST_DIR/bad-password" POSTGRES_PASSWORD=incorrect sh "$SCRIPT_DIR/backup-postgres.sh"; then
    echo 'Invalid credentials unexpectedly succeeded' >&2
    exit 1
fi
[ -z "$(find "$TEST_DIR/bad-password" -name 'finveille-*.dump' -type f)" ]

# Simulate pg_dump failing after creating a partial file.
mkdir -p "$TEST_DIR/bin"
cat > "$TEST_DIR/bin/pg_dump" <<'EOF'
#!/usr/bin/env sh
while [ "$#" -gt 0 ]; do
    if [ "$1" = -f ]; then
        shift
        case "${FAKE_DUMP_MODE:-fail}" in
            fail) printf 'partial dump' > "$1"; exit 42 ;;
            invalid) printf 'invalid dump' > "$1"; exit 0 ;;
            empty) : > "$1"; exit 0 ;;
        esac
    fi
    shift
done
exit 42
EOF
chmod +x "$TEST_DIR/bin/pg_dump"
if BACKUP_DIR="$TEST_DIR/failed-dump" PATH="$TEST_DIR/bin:$PATH" sh "$SCRIPT_DIR/backup-postgres.sh"; then
    echo 'Failed pg_dump unexpectedly succeeded' >&2
    exit 1
fi
[ -z "$(find "$TEST_DIR/failed-dump" -type f)" ]

for mode in invalid empty; do
    if BACKUP_DIR="$TEST_DIR/$mode" FAKE_DUMP_MODE="$mode" PATH="$TEST_DIR/bin:$PATH" sh "$SCRIPT_DIR/backup-postgres.sh"; then
        echo "A $mode dump unexpectedly succeeded" >&2
        exit 1
    fi
    [ -z "$(find "$TEST_DIR/$mode" -type f)" ]
done
echo 'Backup regression tests passed'
