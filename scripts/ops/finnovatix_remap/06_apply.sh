#!/usr/bin/env bash
# Rattachement des kafundo_id Finnovatix (PRODUCTION) - SIMULATION par défaut, écriture seulement avec --apply.
#
#   bash 06_apply.sh                       # contrôles + plan chiffré, n'écrit RIEN
#   bash 06_apply.sh --apply               # applique finnovatix_apply.sql (transaction gardée par ligne)
#   bash 06_apply.sh --apply --with-merge  # + fusion optionnelle (3 FundingCall dont la cible n'a aucun dossier)
#   bash 06_apply.sh --rollback            # retour arrière exact (valeurs d'origine capturées avant le changement)
#
# NE PAS EXÉCUTER --apply / --rollback sans accord explicite du propriétaire et créneau convenu.
#
# Garanties :
#   * sauvegarde vérifiée (gzip -t + sha256) de moins de MAX_BACKUP_AGE_H heures, sinon arrêt ;
#   * refuse de tourner pendant la synchronisation Kafundo de Finnovatix (06:30) ou si elle est en cours ;
#   * le script SQL est transactionnel : une seule ligne hors état attendu => ROLLBACK complet (rejeu sans effet) ;
#   * ne touche ni funding_opportunities ni marketing_contents (sauf --with-merge, journalisé et réversible) ;
#   * jamais de mot de passe en argument ni à l'écran : MYSQL_PWD est lu DANS le conteneur MySQL.
set -euo pipefail

AUDIT_DIR="${AUDIT_DIR:-/opt/finveille-backups/audit_20261010}"
MYSQL_CONTAINER="${MYSQL_CONTAINER:-finnovatix-platform-finnovatix-mysql-1}"
APP_CONTAINER="${APP_CONTAINER:-finnovatix-platform-app-1}"
DB="${DB:-finnovatix}"
EXPECT_FUNDING_CALLS="${EXPECT_FUNDING_CALLS:-1775}"
MAX_BACKUP_AGE_H="${MAX_BACKUP_AGE_H:-3}"
BLOCKED_FROM="${BLOCKED_FROM:-06:15}"; BLOCKED_TO="${BLOCKED_TO:-06:55}"   # fenêtre de la synchro quotidienne 06:30

MODE=dry; WITH_MERGE=0
for a in "$@"; do
  case "$a" in
    --apply) MODE=apply ;; --rollback) MODE=rollback ;; --with-merge) WITH_MERGE=1 ;;
    -h|--help) sed -n 2,20p "$0"; exit 0 ;;
    *) echo "option inconnue: $a" >&2; exit 2 ;;
  esac
done

say() { printf '%s\n' "$*"; }
die() { printf 'ARRÊT: %s\n' "$*" >&2; exit 1; }
mysql_q() { docker exec -i "$MYSQL_CONTAINER" sh -c "MYSQL_PWD=\"\$MYSQL_ROOT_PASSWORD\" mysql -uroot --default-character-set=utf8mb4 --batch --skip-column-names $DB" 2>&1 | grep -av "Using a password" || true; }

# ---------- 1. Contrôles préalables (lecture seule) ----------
for f in finnovatix_apply.sql finnovatix_rollback.sql finnovatix_action_plan.csv; do
  [ -f "$AUDIT_DIR/$f" ] || die "fichier introuvable: $AUDIT_DIR/$f"
done
BK="$(ls -t "$AUDIT_DIR"/finnovatix_funding_backup_*.sql.gz 2>/dev/null | head -1 || true)"
[ -n "$BK" ] || die "aucune sauvegarde finnovatix_funding_backup_*.sql.gz dans $AUDIT_DIR"
( cd "$AUDIT_DIR" && sha256sum -c "$(basename "$BK").sha256" >/dev/null ) || die "somme SHA-256 de la sauvegarde invalide"
gzip -t "$BK" || die "sauvegarde illisible"
AGE_H=$(( ( $(date +%s) - $(stat -c %Y "$BK") ) / 3600 ))
[ "$AGE_H" -lt "$MAX_BACKUP_AGE_H" ] || die "sauvegarde trop ancienne (${AGE_H} h >= ${MAX_BACKUP_AGE_H} h): refaire 05_simulate.sh"
docker inspect -f '{{.State.Health.Status}}' "$MYSQL_CONTAINER" 2>/dev/null | grep -q healthy || die "$MYSQL_CONTAINER n'est pas sain"

NOW_HM="$(date +%H:%M)"
if [[ "$NOW_HM" > "$BLOCKED_FROM" && "$NOW_HM" < "$BLOCKED_TO" ]] && [ "$MODE" != dry ]; then
  die "fenêtre de synchronisation Kafundo->Finnovatix ($BLOCKED_FROM-$BLOCKED_TO, heure du serveur): réessayer hors fenêtre"
fi
if docker exec "$APP_CONTAINER" sh -c 'pgrep -f "kafundo:sync-funding-calls" >/dev/null' 2>/dev/null; then
  die "la synchronisation kafundo:sync-funding-calls est en cours"
fi

COUNT="$(echo "select count(*) from funding_calls;" | mysql_q | tail -1)"
[ "$COUNT" = "$EXPECT_FUNDING_CALLS" ] || die "funding_calls = $COUNT (attendu $EXPECT_FUNDING_CALLS): l'état a changé depuis la simulation, refaire 04 et 05"

# plafond de creation : doit etre 0 (sinon la synchro suivante creerait des doublons / LinkedIn / rapprochements de leads)
CAP="$(docker exec "$APP_CONTAINER" sh -c 'grep -E "^KAFUNDO_SYNC_CREATE_CAP=" /var/www/html/.env | cut -d= -f2' 2>/dev/null || true)"
if [ "$MODE" != dry ] && [ "${SKIP_CAP_CHECK:-0}" != 1 ] && [ "$CAP" != "0" ]; then die "KAFUNDO_SYNC_CREATE_CAP='${CAP:-absent}' (attendu 0)"; fi

N_UPD="$(grep -c '^UPDATE funding_calls' "$AUDIT_DIR/finnovatix_apply.sql")"
say "Sauvegarde vérifiée : $(basename "$BK") (${AGE_H} h)"
say "funding_calls       : $COUNT (attendu $EXPECT_FUNDING_CALLS)"
say "UPDATE prévus       : $N_UPD"
say "Répartition par action :"
tail -n +2 "$AUDIT_DIR/finnovatix_action_plan.csv" | cut -d, -f3 | sort | uniq -c | sed 's/^/   /'
say "Fenêtre horaire     : OK ($NOW_HM, interdit $BLOCKED_FROM-$BLOCKED_TO)"

if [ "$MODE" = dry ]; then
  say ""; say "(simulation) Aucune écriture. Pour appliquer : bash $0 --apply   (accord explicite requis)"
  exit 0
fi

# ---------- 2. Exécution ----------
if [ "${ASSUME_YES:-0}" != "1" ]; then
  read -rp "Tapez $(echo "$MODE" | tr a-z A-Z) pour exécuter sur la PRODUCTION Finnovatix : " CONFIRM
  [ "$CONFIRM" = "$(echo "$MODE" | tr a-z A-Z)" ] || die "confirmation absente"
fi
snapshot() { echo "select count(*), count(distinct kafundo_id), sum(status='open'), sum(status='expired'), sum(status='unknown'), sum(status='recurring'), \
  (select count(*) from funding_opportunities), (select count(*) from marketing_contents) from funding_calls;" | mysql_q | tail -1; }
BEFORE="$(snapshot)"
say "AVANT : fc / kafundo_id distincts / open / expired / unknown / recurring / opportunités / marketing = $(echo "$BEFORE" | tr '\t' ' ')"

if [ "$MODE" = apply ]; then
  OUT="$(mysql_q < "$AUDIT_DIR/finnovatix_apply.sql" | tail -2)"
  say "$OUT"
  echo "$OUT" | grep -q "COMMIT effectue" || die "ROLLBACK automatique: aucune modification appliquée"
  if [ "$WITH_MERGE" = 1 ]; then
    mysql_q < "$AUDIT_DIR/finnovatix_apply_optional_M.sql" | tail -1
  fi
else
  mysql_q < "$AUDIT_DIR/finnovatix_rollback_optional_M.sql" >/dev/null || true
  mysql_q < "$AUDIT_DIR/finnovatix_rollback.sql" | tail -1
fi
AFTER="$(snapshot)"
say "APRÈS : fc / kafundo_id distincts / open / expired / unknown / recurring / opportunités / marketing = $(echo "$AFTER" | tr '\t' ' ')"
DUP="$(echo "select count(*) from (select kafundo_id from funding_calls group by kafundo_id having count(*) > 1) t;" | mysql_q | tail -1)"
say "doublons kafundo_id : $DUP (attendu 0)"
printf '%s\tmode=%s\tavant=%s\tapres=%s\n' "$(date -u +%FT%TZ)" "$MODE" "$BEFORE" "$AFTER" >> "${JOURNAL:-$AUDIT_DIR/finnovatix_apply_journal.tsv}"
if [ "$MODE" = apply ]; then
  say ""; say "--- verification (valeurs rattachees == API Kafundo, doublons, annotations) :"
  ( cd "$(dirname "$(readlink -f "$0")")" && AUDIT_DIR="$AUDIT_DIR" python3 07_verify.py ) || say "ATTENTION : ecarts detectes, voir ci-dessus (retour arriere possible)"
  say ""; say "Synthese par consultant (non envoyee) : bash $(dirname "$0")/08_digest.sh   puis --apply apres verification"
  say "Retour arrière si nécessaire : 1) bash $(dirname "$0")/08_digest.sh --rollback  2) bash $0 --rollback"
fi
