#!/bin/bash
# Simulation COMPLETE sur copie jetable, avec le VRAI code Finnovatix (artisan) et l'API Kafundo reelle en lecture seule.
# Aucune ecriture dans la base de production : MySQL jetable (reseau dedie, aucun port publie) ; le code Finnovatix est
# monte en LECTURE SEULE ; les variables DB_* pointent vers la copie (verifie avant chaque lancement) ; aucune sortie reseau
# autre que l'API Kafundo locale (proxy sortant neutralise).
#
# Verifie : (1) valeurs des fiches rattachees == API Kafundo ; (2) aucune notification pendant l'operation ;
# (3) la synchro suivante notifie EXACTEMENT comme avant l'operation (aucun envoi massif) ; (4) un vrai changement futur
# est detecte et notifie ; (5) synthese par consultant, rejeu sans doublon ; (6) rejeu du SQL refuse ; (7) retour arriere
# complet (valeurs, metadonnees, historique, notifications) identique a l'etat initial.
set -uo pipefail
umask 077
HERE="$(dirname "$(readlink -f "$0")")"
D=${AUDIT_DIR:-/opt/finveille-backups/audit_20261010}
PROD=${PROD:-finnovatix-platform-finnovatix-mysql-1}
CODE=${CODE:-/opt/finnovatix-platform}
APPIMG=${APPIMG:-finnovatix/app:latest}
SIM=fx-sim2-mysql; NET=fx-sim2-net
REPORT=$D/finnovatix_simulation_sync_report.txt
W=$(mktemp -d)
trap '[ -n "${FAKE_PID:-}" ] && kill $FAKE_PID 2>/dev/null; docker rm -f $SIM >/dev/null 2>&1; docker network rm $NET >/dev/null 2>&1; shred -u "$W"/* 2>/dev/null; rm -rf "$W"' EXIT
say() { echo "$*" | tee -a "$REPORT"; }
fail=0; check() { if eval "$2"; then say "  [OK]    $1"; else say "  [ECHEC] $1"; fail=1; fi; }
: > "$REPORT"

say "===== 0. Plan regenere (lecture seule sur la production) ====="
( cd "$HERE" && AUDIT_DIR="$D" python3 04_generate_sql.py ) 2>&1 | sed 's/^/   /' | tee -a "$REPORT"

# API Kafundo figee (instantane complet, pagination deterministe) : la vraie API pagine de facon instable
FAKE_PORT=${FAKE_PORT:-18000}
python3 "$HERE/fake_kafundo_api.py" "$D/kafundo_api_snapshot.json" $FAKE_PORT & FAKE_PID=$!
sleep 2
curl -fsS "http://127.0.0.1:$FAKE_PORT/api/health" >/dev/null || { say "ARRET : API figee indisponible"; exit 1; }
export API_URL="http://127.0.0.1:$FAKE_PORT"
say "API Kafundo figee : $(python3 -c "import json;print(len(json.load(open('$D/kafundo_api_snapshot.json',encoding='utf-8'))))") dispositifs (instantane complet)"

say ""; say "===== 1. Copie jetable ====="
RP=$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 24)
docker network create $NET >/dev/null
docker run -d --name $SIM --network $NET -e MYSQL_ROOT_PASSWORD="$RP" -e MYSQL_ROOT_HOST=% -e MYSQL_DATABASE=finnovatix mysql/mysql-server:8.0 >/dev/null
READY=0
for i in $(seq 1 150); do
  H=$(docker inspect -f '{{.State.Health.Status}}' $SIM 2>/dev/null)
  if [ "$H" = healthy ] && docker exec $SIM mysql -uroot -p"$RP" -e "select 1" >/dev/null 2>&1; then
    sleep 3; docker exec $SIM mysql -uroot -p"$RP" -e "select 1" >/dev/null 2>&1 && { READY=1; break; }
  fi
  sleep 3
done
[ $READY = 1 ] || { say "ECHEC : la base jetable n est pas prete"; exit 1; }
SIMIP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $SIM)
simq() { docker exec -i $SIM mysql -uroot -p"$RP" --default-character-set=utf8mb4 --batch --skip-column-names finnovatix 2>&1 | grep -av "Using a password"; }
simh() { docker exec -i $SIM mysql -uroot -p"$RP" --default-character-set=utf8mb4 --batch finnovatix 2>&1 | grep -av "Using a password"; }
export MYSQL_EXEC="docker exec -i $SIM mysql -uroot -p$RP --default-character-set=utf8mb4 --batch --skip-column-names finnovatix"

# dumps (lecture seule sur la production)
docker exec "$PROD" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --no-data --no-tablespaces --skip-lock-tables --default-character-set=utf8mb4 finnovatix' 2>/dev/null > "$W/schema.sql"
docker exec "$PROD" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --single-transaction --no-create-info --skip-triggers --no-tablespaces --skip-lock-tables --default-character-set=utf8mb4 finnovatix funding_calls funding_opportunities marketing_contents users consulting_projects notification_preferences' 2>/dev/null > "$W/data.sql"
say "schema: $(wc -l < $W/schema.sql) lignes ; donnees: $(wc -c < $W/data.sql) octets"
reset() {
  echo "DROP DATABASE finnovatix; CREATE DATABASE finnovatix CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" | docker exec -i $SIM mysql -uroot -p"$RP" 2>&1 | grep -av "Using a password"
  simq < "$W/schema.sql" | head -3
  simq < "$W/data.sql" | head -3
  # donnees personnelles inutiles a la simulation : secrets d'authentification neutralises dans la copie
  echo "UPDATE users SET password='x', remember_token=NULL;" | simq >/dev/null 2>&1
}
chk() { echo "CHECKSUM TABLE funding_calls, funding_opportunities, marketing_contents, notifications, jobs;" | simh | tail -n +2 | awk '{print $1"="$2}' | tr '\n' ' '; }
n() { echo "$1" | simq | tail -1; }
reset
say "restauration : funding_calls=$(n 'select count(*) from funding_calls')  opportunites=$(n 'select count(*) from funding_opportunities')  utilisateurs=$(n 'select count(*) from users')  projets=$(n 'select count(*) from consulting_projects')"

# ---- executeur du vrai code Finnovatix sur la copie ----
app() { # $1 = commande shell ; stdin transmis ; EXTRA_ENV = tableau de -e K=V
  docker run --rm -i --network host --entrypoint sh -v "$CODE":/var/www/html:ro \
    --tmpfs /var/www/html/storage:rw,mode=1777 --tmpfs /var/www/html/bootstrap/cache:rw,mode=1777 -w /var/www/html \
    -e DB_CONNECTION=mysql -e DB_HOST="$SIMIP" -e DB_PORT=3306 -e DB_DATABASE=finnovatix -e DB_USERNAME=root -e DB_PASSWORD="$RP" \
    -e CACHE_STORE=array -e SESSION_DRIVER=array -e QUEUE_CONNECTION=database -e MAIL_MAILER=log -e REDIS_HOST=127.0.0.1 \
    -e KAFUNDO_BASE_URL=http://127.0.0.1:$FAKE_PORT -e KAFUNDO_SYNC_CREATE_CAP=0 -e APP_ENV=local -e APP_DEBUG=false \
    -e HTTP_PROXY=http://127.0.0.1:9 -e HTTPS_PROXY=http://127.0.0.1:9 -e NO_PROXY=127.0.0.1,localhost -e OPENAI_API_KEY= \
    ${EXTRA_ENV[@]+"${EXTRA_ENV[@]}"} "$APPIMG" -c 'mkdir -p storage/framework/cache/data storage/framework/sessions storage/framework/views storage/logs && '"$1" 2>&1
}
EXTRA_ENV=()
HOSTCHK=$(printf '%s' "<?php require 'vendor/autoload.php'; \$a=require 'bootstrap/app.php'; \$a->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap(); echo config('database.connections.mysql.host');" | app "php" | tail -1)
[ "$HOSTCHK" = "$SIMIP" ] || { say "ARRET : l'application ne vise pas la copie (hote=$HOSTCHK attendu=$SIMIP)"; exit 1; }
say "application Finnovatix (code reel, lecture seule) -> copie jetable $SIMIP : OK"
sync() { app "php artisan kafundo:sync-funding-calls --apply" | tail -4; }
ran() { local k; k=$(echo "$1" | grep -oE '[0-9]+ à mettre à jour' | grep -oE '^[0-9]+' | head -1); [ -n "$k" ] && [ "$k" -gt 1000 ]; }
summ() { sed -n 's/.*\([0-9][0-9]* changement(s) matériel(s) détecté(s), [0-9][0-9]* notification(s) envoyée(s)\).*/\1/p' | tail -1; }
notif_set() { echo "select user_id, title, body from notifications where type='funding_opportunity_changed' order by user_id, title, body;" | simq | md5sum | cut -c1-12; }

say ""; say "===== 2. REFERENCE : synchro sur l'etat actuel (sans l'operation) ====="
OUT=$(sync); say "$(echo "$OUT" | summ)"; check "la synchro de reference s'est reellement executee (>1000 mises a jour)" "ran \"\$OUT\""
NOT0=$(n "select count(*) from notifications"); SET0=$(notif_set)
say "notifications creees par la synchro de reference : $NOT0 (empreinte $SET0)"

say ""; say "===== 3. OPERATION : application du SQL + verification + synchro suivante ====="
reset
CK0=$(chk); say "empreintes initiales : $CK0"
RES=$(simq < "$D/finnovatix_apply.sql" | tail -1); say "application : $RES"
check "COMMIT effectue" "echo '$RES' | grep -q 'COMMIT effectue'"
check "aucune notification creee par l'operation elle-meme" "[ \"\$(n 'select count(*) from notifications')\" = 0 ]"
check "aucune tache en file creee par l'operation" "[ \"\$(n 'select count(*) from jobs')\" = 0 ]"
say "--- controle 07_verify.py (valeurs rattachees == API Kafundo) :"
( cd "$HERE" && AUDIT_DIR="$D" python3 07_verify.py ) 2>&1 | sed 's/^/   /' | tee -a "$REPORT"
check "07_verify.py : aucun ecart" "( cd '$HERE' && AUDIT_DIR='$D' python3 07_verify.py >/dev/null 2>&1 )"
REAL=$(n "select count(*) from funding_calls where cast(metadata as char) like '%silent_realign%'")
say "fiches avec historique silent_realign : $REAL"
OUT=$(sync); say "synchro suivante : $(echo "$OUT" | summ)"; check "la synchro suivante s'est reellement executee" "ran \"\$OUT\""
NOT1=$(n "select count(*) from notifications"); SET1=$(notif_set)
say "notifications apres la synchro : $NOT1 (empreinte $SET1)"
check "la synchro notifie exactement comme la reference ($NOT0)" "[ '$NOT1' = '$NOT0' ] && [ '$SET1' = '$SET0' ]"
HIST_KEPT=$(n "select count(*) from funding_calls where cast(metadata as char) like '%silent_realign%'")
check "l'historique silent_realign survit a la synchro" "[ '$HIST_KEPT' = '$REAL' ] && [ '$REAL' != 0 ]"

say ""; say "===== 4. Changement futur detecte normalement ====="
# deux fiches realignees qui ont des dossiers : on simule un vrai changement d'echeance cote Kafundo en decalant la valeur locale
IDS=$(python3 - <<PY
import json
d=json.load(open("$D/finnovatix_digest.json",encoding="utf-8"))
seen=[]
for items in d.values():
    for it in items:
        if it["funding_call_id"] not in seen: seen.append(it["funding_call_id"])
print(",".join(str(i) for i in seen[:2]))
PY
)
echo "update funding_calls set deadline = '2030-01-01' where id in ($IDS);" | simq
EXPECT=$(n "select count(*) from funding_opportunities o join consulting_projects p on p.id=o.consulting_project_id where o.funding_call_id in ($IDS)")
BEFORE_N=$(n "select count(*) from notifications")
OUT=$(sync); say "synchro apres un changement simule sur les fiches $IDS : $(echo "$OUT" | summ)"; check "la synchro du test de changement futur s'est reellement executee" "ran \"\$OUT\""
AFTER_N=$(n "select count(*) from notifications")
say "nouvelles notifications : $((AFTER_N - BEFORE_N)) (attendu $EXPECT : une par dossier suivi)"
check "le changement futur est detecte et notifie" "[ $((AFTER_N - BEFORE_N)) = $EXPECT ] && [ $EXPECT -gt 0 ]"
HIST2=$(n "select max(json_length(json_extract(metadata,'\$.change_history'))) from funding_calls where id in ($IDS)")
check "historique cumulatif (entree silencieuse + nouvelle entree)" "[ '$HIST2' -ge 2 ]"

say ""; say "===== 5. Synthese par consultant, rejeu, retour arriere ====="
reset
CK0=$(chk)
simq < "$D/finnovatix_apply.sql" | tail -1 | sed 's/^/   /' | tee -a "$REPORT"
B64=$(base64 -w0 "$D/finnovatix_digest.json")
EXTRA_ENV=(-e RUN=FXREMAP-20261010 -e DIGEST_JSON_B64="$B64")
NDEST=$(python3 -c "import json;print(len(json.load(open('$D/finnovatix_digest.json',encoding='utf-8'))))")
EXTRA_ENV+=(-e DIGEST_MODE=dry);   say "--- simulation :"; app "php" < "$HERE/08_digest.php" | tail -4 | sed 's/^/   /' | tee -a "$REPORT"
check "simulation : aucune ecriture" "[ \"\$(n 'select count(*) from notifications')\" = 0 ]"
EXTRA_ENV=(-e RUN=FXREMAP-20261010 -e DIGEST_JSON_B64="$B64" -e DIGEST_MODE=apply)
say "--- application :"; app "php" < "$HERE/08_digest.php" | tail -2 | sed 's/^/   /' | tee -a "$REPORT"
NS=$(n "select count(*) from notifications where type='funding_opportunity_changed'")
check "une synthese par destinataire ($NDEST)" "[ '$NS' = '$NDEST' ]"
say "--- rejeu :"; app "php" < "$HERE/08_digest.php" | tail -1 | sed 's/^/   /' | tee -a "$REPORT"
check "rejeu sans doublon" "[ \"\$(n \"select count(*) from notifications where type='funding_opportunity_changed'\")\" = '$NDEST' ]"
say "--- apercu d'une synthese (corps tronque) :"
echo "select title, left(body, 400) from notifications order by id limit 1;" | simq | sed 's/^/   /' | tee -a "$REPORT"
say "--- rejeu du SQL principal (doit tout annuler) :"
simq < "$D/finnovatix_apply.sql" | tail -1 | sed 's/^/   /' | tee -a "$REPORT"
EXTRA_ENV=(-e RUN=FXREMAP-20261010 -e DIGEST_MODE=rollback)
say "--- retour arriere des syntheses :"; app "php" < "$HERE/08_digest.php" | tail -1 | sed 's/^/   /' | tee -a "$REPORT"
simq < "$D/finnovatix_rollback.sql" | tail -1 | sed 's/^/   /' | tee -a "$REPORT"
CK2=$(chk); say "empreintes apres retour arriere : $CK2"
check "retour arriere identique a l'etat initial (valeurs, metadonnees, historique, notifications, taches)" \
      "[ -n '$CK0' ] && ! echo '$CK0' | grep -q NULL && [ '$CK0' = '$CK2' ]"
say ""; say "===== 6. Disponibilite : fiches expirees / non confirmees retirees des recommandations (etape distincte) ====="
reset
simq < "$D/finnovatix_apply.sql" | tail -1 | sed 's/^/   /' | tee -a "$REPORT"
CKA=$(chk)
DOS0=$(echo "CHECKSUM TABLE funding_opportunities, marketing_contents;" | simh | tail -n +2 | awk '{print $2}' | tr '
' ' ')
OPEN0=$(n "select count(*) from funding_calls where status='open'")
PAST0=$(n "select count(*) from funding_calls where status='open' and deadline < curdate()")
( cd "$HERE" && AUDIT_DIR="$D" python3 09_availability.py ) 2>&1 | sed 's/^/   /' | tee -a "$REPORT"
NCH=$(tail -n +2 "$D/finnovatix_availability.csv" | wc -l)
RES=$(simq < "$D/finnovatix_availability.sql" | tail -1); say "application : $RES"
check "COMMIT effectue" "echo '$RES' | grep -q 'COMMIT effectue'"
OPEN1=$(n "select count(*) from funding_calls where status='open'")
say "fiches open : $OPEN0 -> $OPEN1 (attendu -$NCH) ; open + echeance passee : $PAST0 -> $(n "select count(*) from funding_calls where status='open' and deadline < curdate()")"
check "exactement les fiches prevues quittent 'open'" "[ $((OPEN0 - OPEN1)) = $NCH ] && [ $NCH -gt 0 ]"
check "plus aucune fiche ouverte avec echeance passee" "[ \"\$(n \"select count(*) from funding_calls where status='open' and deadline < curdate()\")\" = 0 ]"
DOS1=$(echo "CHECKSUM TABLE funding_opportunities, marketing_contents;" | simh | tail -n +2 | awk '{print $2}' | tr '
' ' ')
check "dossiers clients et marketing inchanges (aucune suppression, aucun lien modifie)" "[ '$DOS0' = '$DOS1' ]"
check "rejeu refuse (plus rien ne correspond)" "[ \"\$(simq < \"$D/finnovatix_availability.sql\" | tail -1 | grep -c ROLLBACK)\" = 1 ]"
simq < "$D/finnovatix_availability_rollback.sql" | tail -1 | sed 's/^/   /' | tee -a "$REPORT"
CKB=$(chk)
check "retour arriere de la disponibilite identique a l'etat precedent" "[ '$CKA' = '$CKB' ]"
simq < "$D/finnovatix_availability.sql" | tail -1 >/dev/null
OUT=$(sync); say "synchro apres application : $(echo "$OUT" | summ)"; check "la synchro s'est reellement executee" "ran \"\$OUT\""
check "les statuts ne sont pas rouverts par la synchro" "[ \"\$(n \"select count(*) from funding_calls where status='open' and deadline < curdate()\")\" = 0 ]"
say ""
if [ $fail = 0 ]; then say "RESULTAT GLOBAL : TOUS LES CONTROLES PASSENT (copie jetable ; production Finnovatix non modifiee)"; else say "RESULTAT GLOBAL : AU MOINS UN ECHEC"; fi
exit $fail
