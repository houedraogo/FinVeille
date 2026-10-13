#!/usr/bin/env bash
# Archivage PROGRESSIF du lot A : sous-lot de 50 (pilote, defaut) ou de 200 fiches (etape 2), reversible, avec gardes de sante
# de l'hote, controles et arret au moindre ecart. SIMULATION (precontroles + plan) par defaut.
#
#   bash lot_a_pilot.sh                                       # precontroles + plan + simulation, n'ecrit RIEN dans la base
#   printf 'ARCHIVE-50\n'  | WINDOW_FROM=... WINDOW_TO=... bash lot_a_pilot.sh --apply                    # pilote (defaut)
#   printf 'ARCHIVE-200\n' | LIMIT=200 EXPECT_IDS=<fichier de 200 ids> EXPECT_HASH=<empreinte> \
#        WINDOW_FROM=... WINDOW_TO=... bash lot_a_pilot.sh --apply                                        # etape 2
#   RUN_ID=LOTA-S2-... LIMIT=200 bash lot_a_pilot.sh --followup                                           # apres la collecte suivante
#
# LIMIT ne peut valoir que 50 ou 200. Confirmation : une seule ligne exactement `ARCHIVE-<LIMIT>`, lue AVANT toute sous-commande ;
# l'entree standard est ensuite fermee. Perimetre : seulement les LIMIT identifiants de EXPECT_IDS, jamais les autres candidates, jamais
# les lots B/C, jamais une fiche protegee (Finnovatix), du lot Q, des 2 exclusions du proprietaire, des 7 projets reserves, ni deja archivee.
# Gardes de sante (precontroles ET juste avant l'ecriture) : charge < 4, steal < 10 %, swap < 2 Go, disque, aucun OOM-kill recent,
# aucun processus suspect, reseau kafundo_default sans conteneur etranger, PostgreSQL/Redis/backend/worker/beat operationnels.
# Parametres de test : LOG_DIR, API_BASE, BACKEND, PG, FNX_MYSQL, AUDIT_DIR, ACTION_PLAN, DUMP_DIR, PROC_ROOT, DF_PATH, SAMPLE_SEC.
set -uo pipefail
umask 077
HERE="$(dirname "$(readlink -f "$0")")"
BACKEND="${BACKEND:-kafundo-backend}"; PG="${PG:-kafundo-postgres}"; PGU="${PGU:-finveille}"; PGDB="${PGDB:-finveille}"
FNX_MYSQL="${FNX_MYSQL:-finnovatix-platform-finnovatix-mysql-1}"
LIMIT="${LIMIT:-50}"
case "$LIMIT" in 50) STAGE_DEFAULT=1 ;; 200) STAGE_DEFAULT=2 ;; *) echo "ARRET: LIMIT doit valoir 50 ou 200 (recu : $LIMIT)" >&2; exit 1 ;; esac
STAGE="${STAGE:-$STAGE_DEFAULT}"
AUDIT_DIR="${AUDIT_DIR:-/opt/finveille-backups/audit_20261012_lotA}"
ACTION_PLAN="${ACTION_PLAN:-/opt/finveille-backups/audit_20261010/finnovatix_action_plan.csv}"
EXPECT_IDS="${EXPECT_IDS:-$AUDIT_DIR/lotA_first_sublot_ids.txt}"
EXCLUDED_CSV="${EXCLUDED_CSV:-/opt/finveille-backups/audit_20261012_lotA/lotA_excluded.csv}"          # lot Q + 2 exclusions (44 ids)
# sous-lots deja archives (etape 2 : le pilote de 50) ; vide pour le pilote lui-meme
PRIOR_IDS_FILES="${PRIOR_IDS_FILES-$([ "$LIMIT" = 50 ] || echo /opt/finveille-backups/audit_20261012_lotA/lotA_first_sublot_ids.txt)}"
EXPECT_HASH="${EXPECT_HASH:-}"
LOG_DIR="${LOG_DIR:-/opt/finveille-backups}"; DUMP_DIR="${DUMP_DIR:-/opt/finveille-backups}"
API_BASE="${API_BASE:-http://127.0.0.1:8000}"; export API_BASE
PROC_ROOT="${PROC_ROOT:-/proc}"; DF_PATH="${DF_PATH:-/opt/finveille-backups}"; SAMPLE_SEC="${SAMPLE_SEC:-5}"
LOAD_MAX="${LOAD_MAX:-4}"; STEAL_MAX="${STEAL_MAX:-10}"; SWAP_MAX_MB="${SWAP_MAX_MB:-2048}"; DISK_MIN_GB="${DISK_MIN_GB:-5}"
BATCH="A_projets_institutionnels"
MIN_START_MIN="${MIN_START_MIN:-20}"; MIN_APPLY_MIN="${MIN_APPLY_MIN:-8}"
HEAD_REV="c8e1f4a7b2d9"
# exclusions imposees par le proprietaire (a ne jamais archiver) : Madagascar P515164, Rwanda P510000, puis les 7 projets reserves a l'etape 4
RESERVED_IDS="8feb4407-42c1-43ee-ab3b-22a3b560924f cacc4c18-fd6a-41f9-9e87-0a9c466147d7 3d0c59f6-6d04-40f4-bcb1-b53ca1d5edd1 8c4b49d7-69c9-4939-bebd-c0045543641e 96fe955f-7c22-40c1-88b9-924b49ff7aa6 cac9fddd-215e-43fd-a08b-c473a57ed74a 5405bc16-88ae-4e40-9166-18c177f5686d 19d51742-0d3b-4126-9db7-468b3d53063f 882a672c-65e8-446f-91c4-51170ae09bf0"
die() { echo "ARRET: $*" >&2; exit 1; }

MODE="${1:-}"
case "$MODE" in ""|--apply|--followup) ;; *) die "option inconnue : $MODE" ;; esac
TOKEN="ARCHIVE-$LIMIT"
if [ "$MODE" = "--apply" ]; then
  if [ -t 0 ]; then IFS= read -r -p "Tapez $TOKEN pour archiver $LIMIT fiches en PRODUCTION : " CONFIRM_LINE || CONFIRM_LINE=""
  else IFS= read -r -t 30 CONFIRM_LINE || CONFIRM_LINE=""; fi
  [ "$CONFIRM_LINE" = "$TOKEN" ] || die "confirmation absente ou incorrecte (attendu : $TOKEN)"
fi
exec 0</dev/null

TS=$(date -u +%Y%m%dT%H%M%SZ)
LOG="$LOG_DIR/lot_a_pilot_${TS}.log"
exec > >(tee -a "$LOG") 2>&1
pg() { docker exec "$PG" psql -U "$PGU" -d "$PGDB" -At -F'|' "$@"; }
ready() { python3 - <<'PY'
import json, os, urllib.request, urllib.error
try:
    with urllib.request.urlopen(os.environ["API_BASE"] + "/api/ready", timeout=5) as r: d = json.load(r); print(200, d.get("schema_revision"))
except urllib.error.HTTPError as e: print(e.code, "-")
except Exception as e: print("ERR", type(e).__name__)
PY
}
pagination() { python3 - <<'PY'
import json, os, urllib.request
base = os.environ["API_BASE"]
ids, page, total = [], 1, 0
while True:
    with urllib.request.urlopen(f"{base}/api/v1/devices/?page={page}&page_size=100", timeout=60) as r: d = json.load(r)
    it = d["items"]
    if not it: break
    ids += [i["id"] for i in it]; total = d["total"]; page += 1
print(total, len(ids), len(set(ids)))
PY
}
celery_state() { docker exec -i -e PYTHONPATH=/app "$BACKEND" python - <<'PY' 2>/dev/null | tail -1
from app.tasks.celery_app import celery_app
i = celery_app.control.inspect(timeout=3)
a = sum(len(v) for v in (i.active() or {}).values()); r = sum(len(v) for v in (i.reserved() or {}).values())
c = celery_app.connection_for_read().default_channel.client
print(a, r, sum(c.llen(q) for q in ("default", "collect", "alerts")), c.llen("celery"))
PY
}
cli() { docker exec -e PYTHONPATH=/app "$BACKEND" python -m app.data.catalog_cleanup "$@"; }
END_EPOCH=""
need_minutes() { [ -n "$END_EPOCH" ] || return 0; local r=$(( (END_EPOCH - $(date -u +%s)) / 60 ))
  [ "$r" -ge "$1" ] || die "temps restant insuffisant dans la fenetre ($r min < $1 min requis avant : $2) - aucune ecriture effectuee a ce stade"
  echo "  [temps] $r min restantes (>= $1 requis avant : $2)"; }

# ---------------- gardes de sante de l'hote (lecture seule) ----------------
cpu_line() { awk '/^cpu /{print $2+$3+$4+$5+$6+$7+$8+$9, $9}' "$PROC_ROOT/stat"; }   # total, steal
host_health() {  # $1 = etiquette ; renvoie 0 si conforme, sinon affiche la cause et renvoie 1
  local label="$1" bad=0 load l1 t1 s1 t2 s2 steal swap_t swap_f swap_mb avail_kb oom sus net
  load=$(cut -d' ' -f1 "$PROC_ROOT/loadavg")
  read -r t1 s1 <<<"$(cpu_line)"; sleep "$SAMPLE_SEC"; read -r t2 s2 <<<"$(cpu_line)"
  steal=$(awk -v a="$s1" -v b="$s2" -v c="$t1" -v d="$t2" 'BEGIN{ if (d-c <= 0) print 0; else printf "%.1f", 100*(b-a)/(d-c) }')
  swap_t=$(awk '/^SwapTotal:/{print $2}' "$PROC_ROOT/meminfo"); swap_f=$(awk '/^SwapFree:/{print $2}' "$PROC_ROOT/meminfo")
  swap_mb=$(( (swap_t - swap_f) / 1024 ))
  avail_kb=$(df -P -k "$DF_PATH" | awk 'NR==2{print $4}')
  oom=$(journalctl -k --since "30 minutes ago" --no-pager 2>/dev/null | grep -ciE "out of memory|oom-kill|killed process")
  sus=$(for p in "$PROC_ROOT"/[0-9]*; do
          e=$(readlink "$p/exe" 2>/dev/null); a=$(tr '\0' ' ' < "$p/cmdline" 2>/dev/null)
          case "$e" in /tmp/*|/var/tmp/*|/dev/shm/*) echo "exe:$e";; esac
          case "$a" in *hasaneyoh*|*safenet-client*|*xmrig*|*minerd*|*cpuminer*|*stratum+tcp*) echo "cmd:${a:0:60}";; esac
        done | head -3 | tr '\n' ';')
  net=$(docker network inspect kafundo_default --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null | tr ' ' '\n' | grep -v '^$' | grep -vE '^kafundo-' | tr '\n' ' ')
  echo "  [sante hote $label] charge=$load steal=${steal}% swap=${swap_mb}Mo disque_libre=$((avail_kb/1024/1024))Go oom30min=$oom suspects='${sus}' conteneurs_etrangers_kafundo_default='${net}'"
  awk -v v="$load" -v m="$LOAD_MAX" 'BEGIN{exit !(v < m)}' || { echo "  REFUS : charge $load >= $LOAD_MAX"; bad=1; }
  awk -v v="$steal" -v m="$STEAL_MAX" 'BEGIN{exit !(v < m)}' || { echo "  REFUS : CPU steal ${steal}% >= ${STEAL_MAX}%"; bad=1; }
  [ "$swap_mb" -lt "$SWAP_MAX_MB" ] || { echo "  REFUS : swap utilise ${swap_mb} Mo >= ${SWAP_MAX_MB} Mo"; bad=1; }
  [ "$((avail_kb / 1024 / 1024))" -ge "$DISK_MIN_GB" ] || { echo "  REFUS : espace disque libre < ${DISK_MIN_GB} Go"; bad=1; }
  [ "$oom" = 0 ] || { echo "  REFUS : $oom OOM-kill dans les 30 dernieres minutes"; bad=1; }
  [ -z "$sus" ] || { echo "  REFUS : processus suspect(s) : $sus"; bad=1; }
  [ -z "$net" ] || { echo "  REFUS : conteneur(s) etranger(s) sur kafundo_default : $net"; bad=1; }
  local st
  for c in "$PG" kafundo-redis; do
    st=$(docker inspect -f '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' "$c" 2>/dev/null)
    case "$st" in "running healthy") ;; *) echo "  REFUS : $c non operationnel ($st)"; bad=1 ;; esac
  done
  for c in "$BACKEND" kafundo-worker kafundo-beat; do
    st=$(docker inspect -f '{{.State.Status}} {{.State.Restarting}}' "$c" 2>/dev/null)
    [ "$st" = "running false" ] || { echo "  REFUS : $c non operationnel ($st)"; bad=1; }
  done
  return $bad
}

# ---------------- suivi apres la collecte (lecture seule) ----------------
if [ "$MODE" = "--followup" ]; then
  : "${RUN_ID:?RUN_ID requis}"
  echo "===== SUIVI $RUN_ID ($(date -u +%FT%TZ)) ====="
  echo "  archivees (run) : $(pg -c "select count(*) from device_archive_log l join devices d on d.id=l.device_id where l.run_id='$RUN_ID' and l.action='archive' and d.validation_status='archived'")  (attendu $LIMIT)"
  echo "  reactivees depuis : $(pg -c "select count(*) from device_archive_log l join devices d on d.id=l.device_id where l.run_id='$RUN_ID' and l.action='archive' and d.validation_status<>'archived'")  (attendu 0)"
  echo "  archivees au total : $(pg -c "select count(*) from devices where validation_status='archived'") ; fiches : $(pg -c 'select count(*) from devices')"
  echo "  collectes 60 min : $(pg -c "select coalesce(string_agg(status||':'||n, ' '), 'aucune') from (select status, count(*) n from collection_logs where started_at > now() - interval '60 minutes' group by 1) t")"
  echo "  erreurs de journaux (60 min) : backend=$(docker logs --since 60m "$BACKEND" 2>&1 | grep -ciE 'traceback|critical') worker=$(docker logs --since 60m kafundo-worker 2>&1 | grep -ciE 'traceback|critical')"
  echo "  /api/ready : $(ready) ; pagination : $(pagination)"
  exit 0
fi

echo "===== 0. PRE-CONTROLES ($(date -u +%FT%TZ)) ; sous-lot de $LIMIT fiches, etape $STAGE ====="
for c in "$BACKEND" kafundo-worker kafundo-beat; do
  S=$(docker inspect -f '{{.State.Status}} {{.Config.Image}}' "$c" 2>/dev/null) || die "$c introuvable"
  echo "  $c : $S"; case "$S" in running*) ;; *) die "$c ne tourne pas" ;; esac
done
host_health "precontroles" || die "gardes de sante de l'hote non satisfaites : operation refusee"
REV=$(pg -c "select version_num from alembic_version"); echo "  revision : $REV"; [ "$REV" = "$HEAD_REV" ] || die "revision $REV (attendue $HEAD_REV)"
echo "  /api/ready : $(ready)"; [ "$(ready)" = "200 $HEAD_REV" ] || die "/api/ready non conforme"
LONG=$(pg -c "select count(*) from pg_stat_activity where datname=current_database() and pid<>pg_backend_pid() and state<>'idle' and now()-xact_start > interval '30 seconds'")
echo "  operations PostgreSQL > 30 s : $LONG"; [ "$LONG" = 0 ] || die "operation longue en cours"
CEL=$(celery_state); echo "  Celery actives / reservees / en file / file 'celery' : $CEL"
[ "$CEL" = "0 0 0 0" ] || die "tache Celery active, reservee ou en attente"
DEV0=$(pg -c "select count(*) from devices"); ARCH0=$(pg -c "select count(*) from devices where validation_status='archived'")
JOUR0=$(pg -c "select count(*) from device_archive_log"); AIH0=$(pg -c "select count(*) from device_archive_log where action='ai_hold'")
ORPH=$(pg -c "select count(*) from device_archive_log l left join devices d on d.id=l.device_id where d.id is null")
echo "  fiches : $DEV0 ; archivees : $ARCH0 ; journal : $JOUR0 (dont ai_hold : $AIH0) ; orphelins : $ORPH"; [ "$ORPH" = 0 ] || die "journal avec orphelins"
[ "$ARCH0" = 0 ] || echo "  (note : $ARCH0 fiche(s) deja archivee(s) avant l'operation)"
[ -f "$EXPECT_IDS" ] || die "fichier d'identifiants absent : $EXPECT_IDS"
NEXP=$(grep -c . "$EXPECT_IDS"); [ "$NEXP" = "$LIMIT" ] || die "le fichier d'identifiants contient $NEXP lignes (attendu $LIMIT)"
[ "$(sort -u "$EXPECT_IDS" | wc -l)" = "$LIMIT" ] || die "identifiants en double"
for r in $RESERVED_IDS; do grep -q "$r" "$EXPECT_IDS" && die "identifiant reserve present dans le sous-lot : $r"; done
echo "  sous-lot attendu : $NEXP identifiants distincts, aucun reserve (Madagascar, Rwanda, 7 projets valides)"
if [ "$LIMIT" != 50 ]; then
  [ -f "$EXCLUDED_CSV" ] || die "liste des exclusions (lot Q + 2) absente : $EXCLUDED_CSV"
  tail -n +2 "$EXCLUDED_CSV" | cut -d, -f1 | sed 's/"//g' | sort -u > /tmp/lota_excl_$$.txt
  EXCL_HIT=$(grep -cFf /tmp/lota_excl_$$.txt "$EXPECT_IDS" || true); EXCL_N=$(grep -c . /tmp/lota_excl_$$.txt); rm -f /tmp/lota_excl_$$.txt
  echo "  exclusions (lot Q + 2) : $EXCL_N ids ; presentes dans le sous-lot : $EXCL_HIT"
  [ "$EXCL_N" -ge 40 ] || die "liste d'exclusions anormalement courte ($EXCL_N)"; [ "$EXCL_HIT" = 0 ] || die "fiche du lot Q ou exclue dans le sous-lot"
fi
for f in $PRIOR_IDS_FILES; do
  [ -f "$f" ] || die "fichier des sous-lots deja archives absent : $f"
  OV=$(grep -cFf "$f" "$EXPECT_IDS" || true)
  echo "  chevauchement avec $(basename "$(dirname "$f")")/$(basename "$f") : $OV"
  [ "$OV" = 0 ] || die "chevauchement avec un sous-lot deja archive ($OV fiches)"
done
CAP=$(docker exec finnovatix-platform-app-1 sh -c 'grep -E "^KAFUNDO_SYNC_CREATE_CAP=" /var/www/html/.env | cut -d= -f2' 2>/dev/null || true)
echo "  KAFUNDO_SYNC_CREATE_CAP (lecture) : ${CAP:-n/a}"

echo ""; echo "===== 1. PROTECTIONS ET PLAN (regeneres) ====="
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
{ echo "select kafundo_id from funding_calls where kafundo_id is not null;" | docker exec -i "$FNX_MYSQL" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --batch --skip-column-names finnovatix' 2>/dev/null | grep -av "Using a password"
  [ -f "$ACTION_PLAN" ] && tail -n +2 "$ACTION_PLAN" | awk -F, '$3=="R_remap"||$3=="R_remap_by_url"{print $4}'
  for r in $RESERVED_IDS; do echo "$r"; done; } | sed '/^$/d' | sort -u > "$W/protect.txt"
NPROT=$(wc -l < "$W/protect.txt"); echo "  identifiants proteges (Finnovatix actuels + cibles de rattachement + reserves) : $NPROT"
[ "$NPROT" -ge 1500 ] || die "fichier de protection anormalement petit ($NPROT) : lecture Finnovatix en echec ?"
docker cp "$W/protect.txt" "$BACKEND:/tmp/lota_pilot_protect.txt" >/dev/null || die "docker cp protect"
PLAN_JSON=$(cli plan --out /tmp/lota_pilot_plan --protect-file /tmp/lota_pilot_protect.txt 2>/dev/null) || die "plan en echec"
read -r FP N_A <<EOF2
$(echo "$PLAN_JSON" | python3 -c "
import json, sys
t = sys.stdin.read(); d = json.loads(t[t.index('{'):])
a = d['batches']['A_projets_institutionnels']; print(a['fingerprint'], a['count'])")
EOF2
echo "  lot A : effectif $N_A, empreinte $FP"
if [ -n "$EXPECT_HASH" ]; then [ "$FP" = "$EXPECT_HASH" ] || die "empreinte du lot $FP differente de l'empreinte validee $EXPECT_HASH (le catalogue a change : revalider)"; echo "  empreinte == empreinte validee ($EXPECT_HASH)"; fi
docker exec "$BACKEND" cat "/tmp/lota_pilot_plan/${BATCH}.csv" 2>/dev/null | tail -n +2 | cut -d, -f1 | sed 's/"//g' | LC_ALL=C sort | head -n "$LIMIT" > "$W/first.txt"
LC_ALL=C sort "$EXPECT_IDS" > "$W/expect.txt"
NSEL=$(grep -c . "$W/first.txt")
echo "  sous-lot calcule : $NSEL fiches"
[ "$NSEL" = "$LIMIT" ] || die "le sous-lot calcule contient $NSEL fiches (attendu $LIMIT)"
if ! diff -q "$W/first.txt" "$W/expect.txt" >/dev/null; then
  echo "  ecarts (calcule < | > attendu) :"; diff "$W/first.txt" "$W/expect.txt" | head -6 | sed 's/^/    /'
  die "les $LIMIT identifiants calcules different de $EXPECT_IDS (le catalogue a change : revalider)"
fi
echo "  les $LIMIT identifiants calcules == fichier valide par le proprietaire"
IDS_CSV=$(paste -sd, "$W/expect.txt")
ALREADY=$(pg -c "select count(*) from devices where validation_status='archived' and id::text = any(string_to_array('$IDS_CSV', ','))")
JARCH=$(pg -c "select count(*) from device_archive_log where action='archive' and device_id::text = any(string_to_array('$IDS_CSV', ','))")
echo "  fiches du sous-lot deja archivees : $ALREADY ; deja presentes dans un archivage du journal : $JARCH"
[ "$ALREADY" = 0 ] && [ "$JARCH" = 0 ] || die "fiche du sous-lot deja archivee"
INNER=$(pg -c "select count(*) from devices where id::text = any(string_to_array('$IDS_CSV', ',')) and validation_status in ('admin_only','rejected','pending_review') and device_type='institutional_project'")
echo "  fiches du sous-lot non publiees et de type institutional_project : $INNER / $LIMIT"; [ "$INNER" = "$LIMIT" ] || die "le sous-lot contient une fiche publique ou d'un autre type"
REFS=$(pg -c "select (select count(*) from favorite_devices where device_id::text = any(string_to_array('$IDS_CSV', ','))) + (select count(*) from device_pipeline where device_id::text = any(string_to_array('$IDS_CSV', ','))) + (select count(*) from alert_deliveries where device_id::text = any(string_to_array('$IDS_CSV', ','))) + (select count(*) from device_duplicate_candidates where device_id::text = any(string_to_array('$IDS_CSV', ',')) or other_device_id::text = any(string_to_array('$IDS_CSV', ','))) + (select count(*) from device_archive_log where merged_into_id::text = any(string_to_array('$IDS_CSV', ',')))")
echo "  references (favoris, pipelines, alertes, paires, cibles de fusion) : $REFS"; [ "$REFS" = 0 ] || die "references trouvees sur le sous-lot"
PROT_HIT=$(grep -cFf "$W/protect.txt" "$W/expect.txt" || true); echo "  fiches du sous-lot presentes dans la liste de protection : $PROT_HIT"; [ "$PROT_HIT" = 0 ] || die "fiche protegee dans le sous-lot"
LIST_HIT=$(python3 - "$W/expect.txt" <<'PY'
import json, os, sys, urllib.request
want = {l.strip() for l in open(sys.argv[1]) if l.strip()}
ids, page = set(), 1
while True:
    with urllib.request.urlopen(f"{os.environ['API_BASE']}/api/v1/devices/?page={page}&page_size=100", timeout=60) as r: d = json.load(r)
    if not d["items"]: break
    ids |= {i["id"] for i in d["items"]}; page += 1
print(len(want & ids))
PY
)
echo "  fiches du sous-lot presentes dans le listing public : $LIST_HIT"; [ "$LIST_HIT" = 0 ] || die "fiche du sous-lot visible dans l'API publique"
PAG0=$(pagination); echo "  pagination avant (total lignes distincts) : $PAG0"
JFP0=$(pg -c "select coalesce(md5(string_agg(concat_ws('~', id, run_id, action, coalesce(previous_validation_status,''), coalesce(previous_status,''), coalesce(previous_ai_rewrite_status,''), archived_at), '|' order by id)), 'vide') from device_archive_log where device_id::text = any(string_to_array('$IDS_CSV', ','))")
AIFP0=$(pg -c "select coalesce(md5(string_agg(concat_ws('~', id, run_id, device_id, action, coalesce(previous_validation_status,''), coalesce(previous_status,''), coalesce(previous_ai_rewrite_status,''), archived_at), '|' order by id)), 'vide') from device_archive_log where action='ai_hold'")
echo "  journal existant sur le sous-lot : $(pg -c "select count(*) from device_archive_log where device_id::text = any(string_to_array('$IDS_CSV', ','))") ligne(s), empreinte $JFP0 ; empreinte ai_hold ($AIH0 lignes) : $AIFP0"
SIM=$(cli apply --batch "$BATCH" --plan-hash "$FP" --run-id "SIMULATION-$TS" --backup-ref none --limit "$LIMIT" --protect-file /tmp/lota_pilot_protect.txt 2>&1 | tr -d '\n ' )
echo "  simulation apply : $SIM"
echo "$SIM" | grep -q '"dry_run":true' && echo "$SIM" | grep -q "\"planned\":$LIMIT" || die "la simulation ne planifie pas exactement $LIMIT fiches"
H=$(date -u +%H:%M); echo "  heure UTC $H"
if [ "$MODE" != "--apply" ]; then
  echo ""; echo "(simulation) tous les controles sont satisfaisants. Aucune ecriture. Execution : printf '$TOKEN\\n' | LIMIT=$LIMIT WINDOW_FROM=... WINDOW_TO=... bash $0 --apply"
  docker exec "$BACKEND" rm -rf /tmp/lota_pilot_plan /tmp/lota_pilot_protect.txt; exit 0
fi

# ---------------- fenetre ----------------
NOWSTAMP=$(date -u +%Y-%m-%dT%H:%M)
[ -n "${WINDOW_FROM:-}" ] && [ -n "${WINDOW_TO:-}" ] || die "WINDOW_FROM et WINDOW_TO requis avec --apply (UTC)"
[[ "$NOWSTAMP" > "$WINDOW_FROM" || "$NOWSTAMP" == "$WINDOW_FROM" ]] && [[ "$NOWSTAMP" < "$WINDOW_TO" ]] \
  || die "hors de la fenetre autorisee ($WINDOW_FROM -> $WINDOW_TO UTC) : $NOWSTAMP"
END_EPOCH=$(date -u -d "${WINDOW_TO/T/ }:00 UTC" +%s) || die "WINDOW_TO illisible"
need_minutes "$MIN_START_MIN" "debut de l'archivage"

echo ""; echo "===== 2. SAUVEGARDE FRAICHE VERIFIEE ====="
B="$DUMP_DIR/pre_lotA_s${STAGE}_${TS}.dump"
docker exec "$PG" pg_dump -U "$PGU" -d "$PGDB" -Fc > "$B" || die "pg_dump"
sha256sum "$B" > "$B.sha256"; chmod 600 "$B" "$B.sha256"
TOC=$(docker exec -i "$PG" pg_restore --list < "$B" | wc -l)
echo "  $(basename "$B") $(stat -c %s "$B") octets, sommaire $TOC entrees"; [ "$TOC" -gt 200 ] || die "sauvegarde suspecte"
sha256sum -c "$B.sha256" >/dev/null || die "sha256 de la sauvegarde"; echo "  sha256 : $(cut -c1-16 "$B.sha256")..."
echo "  restauration disponible : restore --run-id ... (dry-run teste ci-dessous apres archivage)"
CEL2=$(celery_state); [ "$CEL2" = "0 0 0 0" ] || die "tache Celery apparue pendant la sauvegarde : $CEL2"
host_health "avant ecriture" || die "gardes de sante de l'hote non satisfaites juste avant l'ecriture : aucune ecriture effectuee"
need_minutes "$MIN_APPLY_MIN" "archivage"

echo ""; echo "===== 3. ARCHIVAGE ($LIMIT fiches) ====="
RUN="LOTA-S${STAGE}-${TS}"
echo "  run-id : $RUN"
OUT=$(cli apply --batch "$BATCH" --plan-hash "$FP" --run-id "$RUN" --backup-ref "$(basename "$B")" --limit "$LIMIT" --protect-file /tmp/lota_pilot_protect.txt --yes 2>&1); RC=$?
echo "$OUT" | sed 's/^/   /'
[ "$RC" = 0 ] || { echo "ECHEC de l'archivage (code $RC) : verifier l'etat, restauration si necessaire : restore --run-id $RUN --yes"; exit 2; }

echo ""; echo "===== 4. CONTROLES POST-ARCHIVAGE ====="
BAD=0
ARCH1=$(pg -c "select count(*) from devices where validation_status='archived'")
ARCH_SUB=$(pg -c "select count(*) from devices where validation_status='archived' and id::text = any(string_to_array('$IDS_CSV', ','))")
DEV1=$(pg -c "select count(*) from devices")
JOUR1=$(pg -c "select count(*) from device_archive_log"); JRUN=$(pg -c "select count(*) from device_archive_log where run_id='$RUN' and action='archive'")
AIH1=$(pg -c "select count(*) from device_archive_log where action='ai_hold'")
AIFP1=$(pg -c "select coalesce(md5(string_agg(concat_ws('~', id, run_id, device_id, action, coalesce(previous_validation_status,''), coalesce(previous_status,''), coalesce(previous_ai_rewrite_status,''), archived_at), '|' order by id)), 'vide') from device_archive_log where action='ai_hold'")
JFP1=$(pg -c "select coalesce(md5(string_agg(concat_ws('~', id, run_id, action, coalesce(previous_validation_status,''), coalesce(previous_status,''), coalesce(previous_ai_rewrite_status,''), archived_at), '|' order by id)), 'vide') from device_archive_log where device_id::text = any(string_to_array('$IDS_CSV', ',')) and run_id <> '$RUN'")
PROT_ARCH=$(docker exec -i "$PG" psql -U "$PGU" -d "$PGDB" -At -c "select count(*) from devices where id::text = any(string_to_array('$(paste -sd, "$W/protect.txt")', ',')) and validation_status='archived'")
echo "  archivees : $ARCH1 (avant $ARCH0, attendu $((ARCH0 + LIMIT))) ; dont du sous-lot : $ARCH_SUB (attendu $LIMIT)"
echo "  fiches totales : $DEV1 (avant $DEV0) ; journal : $JOUR1 (avant $JOUR0, attendu $((JOUR0 + LIMIT))) ; entrees du run : $JRUN"
echo "  historique anterieur du sous-lot conserve : $([ "$JFP1" = "$JFP0" ] && echo OUI || echo NON) ($JFP0 -> $JFP1)"
echo "  ai_hold : $AIH1 lignes (avant $AIH0) ; empreinte conservee : $([ "$AIFP1" = "$AIFP0" ] && echo OUI || echo NON)"
echo "  fiches protegees archivees : $PROT_ARCH (attendu 0)"
[ "$ARCH1" = "$((ARCH0 + LIMIT))" ] && [ "$ARCH_SUB" = "$LIMIT" ] || { echo "ANOMALIE : nombre d'archivees"; BAD=1; }
[ "$DEV1" = "$DEV0" ] || { echo "ANOMALIE : fiches totales modifiees"; BAD=1; }
[ "$JOUR1" = "$((JOUR0 + LIMIT))" ] && [ "$JRUN" = "$LIMIT" ] || { echo "ANOMALIE : journal"; BAD=1; }
[ "$JFP1" = "$JFP0" ] || { echo "ANOMALIE : historique journal modifie"; BAD=1; }
[ "$AIH1" = "$AIH0" ] && [ "$AIFP1" = "$AIFP0" ] || { echo "ANOMALIE : entrees ai_hold modifiees"; BAD=1; }
[ "$PROT_ARCH" = 0 ] || { echo "ANOMALIE : fiche protegee archivee"; BAD=1; }
echo "  /api/ready : $(ready) ; pagination apres : $(pagination) (avant $PAG0)"
[ "$(ready)" = "200 $HEAD_REV" ] || { echo "ANOMALIE : /api/ready"; BAD=1; }
[ "$(pagination)" = "$PAG0" ] || { echo "ANOMALIE : pagination modifiee"; BAD=1; }
echo "  Celery (actives reservees en_file celery) : $(celery_state)"
ERRS=$(for c in "$BACKEND" kafundo-worker kafundo-beat; do docker logs --since 10m "$c" 2>&1; done | grep -ciE 'traceback|critical'); echo "  erreurs de journaux (10 min) : $ERRS"
[ "$ERRS" = 0 ] || { echo "ANOMALIE : erreurs de journaux"; BAD=1; }
REST=$(cli restore --run-id "$RUN" 2>&1 | tr -d '\n '); echo "  restauration (simulation) : $REST"
echo "$REST" | grep -q "\"entries\":$LIMIT" || { echo "ANOMALIE : restauration non disponible pour $LIMIT entrees"; BAD=1; }
docker exec "$BACKEND" rm -rf /tmp/lota_pilot_plan /tmp/lota_pilot_protect.txt
echo ""
if [ "$BAD" = 0 ]; then echo "RESULTAT : $LIMIT FICHES ARCHIVEES ET CONTROLEES (run-id $RUN)"; else echo "RESULTAT : ANOMALIE(S) - NE PAS POURSUIVRE ; restauration : docker exec -e PYTHONPATH=/app $BACKEND python -m app.data.catalog_cleanup restore --run-id $RUN --yes"; fi
echo "Suite : controle apres la prochaine collecte planifiee : RUN_ID=$RUN LIMIT=$LIMIT bash $0 --followup"
echo "Restauration complete : docker exec -e PYTHONPATH=/app $BACKEND python -m app.data.catalog_cleanup restore --run-id $RUN --yes"
echo "Restauration ciblee   : ... restore --run-id $RUN --device-id <id> [--device-id <id> ...] --yes"
echo "Sauvegarde : $B ; journal : $LOG"
exit $BAD
