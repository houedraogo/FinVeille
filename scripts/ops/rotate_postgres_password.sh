#!/usr/bin/env bash
# Rotation du mot de passe PostgreSQL de Kafundo — NE PAS EXÉCUTER sans accord explicite et créneau convenu.
#
#   bash scripts/ops/rotate_postgres_password.sh --dry-run     # contrôles + plan, n'écrit rien
#   bash scripts/ops/rotate_postgres_password.sh               # exécution (confirmation "ROTATE" demandée)
#
# Topologie réelle (constat du 10/10/2026) : backend, worker, beat et frontend sont des conteneurs lancés
# avec `docker run` (pas de labels compose) ; seul `postgres-backup` est géré par compose. Les conteneurs
# applicatifs sont donc recréés par scripts/ops/swap_container.py (même configuration, nouvel environnement,
# ancien conteneur conservé pour retour arrière instantané). Leur environnement vient de `.env`.
#
# Le nouveau mot de passe est généré ici (alphanumérique, 40 caractères), jamais affiché, jamais passé en
# argument ; les copies de travail (0600, dossier 0700) sont détruites à la sortie. Échec après le changement
# => retour arrière automatique (rôle PostgreSQL, fichiers .env, conteneurs).
#
# Variables de surcharge (tests) : APP_DIR COMPOSE_FILE BACKUP_DIR PG_CONTAINER DB_USER DB_NAME ENV_PRIMARY ENV_FILES
#   APP_CONTAINERS COMPOSE_SERVICES DB_SERVICE_HOST HEALTH_CONTAINER HEALTH_CMD SKIP_BACKUP_CHECK ASSUME_YES
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/finveille}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-/opt/finveille-backups}"
PG_CONTAINER="${PG_CONTAINER:-kafundo-postgres}"
DB_USER="${DB_USER:-finveille}"
DB_NAME="${DB_NAME:-finveille}"
ENV_PRIMARY="${ENV_PRIMARY:-.env}"                      # fichier source de l'environnement des conteneurs
ENV_FILES="${ENV_FILES:-.env .env.production}"          # fichiers tenus à jour (compose lit .env.production)
APP_CONTAINERS="${APP_CONTAINERS:-kafundo-backend kafundo-worker kafundo-beat kafundo-frontend}"
COMPOSE_SERVICES="${COMPOSE_SERVICES-postgres-backup}"  # services gérés par compose à recréer (vide = aucun)
DB_SERVICE_HOST="${DB_SERVICE_HOST:-postgres}"
HEALTH_CONTAINER="${HEALTH_CONTAINER:-kafundo-backend}"
HEALTH_CMD="${HEALTH_CMD:-curl -fsS http://localhost:8000/api/health}"
HERE="$(cd "$(dirname "$0")" && pwd)"
swap_container() { python3 "$HERE/swap_container.py" "$@"; }
KEYS="POSTGRES_PASSWORD,DATABASE_URL,DATABASE_SYNC_URL"
DRY_RUN=0; [ "${1:-}" = "--dry-run" ] && DRY_RUN=1

cd "$APP_DIR"
compose() { docker compose -f "$COMPOSE_FILE" "$@"; }
say() { printf '%s\n' "$*"; }
die() { printf 'ARRÊT: %s\n' "$*" >&2; exit 1; }

health_for() {  # commande de santé selon le conteneur
  case "$1" in
    *worker*)   echo "celery -A app.tasks.celery_app inspect ping -t 5" ;;
    *beat*)     echo 'python -c "import os; os.kill(1, 0)"' ;;
    *frontend*) echo 'true' ;;
    *)          echo "$HEALTH_CMD" ;;
  esac
}

# ---------- 1. Contrôles préalables (lecture seule) ----------
for f in $ENV_FILES; do [ -f "$f" ] || die "fichier introuvable: $f"; done
for key in POSTGRES_PASSWORD DATABASE_URL DATABASE_SYNC_URL; do
  for f in $ENV_FILES; do
    python3 "$HERE/envfile.py" names "$f" | grep -qx "$key" || die "$key absent de $f"
  done
done
for c in $PG_CONTAINER $APP_CONTAINERS; do
  docker inspect -f '{{.State.Running}}' "$c" 2>/dev/null | grep -q true || die "$c n'est pas démarré"
  if docker container inspect "$c-prev" >/dev/null 2>&1; then die "$c-prev existe déjà (bascule précédente non validée)"; fi
done
# Le mot de passe actuel des conteneurs doit être celui du fichier source : sinon la rotation ferait un saut de version.
CUR_FILE="$(python3 "$HERE/envfile.py" get "$ENV_PRIMARY" POSTGRES_PASSWORD)"
CUR_LIVE="$(docker exec "$HEALTH_CONTAINER" printenv POSTGRES_PASSWORD)"
[ "$CUR_FILE" = "$CUR_LIVE" ] || die "POSTGRES_PASSWORD de $ENV_PRIMARY différent de celui du conteneur $HEALTH_CONTAINER (à réconcilier d'abord)"
unset CUR_FILE CUR_LIVE

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
say "  3. recréer à l'identique (même image, même config) avec le nouvel environnement : ${APP_CONTAINERS}"
[ -n "$COMPOSE_SERVICES" ] && say "     et, via compose : ${COMPOSE_SERVICES}"
say "  4. vérifier : santé, nouvelle clé acceptée et ancienne clé REFUSÉE"
say "  5. en cas d'échec : retour arrière automatique (rôle, fichiers, conteneurs ; anciens conteneurs conservés)"
say "  Coupure attendue : quelques secondes par conteneur ; PostgreSQL n'est pas redémarré."
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

OLD="$(python3 "$HERE/envfile.py" get "$ENV_PRIMARY" POSTGRES_PASSWORD)"
NEW="$(openssl rand -base64 64 | tr -dc 'A-Za-z0-9' | head -c 40)"
[ "${#NEW}" -eq 40 ] || die "génération du mot de passe échouée"
for f in $ENV_FILES; do cp -p "$f" "$WORK/$(basename "$f").orig"; done
SWAPPED=""

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
current_image() { docker inspect -f '{{.Config.Image}}' "$1"; }
connect_check() {
  printf 'PW_OLD=%s\nPW_NEW=%s\nDB_HOST=%s\nDB_USER=%s\nDB_NAME=%s\n' "$OLD" "$NEW" "$DB_SERVICE_HOST" "$DB_USER" "$DB_NAME" > "$WORK/check.env"
  docker exec --env-file "$WORK/check.env" "$HEALTH_CONTAINER" python - <<'PY'
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
  for c in $SWAPPED; do swap_container rollback "$c" >/dev/null 2>&1 || say "ATTENTION: retour arrière de $c à vérifier"; done
  set_role_password "$OLD" || say "ATTENTION: impossible de remettre l'ancien mot de passe automatiquement"
  for f in $ENV_FILES; do cp -p "$WORK/$(basename "$f").orig" "$f"; done
  [ -n "$COMPOSE_SERVICES" ] && compose up -d --no-deps --force-recreate $COMPOSE_SERVICES >/dev/null 2>&1 || true
  say "Retour arrière effectué (anciens conteneurs, ancien mot de passe, anciens fichiers)."
}

say "1/4 changement du mot de passe du rôle…"
set_role_password "$NEW" || die "ALTER ROLE refusé — rien n'a été modifié"
say "2/4 mise à jour des fichiers d'environnement…"
if ! apply_env "$NEW"; then rollback; die "mise à jour des fichiers échouée"; fi
say "3/4 recréation des conteneurs…"
for c in $APP_CONTAINERS; do
  if swap_container swap "$c" --image "$(current_image "$c")" --env-from "$ENV_PRIMARY" --env-only "$KEYS" \
        --health "$(health_for "$c")" --wait 120 --stop-timeout 60 >/dev/null 2>&1; then
    SWAPPED="$SWAPPED $c"; say "   $c : OK"
  else
    rollback; die "$c non sain après recréation"
  fi
done
if [ -n "$COMPOSE_SERVICES" ]; then
  compose up -d --no-deps --force-recreate $COMPOSE_SERVICES >/dev/null || { rollback; die "recréation compose échouée"; }
fi
say "4/4 vérification des identifiants…"
if ! connect_check; then rollback; die "vérification échouée (la nouvelle clé doit passer, l'ancienne être refusée)"; fi

say "OK — rotation terminée. Les anciens conteneurs sont conservés (<nom>-prev) le temps de la validation :"
say "  - vérifier l'application, lancer une sauvegarde manuelle, puis valider : swap_container.py commit <nom> pour chacun"
say "  - supprimer toute autre copie de l'ancien mot de passe (scripts, notes, gestionnaires)"
