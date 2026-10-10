#!/usr/bin/env python3
"""Lecture seule : classe les 44 FundingCall sans equivalent et retrouve leur titre d'origine dans la sauvegarde
Kafundo du 01/10 04:39 (avant suppression). Aucune ecriture."""
import csv, subprocess, collections, datetime, glob, re
import os
D = os.environ.get("AUDIT_DIR", "/opt/finveille-backups/audit_20261010")
PREFIXES = ["Subvention", "Concours", "Appel à projets", "Appel a projets", "Appel à manifestation d'intérêt",
            "Appel a manifestation d'interet", "Programme d'accompagnement", "Opportunité d'investissement",
            "Opportunite d'investissement", "Investissement", "Opportunité", "Opportunite", "Bourse", "Prêt", "Pret",
            "Garantie", "Equity"]
def strip(t):
    t = t.strip(); layers = 0; ch = True
    while ch:
        ch = False
        for p in PREFIXES:
            m = p.lower() + " - "
            if t.lower().startswith(m):
                t = t[len(m):].strip(); layers += 1; ch = True; break
    return t, layers

control = list(csv.DictReader(open(f"{D}/finnovatix_remap_control.csv", encoding="utf-8")))
known = {r["old_kafundo_id"] for r in control}
missing = [l.strip() for l in open(f"{D}/finnovatix_protected_ids_missing_in_kafundo.txt") if l.strip()]
ids = [r["old_kafundo_id"] for r in control if not r["final_kafundo_id"]] + [m for m in missing if m not in known]
IN = ",".join("'%s'" % i for i in ids)

# 1) Finnovatix (utf8mb4 explicite)
sql = f"""select fc.id, fc.kafundo_id, replace(replace(fc.title,'\\t',' '),'\\n',' '), fc.status, coalesce(fc.deadline,''),
  coalesce(fc.organism,''), coalesce(fc.source_url,''), coalesce(length(fc.description),0),
  (select count(*) from funding_opportunities o where o.funding_call_id=fc.id)
  from funding_calls fc where fc.kafundo_id in ({IN})"""
out = subprocess.run(["docker","exec","-i","finnovatix-platform-finnovatix-mysql-1","sh","-c",
    'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --default-character-set=utf8mb4 --batch --skip-column-names finnovatix'],
    input=sql.encode(), capture_output=True).stdout.decode("utf-8", errors="replace")

# 2) titres d'origine depuis la sauvegarde Kafundo (COPY de la table devices)
dump = sorted(glob.glob("/opt/finveille-backups/pre_dedup_titles_*.dump"))[0]
pr = subprocess.Popen(["docker","exec","-i","kafundo-postgres","pg_restore","-a","-t","devices","-f","-"],
                      stdin=open(dump, "rb"), stdout=subprocess.PIPE)
orig = {}; idx_title = idx_src = None; want = set(ids); in_copy = False
for raw in pr.stdout:
    line = raw.decode("utf-8", errors="replace").rstrip("\n")
    if line.startswith("COPY public.devices"):
        cols = [c.strip() for c in line[line.index("(")+1:line.index(")")].split(",")]
        idx_title = cols.index("title"); in_copy = True; continue
    if in_copy:
        if line == "\\.": break
        f = line.split("\t")
        if f and f[0] in want:
            orig[f[0]] = f[idx_title]
pr.wait()
print(f"titres d'origine retrouves dans {dump.split('/')[-1]} : {len(orig)} / {len(ids)}")

today = datetime.date(2026, 10, 10)
cats = collections.defaultdict(list)
for l in out.splitlines():
    p = l.split("\t")
    if len(p) < 9: continue
    fc_id, kid, title, status, deadline, org, url, desc_len, n_opps = p[:9]
    full = orig.get(kid, title)
    clean, layers = strip(full)
    stacked = layers >= 2 or strip(title)[1] >= 2
    fonsti = "fonsti" in (org + " " + url + " " + full).lower()
    try: dl = datetime.date.fromisoformat(deadline) if deadline else None
    except ValueError: dl = None
    future = dl is not None and dl >= today
    if fonsti and not stacked:
        cat = "B_actualite_FONSTI_non_opportunite"
    elif stacked:
        cat = "A_titre_empile_opportunite_reelle" + ("_echeance_future" if future else "_echeance_passee_ou_absente")
    else:
        cat = "C_autre_a_examiner"
    cats[cat].append(dict(fc_id=fc_id, kid=kid, title=title, clean=clean, recovered=(kid in orig), status=status,
                          deadline=deadline, org=org, url=url, desc_len=int(desc_len or 0), n_opps=int(n_opps)))
print("classification des", sum(len(v) for v in cats.values()), "references sans equivalent Kafundo :")
for k in sorted(cats):
    v = cats[k]
    print(f"  {len(v):3d}  {k:58s} opportunites rattachees={sum(x['n_opps'] for x in v):3d}  titre d'origine retrouve: {sum(1 for x in v if x['recovered'])}")
print()
for k in sorted(cats):
    print("--", k)
    for x in cats[k][:5]:
        print(f"     fc {x['fc_id']:>4} | {x['org'][:26]:26s} | ech {x['deadline'] or '-':10s} | opps {x['n_opps']:>2} | {x['clean'][:78]}")
with open(f"{D}/finnovatix_no_equivalent_classified.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["category","fc_id","kafundo_id","status","deadline","organism","n_opportunities","title_recovered","clean_title","finnovatix_title","source_url"])
    for k in sorted(cats):
        for x in cats[k]:
            w.writerow([k, x["fc_id"], x["kid"], x["status"], x["deadline"], x["org"], x["n_opps"], int(x["recovered"]), x["clean"], x["title"], x["url"]])
