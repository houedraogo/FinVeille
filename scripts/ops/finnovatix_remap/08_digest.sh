#!/usr/bin/env bash
# Synthese par consultant : bash 08_digest.sh [--apply|--rollback]  (simulation par defaut). Ecrit dans la table notifications
# UNIQUEMENT avec --apply, via NotificationCenter (aucune notification individuelle, aucun e-mail).
set -euo pipefail
AUDIT_DIR="${AUDIT_DIR:-/opt/finveille-backups/audit_20261010}"
APP_CONTAINER="${APP_CONTAINER:-finnovatix-platform-app-1}"
MODE=dry; case "${1:-}" in --apply) MODE=apply;; --rollback) MODE=rollback;; "") ;; *) echo "option inconnue" >&2; exit 2;; esac
[ "$MODE" = dry ] || [ "${ASSUME_YES:-0}" = 1 ] || { read -rp "Tapez $(echo $MODE | tr a-z A-Z) : " c; [ "$c" = "$(echo $MODE | tr a-z A-Z)" ] || exit 1; }
B64=$(base64 -w0 "$AUDIT_DIR/finnovatix_digest.json")
docker exec -i -e RUN=FXREMAP-20261010 -e DIGEST_MODE="$MODE" -e DIGEST_JSON_B64="$B64" "$APP_CONTAINER" php < "$(dirname "$(readlink -f "$0")")/08_digest.php"
