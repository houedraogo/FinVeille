#!/bin/bash
# Sauvegarde verifiee + SIMULATION sur copie isolee. Aucune ecriture dans la base Finnovatix de production.
set -uo pipefail
umask 077
D=${AUDIT_DIR:-/opt/finveille-backups/audit_20261010}
PROD=finnovatix-platform-finnovatix-mysql-1
SIM=fx-sim-mysql; NET=fx-sim-net
TS=$(date -u +%Y%m%dT%H%M%SZ)
rm -f $D/finnovatix_funding_backup_*.sql.gz $D/finnovatix_funding_backup_*.sha256; BK=$D/finnovatix_funding_backup_$TS.sql.gz
REPORT=$D/finnovatix_simulation_report.txt
W=$(mktemp -d); trap 'docker rm -f $SIM >/dev/null 2>&1; docker network rm $NET >/dev/null 2>&1; shred -u "$W"/* 2>/dev/null; rm -rf "$W"' EXIT
say() { echo "$*" | tee -a "$REPORT"; }
: > "$REPORT"

say "===== SAUVEGARDE (production, lecture seule) ====="
docker exec "$PROD" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --single-transaction --no-tablespaces --skip-lock-tables --default-character-set=utf8mb4 finnovatix funding_calls funding_opportunities marketing_contents' 2>/dev/null | gzip > "$BK"
sha256sum "$BK" > "$BK.sha256"
say "fichier : $(basename $BK)  taille=$(stat -c %s "$BK") octets"
say "sha256  : $(cut -c1-24 "$BK.sha256")..."
gzip -t "$BK" && say "integrite gzip : OK"
zcat "$BK" | tail -1 | grep -q "Dump completed" && say "fin de dump : OK (Dump completed)" || say "fin de dump : ABSENTE"

say ""; say "===== COPIE ISOLEE (MySQL jetable, reseau dedie, aucun port publie) ====="
RP=$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 24)
docker network create $NET >/dev/null
docker run -d --name $SIM --network $NET -e MYSQL_ROOT_PASSWORD="$RP" -e MYSQL_DATABASE=finnovatix mysql/mysql-server:8.0 >/dev/null
READY=0
for i in $(seq 1 150); do
  H=$(docker inspect -f '{{.State.Health.Status}}' $SIM 2>/dev/null)
  if [ "$H" = healthy ] && docker exec $SIM mysql -uroot -p"$RP" -e "select 1" >/dev/null 2>&1; then
    sleep 3
    docker exec $SIM mysql -uroot -p"$RP" -e "select 1" >/dev/null 2>&1 && { READY=1; break; }
  fi
  sleep 3
done
[ $READY = 1 ] || { say "ECHEC : la base jetable n est pas prete"; exit 1; }
sim() { docker exec -i $SIM mysql -uroot -p"$RP" --default-character-set=utf8mb4 --batch --skip-column-names finnovatix 2>&1 | grep -av "Using a password"; }
simt() { docker exec -i $SIM mysql -uroot -p"$RP" --default-character-set=utf8mb4 --batch finnovatix 2>&1 | grep -av "Using a password"; }
zcat "$BK" | docker exec -i $SIM mysql -uroot -p"$RP" --default-character-set=utf8mb4 finnovatix 2>&1 | grep -av "Using a password" | head -3
say "restauration : fc=$(echo 'select count(*) from funding_calls' | sim)  opportunites=$(echo 'select count(*) from funding_opportunities' | sim)  marketing=$(echo 'select count(*) from marketing_contents' | sim)"

# ids Kafundo actuels (pour mesurer les references orphelines)
docker exec kafundo-postgres psql -U finveille -d finveille -At -c "select id from devices" > "$W/ids.txt"
echo "CREATE TABLE sim_kafundo_ids (id CHAR(36) COLLATE utf8mb4_unicode_ci PRIMARY KEY) COLLATE utf8mb4_unicode_ci;" | sim
awk '{ if (NR % 500 == 1) { if (NR > 1) print ";"; printf "INSERT INTO sim_kafundo_ids VALUES " } else printf ","; printf "(\047%s\047)", $1 } END { print ";" }' "$W/ids.txt" | sim
say "ids Kafundo charges dans la copie : $(echo 'select count(*) from sim_kafundo_ids' | sim)"

metrics() { # $1 = etiquette
cat <<SQL | simt
SELECT '$1' AS etape;
SELECT COUNT(*) AS funding_calls, COUNT(DISTINCT kafundo_id) AS kafundo_id_distincts FROM funding_calls;
SELECT status, COUNT(*) AS n FROM funding_calls GROUP BY status ORDER BY n DESC;
SELECT COUNT(*) AS fc_dont_kafundo_id_absent_de_kafundo FROM funding_calls fc LEFT JOIN sim_kafundo_ids k ON k.id=fc.kafundo_id WHERE k.id IS NULL;
SELECT COUNT(*) AS opportunites_dossiers FROM funding_opportunities;
SELECT COUNT(*) AS opportunites_orphelines FROM funding_opportunities o LEFT JOIN funding_calls f ON f.id=o.funding_call_id WHERE f.id IS NULL;
SELECT COUNT(*) AS contenus_marketing FROM marketing_contents;
SELECT COUNT(*) AS fc_avec_annotation_kafundo FROM funding_calls WHERE JSON_CONTAINS_PATH(metadata,'one','$.kafundo_remap','$.kafundo_retired','$.kafundo_superseded','$.kafundo_source_missing');
SQL
}
chk() { echo "CHECKSUM TABLE funding_calls, funding_opportunities, marketing_contents;" | simt | tail -n +2 | awk '{print $1"="$2}' | tr '\n' ' '; }

say ""; say "===== AVANT ====="; metrics AVANT | tee -a "$REPORT"
CK0=$(chk); say "checksums AVANT : $CK0"

say ""; say "===== SIMULATION 1 : application de finnovatix_apply.sql ====="
OUT=$(sim < "$D/finnovatix_apply.sql" | tail -3); say "$OUT"
say ""; say "===== APRES application ====="; metrics APRES | tee -a "$REPORT"
CK1=$(chk); say "checksums APRES  : $CK1"
say "unicite kafundo_id : doublons = $(echo 'select count(*) from (select kafundo_id from funding_calls group by kafundo_id having count(*)>1) t' | sim)"

say ""; say "===== PROTECTION CONTRE LE REJEU : seconde application (doit tout annuler) ====="
sim < "$D/finnovatix_apply.sql" | tail -2 | sed 's/^/   /' | tee -a "$REPORT"
say "checksums apres rejeu : $(chk)"

say ""; say "===== RETOUR ARRIERE : finnovatix_rollback.sql ====="
sim < "$D/finnovatix_rollback.sql" | tail -1 | tee -a "$REPORT"
CK2=$(chk); say "checksums apres retour arriere : $CK2"
[ -n "$CK0" ] && ! echo "$CK0" | grep -q NULL && [ "$CK0" = "$CK2" ] && say "RESULTAT retour arriere : IDENTIQUE a l etat initial (3 tables)" || say "RESULTAT retour arriere : NON VALIDE ou DIFFERENT (empreintes vides ou distinctes)"

say ""; say "===== SIMULATION 2 : fusion optionnelle (3 FundingCall sans dossier sur la cible) ====="
sim < "$D/finnovatix_apply.sql" | tail -1 >/dev/null
CKA=$(chk)
echo "select 'avant fusion' as etape, (select count(*) from funding_opportunities where funding_call_id in (381,386,384)) as opps_sur_anciennes;" | simt | tee -a "$REPORT"
sim < "$D/finnovatix_apply_optional_M.sql" | tail -1 | tee -a "$REPORT"
echo "select 'apres fusion' as etape, (select count(*) from funding_opportunities where funding_call_id in (381,386,384)) as opps_sur_anciennes, (select count(*) from funding_opportunities where funding_call_id in (762,1149,764)) as opps_sur_cibles;" | simt | tee -a "$REPORT"
sim < "$D/finnovatix_rollback_optional_M.sql" | tail -1 >/dev/null
sim < "$D/finnovatix_rollback.sql" | tail -1 >/dev/null
CK3=$(chk); say "checksums apres retour arriere complet : $CK3"
[ -n "$CK0" ] && ! echo "$CK0" | grep -q NULL && [ "$CK0" = "$CK3" ] && say "RESULTAT : IDENTIQUE a l etat initial apres fusion + retour arriere" || say "RESULTAT : NON VALIDE ou DIFFERENT"

say ""; say "===== SIMULATION 3 : executeur garde 06_apply.sh (sur la COPIE jetable, jamais la production) ====="
RUNNER="$(dirname "$(readlink -f "$0")")/06_apply.sh"
if [ -f "$RUNNER" ]; then
  export AUDIT_DIR="$D" MYSQL_CONTAINER="$SIM" APP_CONTAINER=aucun-conteneur DB=finnovatix ASSUME_YES=1
  export SKIP_CAP_CHECK=1 MYSQL_EXEC="docker exec -i $SIM mysql -uroot -p$RP --default-character-set=utf8mb4 --batch --skip-column-names finnovatix"
  export BLOCKED_FROM=99:98 BLOCKED_TO=99:99 JOURNAL="$W/journal.tsv"
  say "--- (a) mode simulation (aucune ecriture attendue)"
  bash "$RUNNER" 2>&1 | tee -a "$REPORT" | tail -12
  CK_A=$(chk); [ "$CK_A" = "$CK0" ] && say "empreintes inchangees apres dry-run : OK" || say "ECART apres dry-run"
  say "--- (b) --apply"
  bash "$RUNNER" --apply 2>&1 | tee -a "$REPORT" | tail -8
  CK_B=$(chk); [ "$CK_B" != "$CK0" ] && say "funding_calls modifiee : OK (attendu)" || say "ANOMALIE : rien n'a change"
  say "--- (c) --rollback"
  bash "$RUNNER" --rollback 2>&1 | tee -a "$REPORT" | tail -6
  CK_C=$(chk)
  [ -n "$CK0" ] && ! echo "$CK0" | grep -q NULL && [ "$CK0" = "$CK_C" ] \
    && say "RESULTAT executeur : retour arriere IDENTIQUE a l etat initial" || say "RESULTAT executeur : NON VALIDE ou DIFFERENT"
else
  say "(06_apply.sh introuvable a cote du script : simulation 3 ignoree)"
fi
say ""; say "(copie jetable supprimee a la sortie ; production Finnovatix non modifiee)"
echo "$BK" > /tmp/fx_backup_path
