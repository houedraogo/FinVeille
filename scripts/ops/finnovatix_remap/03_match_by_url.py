#!/usr/bin/env python3
"""Lecture seule : pour les 44 FundingCall sans equivalent, cherche une fiche Kafundo actuelle de meme source_url."""
import csv, subprocess, collections
import os
D = os.environ.get("AUDIT_DIR", "/opt/finveille-backups/audit_20261010")
rows = list(csv.DictReader(open(f"{D}/finnovatix_no_equivalent_classified.csv", encoding="utf-8")))
urls = sorted({r["source_url"] for r in rows if r["source_url"]})
q = ("set default_transaction_read_only=on; select d.source_url, d.id, d.validation_status, d.status, coalesce(d.close_date::text,''), "
     "left(replace(d.title,E'\\t',' '),60), date(d.created_at) from devices d where d.source_url in (%s)" % ",".join("'%s'" % u.replace("'", "''") for u in urls))
out = subprocess.run(["docker","exec","kafundo-postgres","psql","-U","finveille","-d","finveille","-At","-F","\t","-c",q],
                     capture_output=True).stdout.decode("utf-8", errors="replace")
by_url = collections.defaultdict(list)
for l in out.splitlines():
    p = l.split("\t")
    if len(p) == 7: by_url[p[0]].append(p[1:])
print(f"urls sources distinctes : {len(urls)}  | trouvees dans Kafundo actuellement : {len(by_url)}")
cnt = collections.Counter(); detail = []
for r in rows:
    m = by_url.get(r["source_url"], [])
    pub = [x for x in m if x[1] in ("auto_published", "validated", "manually_published")]
    key = "AUCUNE" if not m else ("1_publique" if len(pub) == 1 else ("plusieurs_publiques" if len(pub) > 1 else "non_publique"))
    cnt[(r["category"][:1], key)] += 1
    detail.append((r, m, key))
print("categorie / correspondance par URL :")
for (c, k), v in sorted(cnt.items()): print(f"   {c}  {k:22s} {v}")
print("\nexemples avec correspondance URL :")
n = 0
for r, m, key in detail:
    if m and n < 8:
        print(f"   fc {r['fc_id']:>4} ({r['category'][:1]}) -> {m[0][0][:8]} | {m[0][1]} | {m[0][2]} | ech {m[0][3] or '-'} | cree {m[0][5]} | {m[0][4]}")
        n += 1
with open(f"{D}/finnovatix_no_equivalent_by_url.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["category","fc_id","kafundo_id","url_match","candidate_ids","candidate_validation"])
    for r, m, key in detail:
        w.writerow([r["category"], r["fc_id"], r["kafundo_id"], key, "|".join(x[0] for x in m), "|".join(x[1] for x in m)])
