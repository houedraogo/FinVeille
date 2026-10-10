"""Nettoyage réversible du catalogue — outil en ligne de commande.

Toutes les commandes écrivent QUELQUE CHOSE seulement avec --yes ; sans --yes elles
simulent (apply, hold-ai, restore, quality). ``plan`` est toujours en lecture seule.

    python -m app.data.catalog_cleanup plan [--out DIR]
    python -m app.data.catalog_cleanup apply --batch A_projets_institutionnels --plan-hash H \
        --run-id RUN --backup-ref pre_cleanup_xxx.dump [--limit N] [--yes]
    python -m app.data.catalog_cleanup hold-ai --run-id RUN [--yes]
    python -m app.data.catalog_cleanup restore --run-id RUN [--batch B] [--device-id ID ...] [--yes]
    python -m app.data.catalog_cleanup quality [--limit N] [--yes]

Aucune suppression physique : voir app.services.catalog_cleanup.
"""
import argparse
import asyncio
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.database import AsyncSessionLocal
from app.services.catalog_cleanup import (
    ARCHIVABLE_BATCHES,
    PlanMismatch,
    archive_batch,
    build_plan,
    hold_pending_ai,
    load_rows,
    restore,
    summarize,
)
from app.services.catalog_quality import evaluate_unrated


def _write_manifests(out_dir: Path, plan, rows) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    by_id = {r["id"]: r for r in rows}
    for batch, ids in plan.batches.items():
        with open(out_dir / f"{batch}.csv", "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["id", "title", "source", "validation_status", "status", "merged_into", "rule"])
            for device_id in plan.ids(batch):
                row = by_id.get(device_id, {})
                writer.writerow([device_id, row.get("title"), row.get("source_name"), row.get("validation_status"),
                                 row.get("status"), plan.merged_into.get(device_id), plan.rules.get(device_id)])


def _protected_ids(args) -> set:
    """Identifiants (un par ligne) de fiches référencées par un système externe, à ne pas archiver."""
    path = getattr(args, "protect_file", None)
    if not path:
        return set()
    return {line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()}


async def run(args) -> int:
    protected = _protected_ids(args)
    async with AsyncSessionLocal() as db:
        if args.command == "plan":
            rows = await load_rows(db)
            plan = build_plan(rows, protected)
            summary = summarize(plan, rows)
            if args.out:
                _write_manifests(Path(args.out), plan, rows)
                (Path(args.out) / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
            print(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "total": len(rows), "batches": summary}, indent=2, default=str))
            return 0

        if args.command == "apply":
            if args.batch not in ARCHIVABLE_BATCHES:
                print(f"Lot non archivable automatiquement: {args.batch} (autorisés: {', '.join(ARCHIVABLE_BATCHES)})", file=sys.stderr)
                return 2
            if args.yes and not args.backup_ref:
                print("--backup-ref est obligatoire pour écrire (nom du dump vérifié avant l'opération).", file=sys.stderr)
                return 2
            plan = build_plan(await load_rows(db), protected)
            try:
                result = await archive_batch(db, plan, args.batch, run_id=args.run_id, expected_hash=args.plan_hash,
                                             dry_run=not args.yes, limit=args.limit)
            except PlanMismatch as exc:
                print(f"ARRÊT: {exc}", file=sys.stderr)
                return 3
            print(json.dumps(result.__dict__, indent=2, default=str))
            return 0

        if args.command == "hold-ai":
            plan = build_plan(await load_rows(db), protected)
            result = await hold_pending_ai(db, plan, run_id=args.run_id, dry_run=not args.yes)
            print(json.dumps(result.__dict__, indent=2, default=str))
            return 0

        if args.command == "restore":
            stats = await restore(db, run_id=args.run_id, batch=args.batch, device_ids=args.device_id, dry_run=not args.yes)
            print(json.dumps({"dry_run": not args.yes, **stats}, indent=2))
            return 0

        if args.command == "quality":
            report = await evaluate_unrated(db, limit=args.limit, apply=args.yes)
            print(json.dumps(report, indent=2, default=str))
            return 0
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--out")
    plan_parser.add_argument("--protect-file")

    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("--batch", required=True)
    apply_parser.add_argument("--plan-hash", required=True)
    apply_parser.add_argument("--run-id", required=True)
    apply_parser.add_argument("--backup-ref")
    apply_parser.add_argument("--limit", type=int)
    apply_parser.add_argument("--yes", action="store_true")
    apply_parser.add_argument("--protect-file")

    hold_parser = sub.add_parser("hold-ai")
    hold_parser.add_argument("--run-id", required=True)
    hold_parser.add_argument("--yes", action="store_true")
    hold_parser.add_argument("--protect-file")

    restore_parser = sub.add_parser("restore")
    restore_parser.add_argument("--run-id", required=True)
    restore_parser.add_argument("--batch")
    restore_parser.add_argument("--device-id", action="append")
    restore_parser.add_argument("--yes", action="store_true")

    quality_parser = sub.add_parser("quality")
    quality_parser.add_argument("--limit", type=int, default=200)
    quality_parser.add_argument("--yes", action="store_true")

    return asyncio.run(run(parser.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
