#!/usr/bin/env bash
# Prevalidation d'une migration Alembic Kafundo SANS TOUCHER LA PRODUCTION :
#   lecture seule sur kafundo-postgres (pg_dump + requetes de controle), puis restauration, migration, tests de comportement,
#   retour arriere et controles fonctionnels sur une base JETABLE du conteneur kafundo-iso-pg.
#
#   IMAGE=kafundo-backend:migtest-<sha> bash migration_prevalidation.sh
# Sorties : journal sur stdout ; sauvegarde /opt/finveille-backups/pre_migration_<ts>.dump (+ .sha256).
set -uo pipefail
umask 077
IMAGE="${IMAGE:?IMAGE requis}"
PROD="${PROD:-kafundo-postgres}"; PROD_USER="${PROD_USER:-finveille}"; PROD_DB="${PROD_DB:-finveille}"
ISO="${ISO:-kafundo-iso-pg}"; ISO_USER="${ISO_USER:-isouser}"; NET="${NET:-kafundo-iso-net}"
PREV_REV="${PREV_REV:-b7d3a91c5e24}"; HEAD_REV="${HEAD_REV:-c8e1f4a7b2d9}"
TS=$(date -u +%Y%m%dT%H%M%SZ); DUMP="/opt/finveille-backups/pre_migration_${TS}.dump"; DB="mig_test_${TS,,}"
fail=0
say() { echo "$*"; }
check() { if eval "$2"; then say "  [OK]    $1"; else say "  [ECHEC] $1"; fail=1; fi; }
prod() { docker exec -i "$PROD" psql -U "$PROD_USER" -d "$PROD_DB" -At -F'|' "$@"; }
iso() { local d="$1"; shift; docker exec -i "$ISO" psql -U "$ISO_USER" -d "$d" -At -F'|' -v ON_ERROR_STOP=1 "$@"; }
ISO_PW="$(docker exec "$ISO" printenv POSTGRES_PASSWORD)"
SECRET_TMP="$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)"
appenv() { echo "-e DATABASE_URL=postgresql+asyncpg://${ISO_USER}:${ISO_PW}@${ISO}:5432/${DB} -e DATABASE_SYNC_URL=postgresql://${ISO_USER}:${ISO_PW}@${ISO}:5432/${DB} \
-e SECRET_KEY=${SECRET_TMP} -e REDIS_URL=redis://:x@127.0.0.1:1/0 -e REDIS_PASSWORD=x -e ENVIRONMENT=test"; }
cleanup() { docker rm -f mig-api >/dev/null 2>&1; docker exec "$ISO" psql -U "$ISO_USER" -d postgres -qc "DROP DATABASE IF EXISTS ${DB} WITH (FORCE)" >/dev/null 2>&1; }
trap cleanup EXIT
fk() { iso "$DB" -c "select conname||'='||confdeltype::text from pg_constraint where contype='f' and conrelid='device_archive_log'::regclass order by 1" | tr '\n' ' '; }
fp() { iso "$DB" -c "select md5(string_agg(t::text, '|' order by id)) from device_archive_log t"; }
fpd() { iso "$DB" -c "select md5(string_agg(t::text, '|' order by id)) from devices t"; }
counts_sql="select table_name||'='||(xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I', table_name), false, true, '')))[1]::text from information_schema.tables where table_schema='public' and table_type='BASE TABLE' order by 1"

say "===== 1. Etat actuel (lecture seule) ====="
say "date UTC            : $(date -u +%FT%TZ)"
docker ps --format '  {{.Names}}  {{.Image}}  {{.Status}}' | grep -E "kafundo-(backend|worker|beat|postgres|redis)( |$)"
say "PostgreSQL          : $(prod -c 'show server_version')"
say "revision Alembic    : $(prod -c 'select version_num from alembic_version')"
say "taille de la base   : $(prod -c 'select pg_size_pretty(pg_database_size(current_database()))')"
say "connexions actives  : $(prod -c "select count(*) from pg_stat_activity where datname=current_database()")"
say "transactions ouvertes > 1 min : $(prod -c "select count(*) from pg_stat_activity where datname=current_database() and xact_start < now() - interval '1 minute' and state <> 'idle'")"
say "cles etrangeres devices <- device_archive_log : $(prod -c "select string_agg(conname||'='||confdeltype::text, ' ' order by conname) from pg_constraint where contype='f' and conrelid='device_archive_log'::regclass")"
say "  (c=CASCADE n=SET NULL r=RESTRICT)"
check "revision actuelle = $PREV_REV" "[ \"\$(prod -c 'select version_num from alembic_version')\" = '$PREV_REV' ]"

say ""; say "===== 2. Donnees pouvant bloquer la migration (lecture seule) ====="
say "journal : $(prod -c "select count(*) from device_archive_log") lignes ; action=$(prod -c "select string_agg(action||':'||n, ' ') from (select action, count(*) n from device_archive_log group by 1) t") ; restaurees=$(prod -c "select count(*) from device_archive_log where restored_at is not null")"
ORPH1=$(prod -c "select count(*) from device_archive_log l left join devices d on d.id=l.device_id where d.id is null")
ORPH2=$(prod -c "select count(*) from device_archive_log l left join devices d on d.id=l.merged_into_id where l.merged_into_id is not null and d.id is null")
check "aucune ligne de journal sans fiche (device_id) : $ORPH1" "[ '$ORPH1' = 0 ]"
check "aucune cible de fusion absente (merged_into_id) : $ORPH2" "[ '$ORPH2' = 0 ]"
say "fiches journalisees: $(prod -c 'select count(distinct device_id) from device_archive_log') ; fiches cibles de fusion: $(prod -c 'select count(distinct merged_into_id) from device_archive_log where merged_into_id is not null')"
N_PROD=$(prod -c "select count(*) from devices")
say "fiches archivees (statut) : $(prod -c "select count(*) from devices where validation_status='archived'")"

say ""; say "===== 3. Sauvegarde complete + restauration jetable ====="
prod_dump_start=$(date +%s)
docker exec "$PROD" pg_dump -U "$PROD_USER" -d "$PROD_DB" -Fc > "$DUMP"
sha256sum "$DUMP" > "$DUMP.sha256"; chmod 600 "$DUMP" "$DUMP.sha256"
say "sauvegarde : $(basename "$DUMP") $(stat -c %s "$DUMP") octets en $(( $(date +%s) - prod_dump_start )) s"
( cd /opt/finveille-backups && sha256sum -c "$(basename "$DUMP").sha256" >/dev/null ) && say "  sha256 : OK"
TOC=$(docker exec -i "$PROD" pg_restore --list < "$DUMP" | wc -l); say "  entrees du sommaire : $TOC"
docker exec "$ISO" psql -U "$ISO_USER" -d postgres -qc "CREATE DATABASE ${DB}" >/dev/null
t=$(date +%s)
docker exec -i "$ISO" pg_restore -U "$ISO_USER" -d "$DB" --no-owner --no-privileges < "$DUMP" 2>&1 | grep -v "^$" | head -3
say "restauration : $(( $(date +%s) - t )) s"
prod -c "$counts_sql" > /tmp/mig_counts_prod.txt
iso "$DB" -c "$counts_sql" > /tmp/mig_counts_iso.txt
check "comptes par table identiques (production / base restauree) : $(wc -l < /tmp/mig_counts_iso.txt) tables" "diff -q /tmp/mig_counts_prod.txt /tmp/mig_counts_iso.txt >/dev/null"
FP0=$(fp); FPD0=$(fpd); say "empreinte journal : $FP0 ; empreinte fiches : $FPD0"
check "revision restauree = $PREV_REV" "[ \"\$(iso $DB -c 'select version_num from alembic_version')\" = '$PREV_REV' ]"
say "cles avant migration : $(fk)"

say ""; say "===== 4. Application de la migration sur la base jetable ====="
t=$(date +%s%3N)
docker run --rm --network "$NET" $(appenv) -w /app --entrypoint python -e PYTHONPATH=/app "$IMAGE" -m migrations.upgrade --backup-confirmed 2>&1 | tail -4 | sed "s/${ISO_PW}/***/g"
say "duree : $(( $(date +%s%3N) - t )) ms"
check "revision = $HEAD_REV" "[ \"\$(iso $DB -c 'select version_num from alembic_version')\" = '$HEAD_REV' ]"
say "cles apres migration : $(fk)"
check "device_id et merged_into_id en RESTRICT" "[ \"\$(iso $DB -c \"select count(*) from pg_constraint where contype='f' and conrelid='device_archive_log'::regclass and confrelid='devices'::regclass and confdeltype='r'\")\" = 2 ]"
check "journal et fiches inchangés par la migration" "[ '$(fp)' = '$FP0' ] && [ '$(fpd)' = '$FPD0' ]"
check "comptes par table inchanges" "[ \"\$(iso $DB -c \"$counts_sql\" | md5sum)\" = \"\$(md5sum < /tmp/mig_counts_prod.txt)\" ]"

say ""; say "===== 5. Comportement des suppressions apres migration (transactions annulees) ====="
J=$(iso "$DB" -c "select device_id from device_archive_log where merged_into_id is null limit 1")
M=$(iso "$DB" -c "select merged_into_id from device_archive_log where merged_into_id is not null limit 1")
U=$(iso "$DB" -c "select id from devices d where not exists (select 1 from device_archive_log l where l.device_id=d.id or l.merged_into_id=d.id) limit 1")
try_delete() { docker exec -i "$ISO" psql -U "$ISO_USER" -d "$DB" -At -c "begin; delete from devices where id='$1'; rollback;" 2>&1 | tr '\n' ' ' | cut -c1-160; }
R=$(try_delete "$J"); say "fiche journalisee    : $R"; check "suppression refusee (journal)" "echo \"$R\" | grep -qi 'violates foreign key'"
if [ -n "$M" ]; then R=$(try_delete "$M"); say "cible de fusion       : $R"; check "suppression refusee (cible de fusion)" "echo \"$R\" | grep -qi 'violates foreign key'"
else
  T=$(iso "$DB" -c "select id from devices d where not exists (select 1 from device_archive_log l where l.device_id=d.id or l.merged_into_id=d.id) offset 1 limit 1")
  R=$(docker exec -i "$ISO" psql -U "$ISO_USER" -d "$DB" -At -c "begin; update device_archive_log set merged_into_id='$T' where id=(select id from device_archive_log limit 1); delete from devices where id='$T'; rollback;" 2>&1 | tr '
' ' ' | cut -c1-170)
  say "cible de fusion (construite, annulee) : $R"; check "suppression refusee (cible de fusion)" "echo \"$R\" | grep -qi 'violates foreign key'"
fi
R=$(try_delete "$U"); say "fiche non journalisee: $R"; check "suppression d'une fiche ordinaire possible (annulee)" "echo \"$R\" | grep -q 'DELETE 1'"
N_AFTER=$(iso "$DB" -c "select count(*) from devices")
check "aucune fiche supprimee (copie $N_AFTER / production $N_PROD)" "[ '$N_AFTER' = '$N_PROD' ]"

say ""; say "===== 6. Retour arriere (downgrade) puis re-application ====="
docker run --rm --network "$NET" $(appenv) -w /app --entrypoint python -e PYTHONPATH=/app "$IMAGE" -m alembic downgrade "$PREV_REV" 2>&1 | tail -2 | sed "s/${ISO_PW}/***/g"
check "revision = $PREV_REV" "[ \"\$(iso $DB -c 'select version_num from alembic_version')\" = '$PREV_REV' ]"
say "cles apres downgrade : $(fk)"
check "cles restituees (CASCADE / SET NULL)" "[ \"\$(iso $DB -c \"select string_agg(confdeltype::text, '' order by conname) from pg_constraint where contype='f' and conrelid='device_archive_log'::regclass and confrelid='devices'::regclass\")\" = 'cn' ]"
check "journal et fiches identiques apres downgrade" "[ '$(fp)' = '$FP0' ] && [ '$(fpd)' = '$FPD0' ]"
docker run --rm --network "$NET" $(appenv) -w /app --entrypoint python -e PYTHONPATH=/app "$IMAGE" -m migrations.upgrade --backup-confirmed 2>&1 | tail -1 | sed "s/${ISO_PW}/***/g"
check "re-application : revision = $HEAD_REV" "[ \"\$(iso $DB -c 'select version_num from alembic_version')\" = '$HEAD_REV' ]"

say ""; say "===== 7. API, import CSV et collecteurs sur la base migree ====="
docker run -d --name mig-api --network "$NET" $(appenv) -w /app -e PYTHONPATH=/app --entrypoint python "$IMAGE" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >/dev/null
for i in $(seq 1 40); do docker exec mig-api python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)" >/dev/null 2>&1 && break; sleep 2; done
docker exec -i mig-api python - <<'PY' 2>&1 | sed 's/^/  /'
import json, urllib.request, collections
def get(u):
    with urllib.request.urlopen("http://127.0.0.1:8000" + u, timeout=60) as r: return json.load(r)
print("health:", get("/api/health")["status"], "| ready:", get("/api/ready"))
ids, page, total = [], 1, 0
while True:
    d = get(f"/api/v1/devices/?page={page}&page_size=100"); it = d["items"]
    if not it: break
    ids += [i["id"] for i in it]; total = d["total"]; page += 1
print(f"pagination: total={total} lignes={len(ids)} distincts={len(set(ids))}")
d = get("/api/v1/devices/?page=1&page_size=5&q=aide"); print("recherche:", d["total"], "resultats")
PY
t=$(date +%s)
docker exec -e PYTHONPATH=/app mig-api python -m app.data.import_aides_entreprises_csv 2>&1 | tail -3 | sed 's/^/  /'
say "  import CSV reel (sur la base jetable) : $(( $(date +%s) - t )) s"
docker exec -i -e PYTHONPATH=/app mig-api python - <<'PY' 2>&1 | grep -v "^$" | tail -8 | sed 's/^/  /'
import asyncio, logging
from sqlalchemy import select, text
from app.tasks import collect_tasks as ct
from app.models.source import Source
async def main():
    async with ct._fresh_db() as db:
        before = (await db.execute(text("select count(*) from devices"))).scalar()
        rows = (await db.execute(text("select id, name, source_type from sources where is_active and level=1 order by name limit 3"))).all()
    for sid, name, ctype in rows:
        try:
            await ct._collect_source_async(str(sid)); print("collecte OK :", name, f"({ctype})")
        except Exception as exc:
            print("collecte ERREUR :", name, type(exc).__name__, str(exc)[:100])
    async with ct._fresh_db() as db:
        after = (await db.execute(text("select count(*) from devices"))).scalar()
    print("fiches avant/apres collecte:", before, after)
asyncio.run(main())
PY
docker rm -f mig-api >/dev/null 2>&1
check "production inchangee : revision $(prod -c 'select version_num from alembic_version')" "[ \"\$(prod -c 'select version_num from alembic_version')\" = '$PREV_REV' ]"

say ""
[ $fail = 0 ] && say "RESULTAT : PREVALIDATION REUSSIE (base jetable ${DB} supprimee ; production non modifiee)" || say "RESULTAT : AU MOINS UN ECHEC"
exit $fail
