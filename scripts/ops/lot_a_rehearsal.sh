#!/usr/bin/env bash
# Repetition COMPLETE d'un sous-lot du lot A (50 ou 200 fiches) sur une COPIE JETABLE (kafundo-iso-pg) : plan reproductible,
# archivage, controles (fiches, journal, ai_hold, protections, API, collecteurs), restauration ciblee puis complete avec retour a
# l'empreinte initiale. Aucune ecriture en production (pg_restore dans la base jetable).
#   IMAGE=kafundo-backend:fixes3-78822f6 DUMP=/opt/finveille-backups/<dump>.dump PROTECT=<protect_for_apply.txt> \
#   LIMIT=200 EXPECT_HASH=<empreinte> EXPECT_IDS=<ids.txt> PRIOR_IDS=<ids deja archives.txt> bash lot_a_rehearsal.sh
set -uo pipefail
umask 077
IMAGE="${IMAGE:?}"; DUMP="${DUMP:?}"; PROTECT="${PROTECT:?}"; EXPECT_HASH="${EXPECT_HASH:-}"; LIMIT="${LIMIT:-50}"
EXPECT_IDS="${EXPECT_IDS:-}"; PRIOR_IDS="${PRIOR_IDS:-}"
ISO="${ISO:-kafundo-iso-pg}"; ISO_USER="${ISO_USER:-isouser}"; NET="${NET:-kafundo-iso-net}"
DB="lota_rehearsal_$(date -u +%Y%m%dt%H%M%S)"; RUN="REHEARSAL-A${LIMIT}"
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
say "  fiches : $(iso "$DB" -c 'select count(*) from devices') ; revision : $(iso "$DB" -c 'select version_num from alembic_version') ; archivees : $(iso "$DB" -c "select count(*) from devices where validation_status='archived'") ; journal : $(iso "$DB" -c 'select count(*) from device_archive_log')"
snap() { iso "$DB" -c "select md5(string_agg(concat_ws('~', id, validation_status, status, coalesce(ai_rewrite_status,''), coalesce(user_quality_decision,''), coalesce(tags::text,''), title), '|' order by id)) from devices where id::text = any(string_to_array('$1', ','))"; }
state_all() { iso "$DB" -c "select md5(string_agg(concat_ws('~', id, validation_status, status, coalesce(ai_rewrite_status,''), coalesce(user_quality_decision,''), title), '|' order by id)) from devices"; }
aifp() { iso "$DB" -c "select md5(string_agg(concat_ws('~', id, run_id, device_id, action, coalesce(previous_validation_status,''), coalesce(previous_status,''), archived_at), '|' order by id)) from device_archive_log where action='ai_hold'"; }

say ""; say "===== 2. Plan (meme fichier de protection que la production) ====="
OUTP=$(cli plan --protect-file /protect.txt)
HASH=$(echo "$OUTP" | python3 -c "
import json, sys
t = sys.stdin.read(); d = json.loads(t[t.index('{'):])
print(d['batches']['A_projets_institutionnels']['fingerprint'], d['batches']['A_projets_institutionnels']['count'])")
say "  lot A : empreinte/effectif = $HASH"
FP=${HASH% *}; N=${HASH#* }
[ -z "$EXPECT_HASH" ] || check "empreinte identique a celle de la production ($EXPECT_HASH)" "[ '$FP' = '$EXPECT_HASH' ]"
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
NSEL=$(echo "$IDS" | tr ',' '\n' | grep -c .)
check "sous-lot calcule : exactement $LIMIT fiches ($NSEL)" "[ '$NSEL' = '$LIMIT' ]"
if [ -n "$EXPECT_IDS" ]; then
  check "identifiants calcules == fichier valide ($EXPECT_IDS)" "[ \"\$(echo '$IDS' | tr ',' '\n' | LC_ALL=C sort)\" = \"\$(LC_ALL=C sort '$EXPECT_IDS')\" ]"
fi
PRIOR_CSV=""
if [ -n "$PRIOR_IDS" ]; then
  PRIOR_CSV=$(paste -sd, "$PRIOR_IDS")
  check "chevauchement avec les fiches deja archivees : 0" "[ \"\$(echo '$IDS' | tr ',' '\n' | grep -cFf '$PRIOR_IDS' || true)\" = 0 ]"
  check "les $(grep -c . "$PRIOR_IDS") fiches deja archivees le sont dans la copie" "[ \"\$(iso $DB -c \"select count(*) from devices where validation_status='archived' and id::text = any(string_to_array('$PRIOR_CSV', ','))\")\" = '$(grep -c . "$PRIOR_IDS")' ]"
fi
PROT_CSV=$(grep -v '^$' "$PROTECT" | sed 's/ .*//' | paste -sd,)
BEFORE_ALL=$(state_all); BEFORE_SUB=$(snap "$IDS"); AIFP0=$(aifp)
JOURNAL0=$(iso "$DB" -c "select count(*) from device_archive_log"); DEV0=$(iso "$DB" -c "select count(*) from devices")
ARCH0=$(iso "$DB" -c "select count(*) from devices where validation_status='archived'")
AIH0=$(iso "$DB" -c "select count(*) from device_archive_log where action='ai_hold'")
say "  avant : fiches=$DEV0 archivees=$ARCH0 journal=$JOURNAL0 ai_hold=$AIH0 (empreinte ai_hold $AIFP0)"

say ""; say "===== 3. Simulation puis archivage du sous-lot ($LIMIT fiches, copie) ====="
cli apply --batch A_projets_institutionnels --plan-hash "$FP" --run-id "$RUN" --backup-ref rehearsal --limit "$LIMIT" --protect-file /protect.txt | tail -12 | sed 's/^/   /'
check "la simulation n'a rien ecrit" "[ \"\$(iso $DB -c \"select count(*) from devices where validation_status='archived'\")\" = '$ARCH0' ]"
cli apply --batch A_projets_institutionnels --plan-hash "$FP" --run-id "$RUN" --backup-ref rehearsal --limit "$LIMIT" --protect-file /protect.txt --yes | tail -14 | sed 's/^/   /'
ARCH=$(iso "$DB" -c "select count(*) from devices where validation_status='archived'")
check "exactement $LIMIT nouvelles fiches archivees ($ARCH0 -> $ARCH)" "[ '$ARCH' = '$((ARCH0 + LIMIT))' ]"
check "fiches totales inchangees ($DEV0)" "[ \"\$(iso $DB -c 'select count(*) from devices')\" = '$DEV0' ]"
check "journal : +$LIMIT lignes (action=archive)" "[ \"\$(iso $DB -c 'select count(*) from device_archive_log')\" = '$((JOURNAL0 + LIMIT))' ] && [ \"\$(iso $DB -c \"select count(*) from device_archive_log where run_id='$RUN' and action='archive'\")\" = '$LIMIT' ]"
check "$AIH0 entrees ai_hold conservees a l'identique" "[ \"\$(iso $DB -c \"select count(*) from device_archive_log where action='ai_hold'\")\" = '$AIH0' ] && [ '$(aifp)' = '$AIFP0' ]"
check "aucune fiche protegee archivee (liste de protection de $(echo $PROT_CSV | tr ',' '\n' | grep -c .) ids)" "[ \"\$(iso $DB -c \"select count(*) from devices where id::text = any(string_to_array('$PROT_CSV', ',')) and validation_status='archived' and id::text <> all(string_to_array('${PRIOR_CSV:-x}', ','))\")\" = 0 ]"
check "seules les fiches du sous-lot (et les precedentes) sont archivees" "[ \"\$(iso $DB -c \"select count(*) from devices where validation_status='archived' and id::text <> all(string_to_array('$IDS,${PRIOR_CSV:-x}', ','))\")\" = 0 ]"

say ""; say "===== 4. API et collecteurs sur la copie archivee ====="
docker run -d --name lota-api --network "$NET" $(envs) -w /app -e PYTHONPATH=/app --entrypoint python "$IMAGE" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >/dev/null
for i in $(seq 1 40); do docker exec lota-api python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)" >/dev/null 2>&1 && break; sleep 2; done
FIRST=$(echo "$IDS" | cut -d, -f1)
docker exec -i -e FIRST="$FIRST" -e IDS="$IDS" lota-api python - <<'PY' 2>&1 | sed 's/^/  /'
import json, os, urllib.request, urllib.error
def get(u):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000" + u, timeout=120) as r: return r.status, json.load(r)
    except urllib.error.HTTPError as e: return e.code, None
print("ready:", get("/api/ready")[1])
ids, page, total = [], 1, 0
while True:
    s, d = get(f"/api/v1/devices/?page={page}&page_size=100"); it = d["items"]
    if not it: break
    ids += [i["id"] for i in it]; total = d["total"]; page += 1
mine = set(os.environ["IDS"].split(","))
print(f"pagination: total={total} lignes={len(ids)} distincts={len(set(ids))} ; fiches du sous-lot listees : {len(mine & set(ids))}")
print("detail d'une fiche archivee (public) :", get("/api/v1/devices/" + os.environ["FIRST"])[0])
PY
LISTED_AFTER=$(docker exec -i lota-api python - <<'PY'
import json, urllib.request
t = json.load(urllib.request.urlopen("http://127.0.0.1:8000/api/v1/devices/?page=1&page_size=1", timeout=120))["total"]
print(t)
PY
)
say "  total du listing public apres archivage : $LISTED_AFTER (production avant : voir le rapport de simulation ; le sous-lot n'y figure pas)"
docker exec -i -e PYTHONPATH=/app -e IDS="$IDS" lota-api python - <<'PY' 2>&1 | grep -v "^$" | tail -8 | sed 's/^/  /'
import asyncio, os
from sqlalchemy import text
from app.tasks import collect_tasks as ct
async def main():
    ids = os.environ["IDS"].split(",")
    async with ct._fresh_db() as db:
        rows = (await db.execute(text("select distinct s.id, s.name from sources s join devices d on d.source_id = s.id where d.id::text = any(:i) order by s.name limit 6"), {"i": ids})).all()
        before = (await db.execute(text("select count(*) from devices where validation_status='archived'"))).scalar()
    print("sources de fiches archivees collectees :", len(rows))
    for sid, name in rows:
        try:
            await ct._collect_source_async(str(sid)); print("  collecte OK :", name)
        except Exception as exc:
            print("  collecte ERREUR :", name, type(exc).__name__, str(exc)[:80])
    async with ct._fresh_db() as db:
        after = (await db.execute(text("select count(*) from devices where validation_status='archived'"))).scalar()
        tot = (await db.execute(text("select count(*) from devices"))).scalar()
    print(f"archivees avant/apres collectes : {before}/{after} ; fiches : {tot}")
asyncio.run(main())
PY
docker rm -f lota-api >/dev/null 2>&1
check "aucune reactivation par les collecteurs" "[ \"\$(iso $DB -c \"select count(*) from devices where validation_status='archived'\")\" = '$ARCH' ]"

say ""; say "===== 5. Restauration ciblee (3 fiches) puis complete du run $RUN ====="
T3=$(echo "$IDS" | cut -d, -f1-3 | tr ',' '\n')
ARGS=""; for i in $T3; do ARGS="$ARGS --device-id $i"; done
cli restore --run-id "$RUN" $ARGS --yes | tr -d '\n ' | sed 's/^/  ciblee : /'; echo
check "restauration ciblee : 3 fiches remises, $((ARCH - 3)) archivees" "[ \"\$(iso $DB -c \"select count(*) from devices where validation_status='archived'\")\" = '$((ARCH - 3))' ]"
cli restore --run-id "$RUN" | tr -d '\n ' | sed 's/^/  simulation du reste : /'; echo
cli restore --run-id "$RUN" --yes | tr -d '\n ' | sed 's/^/  complete : /'; echo
check "retour a $ARCH0 fiches archivees (les precedentes restent archivees)" "[ \"\$(iso $DB -c \"select count(*) from devices where validation_status='archived'\")\" = '$ARCH0' ]"
AFTER_SUB=$(snap "$IDS"); AFTER_ALL=$(state_all)
check "valeurs des $LIMIT fiches restituees a l'identique (statut, IA, qualite, tags, titre)" "[ '$BEFORE_SUB' = '$AFTER_SUB' ]"
check "empreinte de TOUT le catalogue (hors dates) identique a l'avant-archivage" "[ '$BEFORE_ALL' = '$AFTER_ALL' ]"
check "entrees ai_hold toujours identiques ($AIH0)" "[ '$(aifp)' = '$AIFP0' ]"
check "journal conserve : $LIMIT lignes du run marquees restaurees" "[ \"\$(iso $DB -c \"select count(*) from device_archive_log where run_id='$RUN' and restored_at is not null\")\" = '$LIMIT' ]"
say ""
[ $fail = 0 ] && say "RESULTAT : REPETITION REUSSIE (base jetable ${DB} supprimee ; production non modifiee)" || say "RESULTAT : AU MOINS UN ECHEC"
exit $fail
