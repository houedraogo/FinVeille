#!/usr/bin/env python3
"""Disponibilite des fiches Finnovatix : ne plus proposer comme OUVERTES (FundingCall::open() => status='open', utilise par
les recommandations, la boucle de decouverte et le rapprochement des leads) des fiches expirees, en attente de verification ou
dont la disponibilite n'est pas confirmee. Lecture seule : genere des scripts, n'ecrit RIEN.

Regles (aucune suppression, aucun lien avec les dossiers modifie ; seules `status` et une annotation `metadata` changent) :
  E  status='open' et echeance passee                                      -> 'expired'
  U  status='open', fiche Kafundo rattachee absente de la liste publique,
     statut Kafundo expired / standby / en attente / admin_only          -> 'expired' si expired, sinon 'unknown'
     (une fiche rattachee `open` cote Kafundo sans echeance connue reste inchangee)
Sorties (AUDIT_DIR) : finnovatix_availability.sql, finnovatix_availability_rollback.sql, finnovatix_availability.csv
Le retour arriere restitue statut et metadonnees d'origine (valeurs capturees)."""
import collections, csv, datetime, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fxlib

D = fxlib.AUDIT_DIR
RUN = "FXAVAIL-20261010"
TODAY = datetime.date.today()
NUL = "<<NULL>>"
my = fxlib.my

plan = [r for r in csv.DictReader(open(f"{D}/finnovatix_action_plan.csv", encoding="utf-8")) if r["action"] in ("R_remap", "R_remap_by_url")]
snap = {d["id"] for d in json.load(open(f"{D}/kafundo_api_snapshot.json", encoding="utf-8"))}
unlisted = {r["fc_id"]: r["new_kafundo_id"] for r in plan if r["new_kafundo_id"] not in snap}

kd = {}
if unlisted:
    ids = ",".join("'%s'" % k for k in unlisted.values())
    out = subprocess.run(["docker", "exec", "-i", os.environ.get("KAFUNDO_PG", "kafundo-postgres"), "psql", "-U", "finveille", "-d", "finveille",
                          "-At", "-F", "|", "-c", f"select id, validation_status, status from devices where id in ({ids})"],
                         capture_output=True, text=True).stdout
    for l in out.splitlines():
        p = l.split("|"); kd[p[0]] = (p[1], p[2])

rows = my("select f.id, f.status, coalesce(f.deadline,'%s'), left(replace(f.title,'\\t',' '),60), "
          "(select count(*) from funding_opportunities o where o.funding_call_id=f.id), "
          "coalesce(to_base64(cast(f.metadata as char character set utf8mb4)),'') "
          "from funding_calls f where f.status='open';" % NUL)
changes = []
for l in rows.splitlines():
    p = l.split("\t")
    if len(p) < 6:
        continue
    fc, status, deadline, title, n_opps, meta = p[0], p[1], p[2], p[3], int(p[4]), p[5].replace("\\n", "").replace("\n", "")
    new = reason = None
    if deadline != NUL and deadline < str(TODAY):
        new, reason = "expired", "deadline_passed"
    elif fc in unlisted:
        vs, st = kd.get(unlisted[fc], ("absente", ""))
        if st == "expired":
            new, reason = "expired", "kafundo_status_expired"
        elif st == "standby" or vs in ("pending_review", "admin_only", "absente"):
            new, reason = "unknown", f"availability_unconfirmed({vs}/{st})"
    if new:
        changes.append(dict(fc=fc, old=status, new=new, reason=reason, deadline=None if deadline == NUL else deadline,
                            title=title, opps=n_opps, meta=meta))

def q(s): return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"

apply_sql = [f"-- {RUN} : disponibilite (transactionnelle, gardee par ligne). NE PAS EXECUTER sans accord explicite.",
             "SET NAMES utf8mb4;", "SET @bad = 0;", "START TRANSACTION;"]
rb = [f"-- {RUN} : retour arriere exact", "SET NAMES utf8mb4;", "START TRANSACTION;"]
for c in changes:
    ann = ("JSON_SET(COALESCE(metadata, JSON_OBJECT()), '$.kafundo_availability', JSON_OBJECT("
           f"'previous_status', {q(c['old'])}, 'reason', {q(c['reason'])}, 'run', {q(RUN)}, 'at', {q(str(TODAY))}))")
    apply_sql.append(f"UPDATE funding_calls SET status={q(c['new'])}, metadata={ann} WHERE id={c['fc']} AND status={q(c['old'])};")
    apply_sql.append("SET @bad = @bad + (ROW_COUNT() <> 1);")
    meta = f"CAST(CONVERT(FROM_BASE64({q(c['meta'])}) USING utf8mb4) AS JSON)" if c["meta"] else "NULL"
    rb.append(f"UPDATE funding_calls SET status={q(c['old'])}, metadata={meta} WHERE id={c['fc']};")
apply_sql += ["SELECT @bad AS lignes_en_ecart;", "SET @fin = IF(@bad = 0, 'COMMIT', 'ROLLBACK');", "PREPARE s FROM @fin;", "EXECUTE s;",
              "DEALLOCATE PREPARE s;",
              "SELECT IF(@bad = 0, 'COMMIT effectue', 'ROLLBACK : au moins une ligne ne correspondait plus a l etat attendu') AS resultat;"]
rb += ["COMMIT;", "SELECT 'retour arriere termine' AS resultat;"]
open(f"{D}/finnovatix_availability.sql", "w", encoding="utf-8").write("\n".join(apply_sql) + "\n")
open(f"{D}/finnovatix_availability_rollback.sql", "w", encoding="utf-8").write("\n".join(rb) + "\n")
with open(f"{D}/finnovatix_availability.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["fc_id", "old_status", "new_status", "reason", "deadline", "dossiers", "title"])
    for c in changes: w.writerow([c["fc"], c["old"], c["new"], c["reason"], c["deadline"] or "", c["opps"], c["title"]])
cnt = collections.Counter((c["new"], c["reason"].split("(")[0]) for c in changes)
print(f"fiches 'open' a retirer des recommandations : {len(changes)} (dont {sum(1 for c in changes if c['opps'])} avec dossiers, "
      f"{sum(c['opps'] for c in changes)} dossiers-opportunites conserves)")
for k, v in cnt.most_common(): print(f"   {v:3d}  -> {k[0]:8s}  {k[1]}")
print("parmi les 10 fiches hors liste publique :", sum(1 for c in changes if c["fc"] in unlisted), "modifiees")
print("fichiers ecrits dans", D)
