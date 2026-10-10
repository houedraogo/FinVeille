#!/usr/bin/env python3
"""Disponibilite des fiches Finnovatix : ne plus proposer comme OUVERTES (FundingCall::open() => status='open', utilise par
les recommandations, la boucle de decouverte et le rapprochement des leads) des fiches expirees, en attente de verification ou
dont la disponibilite n'est pas confirmee. Lecture seule : genere des scripts, n'ecrit RIEN.

Regles (aucune suppression, aucun lien avec les dossiers modifie ; seules `status` et une annotation `metadata` changent).
Les preuves sont lues cote Kafundo (statut, echeance, recurrence de la fiche rattachee) :
  echeance Finnovatix depassee, status='open' :
      echeance Kafundo ulterieure a aujourd'hui                -> MAINTENUE ouverte (prolongation identifiee), listee
      fiche Kafundo recurrente / standby / recurring            -> 'unknown'
      fiche Kafundo 'open' sans date (reouverture possible)     -> 'unknown'
      sinon                                                     -> 'expired'
  rattachee hors liste publique, status='open' :
      fiche Kafundo expired                                     -> 'expired'
      standby / pending_review / admin_only / absente           -> 'unknown'
Sorties (AUDIT_DIR) : finnovatix_availability.sql, _rollback.sql, finnovatix_availability.csv (avec preuves),
finnovatix_availability_kept_open.csv. Le retour arriere restitue statut et metadonnees d'origine (valeurs capturees)."""
import collections, csv, datetime, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fxlib

D = fxlib.AUDIT_DIR
RUN = "FXAVAIL-20261010"
TODAY = datetime.date.today()
NUL = "<<NULL>>"
my = fxlib.my


def psql(sql):
    return subprocess.run(["docker", "exec", "-i", os.environ.get("KAFUNDO_PG", "kafundo-postgres"), "psql", "-U", "finveille",
                           "-d", "finveille", "-At", "-F", "|", "-c", sql], capture_output=True, text=True).stdout


plan = [r for r in csv.DictReader(open(f"{D}/finnovatix_action_plan.csv", encoding="utf-8")) if r["action"] in ("R_remap", "R_remap_by_url")]
snap = {d["id"] for d in json.load(open(f"{D}/kafundo_api_snapshot.json", encoding="utf-8"))}
unlisted = {r["fc_id"] for r in plan if r["new_kafundo_id"] not in snap}

rows = my("select f.id, f.status, coalesce(f.deadline,'" + NUL + "'), left(replace(f.title,'\\t',' '),60), "
          "(select count(*) from funding_opportunities o where o.funding_call_id=f.id), "
          "coalesce(to_base64(cast(f.metadata as char character set utf8mb4)),''), coalesce(f.kafundo_id,''), "
          "(select count(*) from marketing_contents m where m.funding_call_id=f.id) "
          "from funding_calls f where f.status='open';")
cand = []
for line in rows.splitlines():
    p = line.split("\t")
    if len(p) >= 8:
        cand.append(dict(fc=p[0], status=p[1], deadline=None if p[2] == NUL else p[2], title=p[3], opps=int(p[4]),
                         meta=p[5].replace("\\n", "").replace("\n", ""), kid=p[6], mkt=int(p[7])))

kd = {}
kids = sorted({c["kid"] for c in cand if c["kid"]})
for i in range(0, len(kids), 400):
    inl = ",".join("'%s'" % k for k in kids[i:i + 400])
    for line in psql("select id, validation_status, status, coalesce(close_date::text,''), is_recurring::text "
                     f"from devices where id in ({inl})").splitlines():
        v = line.split("|")
        kd[v[0]] = dict(vs=v[1], st=v[2], close=v[3] or None, rec=v[4] == "true")

changes, kept = [], []
for c in cand:
    e = kd.get(c["kid"])
    listed = c["kid"] in snap
    c.update(k_status=e["st"] if e else "absente", k_valid=e["vs"] if e else "", k_close=(e or {}).get("close") or "",
             k_rec=bool(e and e["rec"]))
    past = c["deadline"] is not None and c["deadline"] < str(TODAY)
    new = reason = None
    if past:
        if e and e["close"] and e["close"] > str(TODAY):
            kept.append((c, "prolongation_identifiee: echeance Kafundo " + e["close"]))
        elif e and (e["rec"] or e["st"] in ("recurring", "standby")):
            new, reason = "unknown", f"recurrent_ou_incertain(kafundo:{e['st']})"
        elif e and e["st"] == "open" and not e["close"]:
            new, reason = "unknown", "reouverture_possible(kafundo:open_sans_date)"
        else:
            new, reason = "expired", "deadline_passed" + ("" if e else "(fiche_kafundo_absente)")
    elif c["fc"] in unlisted or (e and not listed and e["st"] != "open"):
        if e and e["st"] == "expired":
            new, reason = "expired", "kafundo_status_expired"
        elif e is None or e["st"] == "standby" or e["vs"] in ("pending_review", "admin_only"):
            new, reason = "unknown", f"availability_unconfirmed({c['k_valid'] or 'absente'}/{c['k_status']})"
    if new:
        c.update(new=new, reason=reason)
        changes.append(c)


def q(s):
    return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"


apply_sql = [f"-- {RUN} : disponibilite (transactionnelle, gardee par ligne). NE PAS EXECUTER sans accord explicite.",
             "SET NAMES utf8mb4;", "SET @bad = 0;", "START TRANSACTION;"]
rb = [f"-- {RUN} : retour arriere exact", "SET NAMES utf8mb4;", "START TRANSACTION;"]
for c in changes:
    ann = ("JSON_SET(COALESCE(metadata, JSON_OBJECT()), '$.kafundo_availability', JSON_OBJECT("
           f"'previous_status', {q(c['status'])}, 'reason', {q(c['reason'])}, 'run', {q(RUN)}, 'at', {q(str(TODAY))}))")
    apply_sql.append(f"UPDATE funding_calls SET status={q(c['new'])}, metadata={ann} WHERE id={c['fc']} AND status={q(c['status'])};")
    apply_sql.append("SET @bad = @bad + (ROW_COUNT() <> 1);")
    meta = f"CAST(CONVERT(FROM_BASE64({q(c['meta'])}) USING utf8mb4) AS JSON)" if c["meta"] else "NULL"
    rb.append(f"UPDATE funding_calls SET status={q(c['status'])}, metadata={meta} WHERE id={c['fc']};")
apply_sql += ["SELECT @bad AS lignes_en_ecart;", "SET @fin = IF(@bad = 0, 'COMMIT', 'ROLLBACK');", "PREPARE s FROM @fin;", "EXECUTE s;",
              "DEALLOCATE PREPARE s;",
              "SELECT IF(@bad = 0, 'COMMIT effectue', 'ROLLBACK : au moins une ligne ne correspondait plus a l etat attendu') AS resultat;"]
rb += ["COMMIT;", "SELECT 'retour arriere termine' AS resultat;"]
open(f"{D}/finnovatix_availability.sql", "w", encoding="utf-8").write("\n".join(apply_sql) + "\n")
open(f"{D}/finnovatix_availability_rollback.sql", "w", encoding="utf-8").write("\n".join(rb) + "\n")
with open(f"{D}/finnovatix_availability.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["fc_id", "old_status", "new_status", "reason", "fc_deadline", "kafundo_status", "kafundo_close_date",
                "kafundo_recurring", "kafundo_validation", "dossiers", "marketing", "title"])
    for c in changes:
        w.writerow([c["fc"], c["status"], c["new"], c["reason"], c["deadline"] or "", c["k_status"], c["k_close"], c["k_rec"],
                    c["k_valid"], c["opps"], c["mkt"], c["title"]])
with open(f"{D}/finnovatix_availability_kept_open.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["fc_id", "fc_deadline", "motif", "dossiers", "title"])
    for c, why in kept:
        w.writerow([c["fc"], c["deadline"] or "", why, c["opps"], c["title"]])

cnt = collections.Counter((c["new"], c["reason"].split("(")[0]) for c in changes)
exp = [c for c in changes if c["new"] == "expired"]
print(f"fiches 'open' a retirer des recommandations : {len(changes)} (dont {sum(1 for c in changes if c['opps'])} avec dossiers, "
      f"{sum(c['opps'] for c in changes)} dossiers-opportunites conserves, {sum(c['mkt'] for c in changes)} contenus marketing conserves)")
for k, v in cnt.most_common():
    print(f"   {v:3d}  -> {k[0]:8s}  {k[1]}")
print(f"controle des 'expired' : {len(exp)} ; echeance non depassee : "
      f"{sum(1 for c in exp if c['deadline'] is not None and c['deadline'] >= str(TODAY))} ; "
      f"prolongation Kafundo : {sum(1 for c in exp if c['k_close'] and c['k_close'] > str(TODAY))} ; "
      f"fiche Kafundo encore 'open' : {sum(1 for c in exp if c['k_status'] == 'open')}")
print(f"maintenues ouvertes (prolongation identifiee) : {len(kept)}")
print("parmi les fiches hors liste publique :", sum(1 for c in changes if c["fc"] in unlisted), "modifiees")
print("fichiers ecrits dans", D)
