#!/usr/bin/env bash
# Tests de lot_a_pilot.sh (sous-lots de 50 et de 200) avec une production SIMULEE : docker, psql, CLI catalog_cleanup, date, sleep,
# journalctl, /proc et API factices. Aucune commande reelle docker/psql n'est lancee.
# Usage : bash scripts/ops/tests/test_lot_a_pilot.sh      (SHOW=1 pour afficher la sortie des echecs)
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../lot_a_pilot.sh"
W="$(mktemp -d)"; trap 'kill $STUB_PID 2>/dev/null; rm -rf "$W"' EXIT
STATE="$W/state"; BIN="$W/bin"; PROC="$W/proc"; mkdir -p "$STATE" "$BIN" "$PROC" "$W/logs" "$W/audit"
REALDATE="$(command -v date)"
PASS=0; FAIL=0
ok() { PASS=$((PASS+1)); echo "  [OK]    $1"; }
ko() { FAIL=$((FAIL+1)); echo "  [ECHEC] $1"; [ "${SHOW:-0}" = 1 ] && { echo "    rc=${RC:-?}"; tail -22 "$W/out" 2>/dev/null | sed 's/^/      | /'; }; }
expect() { if eval "$2"; then ok "$1"; else ko "$1"; fi; }

python3_bin="$(for c in python3 python; do if "$c" -c 'import sys' >/dev/null 2>&1; then command -v "$c"; break; fi; done)"
printf '#!/usr/bin/env bash\nexec "%s" "$@"\n' "$python3_bin" > "$BIN/python3"
"$python3_bin" - "$W" <<'PY'
import sys, uuid, random
w = sys.argv[1]; random.seed(7)
ids = sorted(str(uuid.UUID(int=random.getrandbits(128))) for _ in range(520))
def out(path, lines):
    with open(path, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
out(f"{w}/audit/stage1_ids.txt", ids[:50])            # pilote deja archive
out(f"{w}/audit/stage2_ids.txt", ids[50:250])         # etape 2 : 200 fiches suivantes
out(f"{w}/state/a_all", ids[:400])                    # lot A calcule par le plan (avant pilote)
excl = [str(uuid.UUID(int=random.getrandbits(128))) for _ in range(44)]
out(f"{w}/audit/excluded.csv", ["id,motif,detail,title,status,validation"] + [f'{i},lot_Q,x,"t, v",open,auto_published' for i in excl])
out(f"{w}/state/fnx_ids", [str(uuid.UUID(int=random.getrandbits(128))) for _ in range(1700)])
PY

cat > "$W/stub.py" <<'PY'
import http.server, json, sys, os
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
with open(os.path.join(sys.argv[1], "port"), "w", newline="\n") as f:
    f.write(str(s.server_address[1]))
s.serve_forever()
PY

cat > "$BIN/date" <<EOF
#!/usr/bin/env bash
if [ -f "$STATE/now" ] && [[ " \$* " != *" -d "* ]]; then exec "$REALDATE" -d "\$(cat "$STATE/now")" "\$@"; fi
exec "$REALDATE" "\$@"
EOF
# sleep factice : chaque appel fait avancer les compteurs CPU de /proc/stat (le steal augmente de steal_bump)
cat > "$BIN/sleep" <<EOF
#!/usr/bin/env bash
b=\$(cat "$STATE/steal_bump" 2>/dev/null || echo 0)
awk -v b="\$b" '/^cpu /{ \$5+=1000; \$9+=b } {print}' "$PROC/stat" > "$PROC/stat.new" && mv "$PROC/stat.new" "$PROC/stat"
exit 0
EOF
cat > "$BIN/journalctl" <<EOF
#!/usr/bin/env bash
cat "$STATE/oom_lines" 2>/dev/null
exit 0
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
  inspect)
    last="${@: -1}"
    case "$*" in
      *State.Health*) case "$last" in kafundo-redis) get redis_state "running healthy" ;; *) get pg_state "running healthy" ;; esac ;;
      *State.Restarting*) get "state_$last" "running false" ;;
      *) echo "running mock:image" ;;
    esac ;;
  network) echo "kafundo-backend kafundo-beat kafundo-frontend kafundo-nginx kafundo-postgres kafundo-redis kafundo-worker $(cat "$S/foreign" 2>/dev/null)" ;;
  cp) exit 0 ;;
  logs) exit 0 ;;
  exec)
    all="$*"
    case "$all" in
      *catalog_cleanup*apply*)
        echo "$all" >> "$S/apply_calls"
        if [[ "$all" == *"--yes"* ]]; then
          n=$(get archive_count "$(get limit 50)"); echo yes > "$S/applied"; echo "$n" > "$S/arch_sub"; echo "$n" > "$S/arch_total"; echo "$n" > "$S/jrun"; echo "$((1012 + n))" > "$S/journal"
          [ -f "$S/alter_aihold" ] && echo changedfp > "$S/aifp"
          [ -f "$S/prot_after_apply" ] && echo 1 > "$S/prot_arch"
          echo "{\"batch\": \"A_projets_institutionnels\", \"run_id\": \"x\", \"dry_run\": false, \"planned\": $n, \"archived\": $n, \"skipped\": []}"
        else
          echo "{\"batch\": \"A_projets_institutionnels\", \"run_id\": \"SIM\", \"dry_run\": true, \"planned\": $(get sim_planned "$(get limit 50)")}"
        fi ;;
      *catalog_cleanup*restore*) echo "{\"dry_run\": true, \"entries\": $(get restore_entries "$(get limit 50)"), \"restored\": 0}" ;;
      *catalog_cleanup*plan*) fp=$(get fp aaaabbbbccccdddd); echo "log line"; echo "{\"total\": 7683, \"batches\": {\"A_projets_institutionnels\": {\"count\": $(get n_a 1118), \"fingerprint\": \"$fp\"}}}" ;;
      *"cat /tmp/lota_pilot_plan"*) echo "id,title,source"; while read -r i; do echo "$i,\"Titre, avec virgule\",src"; done < "$S/a_ids_mock" ;;
      *"rm -rf"*) exit 0 ;;
      *pg_dump*) [ -f "$S/steal_after_dump" ] && cat "$S/steal_after_dump" > "$S/steal_bump"; for i in $(seq 1 300); do echo "dump-line-$i"; done ;;
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
          *"where action='ai_hold'"*md5*|*md5*"where action='ai_hold'"*) echo "$(get aifp aifp_initial)" ;;
          *"md5(string_agg"*) echo "$(get jfp journalfp)" ;;
          *"count(*) from device_archive_log where action='ai_hold'"*) echo 1012 ;;
          *"action='archive' and device_id"*) echo "$(get jarch 0)" ;;
          *"run_id='LOTA"*) echo "$(get jrun 0)" ;;
          *favorite_devices*) echo "$(get refs 0)" ;;
          *"validation_status in ('admin_only'"*) echo "$(get inner "$(get limit 50)")" ;;
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
chmod +x "$BIN/date" "$BIN/sleep" "$BIN/journalctl" "$BIN/docker" "$BIN/python3"
export MOCK_STATE="$STATE" REALDATE
"$BIN/python3" "$W/stub.py" "$STATE" & STUB_PID=$!
for i in $(seq 1 50); do [ -f "$STATE/port" ] && break; sleep 0.1; done
PORT="$(cat "$STATE/port")"

reset() {  # $1 = heure simulee ; sous-lot de 50 par defaut
  rm -rf "$STATE"/{consumed,docker_calls,apply_calls,applied,arch_sub,arch_total,fp,n_a,sim_planned,archive_count,restore_entries,celery_busy,refs,inner,jfp,jrun,jold,journal,devices,fnx_extra,steal_bump,steal_after_dump,oom_lines,foreign,pg_state,redis_state,aifp,alter_aihold,prot_after_apply,prot_arch,jarch,limit,state_kafundo-worker,state_kafundo-backend,state_kafundo-beat}
  rm -f "$W"/logs/*
  echo "$1" > "$STATE/now"
  # /proc factice : charge 1.2, swap 1 Go utilise, aucun processus
  rm -rf "$PROC"; mkdir -p "$PROC"
  echo "1.20 1.10 1.00 1/200 123" > "$PROC/loadavg"
  echo "cpu  10000 0 5000 80000 100 0 0 0 0 0" > "$PROC/stat"
  printf 'MemTotal: 8130000 kB\nSwapTotal: 4194300 kB\nSwapFree: 3145725 kB\n' > "$PROC/meminfo"
  cp "$W/audit/stage1_ids.txt" "$W/audit/lotA_first_sublot_ids.txt"
  LIM=50; EXPF="$W/audit/ids.txt"; HASHX=""; PRIOR=""
  cp "$W/audit/stage1_ids.txt" "$W/audit/ids.txt"
  head -50 "$STATE/a_all" > "$STATE/a_ids_mock"          # plan : premieres 50 = pilote
}
stage2() {  # configure l'etape 2 : le plan ne contient plus les 50 deja archivees
  LIM=200; cp "$W/audit/stage2_ids.txt" "$W/audit/ids2.txt"; EXPF="$W/audit/ids2.txt"; HASHX="aaaabbbbccccdddd"; PRIOR="$W/audit/stage1_ids.txt"
  sed -n '51,400p' "$STATE/a_all" > "$STATE/a_ids_mock"
  echo 200 > "$STATE/limit"
}
run() {
  local input="$1"; shift
  local envs=(PATH="$BIN:$PATH" LOG_DIR="$W/logs" DUMP_DIR="$W/logs" API_BASE="http://127.0.0.1:$PORT" AUDIT_DIR="$W/audit"
              ACTION_PLAN="$W/none.csv" EXPECT_IDS="$EXPF" LIMIT="$LIM" EXPECT_HASH="$HASHX" PRIOR_IDS_FILES="$PRIOR"
              EXCLUDED_CSV="$W/audit/excluded.csv" PROC_ROOT="$PROC" DF_PATH="$W" SAMPLE_SEC=0 ${DISKMIN:+DISK_MIN_GB=$DISKMIN})
  if [ "$input" = "__NONE__" ]; then env "${envs[@]}" bash "$SCRIPT" "$@" < /dev/null > "$W/out" 2>&1
  else printf "%b" "$input" | env "${envs[@]}" bash "$SCRIPT" "$@" > "$W/out" 2>&1; fi
  RC=$?
}
nowrite() { [ ! -f "$STATE/applied" ] && { [ ! -f "$STATE/apply_calls" ] || ! grep -q -- "--yes" "$STATE/apply_calls"; }; }
nodump() { ! ls "$W"/logs/pre_lotA_s*.dump >/dev/null 2>&1; }
export WINDOW_FROM=2026-10-13T21:15 WINDOW_TO=2026-10-13T21:45
IN_WIN="2026-10-13 21:16:00 UTC"
T50='ARCHIVE-50\n'; T200='ARCHIVE-200\n'

echo "== 1. pilote de 50 fiches : fonctionnement inchange (execution nominale non interactive)"
reset "$IN_WIN"; run 'ARCHIVE-50\nLIGNE_SENTINELLE\n' --apply
expect "code retour 0, 50 fiches archivees et controlees" '[ $RC = 0 ] && grep -q "50 FICHES ARCHIVEES ET CONTROLEES" "$W/out"'
expect "un seul apply reel, --limit 50, avec empreinte" '[ "$(grep -c -- "--yes" "$STATE/apply_calls")" = 1 ] && grep -- "--yes" "$STATE/apply_calls" | grep -q -- "--limit 50" && grep -- "--yes" "$STATE/apply_calls" | grep -q -- "--plan-hash aaaabbbbccccdddd"'
expect "run-id etape 1 + sauvegarde sha256" 'grep -q "run-id : LOTA-S1-" "$W/out" && ls "$W"/logs/pre_lotA_s1_*.dump.sha256 >/dev/null 2>&1'
expect "gardes de sante evaluees (precontroles et avant ecriture)" '[ "$(grep -c "sante hote" "$W/out")" = 2 ]'
expect "confirmation non lisible par les sous-commandes" '[ ! -f "$STATE/consumed" ] || ! grep -qE "ARCHIVE-50|LIGNE_SENTINELLE" "$STATE/consumed"'

echo "== 2. etape 2 : 200 fiches (execution nominale)"
reset "$IN_WIN"; stage2; run 'ARCHIVE-200\nLIGNE_SENTINELLE\n' --apply
expect "code retour 0, 200 fiches archivees et controlees" '[ $RC = 0 ] && grep -q "200 FICHES ARCHIVEES ET CONTROLEES" "$W/out"'
expect "un seul apply reel, --limit 200, empreinte, run-id etape 2 distinct" '[ "$(grep -c -- "--yes" "$STATE/apply_calls")" = 1 ] && grep -- "--yes" "$STATE/apply_calls" | grep -q -- "--limit 200" && grep -q "run-id : LOTA-S2-" "$W/out"'
expect "journal +200, ai_hold conserves, protegees intactes" 'grep -q "journal : 1212 (avant 1012, attendu 1212)" "$W/out" && grep -q "empreinte conservee : OUI" "$W/out" && grep -q "fiches protegees archivees : 0" "$W/out"'
expect "restauration ciblee et complete indiquees, sauvegarde etape 2" 'grep -q "Restauration ciblee" "$W/out" && ls "$W"/logs/pre_lotA_s2_*.dump >/dev/null 2>&1'
expect "confirmation non lisible par les sous-commandes" '[ ! -f "$STATE/consumed" ] || ! grep -qE "ARCHIVE-200|LIGNE_SENTINELLE" "$STATE/consumed"'

echo "== 3. confirmation absente ou incorrecte : refus sans aucune commande"
for bad in "__NONE__" 'archive-50\n' 'ARCHIVE-50 ok\n' 'MIGRATE\n' 'ARCHIVE-500\n' '\n' 'ARCHIVE-200\n'; do
  reset "$IN_WIN"; run "$bad" --apply
  expect "refus pour [$bad] (etape 1)" '[ $RC = 1 ] && grep -q "confirmation absente ou incorrecte" "$W/out" && [ ! -f "$STATE/docker_calls" ]'
done
for bad in 'ARCHIVE-50\n' 'archive-200\n' 'ARCHIVE-2000\n'; do
  reset "$IN_WIN"; stage2; run "$bad" --apply
  expect "refus pour [$bad] (etape 2)" '[ $RC = 1 ] && grep -q "confirmation absente ou incorrecte" "$W/out" && [ ! -f "$STATE/docker_calls" ]'
done
reset "$IN_WIN"; LIM=100; run 'ARCHIVE-100\n' --apply
expect "LIMIT hors {50, 200} refuse" '[ $RC = 1 ] && grep -q "LIMIT doit valoir 50 ou 200" "$W/out"'

echo "== 4. fenetre expiree ou trop courte"
for t in "2026-10-13 21:14:00 UTC" "2026-10-13 21:45:00 UTC" "2026-10-13 08:30:00 UTC" "2026-10-14 21:20:00 UTC"; do
  reset "$t"; stage2; run 'ARCHIVE-200\n' --apply
  expect "refus a $t (etape 2)" '[ $RC = 1 ] && grep -q "hors de la fenetre" "$W/out" && nowrite && nodump'
done
reset "$IN_WIN"; stage2; unset WINDOW_FROM WINDOW_TO; run 'ARCHIVE-200\n' --apply; export WINDOW_FROM=2026-10-13T21:15 WINDOW_TO=2026-10-13T21:45
expect "refus sans fenetre" '[ $RC = 1 ] && grep -q "WINDOW_FROM et WINDOW_TO requis" "$W/out" && nowrite && nodump'
reset "2026-10-13 21:30:00 UTC"; stage2; run 'ARCHIVE-200\n' --apply
expect "refus s'il reste moins de 20 min (15 min)" '[ $RC = 1 ] && grep -q "temps restant insuffisant" "$W/out" && nowrite && nodump'

echo "== 5. sous-lot incorrect ou protection violee (etape 2) : arret sans ecriture"
reset "$IN_WIN"; stage2; head -199 "$W/audit/ids2.txt" > "$W/audit/ids2b.txt"; EXPF="$W/audit/ids2b.txt"; run 'ARCHIVE-200\n' --apply
expect "199 identifiants au lieu de 200" '[ $RC = 1 ] && grep -q "attendu 200" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; { cat "$W/audit/ids2.txt"; echo extra; } > "$W/audit/ids2b.txt"; EXPF="$W/audit/ids2b.txt"; run 'ARCHIVE-200\n' --apply
expect "201 identifiants" '[ $RC = 1 ] && grep -q "attendu 200" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; { head -199 "$W/audit/ids2.txt"; head -1 "$W/audit/ids2.txt"; } > "$W/audit/ids2b.txt"; EXPF="$W/audit/ids2b.txt"; run 'ARCHIVE-200\n' --apply
expect "identifiants en double" '[ $RC = 1 ] && grep -q "identifiants en double" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; { head -199 "$W/audit/ids2.txt"; head -1 "$W/audit/stage1_ids.txt"; } > "$W/audit/ids2b.txt"; EXPF="$W/audit/ids2b.txt"; run 'ARCHIVE-200\n' --apply
expect "chevauchement avec les 50 deja archivees" '[ $RC = 1 ] && grep -q "chevauchement avec un sous-lot deja archive" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; echo 3 > "$STATE/arch_sub"; run 'ARCHIVE-200\n' --apply
expect "fiche du sous-lot deja archivee (base)" '[ $RC = 1 ] && grep -q "deja archivee" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; echo 2 > "$STATE/jarch"; run 'ARCHIVE-200\n' --apply
expect "fiche du sous-lot deja presente dans un archivage du journal" '[ $RC = 1 ] && grep -q "deja archivee" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; { head -199 "$W/audit/ids2.txt"; echo 8feb4407-42c1-43ee-ab3b-22a3b560924f; } > "$W/audit/ids2b.txt"; EXPF="$W/audit/ids2b.txt"; run 'ARCHIVE-200\n' --apply
expect "Madagascar P515164 dans le sous-lot" '[ $RC = 1 ] && grep -q "reserve" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; { head -199 "$W/audit/ids2.txt"; echo 882a672c-65e8-446f-91c4-51170ae09bf0; } > "$W/audit/ids2b.txt"; EXPF="$W/audit/ids2b.txt"; run 'ARCHIVE-200\n' --apply
expect "un des 7 projets reserves dans le sous-lot" '[ $RC = 1 ] && grep -q "reserve" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; { head -199 "$W/audit/ids2.txt"; sed -n 2p "$W/audit/excluded.csv" | cut -d, -f1; } > "$W/audit/ids2b.txt"; EXPF="$W/audit/ids2b.txt"; run 'ARCHIVE-200\n' --apply
expect "fiche du lot Q dans le sous-lot" '[ $RC = 1 ] && grep -q "lot Q ou exclue" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; head -1 "$W/audit/ids2.txt" > "$STATE/fnx_extra"; run 'ARCHIVE-200\n' --apply
expect "fiche du sous-lot referencee par Finnovatix" '[ $RC = 1 ] && grep -q "protegee" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; echo 2 > "$STATE/refs"; run 'ARCHIVE-200\n' --apply
expect "reference (favori/pipeline/alerte) sur le sous-lot" '[ $RC = 1 ] && grep -q "references trouvees" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; echo 199 > "$STATE/inner"; run 'ARCHIVE-200\n' --apply
expect "fiche publique ou d'un autre type" '[ $RC = 1 ] && grep -q "publique ou d.un autre type" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; echo deadbeefdeadbeef > "$STATE/fp"; run 'ARCHIVE-200\n' --apply
expect "empreinte du lot differente de l'empreinte validee" '[ $RC = 1 ] && grep -q "empreinte du lot" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; sed -n '52,400p' "$STATE/a_all" > "$STATE/a_ids_mock"; run 'ARCHIVE-200\n' --apply
expect "sous-lot calcule different du fichier valide (catalogue modifie)" '[ $RC = 1 ] && grep -q "different" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; echo 199 > "$STATE/sim_planned"; run 'ARCHIVE-200\n' --apply
expect "la simulation ne planifie pas exactement 200" '[ $RC = 1 ] && grep -q "ne planifie pas exactement 200" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; echo "1 0 0 0" > "$STATE/celery_busy"; run 'ARCHIVE-200\n' --apply
expect "tache Celery active" '[ $RC = 1 ] && grep -q "tache Celery" "$W/out" && nowrite && nodump'

echo "== 6. gardes de sante de l'hote (etape 2) : refus sans ecriture"
reset "$IN_WIN"; stage2; echo "5.50 4.0 3.0 1/200 1" > "$PROC/loadavg"; run 'ARCHIVE-200\n' --apply
expect "charge 5,5 >= 4" '[ $RC = 1 ] && grep -q "REFUS : charge" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; echo 3.99 > /dev/null; echo "3.99 3.0 2.0 1/200 1" > "$PROC/loadavg"; run 'ARCHIVE-200\n' --apply
expect "charge 3,99 acceptee" '[ $RC = 0 ]'
reset "$IN_WIN"; stage2; echo 200 > "$STATE/steal_bump"; run 'ARCHIVE-200\n' --apply
expect "CPU steal 16 % >= 10 %" '[ $RC = 1 ] && grep -q "REFUS : CPU steal" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; printf 'SwapTotal: 4194300 kB\nSwapFree: 1000000 kB\n' > "$PROC/meminfo"; run 'ARCHIVE-200\n' --apply
expect "swap 3 Go >= 2 Go" '[ $RC = 1 ] && grep -q "REFUS : swap" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; DISKMIN=99999; run 'ARCHIVE-200\n' --apply; DISKMIN=""
expect "espace disque insuffisant" '[ $RC = 1 ] && grep -q "REFUS : espace disque" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; echo "Oct 13 21:10:01 kernel: Memory cgroup out of memory: Killed process 4242 (python3.12)" > "$STATE/oom_lines"; run 'ARCHIVE-200\n' --apply
expect "OOM-kill dans les 30 dernieres minutes" '[ $RC = 1 ] && grep -q "REFUS : 1 OOM-kill" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; mkdir -p "$PROC/4242"; printf '/tmp/hasaneyoh\0-o\0pool:10008\0' > "$PROC/4242/cmdline"; run 'ARCHIVE-200\n' --apply
expect "processus suspect (mineur)" '[ $RC = 1 ] && grep -q "REFUS : processus suspect" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; mkdir -p "$PROC/4243"; printf 'safenet-client\0' > "$PROC/4243/cmdline"; run 'ARCHIVE-200\n' --apply
expect "processus suspect (safenet-client)" '[ $RC = 1 ] && grep -q "REFUS : processus suspect" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; echo "fasodata-web-1" > "$STATE/foreign"; run 'ARCHIVE-200\n' --apply
expect "conteneur etranger sur kafundo_default (FasoData)" '[ $RC = 1 ] && grep -q "conteneur(s) etranger(s)" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; echo "running unhealthy" > "$STATE/pg_state"; run 'ARCHIVE-200\n' --apply
expect "PostgreSQL non sain" '[ $RC = 1 ] && grep -q "REFUS : kafundo-postgres non operationnel" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; echo "exited " > "$STATE/redis_state"; run 'ARCHIVE-200\n' --apply
expect "Redis arrete" '[ $RC = 1 ] && grep -q "REFUS : kafundo-redis non operationnel" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; echo "running true" > "$STATE/state_kafundo-worker"; run 'ARCHIVE-200\n' --apply
expect "worker en redemarrage" '[ $RC = 1 ] && grep -q "REFUS : kafundo-worker non operationnel" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; stage2; echo 200 > "$STATE/steal_after_dump"; run 'ARCHIVE-200\n' --apply
expect "degradation apparue pendant la sauvegarde : refus juste avant l'ecriture (sauvegarde faite, aucun archivage)" '[ $RC = 1 ] && grep -q "juste avant l.ecriture" "$W/out" && nowrite && ! nodump'

echo "== 7. anomalies apres archivage : alerte, pas de poursuite (etape 2)"
reset "$IN_WIN"; stage2; echo 199 > "$STATE/archive_count"; run 'ARCHIVE-200\n' --apply
expect "199 archivees : anomalie + commande de restauration" '[ $RC = 1 ] && grep -q "ANOMALIE : nombre d.archivees" "$W/out" && grep -q "restore --run-id LOTA-S2-" "$W/out"'
reset "$IN_WIN"; stage2; touch "$STATE/alter_aihold"; run 'ARCHIVE-200\n' --apply
expect "entrees ai_hold modifiees : anomalie" '[ $RC = 1 ] && grep -q "ANOMALIE : entrees ai_hold modifiees" "$W/out"'
reset "$IN_WIN"; stage2; touch "$STATE/prot_after_apply"; run 'ARCHIVE-200\n' --apply
expect "fiche protegee archivee : anomalie" '[ $RC = 1 ] && grep -q "ANOMALIE : fiche protegee archivee" "$W/out"'
reset "$IN_WIN"; stage2; echo 150 > "$STATE/restore_entries"; run 'ARCHIVE-200\n' --apply
expect "restauration non disponible pour 200 entrees : anomalie" '[ $RC = 1 ] && grep -q "restauration non disponible" "$W/out"'

echo "== 8. simulation par defaut : aucune ecriture"
reset "$IN_WIN"; stage2; run "__NONE__"
expect "simulation etape 2 OK, aucune sauvegarde ni ecriture" '[ $RC = 0 ] && grep -q "tous les controles sont satisfaisants" "$W/out" && nowrite && nodump'
reset "$IN_WIN"; run "__NONE__"
expect "simulation etape 1 OK" '[ $RC = 0 ] && grep -q "tous les controles sont satisfaisants" "$W/out" && nowrite && nodump'

echo ""
echo "RESULTAT : $PASS reussis, $FAIL en echec"
[ "$FAIL" = 0 ]
