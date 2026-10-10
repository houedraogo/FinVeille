#!/usr/bin/env bash
# Instantané LECTURE SEULE de l'état de Kafundo (conteneurs, base, API) — avant/après un déploiement.
#   bash scripts/ops/kafundo_snapshot.sh > avant.txt ; ... ; bash scripts/ops/kafundo_snapshot.sh > apres.txt ; diff avant.txt apres.txt
# Aucune valeur secrète n'est lue ni affichée.
set -uo pipefail
PG="${PG_CONTAINER:-kafundo-postgres}"; DB_USER="${DB_USER:-finveille}"; DB="${DB_NAME:-finveille}"
API="${API_URL:-http://127.0.0.1:8000}"
q() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=60000' "$PG" psql -U "$DB_USER" -d "$DB" -At -F ' | ' -c "$1" 2>&1; }

echo "== horodatage: $(date -u +%FT%TZ)"
echo "== conteneurs (nom | image | état)"
for c in kafundo-backend kafundo-worker kafundo-beat kafundo-frontend kafundo-postgres kafundo-redis kafundo-nginx kafundo-postgres-backup; do
  docker inspect -f '{{.Name}} | {{.Config.Image}} | {{.State.Status}} | démarré {{.State.StartedAt}}' "$c" 2>/dev/null || echo "/$c | ABSENT"
done
echo "== API"
echo "health: $(curl -s -o /dev/null -w '%{http_code}' "$API/api/health")"
echo "catalogue public (total): $(curl -s "$API/api/v1/devices/?page=1&page_size=1" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("total"))' 2>/dev/null)"
echo "stats publiques: $(curl -s "$API/api/v1/devices/stats" | python3 -c 'import sys,json; d=json.load(sys.stdin); print({k:d[k] for k in ("total_active","total","new_last_7_days")})' 2>/dev/null)"
echo "== schéma"
echo "alembic: $(q 'select version_num from alembic_version')"
echo "== fiches"
echo "total: $(q 'select count(*) from devices')"
q "select 'validation', validation_status, count(*) from devices group by 2 order by 3 desc"
q "select 'statut', status, count(*) from devices group by 2 order by 3 desc"
q "select 'ia_reecriture', coalesce(ai_rewrite_status,'NULL'), count(*) from devices group by 2 order by 3 desc"
q "select 'sans_decision_qualite', count(*) from devices where user_quality_decision is null and validation_status in ('auto_published','approved','validated')"
q "select 'slug_csv_stable', count(*) filter (where slug ~ '^fr-ae-[0-9]+\$'), 'slug_csv_titre', count(*) filter (where slug like 'fr-ae-%' and slug !~ '^fr-ae-[0-9]+\$') from devices"
q "select 'creees_24h', count(*) from devices where created_at > now() - interval '24 hours'"
q "select 'modifiees_24h', count(*) from devices where updated_at > now() - interval '24 hours'"
echo "== tables du nettoyage (si migrées)"
for t in device_archive_log device_rejections device_duplicate_candidates; do
  echo "$t: $(q "select count(*) from $t" | head -1)"
done
echo "== collecteurs (24 h)"
q "select status, count(*), coalesce(sum(items_new),0) nouveaux, coalesce(sum(items_updated),0) maj, coalesce(sum(items_error),0) erreurs from collection_logs where started_at > now() - interval '24 hours' group by status order by 2 desc"
q "select 'derniere_collecte', max(started_at) from collection_logs"
q "select 'import_csv_derniere_reussite', last_success_at from sources where name like 'data.aides-entreprises.fr%CSV%'"
echo "== doublons CERTAINS potentiels (même URL source exacte + même titre normalisé)"
q "select count(*) from (select 1 from devices where length(source_url) > 25 and title_normalized is not null group by source_url, title_normalized having count(*) > 1) x"
