#!/usr/bin/env bash
# Controle LECTURE SEULE apres la synchronisation de 06:30 UTC : nombre reel de notifications, doublons, creations, echecs.
#   bash 10_post_sync_check.sh [SINCE='YYYY-MM-DD 06:25:00'] [EXPECTED=81]
# SINCE : par defaut aujourd'hui 06:25 (heure du serveur = UTC, comme la base).
set -uo pipefail
MYSQL_CONTAINER="${MYSQL_CONTAINER:-finnovatix-platform-finnovatix-mysql-1}"
SINCE="${1:-$(date -u +%F) 06:25:00}"; EXPECTED="${2:-81}"
q() { docker exec -i "$MYSQL_CONTAINER" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --default-character-set=utf8mb4 --batch --skip-column-names finnovatix' 2>&1 | grep -av "Using a password"; }
N=$(echo "select count(*) from notifications where type='funding_opportunity_changed' and created_at >= '$SINCE';" | q | tail -1)
D=$(echo "select count(*) from (select user_id, title, body, action_url from notifications where type='funding_opportunity_changed' and created_at >= '$SINCE' group by 1,2,3,4 having count(*) > 1) t;" | q | tail -1)
R=$(echo "select count(distinct user_id), count(distinct title) from notifications where type='funding_opportunity_changed' and created_at >= '$SINCE';" | q | tail -1)
T=$(echo "select count(*) from funding_calls where last_verified_at >= '$SINCE';" | q | tail -1)
C=$(echo "select count(*) from funding_calls where created_at >= '$SINCE';" | q | tail -1)
FJ=$(echo "select count(*) from failed_jobs where failed_at >= '$SINCE';" | q | tail -1)
PJ=$(echo "select count(*) from jobs;" | q | tail -1)
OTHER=$(echo "select count(*) from notifications where type <> 'funding_opportunity_changed' and created_at >= '$SINCE';" | q | tail -1)
APP_CONTAINER="${APP_CONTAINER:-finnovatix-platform-app-1}"
CAP=$(docker exec "$APP_CONTAINER" sh -c 'grep -E "^KAFUNDO_SYNC_CREATE_CAP=" /var/www/html/.env | cut -d= -f2' 2>/dev/null || true)
echo "Depuis                                   : $SINCE (UTC)"
echo "fiches verifiees par la synchro          : $T"
echo "fiches creees (attendu 0, plafond 0)     : $C"
echo "notifications 'modification detectee'    : $N (attendu ~$EXPECTED ; ecart = changements reels survenus entre-temps)"
echo "  destinataires / dispositifs distincts  : $R"
echo "  doublons exacts (user,titre,corps,lien) : $D (attendu 0)"
echo "autres notifications sur la periode      : $OTHER (non liees a la synchro)"
echo "KAFUNDO_SYNC_CREATE_CAP                 : ${CAP:-absent} (attendu 0)"
echo "taches echouees depuis / en file         : $FJ / $PJ"
[ "$D" = 0 ] && [ "$C" = 0 ] && [ "$CAP" = 0 ] && echo "RESULTAT : OK (aucun doublon, aucune creation)" || { echo "RESULTAT : A EXAMINER"; exit 1; }
