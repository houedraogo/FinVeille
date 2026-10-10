#!/usr/bin/env python3
"""Genere (sans rien executer) : plan d'actions Finnovatix, script d'application transactionnel, script
optionnel de fusion, script de retour arriere exact. Lecture seule sur la production (SELECT uniquement)."""
import csv, subprocess, base64, datetime, collections, json
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fxlib
D = os.environ.get("AUDIT_DIR", "/opt/finveille-backups/audit_20261010")
RUN = "FXREMAP-20261010"
TODAY = datetime.date(2026, 10, 10)

control = list(csv.DictReader(open(f"{D}/finnovatix_remap_control.csv", encoding="utf-8")))
noeq = list(csv.DictReader(open(f"{D}/finnovatix_no_equivalent_classified.csv", encoding="utf-8")))
byurl = {r["fc_id"]: r for r in csv.DictReader(open(f"{D}/finnovatix_no_equivalent_by_url.csv", encoding="utf-8"))}

# ---------------- plan d'actions ----------------
plan = []   # dict(fc_id, old_kid, action, new_kid, target_fc, note)
def add(fc_id, old, action, new="", tgt="", note=""):
    plan.append(dict(fc_id=str(fc_id), old_kid=old, action=action, new_kid=new, target_fc="" if tgt is None else str(tgt), note=note))

# fc cibles (id Finnovatix des kafundo_id finaux), recupere en une requete
my = fxlib.my
finals = sorted({r["final_kafundo_id"] for r in control if r["final_kafundo_id"]})
tfc = {}
for l in my("select kafundo_id, id from funding_calls where kafundo_id in (%s);" % ",".join("'%s'" % f for f in finals)).splitlines():
    k, i = l.split("\t"); tfc[k] = i

for r in control:
    if not r["final_kafundo_id"]:
        continue
    fl = r["flags"]
    conflict = "CONFLIT" in fl or "PLUSIEURS" in fl
    if not conflict:
        add(r["fc_id"], r["old_kafundo_id"], "R_remap", new=r["final_kafundo_id"], note=fl)
    else:
        tgt = tfc.get(r["final_kafundo_id"], "")
        n_old, common = int(r["n_opportunities"]), None
        # 3 cas : aucun dossier sur l'ancienne -> annotation ; l'ancienne a des dossiers et la cible aucun -> fusion optionnelle ; sinon annotation
        add(r["fc_id"], r["old_kafundo_id"], "S_superseded_annotate", new=r["final_kafundo_id"], tgt=tgt, note=fl)

# les 44 sans equivalent par titre
for r in noeq:
    cat = r["category"]; u = byurl.get(r["fc_id"], {})
    um = u.get("url_match", "")
    if um == "1_publique" and cat.startswith("C"):
        cand = u["candidate_ids"].split("|")[0]
        add(r["fc_id"], r["kafundo_id"], "R_remap_by_url", new=cand, note="meme source_url, 1 fiche publique")
    elif cat.startswith("B"):
        add(r["fc_id"], r["kafundo_id"], "U_unknown_status", note="actualite FONSTI, pas une opportunite")
    elif cat.startswith("A") and "echeance_passee" in cat:
        add(r["fc_id"], r["kafundo_id"], "E_expired", note="echeance depassee, fiche Kafundo supprimee")
    elif cat.startswith("A"):
        add(r["fc_id"], r["kafundo_id"], "K_keep_open_annotate", note="opportunite reelle a echeance future, titre abime")
    else:
        add(r["fc_id"], r["kafundo_id"], "K_keep_open_annotate", note="a examiner (plusieurs fiches publiques ou titre different)")

# ---------------- etat d'origine des lignes touchees ----------------
ids = [p["fc_id"] for p in plan]
orig = {}
NUL = "<<NULL>>"
out = my("select id, kafundo_id, status, if(deadline is null,'%s',deadline), if(funding_max is null,'%s',funding_max), "
         "if(source_updated_at is null,'%s',source_updated_at), coalesce(to_base64(cast(metadata as char character set utf8mb4)),'') "
         "from funding_calls where id in (%s);" % (NUL, NUL, NUL, ",".join(ids)))
for l in out.splitlines():
    p = l.split("\t")
    if len(p) >= 7:
        orig[p[0]] = dict(kid=p[1], status=p[2], deadline=None if p[3] == NUL else p[3], fmax=None if p[4] == NUL else p[4],
                          sua=None if p[5] == NUL else p[5], meta_b64=p[6].replace("\\n", "").replace("\n", ""))
missing = [i for i in ids if i not in orig]
assert not missing, f"fc introuvables: {missing[:5]}"
assert len(set(ids)) == len(ids), "fc en double dans le plan"

def q(s): return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"
NOTE = lambda p: q(p["note"][:180])
def qn(v): return "NULL" if v is None else q(str(v))

apply_sql = [f"-- {RUN} : application (transactionnelle, garde par ligne). NE PAS EXECUTER sans accord explicite.",
             "SET NAMES utf8mb4;", "SET @bad = 0;", "START TRANSACTION;"]
optional_sql = [f"-- {RUN} : fusion OPTIONNELLE (3 FundingCall dont la cible n'a aucun dossier). Decision requise.",
                "SET NAMES utf8mb4;", "SET @bad = 0;", "START TRANSACTION;"]
rollback_sql = [f"-- {RUN} : retour arriere exact (valeurs d'origine capturees le {TODAY}).",
                "SET NAMES utf8mb4;", "START TRANSACTION;"]

def meta_json(key, obj, base="COALESCE(metadata, JSON_OBJECT())"):
    pairs = ", ".join(f"{q(k)}, {q(str(v))}" for k, v in obj.items())
    return f"JSON_SET({base}, '$.{key}', JSON_OBJECT({pairs}))"

# ---- reproduction de la detection de la synchro : changements que la prochaine synchro NOTIFIERAIT ----
api = fxlib.api_devices()
print("dispositifs lus dans l'API Kafundo (instantane complet) :", len(api))
json.dump(list(api.values()), open(f"{D}/kafundo_api_snapshot.json", "w", encoding="utf-8"), ensure_ascii=False)
realign = {}      # fc_id -> dict(changes, dev)
not_in_api = []
for p in plan:
    if p["action"] not in ("R_remap", "R_remap_by_url"):
        continue
    dev = api.get(p["new_kid"])
    if dev is None:
        not_in_api.append(p["fc_id"]); continue
    o = orig[p["fc_id"]]
    cur = dict(deadline=o["deadline"], funding_max=None if o["fmax"] is None else float(o["fmax"]), status=o["status"])
    ch = fxlib.diff(cur, dev)
    if ch:
        realign[p["fc_id"]] = dict(changes=ch, dev=fxlib.mapped(dev))

counts = collections.Counter()
for p in plan:
    o = orig[p["fc_id"]]; fc = p["fc_id"]; act = p["action"]
    guard = (f"id={fc} AND kafundo_id={q(o['kid'])} AND status={q(o['status'])} AND deadline <=> {qn(o['deadline'])} "
             f"AND funding_max <=> {qn(o['fmax'])}")
    if act in ("R_remap", "R_remap_by_url"):
        base = meta_json("kafundo_remap", dict(previous_kafundo_id=o["kid"], run=RUN, at=str(TODAY), match=p["note"][:120]))
        sets = [f"kafundo_id={q(p['new_kid'])}"]
        if fc in realign:
            r = realign[fc]
            hist = [dict(field=c["field"], old=c["old"], new=c["new"], detected_at=f"{TODAY}T00:00:00+00:00",
                         silent_realign=True, run=RUN) for c in r["changes"]]
            for c in r["changes"]:
                if c["field"] == "deadline":    sets.append(f"deadline={q(c['new'])}")
                if c["field"] == "funding_max": sets.append(f"funding_max={c['new']:.2f}")
                if c["field"] == "status":      sets.append(f"status={q(c['new'])}")
            sets.append("source_updated_at=NOW()")
            hj = json.dumps(hist, ensure_ascii=False)
            base = ("JSON_SET(" + base + ", '$.change_history', JSON_MERGE_PRESERVE(COALESCE(JSON_EXTRACT(metadata, '$.change_history'), "
                    f"JSON_ARRAY()), CAST({q(hj)} AS JSON)))")
        sets.append(f"metadata={base}")
        apply_sql.append(f"UPDATE funding_calls SET {', '.join(sets)} WHERE {guard};")
    elif act == "S_superseded_annotate":
        m = meta_json("kafundo_superseded", dict(by_kafundo_id=p["new_kid"], by_funding_call_id=p["target_fc"], run=RUN, at=str(TODAY)))
        apply_sql.append(f"UPDATE funding_calls SET metadata={m} WHERE {guard};")
    elif act == "U_unknown_status":
        m = meta_json("kafundo_retired", dict(reason="source_item_removed_from_kafundo", previous_status=o["status"], run=RUN, at=str(TODAY), note=p["note"]))
        apply_sql.append(f"UPDATE funding_calls SET status='unknown', metadata={m} WHERE {guard};")
    elif act == "E_expired":
        m = meta_json("kafundo_retired", dict(reason="deadline_passed_and_source_removed", previous_status=o["status"], run=RUN, at=str(TODAY)))
        apply_sql.append(f"UPDATE funding_calls SET status='expired', metadata={m} WHERE {guard};")
    elif act == "K_keep_open_annotate":
        m = meta_json("kafundo_source_missing", dict(note=p["note"], run=RUN, at=str(TODAY)))
        apply_sql.append(f"UPDATE funding_calls SET metadata={m} WHERE {guard};")
    else:
        raise SystemExit("action inconnue " + act)
    apply_sql.append("SET @bad = @bad + (ROW_COUNT() <> 1);")
    counts[act] += 1
    # retour arriere : valeurs exactes d'origine (kafundo_id, statut, echeance, montant, fraicheur, metadonnees)
    meta = f"CAST(CONVERT(FROM_BASE64({q(o['meta_b64'])}) USING utf8mb4) AS JSON)" if o["meta_b64"] else "NULL"
    rollback_sql.append(f"UPDATE funding_calls SET kafundo_id={q(o['kid'])}, status={q(o['status'])}, deadline={qn(o['deadline'])}, "
                        f"funding_max={qn(o['fmax'])}, source_updated_at={qn(o['sua'])}, metadata={meta} WHERE id={fc};")

# fusion optionnelle : 3 cas ou l'ancienne a des dossiers et la cible aucun
opt = []
for r in control:
    if r["final_kafundo_id"] and ("CONFLIT" in r["flags"]) and int(r["n_opportunities"]) > 0:
        t = tfc.get(r["final_kafundo_id"])
        if not t: continue
        n = my(f"select count(*) from funding_opportunities where funding_call_id={t};").strip()
        if n == "0":
            opt.append((r["fc_id"], t))
for old_fc, new_fc in opt:
    optional_sql.append(f"UPDATE funding_opportunities SET funding_call_id={new_fc} WHERE funding_call_id={old_fc};")
    optional_sql.append(f"UPDATE marketing_contents SET funding_call_id={new_fc} WHERE funding_call_id={old_fc};")
    rollback_sql.append(f"-- (fusion optionnelle {old_fc}->{new_fc}) : voir finnovatix_rollback_optional_M.sql")

rb_opt = [f"-- {RUN} : retour arriere de la fusion optionnelle", "START TRANSACTION;"]
# ids des lignes deplacees, captures avant
for old_fc, new_fc in opt:
    ids_o = my(f"select group_concat(id) from funding_opportunities where funding_call_id={old_fc};").strip()
    ids_m = my(f"select group_concat(id) from marketing_contents where funding_call_id={old_fc};").strip()
    if ids_o and ids_o != "NULL": rb_opt.append(f"UPDATE funding_opportunities SET funding_call_id={old_fc} WHERE id IN ({ids_o});")
    if ids_m and ids_m != "NULL": rb_opt.append(f"UPDATE marketing_contents SET funding_call_id={old_fc} WHERE id IN ({ids_m});")
rb_opt.append("COMMIT;")

tail_apply = ["SELECT @bad AS lignes_en_ecart;",
              "SET @fin = IF(@bad = 0, 'COMMIT', 'ROLLBACK');", "PREPARE s FROM @fin;", "EXECUTE s;", "DEALLOCATE PREPARE s;",
              "SELECT IF(@bad = 0, 'COMMIT effectue', 'ROLLBACK : au moins une ligne ne correspondait plus a l etat attendu') AS resultat;"]
apply_sql += tail_apply
optional_sql += ["SELECT 'fusion optionnelle appliquee' AS resultat;", "COMMIT;"]
rollback_sql += ["COMMIT;", "SELECT 'retour arriere termine' AS resultat;"]

def w(name, lines): open(f"{D}/{name}", "w", encoding="utf-8").write("\n".join(lines) + "\n")
w("finnovatix_apply.sql", apply_sql); w("finnovatix_apply_optional_M.sql", optional_sql)
w("finnovatix_rollback.sql", rollback_sql); w("finnovatix_rollback_optional_M.sql", rb_opt)
with open(f"{D}/finnovatix_action_plan.csv", "w", newline="", encoding="utf-8") as f:
    wr = csv.writer(f); wr.writerow(["fc_id","old_kafundo_id","action","new_kafundo_id","target_fc_id","previous_status","note"])
    for p in plan: wr.writerow([p["fc_id"], p["old_kid"], p["action"], p["new_kid"], p["target_fc"], orig[p["fc_id"]]["status"], p["note"]])
print("plan d'actions :", sum(counts.values()), "lignes")
for a, n in counts.most_common(): print(f"   {n:4d}  {a}")
print("fusion optionnelle (cibles sans dossier) :", len(opt), opt)
# ---- synthese par consultant (rien n'est envoye ici) ----
admin = my("select id from users where role='admin' order by id limit 1;").strip()
digest = collections.OrderedDict()
n_opps = 0
LABEL = {"deadline": "échéance : {old} → {new}", "funding_max": "montant max : {old} → {new}", "status": "statut : {old} → {new}"}
for fc, r in realign.items():
    title = my(f"select title from funding_calls where id={fc};").strip()
    rows = my("select o.id, o.consulting_project_id, coalesce(p.consultant_id,''), coalesce(nullif(p.client_name,''), p.name), o.dispositif "
              f"from funding_opportunities o join consulting_projects p on p.id=o.consulting_project_id where o.funding_call_id={fc};")
    summary = " · ".join(LABEL[c["field"]].format(old=c["old"] if c["old"] is not None else "—", new=c["new"]) for c in r["changes"])
    for l in rows.splitlines():
        oid, pid, cons, label, disp = (l.split("\t") + [""] * 5)[:5]
        uid = cons or admin
        n_opps += 1
        digest.setdefault(uid, []).append(dict(funding_call_id=int(fc), opportunity_id=int(oid), project_id=int(pid),
                                               project=label, dispositif=disp or title, changes=summary))
json.dump(digest, open(f"{D}/finnovatix_digest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
with open(f"{D}/finnovatix_realign_changes.csv", "w", newline="", encoding="utf-8") as f:
    wr = csv.writer(f); wr.writerow(["fc_id", "new_kafundo_id", "field", "old", "new"])
    for fc, r in realign.items():
        pl = next(p for p in plan if p["fc_id"] == fc)
        for c in r["changes"]: wr.writerow([fc, pl["new_kid"], c["field"], c["old"], c["new"]])
print(f"realignement silencieux : {len(realign)} fiches, {sum(len(r['changes']) for r in realign.values())} changements "
      f"({dict(collections.Counter(c['field'] for r in realign.values() for c in r['changes']))})")
print(f"rattachees mais absentes de la liste de l'API (jamais synchronisees : aucune notification possible) : {len(not_in_api)}")
# information : ecarts de valeurs de ces fiches vis-a-vis de la fiche Kafundo (detail), NON realignes par cette operation
ns = []
for fc in not_in_api:
    pl = next(p for p in plan if p["fc_id"] == fc); o = orig[fc]
    dev = fxlib.api_detail(pl["new_kid"])
    if dev is None:
        ns.append((fc, pl["new_kid"], "fiche_non_publique", "", "")); continue
    cur = dict(deadline=o["deadline"], funding_max=None if o["fmax"] is None else float(o["fmax"]), status=o["status"])
    ch = fxlib.diff(cur, dev)
    for c in ch: ns.append((fc, pl["new_kid"], c["field"], c["old"], c["new"]))
with open(f"{D}/finnovatix_not_synced_changes.csv", "w", newline="", encoding="utf-8") as f:
    wr = csv.writer(f); wr.writerow(["fc_id", "new_kafundo_id", "field_or_reason", "old", "new"]); wr.writerows(ns)
print("   dont ecarts de valeurs vs fiche Kafundo (information, non realignes) :",
      dict(collections.Counter(r[2] for r in ns)), "sur", len({r[0] for r in ns}), "fiches")
print(f"synthese : {len(digest)} destinataire(s), {n_opps} dossier(s)-opportunite(s) concerne(s)")
print("fichiers ecrits dans", D)
