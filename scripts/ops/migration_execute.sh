#!/usr/bin/env bash
# Deploiement controle de la migration Alembic c8e1f4a7b2d9 : images compatibles puis migration, avec controles et plan de
# retour arriere. SIMULATION (controles seuls) par defaut ; --apply exige l'accord du proprietaire et la confirmation MIGRATE.
#
#   IMAGE_TAG=fixes3-<sha> bash migration_execute.sh            # pre-controles, n'ecrit RIEN
#   IMAGE_TAG=fixes3-<sha> bash migration_execute.sh --apply
#
# Sequence (--apply) :
#   0. pre-controles   1. sauvegarde verifiee   2. images (backend, worker, beat) -> acceptent b7d3 ET c8e1 : /api/ready reste 200
#   3. migration (transactionnelle, lock_timeout 10 s)   4. controles post-migration   5. consignes de retour arriere
# Aucune suppression de conteneur : les anciens restent en `-prev` (voir ROLLBACK ci-dessous).
set -uo pipefail
umask 077
HERE="$(dirname "$(readlink -f "$0")")"
TAG="${IMAGE_TAG:?IMAGE_TAG requis (ex. fixes3-2b479ed)}"
PREV_REV="b7d3a91c5e24"; HEAD_REV="c8e1f4a7b2d9"
PG="${PG:-kafundo-postgres}"; PGU="${PGU:-finveille}"; PGDB="${PGDB:-finveille}"
SWAP="python3 $HERE/swap_container.py"
APPLY=0; [ "${1:-}" = "--apply" ] && APPLY=1
if [ "${1:-}" = "--followup" ]; then   # controle des collecteurs apres la fenetre (lecture seule)
  echo "===== SUIVI POST-MIGRATION ($(date -u +%FT%TZ)) ====="
  echo "  revision : $(docker exec -i "$PG" psql -U "$PGU" -d "$PGDB" -At -c 'select version_num from alembic_version')"
  echo "  collectes des 60 dernieres minutes (statut:nombre) : $(docker exec -i "$PG" psql -U "$PGU" -d "$PGDB" -At -c "select coalesce(string_agg(status||':'||n, ' '), 'aucune') from (select status, count(*) n from collection_logs where started_at > now() - interval '60 minutes' group by 1) t")"
  echo "  taches planifiees recues (60 min) : $(docker logs --since 60m kafundo-beat 2>&1 | grep -c 'Sending due task')"
  echo "  erreurs de journaux (60 min) : backend=$(docker logs --since 60m kafundo-backend 2>&1 | grep -ciE 'traceback|critical') worker=$(docker logs --since 60m kafundo-worker 2>&1 | grep -ciE 'traceback|critical') beat=$(docker logs --since 60m kafundo-beat 2>&1 | grep -ciE 'traceback|critical')"
  echo "  fiches : $(docker exec -i "$PG" psql -U "$PGU" -d "$PGDB" -At -c "select count(*) from devices") ; archivees : $(docker exec -i "$PG" psql -U "$PGU" -d "$PGDB" -At -c "select count(*) from devices where validation_status='archived'")"
  exit 0
fi
TS=$(date -u +%Y%m%dT%H%M%SZ); LOG="/opt/finveille-backups/migration_execute_${TS}.log"
exec > >(tee -a "$LOG") 2>&1
die() { echo "ARRET: $*" >&2; exit 1; }
pg() { docker exec -i "$PG" psql -U "$PGU" -d "$PGDB" -At -F'|' "$@"; }
ready() { python3 - <<'PY'
import json, urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:8000/api/ready", timeout=5) as r: d = json.load(r); print(200, d.get("schema_revision"))
except urllib.error.HTTPError as e: print(e.code, "-")
except Exception as e: print("ERR", type(e).__name__)
PY
}
POLL_LOG=""
poll_start() { POLL_LOG="$(mktemp)"; ( while true; do
    c=$(python3 - <<'PY'
import urllib.request
try:
    print(urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2).status)
except Exception:
    print(0)
PY
); echo "$(date +%s.%N) $c" >> "$POLL_LOG"; sleep 0.5; done ) & POLL_PID=$!; }
poll_stop() { kill "$POLL_PID" 2>/dev/null; wait "$POLL_PID" 2>/dev/null
  python3 - "$POLL_LOG" <<'PY'
import sys
rows = [l.split() for l in open(sys.argv[1]) if l.strip()]
down = [(float(t), c) for t, c in rows if c != "200"]
total = 0.0; runs = 0; prev = None
for i, (t, c) in enumerate(rows):
    if c != "200":
        nxt = float(rows[i + 1][0]) if i + 1 < len(rows) else t + 0.5
        total += nxt - float(t)
        if prev is None or float(t) - prev > 1.5: runs += 1
        prev = float(t)
print(f"  indisponibilite mesuree de /api/health : {total:.1f} s en {runs} interruption(s) ({len(rows)} sondages sur {float(rows[-1][0]) - float(rows[0][0]):.0f} s)")
PY
  rm -f "$POLL_LOG"; }
gate() { echo "  [controle] $1"; shift; if ! eval "$*"; then echo "ARRET : controle bloquant en echec -> procedure interrompue, aucune etape suivante."; echo "  Rollback images : $SWAP rollback kafundo-beat ; $SWAP rollback kafundo-worker ; $SWAP rollback kafundo-backend"; poll_stop; exit 3; fi; }
img_ok() { docker image inspect "$1" >/dev/null 2>&1 || die "image absente : $1"; }

echo "===== 0. PRE-CONTROLES ($(date -u +%FT%TZ)) ====="
for n in backend worker beat; do
  S=$(docker inspect -f '{{.State.Status}} {{.Config.Image}}' kafundo-$n 2>/dev/null) || die "kafundo-$n introuvable"
  echo "  kafundo-$n : $S"; case "$S" in running*) ;; *) die "kafundo-$n ne tourne pas" ;; esac
done
img_ok "kafundo-backend:$TAG"; img_ok "kafundo-celery-worker:$TAG"; img_ok "kafundo-celery-beat:$TAG"
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
DISK=$(df -BG --output=avail /opt | tail -1 | tr -dc '0-9'); echo "  espace libre /opt : ${DISK} Go"; [ "$DISK" -ge 3 ] || die "espace disque insuffisant"
CAP=$(docker exec finnovatix-platform-app-1 sh -c 'grep -E "^KAFUNDO_SYNC_CREATE_CAP=" /var/www/html/.env | cut -d= -f2' 2>/dev/null || true)
echo "  KAFUNDO_SYNC_CREATE_CAP (Finnovatix, lecture) : ${CAP:-n/a}"
H=$(date -u +%H:%M); echo "  heure UTC $H (creneau recommande 21:15-21:45)"
if [ "$APPLY" = 0 ]; then
  echo ""; echo "(simulation) pre-controles OK. Aucune ecriture. Pour executer : IMAGE_TAG=$TAG bash $0 --apply"; exit 0
fi

# fenetre autorisee par le proprietaire : dimanche 11/10/2026 21:15-21:45 UTC (surcharge : WINDOW_OVERRIDE=1, autre accord requis)
NOWSTAMP=$(date -u +%Y-%m-%dT%H:%M)
if [ "${WINDOW_OVERRIDE:-0}" != 1 ]; then
  [[ "$NOWSTAMP" > "2026-10-11T21:14" && "$NOWSTAMP" < "2026-10-11T21:46" ]] || die "hors de la fenetre autorisee (2026-10-11 21:15-21:45 UTC) : $NOWSTAMP"
fi
read -rp "Tapez MIGRATE pour executer sur la PRODUCTION : " c; [ "$c" = MIGRATE ] || die "confirmation absente"

poll_start
echo ""; echo "===== 1. SAUVEGARDE VERIFIEE ====="
B="/opt/finveille-backups/pre_c8e1_migration_${TS}.dump"
docker exec "$PG" pg_dump -U "$PGU" -d "$PGDB" -Fc > "$B" || die "pg_dump"
sha256sum "$B" > "$B.sha256"; chmod 600 "$B" "$B.sha256"
TOC=$(docker exec -i "$PG" pg_restore --list < "$B" | wc -l)
echo "  $(basename "$B") $(stat -c %s "$B") octets, sommaire $TOC entrees"; [ "$TOC" -gt 200 ] || die "sauvegarde suspecte"
sha256sum -c "$B.sha256" >/dev/null || die "sha256"
echo "  (restauration testee en preparation sur base jetable : migration_prevalidation.sh)"

echo ""; echo "===== 2. IMAGES COMPATIBLES (backend, worker, beat) ====="
# les -prev actuels sont conserves sous un nom daté pour laisser la place au nouveau retour arriere
for n in backend worker beat; do
  if docker container inspect kafundo-$n-prev >/dev/null 2>&1; then
    docker rename kafundo-$n-prev "kafundo-$n-prev-before-$TS" && echo "  kafundo-$n-prev -> kafundo-$n-prev-before-$TS"
  fi
done
$SWAP swap kafundo-backend --image "kafundo-backend:$TAG" --health "curl -fsS http://localhost:8000/api/health" --wait 120 --stop-timeout 15 | tail -2 || die "swap backend (retour automatique effectue)"
echo "  /api/ready : $(ready)"
$SWAP swap kafundo-worker --image "kafundo-celery-worker:$TAG" --wait 90 --stop-timeout 60 | tail -2 || die "swap worker"
$SWAP swap kafundo-beat --image "kafundo-celery-beat:$TAG" --wait 60 --stop-timeout 20 | tail -2 || die "swap beat"
sleep 8
BEAT_FIRED=$(docker logs kafundo-beat 2>&1 | grep -c 'Sending due task')
echo "  beat : taches lancees au demarrage = $BEAT_FIRED (attendu 0)"
echo "  /api/ready apres images : $(ready)  (attendu 200 $PREV_REV)"
gate "beat n'a lance aucune tache" '[ "$BEAT_FIRED" = 0 ]'
gate "/api/ready = 200 sur la revision precedente" '[ "$(ready)" = "200 $PREV_REV" ]'
gate "worker repond (ping Celery)" 'docker exec -i -e PYTHONPATH=/app kafundo-worker python -c "from app.tasks.celery_app import celery_app as a; import sys; sys.exit(0 if a.control.inspect(timeout=5).ping() else 1)"'
gate "aucune erreur dans les journaux backend/worker/beat (3 min)" '[ "$(for n in backend worker beat; do docker logs --since 3m kafundo-$n 2>&1; done | grep -ciE "traceback|critical")" = 0 ]'
gate "images attendues en service" '[ "$(docker inspect -f "{{.Config.Image}}" kafundo-backend kafundo-worker kafundo-beat | grep -c ":$TAG")" = 3 ]'

echo ""; echo "===== 3. MIGRATION $HEAD_REV ====="
T0=$(date +%s)
$SWAP run-once --image "kafundo-backend:$TAG" kafundo-backend -- python -m migrations.upgrade --backup-confirmed 2>&1 | tail -4
REV2=$(pg -c "select version_num from alembic_version")
echo "  revision : $REV2 (duree $(( $(date +%s) - T0 )) s)"
if [ "$REV2" != "$HEAD_REV" ]; then
  echo "ECHEC de la migration : transaction annulee, schema inchange ($REV2). Images deja deployees (compatibles)."
  echo "  Rien a defaire cote schema. Retour des images si souhaite : $SWAP rollback kafundo-beat ; $SWAP rollback kafundo-worker ; $SWAP rollback kafundo-backend"
  poll_stop; exit 2
fi

echo ""; echo "===== 4. CONTROLES POST-MIGRATION ====="
FKS=$(pg -c "select string_agg(confdeltype::text, '' order by conname) from pg_constraint where contype='f' and conrelid='device_archive_log'::regclass and confrelid='devices'::regclass")
DEV2=$(pg -c 'select count(*) from devices'); LOG2=$(pg -c 'select count(*) from device_archive_log')
ARCH2=$(pg -c "select count(*) from devices where validation_status='archived'")
echo "  cles etrangeres : $FKS (attendu rr) ; fiches : $DEV2 (avant $DEV) ; journal : $LOG2 (avant $FIRST) ; archivees : $ARCH2"
echo "  /api/ready : $(ready)  (attendu 200 $HEAD_REV)"
PAG=$(python3 - <<'PY'
import json, urllib.request
def get(u):
    with urllib.request.urlopen("http://127.0.0.1:8000" + u, timeout=60) as r: return json.load(r)
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
set -- $PAG; [ "$1" = "$2" ] && [ "$2" = "$3" ] || { echo "ANOMALIE : pagination"; BAD=1; }
[ "$ERRS" = 0 ] || { echo "ANOMALIE : erreurs de journaux a examiner"; BAD=1; }
echo ""
if [ "$BAD" = 0 ]; then echo "RESULTAT : MIGRATION APPLIQUEE ET CONTROLEE (revision $HEAD_REV)"; else echo "RESULTAT : ANOMALIE(S) - NE PAS POURSUIVRE, appliquer le retour arriere adapte :"; fi
echo ""
echo "ROLLBACK :"
echo "  schema seul   : $SWAP run-once --image kafundo-backend:$TAG kafundo-backend -- python -m alembic downgrade $PREV_REV   (le code accepte les deux revisions)"
echo "  images        : $SWAP rollback kafundo-beat ; $SWAP rollback kafundo-worker ; $SWAP rollback kafundo-backend"
echo "  restauration  : pg_restore du dump $B dans une base neuve, puis bascule (derniere extremite)"
echo "Suite : controle des collecteurs apres 22:05 UTC -> bash $0 --followup"
echo "journal : $LOG"
exit $BAD
