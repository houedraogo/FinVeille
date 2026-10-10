#!/usr/bin/env bash
# Retire des recommandations les fiches 'open' expirees / non confirmees (voir 09_availability.py).
#   bash 09_apply_availability.sh              # simulation : affiche le plan, n'ecrit RIEN
#   bash 09_apply_availability.sh --apply      # applique (confirmation APPLY) ; apres 06_apply.sh, avec accord explicite
#   bash 09_apply_availability.sh --rollback   # retour arriere exact
# Prealable : bash 09_availability.py regenere les scripts depuis l'etat reel (lecture seule).
set -euo pipefail
AUDIT_DIR="${AUDIT_DIR:-/opt/finveille-backups/audit_20261010}"
MYSQL_CONTAINER="${MYSQL_CONTAINER:-finnovatix-platform-finnovatix-mysql-1}"
MODE=dry; case "${1:-}" in --apply) MODE=apply;; --rollback) MODE=rollback;; "") ;; *) echo "option inconnue" >&2; exit 2;; esac
die() { echo "ARRÊT: $*" >&2; exit 1; }
q() { docker exec -i "$MYSQL_CONTAINER" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --default-character-set=utf8mb4 --batch --skip-column-names finnovatix' 2>&1 | grep -av "Using a password" || true; }
for f in finnovatix_availability.sql finnovatix_availability_rollback.sql finnovatix_availability.csv; do [ -f "$AUDIT_DIR/$f" ] || die "manquant: $f"; done
BK="$(ls -t "$AUDIT_DIR"/finnovatix_funding_backup_*.sql.gz | head -1)"; [ -n "$BK" ] || die "aucune sauvegarde"
( cd "$AUDIT_DIR" && sha256sum -c "$(basename "$BK").sha256" >/dev/null ) || die "sha256 invalide"
[ $(( ( $(date +%s) - $(stat -c %Y "$BK") ) / 3600 )) -lt "${MAX_BACKUP_AGE_H:-3}" ] || die "sauvegarde trop ancienne"
N=$(( $(wc -l < "$AUDIT_DIR/finnovatix_availability.csv") - 1 ))
echo "fiches concernées : $N (dossiers et contenus marketing non modifiés)"
cut -d, -f2,3,4 "$AUDIT_DIR/finnovatix_availability.csv" | tail -n +2 | sort | uniq -c | sed 's/^/   /'
[ "$MODE" = dry ] && { echo "(simulation) aucune écriture"; exit 0; }
H=$(date +%H:%M); [[ "$H" > "06:15" && "$H" < "06:55" ]] && die "fenêtre de synchronisation 06:15-06:55"
if [ "${ASSUME_YES:-0}" != 1 ]; then read -rp "Tapez $(echo $MODE | tr a-z A-Z) pour exécuter sur la PRODUCTION : " c; [ "$c" = "$(echo $MODE | tr a-z A-Z)" ] || die "confirmation absente"; fi
if [ "$MODE" = apply ]; then q < "$AUDIT_DIR/finnovatix_availability.sql" | tail -1; else q < "$AUDIT_DIR/finnovatix_availability_rollback.sql" | tail -1; fi
echo "fiches open : $(echo "select count(*) from funding_calls where status='open';" | q | tail -1) ; open + échéance passée : $(echo "select count(*) from funding_calls where status='open' and deadline < curdate();" | q | tail -1)"
