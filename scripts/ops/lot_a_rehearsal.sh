#!/usr/bin/env bash
# Repetition COMPLETE du premier sous-lot du lot A sur une COPIE JETABLE (kafundo-iso-pg) : plan reproductible, archivage,
# controles (fiches, journal, API, collecteurs), restauration exacte. Aucune ecriture en production (pg_restore dans la base
# jetable ; la base de production n'est lue qu'au travers de la sauvegarde).
#   IMAGE=kafundo-backend:fixes3-78822f6 DUMP=/opt/finveille-backups/pre_c8e1_migration_<ts>.dump \
#   PROTECT=/opt/finveille-backups/audit_20261012_lotA/protect_for_apply.txt EXPECT_HASH=<empreinte> bash lot_a_rehearsal.sh
set -uo pipefail
umask 077
IMAGE="${IMAGE:?}"; DUMP="${DUMP:?}"; PROTECT="${PROTECT:?}"; EXPECT_HASH="${EXPECT_HASH:-}"; LIMIT="${LIMIT:-50}"
ISO="${ISO:-kafundo-iso-pg}"; ISO_USER="${ISO_USER:-isouser}"; NET="${NET:-kafundo-iso-net}"
DB="lota_rehearsal_$(date -u +%Y%m%dt%H%M%S)"; RUN="REHEARSAL-A1"
fail=0; say() { echo "$*"; }
check() { if eval "$2"; then say "  [OK]    $1"; else say "  [ECHEC] $1"; fail=1; fi; }
ISO_PW="$(docker exec "$ISO" printenv POSTGRES_PASSWORD)"; SECRET_TMP="$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)"
iso() { local d="$1"; shift; docker exec "$ISO" psql -U "$ISO_USER" -d "$d" -At -F'|' -v ON_ERROR_STOP=1 "$@"; }
envs() { echo "-e DATABASE_URL=postgresql+asyncpg://${ISO_USER}:${ISO_PW}@${ISO}:5432/${DB} -e DATABASE_SYNC_URL=postgresql://${ISO_USER}:${ISO_PW}@${ISO}:5432/${DB} -e SECRET_KEY=${SECRET_TMP} -e REDIS_URL=redis://:x@127.0.0.1:1/0 -e REDIS_PASSWORD=x -e ENVIRONMENT=test"; }
cleanup() { docker rm -f lota-api >/dev/null 2>&1; docker exec "$ISO" psql -U "$ISO_USER" -d postgres -qc "DROP DATABASE IF EXISTS ${DB} WITH (FORCE)" >/dev/null 2>&1; }
trap cleanup EXIT
cli() { docker run --rm --network "$NET" $(envs) -w /app -e PYTHONPATH=/app -v "$PROTECT:/protect.txt:ro" --entrypoint python "$IMAGE" -m app.data.catalog_cleanup "$@" 2>&1 | sed "s/${ISO_PW}/***/g"; }

say "===== 1. Restauration de la sauvegarde dans une base jetable ====="
docker exec "$ISO" psql -U "$ISO_USER" -d postgres -qc "CREATE DATABASE ${DB}" >/dev/null
docker exec -i "$ISO" pg_restore -U "$ISO_USER" -d "$DB" --no-owner --no-privileges < "$DUMP" 2>&1 | head -3
say "  fiches : $(iso "$DB" -c 'select count(*) from devices') ; revision : $(iso "$DB" -c 'select version_num from alembic_version')"
snap() { iso "$DB" -c "select md5(string_agg(concat_ws('~', id, validation_status, status, coalesce(ai_rewrite_status,''), coalesce(user_quality_decision,''), coalesce(tags::text,''), title), '|' order by id)) from devices where id::text = any(string_to_array('$1', ','))"; }
state_all() { iso "$DB" -c "select md5(string_agg(concat_ws('~', id, validation_status, status, coalesce(ai_rewrite_status,''), coalesce(user_quality_decision,''), title), '|' order by id)) from devices"; }

say ""; say "===== 2. Plan (meme fichier de protection que la production) ====="
OUTP=$(cli plan --protect-file /protect.txt)
HASH=$(echo "$OUTP" | python3 -c "
import json, sys
t = sys.stdin.read(); d = json.loads(t[t.index('{'):])
print(d['batches']['A_projets_institutionnels']['fingerprint'], d['batches']['A_projets_institutionnels']['count'])")
say "  lot A : empreinte/effectif = $HASH"
FP=${HASH% *}; N=${HASH#* }
[ -z "$EXPECT_HASH" ] || check "empreinte identique a celle de la production ($EXPECT_HASH)" "[ '$FP' = '$EXPECT_HASH' ]"
# les LIMIT premieres fiches du lot, dans l'ordre du plan
IDS=$(docker run --rm --network "$NET" $(envs) -w /app -e PYTHONPATH=/app -v "$PROTECT:/protect.txt:ro" --entrypoint python "$IMAGE" -c "
import asyncio
from pathlib import Path
from app.database import AsyncSessionLocal
from app.services.catalog_cleanup import build_plan, load_rows, BATCH_A
async def m():
    prot = {l.strip() for l in Path('/protect.txt').read_text().splitlines() if l.strip()}
    async with AsyncSessionLocal() as db:
        plan = build_plan(await load_rows(db), prot)
        print(','.join(str(i) for i in plan.ids(BATCH_A)[:$LIMIT]))
asyncio.run(m())" 2>/dev/null | tail -1)
say "  premier sous-lot : $(echo "$IDS" | tr ',' '\n' | wc -l) fiches"
BEFORE_ALL=$(state_all); BEFORE_SUB=$(snap "$IDS")
JOURNAL0=$(iso "$DB" -c "select count(*) from device_archive_log")
DEV0=$(iso "$DB" -c "select count(*) from devices")

say ""; say "===== 3. Simulation puis archivage du sous-lot (copie) ====="
cli apply --batch A_projets_institutionnels --plan-hash "$FP" --run-id "$RUN" --backup-ref rehearsal --limit "$LIMIT" --protect-file /protect.txt | tail -12 | sed 's/^/   /'
check "la simulation n'a rien ecrit" "[ \"\$(iso $DB -c \"select count(*) from devices where validation_status='archived'\")\" = 0 ]"
cli apply --batch A_projets_institutionnels --plan-hash "$FP" --run-id "$RUN" --backup-ref rehearsal --limit "$LIMIT" --protect-file /protect.txt --yes | tail -14 | sed 's/^/   /'
ARCH=$(iso "$DB" -c "select count(*) from devices where validation_status='archived'")
check "$LIMIT fiches archivees" "[ '$ARCH' = '$LIMIT' ]"
check "fiches totales inchangees ($DEV0)" "[ \"\$(iso $DB -c 'select count(*) from devices')\" = '$DEV0' ]"
check "journal : +$LIMIT lignes (action=archive)" "[ \"\$(iso $DB -c \"select count(*) from device_archive_log where run_id='$RUN' and action='archive'\")\" = '$LIMIT' ]"
check "aucune fiche supprimee" "[ \"\$(iso $DB -c 'select count(*) from devices')\" = '$DEV0' ]"
check "seules les fiches du sous-lot ont change" "[ \"\$(iso $DB -c \"select count(*) from devices where validation_status='archived' and id::text <> all(string_to_array('$IDS', ','))\")\" = 0 ]"

say ""; say "===== 4. API et collecteurs sur la copie archivee ====="
docker run -d --name lota-api --network "$NET" $(envs) -w /app -e PYTHONPATH=/app --entrypoint python "$IMAGE" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >/dev/null
for i in $(seq 1 40); do docker exec lota-api python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)" >/dev/null 2>&1 && break; sleep 2; done
FIRST=$(echo "$IDS" | cut -d, -f1)
docker exec -i -e FIRST="$FIRST" lota-api python - <<'PY' 2>&1 | sed 's/^/  /'
import json, os, urllib.request, urllib.error
def get(u):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000" + u, timeout=60) as r: return r.status, json.load(r)
    except urllib.error.HTTPError as e: return e.code, None
print("ready:", get("/api/ready")[1])
ids, page, total = [], 1, 0
while True:
    s, d = get(f"/api/v1/devices/?page={page}&page_size=100"); it = d["items"]
    if not it: break
    ids += [i["id"] for i in it]; total = d["total"]; page += 1
print(f"pagination: total={total} lignes={len(ids)} distincts={len(set(ids))}")
s, _ = get("/api/v1/devices/" + os.environ["FIRST"]); print("detail d'une fiche archivee (public) :", s)
PY
CNT=$(iso "$DB" -c "select count(*) from devices")
docker exec -i -e PYTHONPATH=/app -e FIRST="$FIRST" lota-api python - <<'PY' 2>&1 | grep -v "^$" | tail -6 | sed 's/^/  /'
import asyncio, os
from sqlalchemy import text
from app.tasks import collect_tasks as ct
async def main():
    async with ct._fresh_db() as db:
        row = (await db.execute(text("select s.id, s.name from sources s join devices d on d.source_id = s.id where d.id::text = :i"), {"i": os.environ["FIRST"]})).first()
        before = (await db.execute(text("select count(*) from devices where validation_status='archived'"))).scalar()
    print("source de la fiche archivee :", row[1])
    try:
        await ct._collect_source_async(str(row[0])); print("collecte : OK")
    except Exception as exc:
        print("collecte : ERREUR", type(exc).__name__, str(exc)[:100])
    async with ct._fresh_db() as db:
        after = (await db.execute(text("select count(*) from devices where validation_status='archived'"))).scalar()
        tot = (await db.execute(text("select count(*) from devices"))).scalar()
    print(f"archivees avant/apres collecte : {before}/{after} ; fiches : {tot}")
asyncio.run(main())
PY
docker rm -f lota-api >/dev/null 2>&1

say ""; say "===== 5. Restauration du run $RUN ====="
cli restore --run-id "$RUN" | tail -5 | sed 's/^/   /'
cli restore --run-id "$RUN" --yes | tail -6 | sed 's/^/   /'
check "plus aucune fiche archivee" "[ \"\$(iso $DB -c \"select count(*) from devices where validation_status='archived'\")\" = 0 ]"
AFTER_SUB=$(snap "$IDS"); AFTER_ALL=$(state_all)
check "valeurs du sous-lot restituees a l'identique (statut, IA, qualite, tags, titre)" "[ '$BEFORE_SUB' = '$AFTER_SUB' ]"
check "empreinte de TOUT le catalogue (hors dates) identique a l'avant-archivage" "[ '$BEFORE_ALL' = '$AFTER_ALL' ]"
check "journal conserve : lignes marquees restaurees" "[ \"\$(iso $DB -c \"select count(*) from device_archive_log where run_id='$RUN' and restored_at is not null\")\" = '$LIMIT' ]"
say ""
[ $fail = 0 ] && say "RESULTAT : REPETITION REUSSIE (base jetable ${DB} supprimee ; production non modifiee)" || say "RESULTAT : AU MOINS UN ECHEC"
exit $fail
