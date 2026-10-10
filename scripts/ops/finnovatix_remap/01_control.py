#!/usr/bin/env python3
"""Controle (lecture seule) de la table de correspondance Kafundo -> Finnovatix.

Entrees : finnovatix_remap.csv (old -> keeper), export MySQL des funding_calls orphelines, tous les kafundo_id
Finnovatix, plan de nettoyage (lots). Sortie : finnovatix_remap_control.csv + resume sur stdout.
Aucune ecriture en base.
"""
import csv, collections, glob, os, sys

import os
D = os.environ.get("AUDIT_DIR", "/opt/finveille-backups/audit_20261010")
remap = list(csv.DictReader(open(f"{D}/finnovatix_remap.csv", encoding="utf-8")))

# funding_calls orphelines (export MySQL)
fc = {}
for r in csv.reader(open(os.path.join(D, "fx_missing_calls.tsv"), encoding="utf-8", errors="replace"), delimiter="\t"):
    if len(r) < 12:
        continue
    fc[r[1]] = dict(fc_id=r[0], title=r[2], status=r[3], deadline=r[4], source_updated_at=r[5], last_verified_at=r[6],
                    created_at=r[7], updated_at=r[8], n_opps=int(r[9]), n_mkt=int(r[10]), n_projects=int(r[11]))
# tous les kafundo_id existants cote Finnovatix
fx_by_kid = {}
for r in csv.reader(open(os.path.join(D, "fx_all_kafundo_ids.tsv"), encoding="utf-8", errors="replace"), delimiter="\t"):
    if len(r) >= 2:
        fx_by_kid[r[1]] = r[0]

# lots du plan (dernier plan calcule) : id -> (lot, validation_status, status, merged_into)
plan = {}
for p in glob.glob(f"{D}/" + os.environ.get("PLAN_SUBDIR", "plan_20261010_0804") + "/*.csv"):
    lot = os.path.basename(p).split("_")[0]
    for r in csv.DictReader(open(p, encoding="utf-8")):
        plan[r["id"]] = (lot, r["validation_status"], r["status"], r.get("merged_into") or "", r["title"])

keeper_users = collections.defaultdict(list)
for r in remap:
    if r["keeper_kafundo_id"]:
        keeper_users[r["keeper_kafundo_id"]].append(r["old_kafundo_id"])

rows = []
for r in remap:
    old, keep = r["old_kafundo_id"], r["keeper_kafundo_id"]
    f = fc.get(old)
    flags = []
    if f is None:
        flags.append("ABSENT_DE_FINNOVATIX")
    final = keep
    keep_lot = keep_vs = keep_st = ""
    if keep:
        info = plan.get(keep)
        if info:
            keep_lot, keep_vs, keep_st, merged, _ = info
            # un doublon certain (lot C) est lui-meme fusionne dans une autre fiche : suivre la chaine
            if keep_lot == "C" and merged:
                flags.append("KEEPER_EST_DOUBLON_LOT_C")
                final = merged
                m = plan.get(merged)
                if m:
                    keep_lot, keep_vs, keep_st = m[0], m[1], m[2]
            if keep_lot in ("A", "B"):
                flags.append(f"KEEPER_ARCHIVABLE_LOT_{keep_lot}")
            if keep_vs not in ("auto_published", "validated", "manually_published"):
                flags.append(f"KEEPER_NON_PUBLIC({keep_vs})")
        else:
            flags.append("KEEPER_HORS_PLAN")
        if final in fx_by_kid:
            flags.append("CONFLIT_UNICITE_kafundo_id_deja_present")
        if len(keeper_users[keep]) > 1:
            flags.append(f"PLUSIEURS_ANCIENS_VERS_MEME_KEEPER({len(keeper_users[keep])})")
        if r["match"].startswith("meme titre+organisme"):
            flags.append("MATCH_FAIBLE_A_REVOIR")
    else:
        flags.append("SANS_EQUIVALENT")
    rows.append(dict(old_kafundo_id=old, final_kafundo_id=final if keep else "", keeper_direct=keep, match=r["match"],
                     source=r["source"], title=(f or {}).get("title") or r["title"], fc_id=(f or {}).get("fc_id", ""),
                     fc_status=(f or {}).get("status", ""), deadline=(f or {}).get("deadline", ""),
                     n_opportunities=(f or {}).get("n_opps", 0), n_projects=(f or {}).get("n_projects", 0),
                     n_marketing=(f or {}).get("n_mkt", 0), keeper_lot=keep_lot, keeper_validation=keep_vs,
                     keeper_status=keep_st, flags="|".join(flags)))

with open(f"{D}/finnovatix_remap_control.csv", "w", newline="", encoding="utf-8") as out:
    w = csv.DictWriter(out, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

# ---- resume ----
tot = len(rows)
print(f"lignes de correspondance : {tot}")
print(f"funding_calls Finnovatix retrouvees : {sum(1 for r in rows if r['fc_id'])} / {tot}")
mapped = [r for r in rows if r["final_kafundo_id"]]
unmapped = [r for r in rows if not r["final_kafundo_id"]]
print(f"avec fiche de remplacement : {len(mapped)}   sans equivalent : {len(unmapped)}")
c = collections.Counter()
for r in rows:
    for fl in r["flags"].split("|"):
        if fl:
            c[fl.split("(")[0] if fl.startswith("PLUSIEURS") else fl] += 1
print("drapeaux :")
for k, v in c.most_common():
    print(f"   {v:4d}  {k}")
def usage(rs):
    return (sum(r["n_opportunities"] for r in rs), sum(r["n_projects"] for r in rs), sum(r["n_marketing"] for r in rs))
print("usage cote clients (opportunites, dossiers distincts cumules, contenus marketing)")
print("   remappables :", usage(mapped))
print("   sans equivalent :", usage(unmapped))
print("statuts Finnovatix des sans-equivalent :", dict(collections.Counter(r["fc_status"] for r in unmapped)))
ok = [r for r in mapped if not r["flags"]]
print(f"remappables SANS aucun drapeau : {len(ok)}")
dst = collections.Counter(r["final_kafundo_id"] for r in mapped)
print("cibles finales distinctes :", len(dst), "  cibles recevant >1 ancien :", sum(1 for v in dst.values() if v > 1))
