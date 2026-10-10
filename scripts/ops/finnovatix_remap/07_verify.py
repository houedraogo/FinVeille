#!/usr/bin/env python3
"""Verification APRES application (lecture seule) : les fiches rattachees pointent bien vers la fiche Kafundo prevue et
leurs valeurs materielles (statut, montant max, echeance) sont celles que l'API Kafundo renvoie, de sorte que la prochaine
synchro ne detectera AUCUN changement pour elles. Code retour 1 au moindre ecart.

  python3 07_verify.py              # production (conteneur MySQL Finnovatix + API locale)
  MYSQL_EXEC=... API_URL=... python3 07_verify.py     # copie jetable
"""
import csv, json, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fxlib

D = fxlib.AUDIT_DIR
plan = [r for r in csv.DictReader(open(f"{D}/finnovatix_action_plan.csv", encoding="utf-8")) if r["action"] in ("R_remap", "R_remap_by_url")]
api = fxlib.api_devices()
ids = ",".join(r["fc_id"] for r in plan)
rows = {}
for l in fxlib.my(f"select id, kafundo_id, coalesce(deadline,''), coalesce(funding_max,''), status, "
                  f"coalesce(JSON_UNQUOTE(JSON_EXTRACT(metadata,'$.kafundo_remap.run')),'') from funding_calls where id in ({ids});").splitlines():
    p = l.split("\t"); rows[p[0]] = p
bad = collections.defaultdict(list); realigned = 0; not_in_api = 0
for r in plan:
    p = rows.get(r["fc_id"])
    if p is None:
        bad["fiche_introuvable"].append(r["fc_id"]); continue
    if p[1] != r["new_kafundo_id"]:
        bad["kafundo_id_inattendu"].append(r["fc_id"])
    if not p[5]:
        bad["annotation_kafundo_remap_absente"].append(r["fc_id"])
    dev = api.get(r["new_kafundo_id"])
    if dev is None:
        not_in_api += 1; continue
    cur = dict(deadline=p[2] or None, funding_max=float(p[3]) if p[3] != "" else None, status=p[4])
    d = fxlib.diff(cur, dev)
    if d:
        bad["valeurs_differentes_de_kafundo"].append((r["fc_id"], [(c["field"], c["old"], c["new"]) for c in d]))
    else:
        realigned += 1
dups = fxlib.my("select count(*) from (select kafundo_id from funding_calls group by kafundo_id having count(*)>1) t;").strip()
print(f"fiches rattachees controlees : {len(plan)}")
print(f"  valeurs identiques a l'API Kafundo (aucun changement detectable a la prochaine synchro) : {realigned}")
print(f"  absentes de l'API (non synchronisees) : {not_in_api}")
print(f"  doublons kafundo_id : {dups} (attendu 0)")
for k, v in bad.items():
    print(f"  ECART {k} : {len(v)}  {v[:5]}")
sys.exit(1 if bad or dups != "0" else 0)
