#!/usr/bin/env bash
# Deploiement controle de la migration Alembic c8e1f4a7b2d9 : images compatibles puis migration, avec controles et plan de
# retour arriere. SIMULATION (controles seuls) par defaut ; --apply exige la fenetre autorisee ET la confirmation MIGRATE.
#
#   IMAGE_TAG=fixes3-<sha> bash migration_execute.sh                  # pre-controles, n'ecrit RIEN
#   WINDOW_FROM=2026-10-12T05:10 WINDOW_TO=2026-10-12T05:55 IMAGE_TAG=fixes3-<sha> bash migration_execute.sh --apply
#     (terminal : la confirmation est saisie au clavier ; non interactif : printf 'MIGRATE\n' | bash migration_execute.sh --apply)
#   IMAGE_TAG=fixes3-<sha> bash migration_execute.sh --followup       # controle des collecteurs apres la fenetre (lecture seule)
#
# Confirmation : une SEULE ligne, exactement `MIGRATE`, lue sur l'entree standard AVANT toute sous-commande ; l'entree standard
# est ensuite fermee (/dev/null) : aucune commande lancee par le script ne peut la lire ni la consommer. Aucune variable
# d'environnement ne remplace la confirmation.
# Temps : le script s'arrete si le temps restant dans la fenetre est insuffisant avant le demarrage (MIN_START_MIN, defaut 25),
# avant les swaps (MIN_SWAP_MIN, defaut 15) et avant la migration (MIN_MIGRATE_MIN, defaut 8).
#
# Sequence (--apply) :
#   0. pre-controles   1. sauvegarde verifiee   2. images (backend, worker, beat) -> acceptent b7d3 ET c8e1 : /api/ready reste 200
#   3. migration (transactionnelle, lock_timeout 10 s)   4. controles post-migration   5. consignes de retour arriere
# Aucune suppression de conteneur : les anciens restent en `-prev` (voir ROLLBACK ci-dessous).
#
# Parametres de test (valeurs par defaut = production) : LOG_DIR, API_BASE, SWAP_CMD, DF_PATH, PG, PGU, PGDB, POST_SWAP_SLEEP.
set -uo pipefail
umask 077
HERE="$(dirname "$(readlink -f "$0")")"
TAG="${IMAGE_TAG:?IMAGE_TAG requis (ex. fixes3-2b479ed)}"
PREV_REV="b7d3a91c5e24"; HEAD_REV="c8e1f4a7b2d9"
PG="${PG:-kafundo-postgres}"; PGU="${PGU:-finveille}"; PGDB="${PGDB:-finveille}"
LOG_DIR="${LOG_DIR:-/opt/finveille-backups}"; API_BASE="${API_BASE:-http://127.0.0.1:8000}"; DF_PATH="${DF_PATH:-/opt}"
SWAP="${SWAP_CMD:-python3 $HERE/swap_container.py}"
MIN_START_MIN="${MIN_START_MIN:-25}"; MIN_SWAP_MIN="${MIN_SWAP_MIN:-15}"; MIN_MIGRATE_MIN="${MIN_MIGRATE_MIN:-8}"
POST_SWAP_SLEEP="${POST_SWAP_SLEEP:-8}"
export API_BASE
die() { echo "ARRET: $*" >&2; exit 1; }

APPLY=0; MODE="${1:-}"
case "$MODE" in ""|--apply|--followup) ;; *) die "option inconnue : $MODE" ;; esac
[ "$MODE" = "--apply" ] && APPLY=1

# ---- confirmation : lue en tout premier, avant toute sous-commande ----
if [ "$APPLY" = 1 ]; then
  if [ -t 0 ]; then
    IFS= read -r -p "Tapez MIGRATE pour executer sur la PRODUCTION : " CONFIRM_LINE || CONFIRM_LINE=""
  else
    IFS= read -r -t 30 CONFIRM_LINE || CONFIRM_LINE=""
  fi
  [ "$CONFIRM_LINE" = "MIGRATE" ] || die "confirmation absente ou incorrecte (attendu : MIGRATE)"
fi
exec 0</dev/null     # plus aucune sous-commande ne peut lire l'entree standard

if [ "$MODE" = "--followup" ]; then
  P() { docker exec "$PG" psql -U "$PGU" -d "$PGDB" -At -c "$1"; }
  echo "===== SUIVI POST-MIGRATION ($(date -u +%FT%TZ)) ====="
  echo "  revision : $(P 'select version_num from alembic_version')"
  echo "  collectes des 60 dernieres minutes (statut:nombre) : $(P "select coalesce(string_agg(status||':'||n, ' '), 'aucune') from (select status, count(*) n from collection_logs where started_at > now() - interval '60 minutes' group by 1) t")"
  echo "  taches planifiees recues (60 min) : $(docker logs --since 60m kafundo-beat 2>&1 | grep -c 'Sending due task')"
  echo "  erreurs de journaux (60 min) : backend=$(docker logs --since 60m kafundo-backend 2>&1 | grep -ciE 'traceback|critical') worker=$(docker logs --since 60m kafundo-worker 2>&1 | grep -ciE 'traceback|critical') beat=$(docker logs --since 60m kafundo-beat 2>&1 | grep -ciE 'traceback|critical')"
  echo "  fiches : $(P 'select count(*) from devices') ; archivees : $(P "select count(*) from devices where validation_status='archived'")"
  exit 0
fi

TS=$(date -u +%Y%m%dT%H%M%SZ); LOG="$LOG_DIR/migration_execute_${TS}.log"
exec > >(tee -a "$LOG") 2>&1
pg() { docker exec "$PG" psql -U "$PGU" -d "$PGDB" -At -F'|' "$@"; }
ready() { python3 - <<'PY'
import json, os, urllib.request, urllib.error
try:
    with urllib.request.urlopen(os.environ["API_BASE"] + "/api/ready", timeout=5) as r: d = json.load(r); print(200, d.get("schema_revision"))
except urllib.error.HTTPError as e: print(e.code, "-")
except Exception as e: print("ERR", type(e).__name__)
PY
}
POLL_LOG=""; POLL_PID=""
poll_start() { POLL_LOG="$(mktemp)"; ( while true; do
    c=$(python3 - <<'PY'
import os, urllib.request
try:
    print(urllib.request.urlopen(os.environ["API_BASE"] + "/api/health", timeout=2).status)
except Exception:
    print(0)
PY
); echo "$(date +%s.%N) $c" >> "$POLL_LOG"; sleep 0.5; done ) & POLL_PID=$!; }
poll_stop() { [ -n "$POLL_PID" ] || return 0; kill "$POLL_PID" 2>/dev/null; wait "$POLL_PID" 2>/dev/null; POLL_PID=""
  python3 - "$POLL_LOG" <<'PY'
import sys
rows = [l.split() for l in open(sys.argv[1]) if l.strip()]
if not rows:
    print("  indisponibilite mesuree de /api/health : aucun sondage")
    raise SystemExit
total = 0.0; runs = 0; prev = None
for i, (t, c) in enumerate(rows):
    if c != "200":
        nxt = float(rows[i + 1][0]) if i + 1 < len(rows) else float(t) + 0.5
        total += nxt - float(t)
        if prev is None or float(t) - prev > 1.5: runs += 1
        prev = float(t)
print(f"  indisponibilite mesuree de /api/health : {total:.1f} s en {runs} interruption(s) ({len(rows)} sondages sur {float(rows[-1][0]) - float(rows[0][0]):.0f} s)")
PY
  rm -f "$POLL_LOG"; }
rollback_hint() { echo "  Rollback images : $SWAP rollback kafundo-beat ; $SWAP rollback kafundo-worker ; $SWAP rollback kafundo-backend"; }
gate() { echo "  [controle] $1"; shift; if ! eval "$*"; then echo "ARRET : controle bloquant en echec -> procedure interrompue, aucune etape suivante."; rollback_hint; poll_stop; exit 3; fi; }
img_ok() { docker image inspect "$1" >/dev/null 2>&1 || die "image absente : $1"; }

# ---- temps restant dans la fenetre ----
END_EPOCH=""
remaining_min() { echo $(( (END_EPOCH - $(date -u +%s)) / 60 )); }
need_minutes() {  # $1 minutes necessaires, $2 etape
  [ -n "$END_EPOCH" ] || return 0
  local r; r=$(remaining_min)
  if [ "$r" -lt "$1" ]; then
    echo "ARRET : temps restant insuffisant dans la fenetre ($r min < $1 min requis avant : $2). Etat laisse inchange a ce stade."
    poll_stop; exit 4
  fi
  echo "  [temps] $r min restantes (>= $1 requis avant : $2)"
}

echo "===== 0. PRE-CONTROLES ($(date -u +%FT%TZ)) ====="
for n in backend worker beat; do
  S=$(docker inspect -f '{{.State.Status}} {{.Config.Image}}' kafundo-$n 2>/dev/null) || die "kafundo-$n introuvable"
  echo "  kafundo-$n : $S"; case "$S" in running*) ;; *) die "kafundo-$n ne tourne pas" ;; esac
done
img_ok "kafundo-backend:$TAG"; img_ok "kafundo-celery-worker:$TAG"; img_ok "kafundo-celery-beat:$TAG"
# le cron hote `docker image prune -af --filter until=24h` (00:33 UTC) supprime toute image non referencee de plus de 24 h
CREATED=$(docker image inspect -f '{{.Created}}' "kafundo-backend:$TAG" 2>/dev/null)
CREATED_EPOCH=$(date -u -d "${CREATED%%.*} UTC" +%s 2>/dev/null) || die "date de creation de l'image illisible : '$CREATED'"
AGE_H=$(( ($(date -u +%s) - CREATED_EPOCH) / 3600 ))
echo "  age des images $TAG : ${AGE_H} h (le prune quotidien de 00:33 UTC supprime les images non utilisees de plus de 24 h)"
[ "${AGE_H:-99}" -lt 20 ] || die "images trop anciennes (${AGE_H} h) : les reconstruire le jour de l'intervention"
for n in backend worker beat; do docker container inspect kafundo-$n-prev >/dev/null 2>&1 && echo "  retour arriere existant : kafundo-$n-prev ($(docker inspect -f '{{.Config.Image}}' kafundo-$n-prev))"; done
REV=$(pg -c "select version_num from alembic_version")
echo "  revision actuelle : $REV ; PostgreSQL : $(pg -c 'show server_version') ; sante : $(docker inspect -f '{{.State.Health.Status}}' "$PG")"
[ "$REV" = "$PREV_REV" ] || die "revision $REV (attendue $PREV_REV)"
echo "  /api/ready avant : $(ready)"
CONN=$(pg -c "select count(*) from pg_stat_activity where datname=current_database() and pid<>pg_backend_pid()")
LONG=$(pg -c "select count(*) from pg_stat_activity where datname=current_database() and pid<>pg_backend_pid() and state<>'idle' and now()-xact_start > interval '30 seconds'")
echo "  connexions : $CONN ; operations > 30 s : $LONG"; [ "$LONG" = 0 ] || die "operation longue en cours"
ACTIVE=$(docker exec -i -e PYTHONPATH=/app kafundo-worker python - <<'PY' 2>/dev/null | tail -1
from app.tasks.celery_app import celery_app
i = celery_app.control.inspect(timeout=3)
a = sum(len(v) for v in (i.active() or {}).values()); r = sum(len(v) for v in (i.reserved() or {}).values())
c = celery_app.connection_for_read().default_channel.client
print(a, r, sum(c.llen(q) for q in ("default", "collect", "alerts")))
PY
)
echo "  taches Celery actives / reservees / en file : $ACTIVE"
[ "$ACTIVE" = "0 0 0" ] || die "taches Celery en cours ou en attente (attendre la fin de la collecte)"
FIRST=$(pg -c "select count(*) from device_archive_log"); DEV=$(pg -c "select count(*) from devices")
ORPH=$(pg -c "select count(*) from device_archive_log l left join devices d on d.id=l.device_id where d.id is null")
echo "  fiches : $DEV ; journal : $FIRST ; orphelins : $ORPH"; [ "$ORPH" = 0 ] || die "lignes de journal orphelines"
DISK=$(df -BG --output=avail "$DF_PATH" | tail -1 | tr -dc '0-9'); echo "  espace libre $DF_PATH : ${DISK} Go"; [ "$DISK" -ge 3 ] || die "espace disque insuffisant"
CAP=$(docker exec finnovatix-platform-app-1 sh -c 'grep -E "^KAFUNDO_SYNC_CREATE_CAP=" /var/www/html/.env | cut -d= -f2' 2>/dev/null || true)
echo "  KAFUNDO_SYNC_CREATE_CAP (Finnovatix, lecture) : ${CAP:-n/a}"
H=$(date -u +%H:%M); echo "  heure UTC $H"
if [ "$APPLY" = 0 ]; then
  echo ""; echo "(simulation) pre-controles OK. Aucune ecriture. Pour executer : WINDOW_FROM=... WINDOW_TO=... IMAGE_TAG=$TAG bash $0 --apply"; exit 0
fi

# ---- fenetre autorisee par le proprietaire : WINDOW_FROM / WINDOW_TO au format YYYY-MM-DDTHH:MM (UTC), OBLIGATOIRES ----
# (surcharge de secours : WINDOW_OVERRIDE=1, uniquement avec un nouvel accord explicite ; les controles de temps sont alors ignores)
NOWSTAMP=$(date -u +%Y-%m-%dT%H:%M)
if [ "${WINDOW_OVERRIDE:-0}" != 1 ]; then
  [ -n "${WINDOW_FROM:-}" ] && [ -n "${WINDOW_TO:-}" ] || die "WINDOW_FROM et WINDOW_TO requis avec --apply (fenetre autorisee, UTC)"
  [[ "$NOWSTAMP" > "$WINDOW_FROM" || "$NOWSTAMP" == "$WINDOW_FROM" ]] && [[ "$NOWSTAMP" < "$WINDOW_TO" ]] \
    || die "hors de la fenetre autorisee ($WINDOW_FROM -> $WINDOW_TO UTC) : $NOWSTAMP"
  END_EPOCH=$(date -u -d "${WINDOW_TO/T/ }:00 UTC" +%s) || die "WINDOW_TO illisible : $WINDOW_TO"
  need_minutes "$MIN_START_MIN" "demarrage de l'intervention"
fi

poll_start
echo ""; echo "===== 1. SAUVEGARDE VERIFIEE ====="
B="$LOG_DIR/pre_c8e1_migration_${TS}.dump"
docker exec "$PG" pg_dump -U "$PGU" -d "$PGDB" -Fc > "$B" || { poll_stop; die "pg_dump"; }
sha256sum "$B" > "$B.sha256"; chmod 600 "$B" "$B.sha256"
TOC=$(docker exec -i "$PG" pg_restore --list < "$B" | wc -l)
echo "  $(basename "$B") $(stat -c %s "$B") octets, sommaire $TOC entrees"; [ "$TOC" -gt 200 ] || { poll_stop; die "sauvegarde suspecte"; }
sha256sum -c "$B.sha256" >/dev/null || { poll_stop; die "sha256"; }
echo "  (restauration testee en preparation sur base jetable : migration_prevalidation.sh)"

echo ""; echo "===== 2. IMAGES COMPATIBLES (backend, worker, beat) ====="
need_minutes "$MIN_SWAP_MIN" "remplacement des conteneurs"
# les -prev actuels sont conserves sous un nom date pour laisser la place au nouveau retour arriere
for n in backend worker beat; do
  if docker container inspect kafundo-$n-prev >/dev/null 2>&1; then
    docker rename kafundo-$n-prev "kafundo-$n-prev-before-$TS" && echo "  kafundo-$n-prev -> kafundo-$n-prev-before-$TS"
  fi
done
$SWAP swap kafundo-backend --image "kafundo-backend:$TAG" --health "curl -fsS http://localhost:8000/api/health" --wait 120 --stop-timeout 15 | tail -2
[ "${PIPESTATUS[0]}" = 0 ] || { poll_stop; die "swap backend (retour automatique effectue)"; }
echo "  /api/ready : $(ready)"
$SWAP swap kafundo-worker --image "kafundo-celery-worker:$TAG" --wait 90 --stop-timeout 60 | tail -2
[ "${PIPESTATUS[0]}" = 0 ] || { poll_stop; rollback_hint; die "swap worker"; }
$SWAP swap kafundo-beat --image "kafundo-celery-beat:$TAG" --wait 60 --stop-timeout 20 | tail -2
[ "${PIPESTATUS[0]}" = 0 ] || { poll_stop; rollback_hint; die "swap beat"; }
sleep "$POST_SWAP_SLEEP"
BEAT_FIRED=$(docker logs kafundo-beat 2>&1 | grep -c 'Sending due task')
echo "  beat : taches lancees au demarrage = $BEAT_FIRED (attendu 0)"
echo "  /api/ready apres images : $(ready)  (attendu 200 $PREV_REV)"
gate "beat n'a lance aucune tache" '[ "$BEAT_FIRED" = 0 ]'
gate "/api/ready = 200 sur la revision precedente" '[ "$(ready)" = "200 $PREV_REV" ]'
gate "worker repond (ping Celery)" 'docker exec kafundo-worker python -c "from app.tasks.celery_app import celery_app as a; import sys; sys.exit(0 if a.control.inspect(timeout=5).ping() else 1)"'
gate "aucune erreur dans les journaux backend/worker/beat (3 min)" '[ "$(for n in backend worker beat; do docker logs --since 3m kafundo-$n 2>&1; done | grep -ciE "traceback|critical")" = 0 ]'
gate "images attendues en service" '[ "$(docker inspect -f "{{.Config.Image}}" kafundo-backend kafundo-worker kafundo-beat | grep -c ":$TAG")" = 3 ]'

echo ""; echo "===== 3. MIGRATION $HEAD_REV ====="
need_minutes "$MIN_MIGRATE_MIN" "migration du schema"
T0=$(date +%s)
$SWAP run-once --image "kafundo-backend:$TAG" kafundo-backend -- python -m migrations.upgrade --backup-confirmed 2>&1 | tail -4
REV2=$(pg -c "select version_num from alembic_version")
echo "  revision : $REV2 (duree $(( $(date +%s) - T0 )) s)"
if [ "$REV2" != "$HEAD_REV" ]; then
  echo "ECHEC de la migration : transaction annulee, schema inchange ($REV2). Images deja deployees (compatibles)."
  echo "  Rien a defaire cote schema. Retour des images si souhaite :"; rollback_hint
  poll_stop; exit 2
fi

echo ""; echo "===== 4. CONTROLES POST-MIGRATION ====="
FKS=$(pg -c "select string_agg(confdeltype::text, '' order by conname) from pg_constraint where contype='f' and conrelid='device_archive_log'::regclass and confrelid='devices'::regclass")
DEV2=$(pg -c 'select count(*) from devices'); LOG2=$(pg -c 'select count(*) from device_archive_log')
ARCH2=$(pg -c "select count(*) from devices where validation_status='archived'")
echo "  cles etrangeres : $FKS (attendu rr) ; fiches : $DEV2 (avant $DEV) ; journal : $LOG2 (avant $FIRST) ; archivees : $ARCH2"
echo "  /api/ready : $(ready)  (attendu 200 $HEAD_REV)"
PAG=$(python3 - <<'PY'
import json, os, urllib.request
base = os.environ["API_BASE"]
def get(u):
    with urllib.request.urlopen(base + u, timeout=60) as r: return json.load(r)
ids, page, total = [], 1, 0
while True:
    d = get(f"/api/v1/devices/?page={page}&page_size=100"); it = d["items"]
    if not it: break
    ids += [i["id"] for i in it]; total = d["total"]; page += 1
print(f"{total} {len(ids)} {len(set(ids))}")
PY
)
echo "  pagination (total lignes distincts) : $PAG"
QUEUES=$(docker exec -i -e PYTHONPATH=/app kafundo-worker python - <<'PY' 2>/dev/null | tail -1
from app.tasks.celery_app import celery_app
c = celery_app.connection_for_read().default_channel.client
print(*[c.llen(q) for q in ("celery", "default", "collect", "alerts")])
PY
)
echo "  files Celery (celery default collect alerts) : $QUEUES"
ERRS=$(for n in backend worker beat; do docker logs --since 5m kafundo-$n 2>&1; done | grep -ciE 'traceback|critical')
echo "  erreurs de journaux (5 min) : $ERRS"
poll_stop
BAD=0
[ "$FKS" = "rr" ] || { echo "ANOMALIE : cles etrangeres"; BAD=1; }
[ "$DEV2" = "$DEV" ] && [ "$LOG2" = "$FIRST" ] || { echo "ANOMALIE : comptes modifies"; BAD=1; }
[ "$ARCH2" = 0 ] || { echo "ANOMALIE : fiches archivees"; BAD=1; }
[ "$(ready)" = "200 $HEAD_REV" ] || { echo "ANOMALIE : /api/ready"; BAD=1; }
set -- $PAG; [ "${1:-x}" = "${2:-y}" ] && [ "${2:-y}" = "${3:-z}" ] || { echo "ANOMALIE : pagination"; BAD=1; }
[ "$ERRS" = 0 ] || { echo "ANOMALIE : erreurs de journaux a examiner"; BAD=1; }
echo ""
if [ "$BAD" = 0 ]; then echo "RESULTAT : MIGRATION APPLIQUEE ET CONTROLEE (revision $HEAD_REV)"; else echo "RESULTAT : ANOMALIE(S) - NE PAS POURSUIVRE, appliquer le retour arriere adapte :"; fi
echo ""
echo "ROLLBACK :"
echo "  schema seul   : $SWAP run-once --image kafundo-backend:$TAG kafundo-backend -- python -m alembic downgrade $PREV_REV   (le code accepte les deux revisions)"
echo "  images        : $SWAP rollback kafundo-beat ; $SWAP rollback kafundo-worker ; $SWAP rollback kafundo-backend"
echo "  restauration  : pg_restore du dump $B dans une base neuve, puis bascule (derniere extremite)"
echo "Suite : controle des collecteurs apres la fenetre -> bash $0 --followup"
echo "journal : $LOG"
exit $BAD
