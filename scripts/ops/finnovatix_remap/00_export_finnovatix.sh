#!/bin/bash
set -uo pipefail
D=${AUDIT_DIR:-/opt/finveille-backups/audit_20261010}
C=finnovatix-platform-finnovatix-mysql-1
my() { docker exec -i "$C" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --batch --skip-column-names finnovatix' 2>&1 | grep -av "Using a password"; }
IN=$(awk '{printf "%s'"'"'%s'"'"'", (NR>1?",":""), $1}' "$D/finnovatix_protected_ids_missing_in_kafundo.txt")
echo "n_ids=$(wc -l < $D/finnovatix_protected_ids_missing_in_kafundo.txt)"
# export des funding_calls concernées + usage (dossiers, marketing)
cat <<SQL | my > "$D/fx_missing_calls.tsv"
select fc.id, fc.kafundo_id, replace(replace(fc.title,'\t',' '),'\n',' '), fc.status, coalesce(fc.deadline,''), coalesce(fc.source_updated_at,''), coalesce(fc.last_verified_at,''), fc.created_at, fc.updated_at,
  (select count(*) from funding_opportunities o where o.funding_call_id=fc.id),
  (select count(*) from marketing_contents m where m.funding_call_id=fc.id),
  (select count(distinct o.consulting_project_id) from funding_opportunities o where o.funding_call_id=fc.id)
from funding_calls fc where fc.kafundo_id in ($IN);
SQL
echo "lignes exportées: $(wc -l < "$D/fx_missing_calls.tsv")"
# tous les kafundo_id existants (pour détecter les conflits d'unicité)
echo "select id, kafundo_id from funding_calls;" | my > "$D/fx_all_kafundo_ids.tsv"
echo "total funding_calls: $(wc -l < "$D/fx_all_kafundo_ids.tsv")"
