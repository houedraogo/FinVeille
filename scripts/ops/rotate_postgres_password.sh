#!/usr/bin/env bash
# Rotation du mot de passe PostgreSQL de Kafundo — NE PAS EXÉCUTER sans accord explicite.
#
#   bash scripts/ops/rotate_postgres_password.sh --dry-run     # contrôles + plan, n'écrit rien
#   bash scripts/ops/rotate_postgres_password.sh               # exécution (confirmation "ROTATE" demandée)
#
# Le nouveau mot de passe est généré ici (alphanumérique, 40 caractères), n'est JAMAIS affiché,
# jamais passé en argument de commande, et les copies de travail (0600, dossier 0700) sont
# détruites à la sortie. En cas d'échec après le changement, retour arrière automatique.
#
# Variables de surcharge (tests) : APP_DIR COMPOSE_FILE BACKUP_DIR PG_CONTAINER DB_USER DB_NAME
#   SERVICES ENV_FILES DB_SERVICE_HOST HEALTH_SERVICE HEALTH_CMD SKIP_BACKUP_CHECK ASSUME_YES
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/finveille}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-/opt/finveille-backups}"
PG_CONTAINER="${PG_CONTAINER:-kafundo-postgres}"
DB_USER="${DB_USER:-finveille}"
DB_NAME="${DB_NAME:-finveille}"
SERVICES="${SERVICES:-backend celery-worker celery-beat postgres-backup}"
ENV_FILES="${ENV_FILES:-.env .env.production}"
DB_SERVICE_HOST="${DB_SERVICE_HOST:-postgres}"
HEALTH_SERVICE="${HEALTH_SERVICE:-kafundo-backend}"
HEALTH_CMD="${HEALTH_CMD:-curl -fsS http://localhost:8000/api/health}"
HERE="$(cd "$(dirname "$0")" && pwd)"
DRY_RUN=0; [ "${1:-}" = "--dry-run" ] && DRY_RUN=1

cd "$APP_DIR"
compose() { docker compose -f "$COMPOSE_FILE" "$@"; }
say() { printf '%s\n' "$*"; }
die() { printf 'ARRÊT: %s\n' "$*" >&2; exit 1; }

# ---------- 1. Contrôles préalables (lecture seule) ----------
for f in $ENV_FILES "$COMPOSE_FILE"; do [ -f "$f" ] || die "fichier introuvable: $f"; done
for key in POSTGRES_PASSWORD DATABASE_URL DATABASE_SYNC_URL; do
  for f in $ENV_FILES; do
    python3 "$HERE/envfile.py" names "$f" | grep -qx "$key" || die "$key absent de $f"
  done
done
docker inspect -f '{{.State.Running}}' "$PG_CONTAINER" | grep -q true || die "$PG_CONTAINER n'est pas démarré"
for svc in $SERVICES; do compose ps --status running --services | grep -qx "$svc" || die "service $svc non démarré"; done

if [ "${SKIP_BACKUP_CHECK:-0}" != "1" ]; then
  LATEST="$(ls -t "$BACKUP_DIR"/finveille_*.sql.gz 2>/dev/null | head -1 || true)"
  [ -n "$LATEST" ] || die "aucune sauvegarde dans $BACKUP_DIR"
  AGE_H=$(( ( $(date +%s) - $(stat -c %Y "$LATEST") ) / 3600 ))
  [ "$AGE_H" -lt 26 ] || die "dernière sauvegarde trop ancienne (${AGE_H} h): $LATEST"
  gzip -t "$LATEST" || die "sauvegarde illisible: $LATEST"
  say "Sauvegarde vérifiée: $(basename "$LATEST") (${AGE_H} h)"
fi

say "Plan :"
say "  1. générer un mot de passe (non affiché) et l'appliquer à ${DB_USER} dans ${PG_CONTAINER}"
say "  2. mettre à jour POSTGRES_PASSWORD, DATABASE_URL, DATABASE_SYNC_URL dans : ${ENV_FILES}"
say "  3. recréer sans dépendances : ${SERVICES} (le conteneur PostgreSQL n'est pas redémarré)"
say "  4. vérifier : santé du service, nouvelle clé acceptée, ancienne clé REFUSÉE"
say "  5. en cas d'échec : retour arrière automatique (mot de passe + fichiers + services)"
say "  Coupure attendue : quelques secondes (redémarrage de l'API, du worker et du planificateur)."
if [ "$DRY_RUN" = "1" ]; then say "(--dry-run) Aucune modification effectuée."; exit 0; fi

if [ "${ASSUME_YES:-0}" != "1" ]; then
  read -rp 'Tapez ROTATE pour exécuter : ' CONFIRM
  [ "$CONFIRM" = "ROTATE" ] || die "confirmation absente"
fi

# ---------- 2. Exécution ----------
umask 077
WORK="$(mktemp -d)"; chmod 700 "$WORK"
cleanup() { find "$WORK" -type f -exec shred -u {} + 2>/dev/null || true; rm -rf "$WORK"; }
trap cleanup EXIT

OLD="$(python3 "$HERE/envfile.py" get "$(echo $ENV_FILES | cut -d' ' -f1)" POSTGRES_PASSWORD)"
NEW="$(openssl rand -base64 64 | tr -dc 'A-Za-z0-9' | head -c 40)"
[ "${#NEW}" -eq 40 ] || die "génération du mot de passe échouée"
for f in $ENV_FILES; do cp -p "$f" "$WORK/$(basename "$f").orig"; done

set_role_password() {  # $1 = mot de passe ; transmis par stdin, jamais en argument
  printf "ALTER ROLE %s WITH PASSWORD '%s';\n" "$DB_USER" "$1" \
    | docker exec -i "$PG_CONTAINER" psql -q -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 >/dev/null
}
apply_env() {  # $1 = mot de passe
  for f in $ENV_FILES; do
    printf '%s' "$1" | python3 "$HERE/envfile.py" set "$f" POSTGRES_PASSWORD >/dev/null
    printf '%s' "$1" | python3 "$HERE/envfile.py" set-url-password "$f" DATABASE_URL DATABASE_SYNC_URL >/dev/null
  done
}
recreate() { compose up -d --no-deps --force-recreate $SERVICES >/dev/null; }
wait_healthy() {
  for _ in $(seq 1 45); do
    if docker exec "$HEALTH_SERVICE" sh -c "$HEALTH_CMD" >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  return 1
}
connect_check() {  # $1 = OLD|NEW attendu ; mots de passe fournis par fichier d'environnement 0600
  printf 'PW_OLD=%s\nPW_NEW=%s\nDB_HOST=%s\nDB_USER=%s\nDB_NAME=%s\n' "$OLD" "$NEW" "$DB_SERVICE_HOST" "$DB_USER" "$DB_NAME" > "$WORK/check.env"
  docker exec --env-file "$WORK/check.env" "$HEALTH_SERVICE" python - <<'PY'
import os, sys
import psycopg2
def attempt(pw):
    try:
        psycopg2.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], dbname=os.environ["DB_NAME"],
                         password=pw, connect_timeout=5).close()
        return True
    except Exception:
        return False
new_ok, old_ok = attempt(os.environ["PW_NEW"]), attempt(os.environ["PW_OLD"])
print(f"nouvelle_cle_acceptee={new_ok} ancienne_cle_acceptee={old_ok}")
sys.exit(0 if (new_ok and not old_ok) else 1)
PY
}
rollback() {
  say "ÉCHEC — retour arrière…"
  set_role_password "$OLD" || say "ATTENTION: impossible de remettre l'ancien mot de passe automatiquement"
  for f in $ENV_FILES; do cp -p "$WORK/$(basename "$f").orig" "$f"; done
  recreate || true
  say "Retour arrière effectué (ancien mot de passe, anciens fichiers, services recréés)."
}

say "1/4 changement du mot de passe du rôle…"
set_role_password "$NEW" || die "ALTER ROLE refusé — rien n'a été modifié"
say "2/4 mise à jour des fichiers d'environnement…"
if ! apply_env "$NEW"; then rollback; die "mise à jour des fichiers échouée"; fi
say "3/4 recréation des services applicatifs…"
if ! recreate || ! wait_healthy; then rollback; die "services non sains après rotation"; fi
say "4/4 vérification des identifiants…"
if ! connect_check; then rollback; die "vérification échouée (la nouvelle clé doit passer, l'ancienne être refusée)"; fi

say "OK — rotation terminée. Étapes suivantes (voir docs/SECRETS_ROTATION_RUNBOOK.md) :"
say "  - vérifier l'application et lancer une sauvegarde manuelle"
say "  - supprimer toute autre copie de l'ancien mot de passe (scripts, notes, gestionnaires)"
