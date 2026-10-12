#!/usr/bin/env bash
# Tests de migration_execute.sh avec une production SIMULEE (docker, swap_container, date et API factices).
# Aucune commande reelle docker/psql n'est lancee. Usage : bash scripts/ops/tests/test_migration_execute.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../migration_execute.sh"
W="$(mktemp -d)"; trap 'kill $STUB_PID 2>/dev/null; rm -rf "$W"' EXIT
STATE="$W/state"; BIN="$W/bin"; mkdir -p "$STATE" "$BIN" "$W/logs"
REALDATE="$(command -v date)"
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "  [OK]    $1"; }
ko()   { FAIL=$((FAIL+1)); echo "  [ECHEC] $1"; [ "${SHOW:-0}" = 1 ] && { echo "    rc=${RC:-?} ; sortie :"; tail -8 "$W/out" 2>/dev/null | sed 's/^/      | /'; }; }
expect() { if eval "$2"; then ok "$1"; else ko "$1"; fi; }

# ---------------- faux serveur API ----------------
cat > "$W/stub.py" <<'PY'
import http.server, json, sys, os
STATE = sys.argv[1]
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _j(self, o, c=200):
        b = json.dumps(o).encode(); self.send_response(c); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/api/health": return self._j({"status": "ok"})
        if p == "/api/ready":
            rev = open(os.path.join(STATE, "rev")).read().strip()
            return self._j({"status": "ready", "schema_revision": rev})
        if p.startswith("/api/v1/devices"):
            page = int(self.path.split("page=")[1].split("&")[0]); items = [{"id": f"d{i}"} for i in range(250)]
            return self._j({"items": items[(page - 1) * 100: page * 100], "total": 250})
        self._j({}, 404)
s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
open(os.path.join(STATE, "port"), "w").write(str(s.server_address[1]))
s.serve_forever()
PY

# ---------------- faux date (horloge pilotee par $STATE/now) ----------------
cat > "$BIN/date" <<EOF
#!/usr/bin/env bash
if [ -f "$STATE/now" ] && [[ " \$* " != *" -d "* ]]; then exec "$REALDATE" -d "\$(cat "$STATE/now")" "\$@"; fi
exec "$REALDATE" "\$@"
EOF
# ---------------- faux docker ----------------
cat > "$BIN/docker" <<'EOF'
#!/usr/bin/env bash
S="$MOCK_STATE"
echo "$*" >> "$S/docker_calls"
# un `-i` sans redirection lirait l'entree standard : on le simule (et on enregistre toute consommation)
for a in "$@"; do if [ "$a" = "-i" ]; then d=$(cat); [ -n "$d" ] && echo "$d" >> "$S/consumed"; INPUT="$d"; fi; done
sub="$1"; shift
rev() { cat "$S/rev"; }
img() { cat "$S/img_$1" 2>/dev/null || echo "kafundo-$1:old"; }
case "$sub" in
  inspect)
    case "$*" in
      *State.Status*) n="${@: -1}"; echo "running $(img "${n#kafundo-}")" ;;
      *State.Health*) echo healthy ;;
      *Config.Image*kafundo-backend*kafundo-worker*kafundo-beat*) for n in backend worker beat; do echo "$(img $n)"; done ;;
      *Config.Image*) echo "prev:image" ;;
    esac ;;
  image)
    if [ "${MISSING_IMAGE:-0}" = 1 ]; then exit 1; fi
    case "$*" in *Created*) "$REALDATE" -u -d "$(cat "$S/now" 2>/dev/null || "$REALDATE" -u) - ${IMG_AGE_H:-1} hours" +%Y-%m-%dT%H:%M:%S.000000000Z ;; esac ;;
  container) exit 0 ;;
  rename) exit 0 ;;
  logs) [ "${BEAT_FIRED:-0}" -gt 0 ] && for i in $(seq 1 "$BEAT_FIRED"); do echo "Scheduler: Sending due task x"; done; exit 0 ;;
  exec)
    all="$*"
    case "$all" in
      *pg_dump*) echo "$all" >> "$S/dump_calls"; for i in $(seq 1 300); do echo "dump-line-$i"; done ;;
      *pg_restore*) for i in $(seq 1 300); do echo "toc-$i"; done ;;
      *psql*)
        case "$all" in
          *alembic_version*) rev ;;
          *server_version*) echo 15.17 ;;
          *"operations"*|*"now()-xact_start"*) echo "${LONG_OPS:-0}" ;;
          *pg_stat_activity*) echo 1 ;;
          *"left join devices"*) echo "${ORPHANS:-0}" ;;
          *confdeltype*) cat "$S/fks" ;;
          *validation_status=*archived*) echo 0 ;;
          *"from device_archive_log"*) echo 1012 ;;
          *"from devices"*) echo 7683 ;;
          *) echo 0 ;;
        esac ;;
      *finnovatix*) echo 0 ;;
      *kafundo-worker*python*)
        case "$INPUT" in
          *"print(a, r,"*) echo "${CELERY_BUSY:-0 0 0}" ;;
          *"print(*[c.llen"*) echo "0 0 0 0" ;;
          *) [ "${PING_FAIL:-0}" = 1 ] && exit 1; exit 0 ;;
        esac ;;
    esac ;;
esac
exit 0
EOF
# ---------------- faux swap_container ----------------
cat > "$BIN/swap_container" <<'EOF'
#!/usr/bin/env bash
S="$MOCK_STATE"
echo "$*" >> "$S/swap_calls"
case "$1" in
  swap) n="${2#kafundo-}"; img="${4}"; echo "$img" > "$S/img_$n"
        [ -n "${ADVANCE_ON_SWAP:-}" ] && "$REALDATE" -u -d "$(cat "$S/now") + ${ADVANCE_ON_SWAP} minutes" +"%Y-%m-%d %H:%M:%S UTC" > "$S/now"
        echo "4/4 OK" ;;
  run-once) if [ "${FAIL_MIGRATION:-0}" = 1 ]; then echo "migration en echec"; exit 1; fi
            echo c8e1f4a7b2d9 > "$S/rev"; echo rr > "$S/fks"; echo "Schema verifie a head" ;;
  rollback) echo "rollback" ;;
esac
EOF
# python3 : sur certains postes (Windows) seul `python` est utilisable
PYREAL="$(for c in python3 python; do if "$c" -c 'import sys' >/dev/null 2>&1; then command -v "$c"; break; fi; done)"
printf '#!/usr/bin/env bash\nexec "%s" "$@"\n' "$PYREAL" > "$BIN/python3"
chmod +x "$BIN/date" "$BIN/docker" "$BIN/swap_container" "$BIN/python3"
export MOCK_STATE="$STATE" REALDATE

"$BIN/python3" "$W/stub.py" "$STATE" & STUB_PID=$!
for i in $(seq 1 50); do [ -f "$STATE/port" ] && break; sleep 0.1; done
PORT="$(cat "$STATE/port")"

reset() {  # $1 = heure simulee "YYYY-MM-DD HH:MM:SS UTC"
  rm -f "$STATE"/{consumed,docker_calls,swap_calls,dump_calls} "$W"/logs/*
  echo b7d3a91c5e24 > "$STATE/rev"; echo cn > "$STATE/fks"
  for n in backend worker beat; do echo "kafundo-$n:old" > "$STATE/img_$n"; done
  echo "$1" > "$STATE/now"
  unset MISSING_IMAGE IMG_AGE_H LONG_OPS ORPHANS CELERY_BUSY PING_FAIL FAIL_MIGRATION ADVANCE_ON_SWAP BEAT_FIRED CONFIRM_MIGRATE
}
run() {  # $1 = entree standard ; args suivants = arguments du script ; sortie dans $W/out ; code dans $RC
  local input="$1"; shift
  if [ "$input" = "__NONE__" ]; then
    PATH="$BIN:$PATH" LOG_DIR="$W/logs" API_BASE="http://127.0.0.1:$PORT" DF_PATH="/tmp" SWAP_CMD="$BIN/swap_container" \
      POST_SWAP_SLEEP=0 IMAGE_TAG=fixes3-test bash "$SCRIPT" "$@" < /dev/null > "$W/out" 2>&1
  else
    printf "%b" "$input" | PATH="$BIN:$PATH" LOG_DIR="$W/logs" API_BASE="http://127.0.0.1:$PORT" DF_PATH="/tmp" SWAP_CMD="$BIN/swap_container" \
      POST_SWAP_SLEEP=0 IMAGE_TAG=fixes3-test bash "$SCRIPT" "$@" > "$W/out" 2>&1
  fi
  RC=$?
}
nowrite() { [ ! -f "$STATE/swap_calls" ] && [ ! -f "$STATE/dump_calls" ] && [ "$(cat "$STATE/rev")" = b7d3a91c5e24 ]; }
WIN="WINDOW_FROM=2026-10-12T05:10 WINDOW_TO=2026-10-12T05:55"
export WINDOW_FROM=2026-10-12T05:10 WINDOW_TO=2026-10-12T05:55

echo "== 1. execution non interactive avec confirmation valide (la confirmation n'est pas consommee par les sous-commandes)"
reset "2026-10-12 05:12:00 UTC"; run 'MIGRATE\nLIGNE_SENTINELLE\n' --apply
expect "code retour 0" '[ $RC = 0 ]'
expect "migration appliquee" 'grep -q "MIGRATION APPLIQUEE ET CONTROLEE" "$W/out" && [ "$(cat $STATE/rev)" = c8e1f4a7b2d9 ]'
expect "3 swaps puis migration, dans l'ordre" '[ "$(grep -c "^swap" $STATE/swap_calls)" = 3 ] && grep -q "^run-once" $STATE/swap_calls && [ "$(head -1 $STATE/swap_calls | cut -d" " -f2)" = kafundo-backend ]'
expect "sauvegarde realisee avant les swaps" '[ -f "$STATE/dump_calls" ]'
expect "aucune sous-commande n'a lu la confirmation ni les lignes suivantes de l'entree standard" '[ ! -f "$STATE/consumed" ] || ! grep -qE "MIGRATE|LIGNE_SENTINELLE" "$STATE/consumed"'
expect "indisponibilite mesuree affichee" 'grep -q "indisponibilite mesuree" "$W/out"'

echo "== 2. execution sans confirmation (entree standard vide) : refus"
reset "2026-10-12 05:12:00 UTC"; run "__NONE__" --apply
expect "refus (code 1)" '[ $RC = 1 ] && grep -q "confirmation absente ou incorrecte" "$W/out"'
expect "aucune ecriture, aucune commande docker" 'nowrite && [ ! -f "$STATE/docker_calls" ]'

echo "== 3. confirmation incorrecte : refus"
for bad in 'migrate\n' 'MIGRATE please\n' 'yes\n' 'MIGRATE ' '\n'; do
  reset "2026-10-12 05:12:00 UTC"; run "$bad" --apply
  expect "refus pour [$bad]" '[ $RC = 1 ] && nowrite && [ ! -f "$STATE/docker_calls" ]'
done

echo "== 4. une variable d'environnement ne remplace pas la confirmation"
reset "2026-10-12 05:12:00 UTC"; export CONFIRM_MIGRATE=MIGRATE; run "__NONE__" --apply; unset CONFIRM_MIGRATE
expect "refus malgre CONFIRM_MIGRATE=MIGRATE" '[ $RC = 1 ] && nowrite'

echo "== 5. hors fenetre : refus (avec confirmation valide)"
for t in "2026-10-12 05:09:00 UTC" "2026-10-12 05:55:00 UTC" "2026-10-12 06:30:00 UTC" "2026-10-13 05:20:00 UTC"; do
  reset "$t"; run 'MIGRATE\n' --apply
  expect "refus a $t" '[ $RC = 1 ] && grep -q "hors de la fenetre" "$W/out" && nowrite'
done
reset "2026-10-12 05:12:00 UTC"; unset WINDOW_FROM WINDOW_TO; run 'MIGRATE\n' --apply; export WINDOW_FROM=2026-10-12T05:10 WINDOW_TO=2026-10-12T05:55
expect "refus sans WINDOW_FROM/WINDOW_TO" '[ $RC = 1 ] && grep -q "WINDOW_FROM et WINDOW_TO requis" "$W/out" && nowrite'

echo "== 6. echec d'un precontrole : arret sans modification"
reset "2026-10-12 05:12:00 UTC"; export MISSING_IMAGE=1; run 'MIGRATE\n' --apply
expect "image absente" '[ $RC = 1 ] && grep -q "image absente" "$W/out" && nowrite'
reset "2026-10-12 05:12:00 UTC"; export IMG_AGE_H=30; run 'MIGRATE\n' --apply
expect "image trop ancienne" '[ $RC = 1 ] && grep -q "images trop anciennes" "$W/out" && nowrite'
reset "2026-10-12 05:12:00 UTC"; export CELERY_BUSY="2 0 0"; run 'MIGRATE\n' --apply
expect "tache Celery active" '[ $RC = 1 ] && grep -q "taches Celery en cours" "$W/out" && nowrite'
reset "2026-10-12 05:12:00 UTC"; export LONG_OPS=3; run 'MIGRATE\n' --apply
expect "operation PostgreSQL longue" '[ $RC = 1 ] && grep -q "operation longue" "$W/out" && nowrite'
reset "2026-10-12 05:12:00 UTC"; export ORPHANS=2; run 'MIGRATE\n' --apply
expect "journal orphelin" '[ $RC = 1 ] && grep -q "orphelines" "$W/out" && nowrite'
reset "2026-10-12 05:12:00 UTC"; echo c8e1f4a7b2d9 > "$STATE/rev"; run 'MIGRATE\n' --apply
expect "revision deja migree" '[ $RC = 1 ] && grep -q "revision c8e1f4a7b2d9" "$W/out" && [ ! -f "$STATE/swap_calls" ]'

echo "== 7. temps restant insuffisant"
reset "2026-10-12 05:40:00 UTC"; run 'MIGRATE\n' --apply
expect "refus au demarrage (15 min restantes < 25)" '[ $RC = 4 ] && grep -q "temps restant insuffisant" "$W/out" && nowrite'
reset "2026-10-12 05:12:00 UTC"; export ADVANCE_ON_SWAP=14; run 'MIGRATE\n' --apply
expect "arret avant la migration si le temps manque apres les swaps" '[ $RC = 4 ] && grep -q "temps restant insuffisant" "$W/out" && grep -q "avant : migration du schema" "$W/out" && [ "$(cat $STATE/rev)" = b7d3a91c5e24 ] && ! grep -q "^run-once" $STATE/swap_calls'

echo "== 8. echecs pendant l'operation"
reset "2026-10-12 05:12:00 UTC"; export BEAT_FIRED=3; run 'MIGRATE\n' --apply
expect "beat lance des taches : arret avant migration (code 3)" '[ $RC = 3 ] && [ "$(cat $STATE/rev)" = b7d3a91c5e24 ] && ! grep -q "^run-once" $STATE/swap_calls'
reset "2026-10-12 05:12:00 UTC"; export FAIL_MIGRATION=1; run 'MIGRATE\n' --apply
expect "migration en echec : code 2, revision inchangee, rollback affiche" '[ $RC = 2 ] && grep -q "ECHEC de la migration" "$W/out" && [ "$(cat $STATE/rev)" = b7d3a91c5e24 ]'

echo "== 9. simulation par defaut (sans --apply) : aucune ecriture"
reset "2026-10-12 05:12:00 UTC"; run "__NONE__"
expect "simulation OK sans ecriture" '[ $RC = 0 ] && grep -q "pre-controles OK" "$W/out" && nowrite'

echo "== 10. test de sensibilite : mutant = defaut d'origine (docker exec -i heritant de l'entree standard, sans fermeture) -> le banc doit le detecter"
grep -v '^exec 0</dev/null' "$SCRIPT" | sed 's|docker exec "$PG" psql|docker exec -i "$PG" psql|' > "$W/mutant.sh"
REAL_SCRIPT="$SCRIPT"; SCRIPT="$W/mutant.sh"
reset "2026-10-12 05:12:00 UTC"; run 'MIGRATE
LIGNE_SENTINELLE
' --apply
SCRIPT="$REAL_SCRIPT"
expect "le mutant laisse une sous-commande lire l'entree standard (detecte par le banc)" '[ -f "$STATE/consumed" ] && grep -q "LIGNE_SENTINELLE" "$STATE/consumed"'

echo ""
echo "RESULTAT : $PASS reussis, $FAIL en echec"
[ "$FAIL" = 0 ]
