"""Simulation LECTURE SEULE du lot A (projets institutionnels) : candidates, verifications individuelles, categories,
exclusions, premier sous-lot. A lancer DANS le conteneur backend :

    docker exec -i -e PYTHONPATH=/app -e OUT=/tmp/lotA kafundo-backend python - < lot_a_simulation.py

Entrees (fichiers dans le conteneur) :
    /tmp/protect_base.txt     references externes (kafundo_id Finnovatix actuels + cibles de rattachement), un par ligne
    /tmp/manual_exclude.txt   exclusions imposees par le proprietaire (une par ligne, avec commentaire apres #)
Sorties dans $OUT : lotA_candidates.csv, lotA_certain_ids.txt, lotA_review.csv, lotA_excluded.csv, lotA_first_sublot_ids.txt,
protect_for_apply.txt (protect_base + exclusions + fiches a revoir : un `apply` avec ce fichier ne contient QUE les certaines),
summary.json. Aucune ecriture en base."""
import asyncio, collections, csv, json, os, urllib.request
from pathlib import Path

from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.services.catalog_cleanup import BATCH_A, BATCH_Q, PUBLIC_VALIDATION, archive_batch, build_plan, load_rows, summarize
from app.services.device_identity import DuplicateIndex, DuplicateTier

OUT = Path(os.environ.get("OUT", "/tmp/lotA")); OUT.mkdir(parents=True, exist_ok=True)
SUBLOT = int(os.environ.get("SUBLOT", "50"))
CALL_LIKE_TYPES = {"subvention", "pret", "garantie", "concours", "appel_a_projets", "aap", "investissement", "avance_remboursable",
                   "credit_impot", "exoneration", "accompagnement", "programme"}
REF_TABLES = (("favorite_devices", True), ("device_pipeline", True), ("alert_deliveries", True),
              ("device_duplicate_candidates", True), ("device_history", False), ("device_relevance_cache", False),
              ("device_archive_log", False))


def api_ids() -> set:
    ids, page = set(), 1
    while True:
        with urllib.request.urlopen(f"http://127.0.0.1:8000/api/v1/devices/?page={page}&page_size=100", timeout=60) as r:
            d = json.load(r)
        if not d["items"]:
            return ids
        ids |= {i["id"] for i in d["items"]}
        page += 1


def read_ids(path: str) -> dict:
    out = {}
    p = Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                out[line.split("#")[0].strip()] = line.split("#", 1)[1].strip() if "#" in line else ""
    return out


async def main():
    base = set(read_ids("/tmp/protect_base.txt"))
    manual = read_ids("/tmp/manual_exclude.txt")
    validated = set(read_ids("/tmp/owner_validated.txt"))   # candidates deja validees individuellement par le proprietaire
    async with AsyncSessionLocal() as db:
        rows = await load_rows(db)
        by_id = {str(r["id"]): r for r in rows}
        plan0 = build_plan(rows, base | set(manual))
        rules = {str(k): v for k, v in plan0.rules.items()}
        A0 = [str(i) for i in plan0.ids(BATCH_A)]
        Q0 = [str(i) for i in plan0.ids(BATCH_Q)]
        listed = api_ids()

        det = {}
        res = await db.execute(text(
            "select id::text, device_type, aid_nature, close_date::text, open_date::text, amount_max, is_recurring, source_url, "
            "ai_rewrite_status, user_quality_decision, created_at::date::text, last_verified_at::date::text, "
            "coalesce(left(short_description, 90), '') from devices where id::text = any(:ids)"), {"ids": A0})
        for r in res.all():
            det[r[0]] = dict(device_type=r[1], aid_nature=r[2], close_date=r[3], open_date=r[4], amount_max=r[5], recurring=r[6],
                             source_url=r[7], ai=r[8], uqd=r[9], created=r[10], verified=r[11], descr=r[12])
        refs = {t: {} for t, _ in REF_TABLES}
        for t, _ in REF_TABLES:
            col = "device_id"
            res = await db.execute(text(f"select {col}::text, count(*) from {t} where {col}::text = any(:ids) group by 1"), {"ids": A0})
            refs[t] = {r[0]: r[1] for r in res.all()}

        live = [r for r in rows if r["validation_status"] != "archived"]
        idx = DuplicateIndex(live)
        dup_out = {}
        a_set = set(A0)
        for i in A0:
            row = by_id[i]
            found = []
            for other, assessment in idx.assess(row):
                oid = str(other["id"])
                if oid == i or oid in a_set:
                    continue
                if assessment.tier in (DuplicateTier.CERTAIN, DuplicateTier.PROBABLE):
                    found.append(f"{assessment.tier.name.lower()}:{oid}")
            if found:
                dup_out[i] = found

    cand = []
    for i in A0:
        r = by_id[i]; d = det.get(i, {})
        reasons_review = []
        if i in listed: reasons_review.append("listee_dans_l_API_publique")
        if r["validation_status"] in PUBLIC_VALIDATION: reasons_review.append("validation_publique:" + r["validation_status"])
        for t, blocking in REF_TABLES:
            n = refs[t].get(i, 0)
            if n and blocking: reasons_review.append(f"reference:{t}={n}")
        if d.get("device_type") in CALL_LIKE_TYPES: reasons_review.append("type_ressemblant_a_un_appel:" + str(d["device_type"]))
        if i in dup_out: reasons_review.append("doublon_hors_lot:" + ",".join(dup_out[i][:2]))
        if d.get("recurring"): reasons_review.append("recurrente")
        soft = all(x.split(":")[0] in ("validation_publique", "type_ressemblant_a_un_appel") for x in reasons_review)
        category = "A_CERTAINE" if not reasons_review else ("A_VALIDEE_PROPRIETAIRE" if (i in validated and soft) else "A_REVUE_HUMAINE")
        cand.append(dict(id=i, category=category, rule=rules.get(i, ""), source=r.get("source_name") or "",
                         title=(r["title"] or "")[:90], status=r["status"], validation=r["validation_status"],
                         device_type=d.get("device_type"), close_date=d.get("close_date"), listed_api=i in listed,
                         refs_blocking=sum(refs[t].get(i, 0) for t, b in REF_TABLES if b),
                         journal=refs["device_archive_log"].get(i, 0), ai=d.get("ai"), source_url=d.get("source_url"),
                         reasons="; ".join(reasons_review)))
    certain = sorted(c["id"] for c in cand if c["category"] == "A_CERTAINE")
    review = [c for c in cand if c["category"] == "A_REVUE_HUMAINE"]
    owner_ok = [c for c in cand if c["category"] == "A_VALIDEE_PROPRIETAIRE"]

    # exclusions : manuelles + lot Q + protegees
    excluded = []
    for i, why in manual.items():
        r = by_id.get(i)
        excluded.append(dict(id=i, motif="exclusion_proprietaire", detail=why or "verification documentaire en attente",
                             title=(r["title"] if r else "(absente)")[:80], status=r["status"] if r else "", validation=r["validation_status"] if r else ""))
    for i in Q0:
        if i in manual: continue
        r = by_id[i]
        excluded.append(dict(id=i, motif="lot_Q_reference_externe", detail=rules.get(i, ""), title=(r["title"] or "")[:80],
                             status=r["status"], validation=r["validation_status"]))

    # protect_for_apply : un apply avec ce fichier n'archive QUE les certaines (les fiches a revoir passent en lot Q)
    prot2 = sorted(base | set(manual) | {c["id"] for c in review})
    (OUT / "protect_for_apply_with_owner_validated.txt").write_text("\n".join(prot2) + "\n", encoding="utf-8")
    prot = sorted(base | set(manual) | {c["id"] for c in review} | {c["id"] for c in owner_ok})
    (OUT / "protect_for_apply.txt").write_text("\n".join(prot) + "\n", encoding="utf-8")
    async with AsyncSessionLocal() as db:
        plan1 = build_plan(await load_rows(db), set(prot))
        A1 = [str(i) for i in plan1.ids(BATCH_A)]
        fp_full = plan1.fingerprint(BATCH_A)
        plan2 = build_plan(await load_rows(db), set(prot2))
        A2 = [str(i) for i in plan2.ids(BATCH_A)]; fp2 = plan2.fingerprint(BATCH_A)
        dry = await archive_batch(db, plan1, BATCH_A, run_id="SIMULATION", expected_hash=fp_full, dry_run=True, limit=SUBLOT)
        dry_full = await archive_batch(db, plan1, BATCH_A, run_id="SIMULATION", expected_hash=fp_full, dry_run=True)
    sub = A1[:SUBLOT]
    (OUT / "lotA_certain_ids.txt").write_text("\n".join(certain) + "\n", encoding="utf-8")
    (OUT / "lotA_first_sublot_ids.txt").write_text("\n".join(sub) + "\n", encoding="utf-8")
    for name, data, fields in (("lotA_candidates.csv", cand, list(cand[0].keys())),
                               ("lotA_review.csv", review, list(cand[0].keys())),
                               ("lotA_excluded.csv", excluded, ["id", "motif", "detail", "title", "status", "validation"])):
        with open(OUT / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(data)

    cnt = collections.Counter
    summary = dict(
        total_fiches=len(rows), candidates_A=len(A0), certaines=len(certain), validees_proprietaire=len(owner_ok), revue_humaine=len(review),
        apply_avec_validees=len(A2), empreinte_apply_avec_validees=fp2,
        apply_avec_validees_egal_certaines_plus_validees=sorted(A2) == sorted(certain + [c["id"] for c in owner_ok]),
        validees_ids=[c["id"] for c in owner_ok],
        exclusions_proprietaire=len(manual), lot_Q=len(Q0),
        apply_lotA_apres_exclusion=len(A1), empreinte_lotA_apply=fp_full, apply_equals_certain=sorted(A1) == certain,
        simulation_apply_planned_full=dry_full.planned, simulation_apply_planned_sublot=dry.planned,
        par_statut=dict(cnt(c["status"] for c in cand)), par_validation=dict(cnt(c["validation"] for c in cand)),
        par_regle=dict(cnt(c["rule"] for c in cand)), par_source=dict(cnt(c["source"] for c in cand).most_common(12)),
        par_type=dict(cnt(str(c["device_type"]) for c in cand)),
        raisons_revue=dict(cnt(r.split(":")[0].split("=")[0] for c in review for r in c["reasons"].split("; ") if r)),
        certaines_par_statut=dict(cnt(c["status"] for c in cand if c["category"] == "A_CERTAINE")),
        certaines_deja_journalisees_ai_hold=sum(1 for c in cand if c["category"] == "A_CERTAINE" and c["journal"]),
        certaines_listees_api=sum(1 for c in cand if c["category"] == "A_CERTAINE" and c["listed_api"]),
        sublot_par_statut=dict(cnt(by_id[i]["status"] for i in sub)),
        sublot_listees_api=sum(1 for i in sub if i in listed),
        manuelles_presentes_dans_A=[i for i in manual if i in set(A0)],
        manuelles_dans_Q=[i for i in manual if i in set(Q0)],
        a_publiques_aujourdhui_listees=[c["id"] for c in cand if c["listed_api"]],
    )
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=str))

asyncio.run(main())
