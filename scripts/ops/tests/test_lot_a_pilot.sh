#!/usr/bin/env bash
# Tests de lot_a_pilot.sh avec une production SIMULEE (docker, psql, CLI catalog_cleanup, date et API factices).
# Aucune commande reelle docker/psql n'est lancee. Usage : bash scripts/ops/tests/test_lot_a_pilot.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../lot_a_pilot.sh"
W="$(mktemp -d)"; trap 'kill $STUB_PID 2>/dev/null; rm -rf "$W"' EXIT
STATE="$W/state"; BIN="$W/bin"; mkdir -p "$STATE" "$BIN" "$W/logs" "$W/audit"
REALDATE="$(command -v date)"
PASS=0; FAIL=0
ok() { PASS=$((PASS+1)); echo "  [OK]    $1"; }
ko() { FAIL=$((FAIL+1)); echo "  [ECHEC] $1"; [ "${SHOW:-0}" = 1 ] && { echo "    rc=${RC:-?}"; tail -22 "$W/out" 2>/dev/null | sed 's/^/      | /'; }; }
expect() { if eval "$2"; then ok "$1"; else ko "$1"; fi; }

# 50 identifiants attendus + 100 autres fiches du lot ; identifiants reserves (a ne jamais archiver)
python3_bin="$(for c in python3 python; do if "$c" -c 'import sys' >/dev/null 2>&1; then command -v "$c"; break; fi; done)"
printf '#!/usr/bin/env bash\nexec "%s" "$@"\n' "$python3_bin" > "$BIN/python3"
"$python3_bin" - "$W" <<'PY'
import sys, uuid, random
w = sys.argv[1]; random.seed(7)
ids = sorted(str(uuid.UUID(int=random.getrandbits(128))) for _ in range(150))
def out(path, lines):
    with open(path, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
out(f"{w}/audit/lotA_first_sublot_ids.txt", ids[:50])
out(f"{w}/state/a_ids_all", ids)
out(f"{w}/state/fnx_ids", [str(uuid.UUID(int=random.getrandbits(128))) for _ in range(1700)])
PY

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
        if p == "/api/ready": return self._j({"status": "ready", "schema_revision": "c8e1f4a7b2d9"})
        if p == "/api/health": return self._j({"status": "ok"})
        if p.startswith("/api/v1/devices"):
            page = int(self.path.split("page=")[1].split("&")[0]); items = [{"id": f"listed-{i}"} for i in range(250)]
            return self._j({"items": items[(page - 1) * 100: page * 100], "total": 250})
        self._j({}, 404)
s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
with open(os.path.join(STATE, "port"), "w", newline="\n") as f:
    f.write(str(s.server_address[1]))
s.serve_forever()
PY

cat > "$BIN/date" <<EOF
#!/usr/bin/env bash
if [ -f "$STATE/now" ] && [[ " \$* " != *" -d "* ]]; then exec "$REALDATE" -d "\$(cat "$STATE/now")" "\$@"; fi
exec "$REALDATE" "\$@"
EOF
cat > "$BIN/docker" <<'EOF'
#!/usr/bin/env bash
S="$MOCK_STATE"
echo "$*" >> "$S/docker_calls"
INPUT=""
for a in "$@"; do if [ "$a" = "-i" ]; then d=$(cat); [ -n "$d" ] && echo "$d" >> "$S/consumed"; INPUT="$d"; fi; done
sub="$1"; shift
get() { cat "$S/$1" 2>/dev/null || echo "$2"; }
case "$sub" in
  inspect) echo "running mock:image" ;;
  cp) exit 0 ;;
  logs) exit 0 ;;
  exec)
    all="$*"
    case "$all" in
      *catalog_cleanup*apply*)
        echo "$all" >> "$S/apply_calls"
        if [[ "$all" == *"--yes"* ]]; then
          n=$(get archive_count 50); echo yes > "$S/applied"; echo "$n" > "$S/arch_sub"; echo "$n" > "$S/arch_total"; echo "$n" > "$S/jrun"; echo "$((1012 + n))" > "$S/journal"
          echo "{\"batch\": \"A_projets_institutionnels\", \"run_id\": \"x\", \"dry_run\": false, \"planned\": 50, \"archived\": $(get archive_count 50), \"skipped\": []}"
        else
          echo "{\"batch\": \"A_projets_institutionnels\", \"run_id\": \"SIM\", \"dry_run\": true, \"planned\": $(get sim_planned 50)}"
        fi ;;
      *catalog_cleanup*restore*) echo "{\"dry_run\": true, \"entries\": $(get restore_entries 50), \"restored\": 0}" ;;
      *catalog_cleanup*plan*) fp=$(get fp aaaabbbbccccdddd); echo "log line"; echo "{\"total\": 7683, \"batches\": {\"A_projets_institutionnels\": {\"count\": $(get n_a 1118), \"fingerprint\": \"$fp\"}}}" ;;
      *"cat /tmp/lota_pilot_plan"*) echo "id,title,source"; while read -r i; do echo "$i,\"Titre, avec virgule\",src"; done < "$S/a_ids_mock" ;;
      *"rm -rf"*) exit 0 ;;
      *pg_dump*) for i in $(seq 1 300); do echo "dump-line-$i"; done ;;
      *pg_restore*) for i in $(seq 1 300); do echo "toc-$i"; done ;;
      *mysql*) cat "$S/fnx_ids"; [ -f "$S/fnx_extra" ] && cat "$S/fnx_extra" ;;
      *finnovatix-platform-app*) echo 0 ;;
      *python*)
        case "$INPUT" in
          *"print(a, r,"*) echo "$(get celery_busy '0 0 0 0')" ;;
          *) exit 0 ;;
        esac ;;
      *psql*)
        case "$all" in
          *alembic_version*) echo c8e1f4a7b2d9 ;;
          *pg_stat_activity*) echo 0 ;;
          *"left join devices"*) echo 0 ;;
          *"md5(string_agg"*) echo "$(get jfp journalfp)" ;;
          *"run_id='LOTA"*) echo "$(get jrun 0)" ;;
          *favorite_devices*) echo "$(get refs 0)" ;;
          *"validation_status in ('admin_only'"*) echo "$(get inner 50)" ;;
          *"')) and validation_status='archived'"*) echo "$(get prot_arch 0)" ;;
          *"validation_status='archived' and id::text = any"*) echo "$(get arch_sub 0)" ;;
          *"validation_status='archived'"*) echo "$(get arch_total 0)" ;;
          *"count(*) from device_archive_log where device_id"*) echo "$(get jold 4)" ;;
          *"count(*) from device_archive_log"*) echo "$(get journal 1012)" ;;
          *"count(*) from devices"*) echo "$(get devices 7683)" ;;
          *) echo 0 ;;
        esac ;;
    esac ;;
esac
exit 0
EOF
chmod +x "$BIN/date" "$BIN/docker" "$BIN/python3"
export MOCK_STATE="$STATE" REALDATE
"$BIN/python3" "$W/stub.py" "$STATE" & STUB_PID=$!
for i in $(seq 1 50); do [ -f "$STATE/port" ] && break; sleep 0.1; done
PORT="$(cat "$STATE/port")"

reset() {
  rm -f "$STATE"/{consumed,docker_calls,apply_calls,applied,arch_sub,arch_total,fp,n_a,sim_planned,archive_count,restore_entries,celery_busy,refs,inner,jfp,jrun,jold,journal,devices,fnx_extra}
  head -50 "$STATE/a_ids_all" > "$STATE/a_ids_mock"; cp "$STATE/a_ids_all" "$STATE/a_ids_tmp"
  echo "$1" > "$STATE/now"
  cp "$W/audit/lotA_first_sublot_ids.txt" "$W/audit/ids.txt"
  rm -f "$W"/logs/*
}
run() {
  local input="$1"; shift
  if [ "$input" = "__NONE__" ]; then
    PATH="$BIN:$PATH" LOG_DIR="$W/logs" DUMP_DIR="$W/logs" API_BASE="http://127.0.0.1:$PORT" AUDIT_DIR="$W/audit" ACTION_PLAN="$W/none.csv" \
      EXPECT_IDS="$W/audit/ids.txt" bash "$SCRIPT" "$@" < /dev/null > "$W/out" 2>&1
  else
    printf "%b" "$input" | PATH="$BIN:$PATH" LOG_DIR="$W/logs" DUMP_DIR="$W/logs" API_BASE="http://127.0.0.1:$PORT" AUDIT_DIR="$W/audit" ACTION_PLAN="$W/none.csv" \
      EXPECT_IDS="$W/audit/ids.txt" bash "$SCRIPT" "$@" > "$W/out" 2>&1
  fi
  RC=$?
}
nowrite() { [ ! -f "$STATE/applied" ] && [ ! -f "$STATE/apply_calls" ] || { [ -f "$STATE/apply_calls" ] && ! grep -q -- "--yes" "$STATE/apply_calls"; }; }
nodump() { ! ls "$W"/logs/pre_lotA_pilot_*.dump >/dev/null 2>&1; }
export WINDOW_FROM=2026-10-12T21:15 WINDOW_TO=2026-10-12T21:45
IN_WIN="2026-10-12 21:16:00 UTC"

echo "== 1. execution nominale (non interactive, confirmation valide)"
reset "$IN_WIN"; run 'ARCHIVE-50\nLIGNE_SENTINELLE\n' --apply
expect "code retour 0, 50 fiches archivees et controlees" '[ $RC = 0 ] && grep -q "50 FICHES ARCHIVEES ET CONTROLEES" "$W/out"'
expect "un seul apply reel, limite a 50, avec empreinte du plan" '[ "$(grep -c -- "--yes" "$STATE/apply_calls")" = 1 ] && grep -- "--yes" "$STATE/apply_calls" | grep -q -- "--limit 50" && grep -- "--yes" "$STATE/apply_calls" | grep -q -- "--plan-hash aaaabbbbccccdddd"'
expect "run-id affiche et sauvegarde creee avec sha256" 'grep -q "run-id : LOTA-S1-" "$W/out" && ls "$W"/logs/pre_lotA_pilot_*.dump.sha256 >/dev/null 2>&1'
expect "la confirmation n'est lisible par aucune sous-commande" '[ ! -f "$STATE/consumed" ] || ! grep -qE "ARCHIVE-50|LIGNE_SENTINELLE" "$STATE/consumed"'

echo "== 2. confirmation absente ou incorrecte : refus, aucune ecriture"
for bad in "__NONE__" 'archive-50\n' 'ARCHIVE-50 ok\n' 'MIGRATE\n' 'ARCHIVE-500\n' '\n'; do
  reset "$IN_WIN"; run "$bad" --apply
  expect "refus pour [$bad]" '[ $RC = 1 ] && grep -q "confirmation absente ou incorrecte" "$W/out" && [ ! -f "$STATE/docker_calls" ]'
done

echo "== 3. hors fenetre : refus avant toute ecriture"
for t in "2026-10-12 21:14:00 UTC" "2026-10-12 21:45:00 UTC" "2026-10-12 08:30:00 UTC" "2026-10-13 21:20:00 UTC"; do
  reset "$t"; run 'ARCHIVE-50\n' --apply
  expect "refus a $t" '[ $RC = 1 ] && grep -q "hors de la fenetre" "$W/out" && nowrite && nodump'
done
reset "$IN_WIN"; unset WINDOW_FROM WINDOW_TO; run 'ARCHIVE-50\n' --apply; export WINDOW_FROM=2026-10-12T21:15 WINDOW_TO=2026-10-12T21:45
expect "refus sans fenetre" '[ $RC = 1 ] && grep -q "WINDOW_FROM et WINDOW_TO requis" "$W/out" && nowrite && nodump'
reset "2026-10-12 21:30:00 UTC"; run 'ARCHIVE-50\n' --apply
expect "refus s'il reste moins de 20 min (15 min)" '[ $RC = 1 ] && grep -q "temps restant insuffisant" "$W/out" && nowrite && nodump'

echo "== 4. controles du sous-lot : arret sans ecriture"
reset "$IN_WIN"; { head -49 "$STATE/a_ids_all"; sed -n 60p "$STATE/a_ids_all"; } > "$STATE/a_ids_mock"; run 'ARCHIVE-50\n' --apply
expect "identifiants calcules differents des 50 valides" '[ $RC = 1 ] && grep -q "different" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; head -49 "$STATE/a_ids_all" > "$STATE/a_ids_mock"; run 'ARCHIVE-50\n' --apply
expect "49 fiches selectionnees au lieu de 50" '[ $RC = 1 ] && grep -q "contient 49 fiches" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; head -49 "$W/audit/lotA_first_sublot_ids.txt" > "$W/audit/ids.txt"; run 'ARCHIVE-50\n' --apply
expect "fichier d'identifiants a 49 lignes" '[ $RC = 1 ] && grep -q "attendu 50" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; { head -49 "$W/audit/lotA_first_sublot_ids.txt"; echo 8feb4407-42c1-43ee-ab3b-22a3b560924f; } > "$W/audit/ids.txt"; run 'ARCHIVE-50\n' --apply
expect "identifiant reserve (Madagascar) dans le sous-lot" '[ $RC = 1 ] && grep -q "reserve" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; head -1 "$W/audit/lotA_first_sublot_ids.txt" > "$STATE/fnx_extra"; run 'ARCHIVE-50\n' --apply
expect "fiche du sous-lot referencee par Finnovatix" '[ $RC = 1 ] && grep -q "protegee" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; echo 2 > "$STATE/refs"; run 'ARCHIVE-50\n' --apply
expect "reference (favori/pipeline/alerte) sur le sous-lot" '[ $RC = 1 ] && grep -q "references trouvees" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; echo 49 > "$STATE/inner"; run 'ARCHIVE-50\n' --apply
expect "fiche publique ou d'un autre type dans le sous-lot" '[ $RC = 1 ] && grep -q "publique ou d.un autre type" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; echo "1 0 0 0" > "$STATE/celery_busy"; run 'ARCHIVE-50\n' --apply
expect "tache Celery active" '[ $RC = 1 ] && grep -q "tache Celery" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; echo 49 > "$STATE/sim_planned"; run 'ARCHIVE-50\n' --apply
expect "la simulation ne planifie pas 50" '[ $RC = 1 ] && grep -q "ne planifie pas exactement 50" "$W/out" && nowrite && nodump'

echo "== 5. anomalies apres archivage : alerte, pas de poursuite"
reset "$IN_WIN"; echo 49 > "$STATE/archive_count"; run 'ARCHIVE-50\n' --apply
expect "49 archivees : anomalie (code 1) + commande de restauration" '[ $RC = 1 ] && grep -q "ANOMALIE" "$W/out" && grep -q "restore --run-id LOTA-S1-" "$W/out"'
reset "$IN_WIN"; echo 47 > "$STATE/restore_entries"; run 'ARCHIVE-50\n' --apply
expect "restauration indisponible pour 50 entrees : anomalie" '[ $RC = 1 ] && grep -q "restauration non disponible" "$W/out"'

echo "== 6. simulation par defaut : aucune ecriture"
reset "$IN_WIN"; run "__NONE__"
expect "simulation OK" '[ $RC = 0 ] && grep -q "tous les controles sont satisfaisants" "$W/out" && nowrite && nodump'

echo ""
echo "RESULTAT : $PASS reussis, $FAIL en echec"
[ "$FAIL" = 0 ]
