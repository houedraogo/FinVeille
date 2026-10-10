"""Nettoyage réversible du catalogue : plan, archivage par lots, restauration.

Principes (décidés avec le propriétaire du produit, octobre 2026)
-----------------------------------------------------------------
* AUCUNE suppression physique : une fiche archivée garde son identifiant
  (les références externes — dossiers clients Finnovatix via ``kafundo_id``,
  favoris, pipelines — restent valides) ; seule sa visibilité change.
* Chaque fiche touchée est journalisée dans ``device_archive_log`` avec ses
  anciennes valeurs : la restauration est exacte, par lot ou par fiche.
* Les lots archivables sont limités à A (fiches projet institutionnelles),
  B (expirées non récurrentes) et C (doublons CERTAINS). Les lots F (admin
  uniquement récupérables), H (en revue) et les doublons PROBABLES sont
  des listes de revue : jamais archivés automatiquement.
* ``plan`` est en lecture seule et produit une empreinte (hash) du lot ;
  ``apply`` refuse de s'exécuter si l'empreinte attendue ne correspond plus
  (la base a changé depuis la validation du plan).
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog_cleanup import AI_HELD_STATUS, ARCHIVED_STATUS, DeviceArchiveLog
from app.models.device import Device
from app.models.source import Source
from app.services.device_identity import DuplicateIndex, DuplicateTier, title_key
from app.services.scope_rules import evaluate_scope

BATCH_A = "A_projets_institutionnels"
BATCH_B = "B_expirees_non_recurrentes"
BATCH_C = "C_doublons_certains"
BATCH_F = "F_admin_only_a_recuperer"
BATCH_H = "H_pending_review"
BATCH_G = "G_deja_rejetees"
BATCH_Z = "Z_reste"
ARCHIVABLE_BATCHES = (BATCH_A, BATCH_B, BATCH_C)
REVIEW_BATCHES = (BATCH_F, BATCH_H)
# Lots dont les réécritures IA en attente sont suspendues (jamais de dépense avant validation).
AI_HOLD_BATCHES = (BATCH_A, BATCH_B, BATCH_C, BATCH_F, BATCH_H, BATCH_G)

PUBLIC_VALIDATION = ("auto_published", "approved", "validated", "manually_published")
CHUNK_SIZE = 200


@dataclass
class Plan:
    batches: dict[str, list[Any]] = field(default_factory=lambda: defaultdict(list))
    merged_into: dict[Any, Any] = field(default_factory=dict)       # doublon -> fiche conservée
    rules: dict[Any, str] = field(default_factory=dict)             # fiche -> règle / motif
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def ids(self, batch: str) -> list[Any]:
        return sorted(self.batches.get(batch, []), key=str)

    def counts(self) -> dict[str, int]:
        return {batch: len(ids) for batch, ids in sorted(self.batches.items())}

    def fingerprint(self, batch: str) -> str:
        payload = json.dumps([str(i) for i in self.ids(batch)])
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _keeper_sort_key(row: dict):
    """Fiche conservée dans un groupe de doublons : publique d'abord, plus complète, plus ancienne."""
    is_public = row.get("validation_status") in PUBLIC_VALIDATION
    created = row.get("created_at")
    return (not is_public, -(row.get("completeness_score") or 0), created or datetime.max.replace(tzinfo=timezone.utc), str(row["id"]))


def build_plan(rows: Iterable[dict]) -> Plan:
    """Classe chaque fiche dans exactement un lot (priorité A > G > B > C > H > F > Z). Pur."""
    plan = Plan()
    rows = [dict(r) for r in rows if r.get("validation_status") != ARCHIVED_STATUS]
    taken: set = set()

    for row in rows:
        decision = evaluate_scope(row, row.get("source_name"))
        if decision.excluded:
            plan.batches[BATCH_A].append(row["id"])
            plan.rules[row["id"]] = decision.rule or "scope"
            taken.add(row["id"])

    for row in rows:
        if row["id"] in taken:
            continue
        if row.get("validation_status") == "rejected":
            plan.batches[BATCH_G].append(row["id"])
            taken.add(row["id"])

    for row in rows:
        if row["id"] in taken:
            continue
        recurring = bool(row.get("is_recurring")) or row.get("status") == "recurring"
        if row.get("status") in ("expired", "closed") and not recurring:
            plan.batches[BATCH_B].append(row["id"])
            plan.rules[row["id"]] = f"status_{row.get('status')}_non_recurrent"
            taken.add(row["id"])

    remaining = [r for r in rows if r["id"] not in taken]
    index = DuplicateIndex(remaining)
    parent: dict = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for row in remaining:
        for other, assessment in index.assess(row):
            if assessment.tier is DuplicateTier.CERTAIN:
                parent[find(row["id"])] = find(other["id"])
    clusters: dict = defaultdict(list)
    by_id = {r["id"]: r for r in remaining}
    for row_id in list(parent):
        clusters[find(row_id)].append(by_id[row_id])
    for members in clusters.values():
        if len(members) < 2:
            continue
        keeper = sorted(members, key=_keeper_sort_key)[0]
        for member in members:
            if member["id"] == keeper["id"]:
                continue
            plan.batches[BATCH_C].append(member["id"])
            plan.merged_into[member["id"]] = keeper["id"]
            plan.rules[member["id"]] = "certain_duplicate"
            taken.add(member["id"])

    for row in rows:
        if row["id"] in taken:
            continue
        if row.get("validation_status") == "pending_review":
            plan.batches[BATCH_H].append(row["id"])
        elif row.get("validation_status") == "admin_only" or row.get("user_quality_decision") == "admin_only":
            plan.batches[BATCH_F].append(row["id"])
        else:
            plan.batches[BATCH_Z].append(row["id"])
    return plan


async def load_rows(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(
            Device.id, Device.title, Device.organism, Device.country, Device.source_url, Device.source_id,
            Device.validation_status, Device.status, Device.is_recurring, Device.user_quality_decision,
            Device.ai_rewrite_status, Device.completeness_score, Device.created_at, Source.name,
        ).outerjoin(Source, Source.id == Device.source_id)
    )
    columns = ["id", "title", "organism", "country", "source_url", "source_id", "validation_status", "status",
               "is_recurring", "user_quality_decision", "ai_rewrite_status", "completeness_score", "created_at", "source_name"]
    return [dict(zip(columns, row)) for row in result.all()]


async def plan_catalog(db: AsyncSession) -> Plan:
    return build_plan(await load_rows(db))


# --- références utilisateur ---------------------------------------------------

_REFERENCE_MOVES = (
    # table, clé qui ne doit pas se retrouver en double chez la fiche conservée
    ("favorite_devices", "user_id"),
    ("device_pipeline", "user_id"),
)


async def _move_user_references(db: AsyncSession, duplicate_id, keeper_id) -> dict[str, list[str]]:
    """Déplace favoris/pipelines vers la fiche conservée quand aucun conflit n'existe.

    Les références en conflit restent sur la fiche archivée (rien n'est perdu).
    Renvoie {table: [clés déplacées]} pour permettre la restauration.
    """
    moved: dict[str, list[str]] = {}
    for table, key in _REFERENCE_MOVES:
        rows = (await db.execute(text(
            f"SELECT {key} FROM {table} t WHERE t.device_id = :dup AND NOT EXISTS "
            f"(SELECT 1 FROM {table} k WHERE k.device_id = :keeper AND k.{key} = t.{key})"
        ), {"dup": str(duplicate_id), "keeper": str(keeper_id)})).scalars().all()
        for value in rows:
            await db.execute(text(
                f"UPDATE {table} SET device_id = :keeper WHERE device_id = :dup AND {key} = :value"
            ), {"dup": str(duplicate_id), "keeper": str(keeper_id), "value": str(value)})
        if rows:
            moved[table] = [str(v) for v in rows]
    return moved


async def _restore_user_references(db: AsyncSession, duplicate_id, keeper_id, moved: dict[str, list[str]]) -> None:
    for table, key in _REFERENCE_MOVES:
        for value in moved.get(table, []):
            await db.execute(text(
                f"UPDATE {table} SET device_id = :dup WHERE device_id = :keeper AND {key} = :value"
            ), {"dup": str(duplicate_id), "keeper": str(keeper_id), "value": str(value)})


# --- application ------------------------------------------------------------------

@dataclass
class ApplyResult:
    batch: str
    run_id: str
    dry_run: bool
    planned: int
    archived: int = 0
    ai_held: int = 0
    refs_moved: int = 0
    skipped: list[str] = field(default_factory=list)


class PlanMismatch(RuntimeError):
    """Le contenu du lot ne correspond plus à l'empreinte validée."""


async def archive_batch(
    db: AsyncSession, plan: Plan, batch: str, *, run_id: str, expected_hash: Optional[str],
    dry_run: bool = True, limit: Optional[int] = None,
) -> ApplyResult:
    if batch not in ARCHIVABLE_BATCHES:
        raise ValueError(f"Le lot {batch} n'est pas archivable automatiquement (lots autorisés: {ARCHIVABLE_BATCHES})")
    if expected_hash is None or expected_hash != plan.fingerprint(batch):
        raise PlanMismatch(f"Empreinte du lot {batch} inattendue: attendu {expected_hash}, calculé {plan.fingerprint(batch)}")
    ids = plan.ids(batch)
    selected = ids[:limit] if limit else ids
    result = ApplyResult(batch=batch, run_id=run_id, dry_run=dry_run, planned=len(selected))
    if dry_run:
        return result

    for start in range(0, len(selected), CHUNK_SIZE):
        chunk = selected[start:start + CHUNK_SIZE]
        devices = (await db.execute(select(Device).where(Device.id.in_(chunk)).with_for_update())).scalars().all()
        for device in devices:
            if device.validation_status == ARCHIVED_STATUS:
                result.skipped.append(f"{device.id}:deja_archivee")
                continue
            keeper_id = plan.merged_into.get(device.id)
            moved = await _move_user_references(db, device.id, keeper_id) if keeper_id else None
            if moved:
                result.refs_moved += sum(len(v) for v in moved.values())
            db.add(DeviceArchiveLog(
                run_id=run_id, batch=batch, device_id=device.id, action="archive",
                rule=plan.rules.get(device.id), reason=f"Nettoyage catalogue {batch}",
                merged_into_id=keeper_id,
                previous_validation_status=device.validation_status, previous_status=device.status,
                previous_user_quality_decision=device.user_quality_decision,
                previous_ai_rewrite_status=device.ai_rewrite_status,
                previous_tags=list(device.tags or []), moved_references=moved or None,
            ))
            device.validation_status = ARCHIVED_STATUS
            if device.ai_rewrite_status in (None, "pending", "failed", "needs_review"):
                device.ai_rewrite_status = AI_HELD_STATUS
                result.ai_held += 1
            device.tags = sorted(set(device.tags or []) | {f"archive:{batch}:{run_id}"})
            result.archived += 1
        await db.flush()
    await db.commit()
    return result


async def hold_pending_ai(
    db: AsyncSession, plan: Plan, *, run_id: str, dry_run: bool = True, batches: Iterable[str] = AI_HOLD_BATCHES,
) -> ApplyResult:
    """Suspend les réécritures IA EN ATTENTE des lots à examiner / à archiver (réversible)."""
    ids: list[Any] = []
    for batch in batches:
        ids.extend(plan.ids(batch))
    result = ApplyResult(batch="AI_HOLD", run_id=run_id, dry_run=dry_run, planned=0)
    for start in range(0, len(ids), CHUNK_SIZE):
        chunk = ids[start:start + CHUNK_SIZE]
        devices = (await db.execute(
            select(Device).where(Device.id.in_(chunk), Device.ai_rewrite_status.in_(("pending", "failed", "needs_review"))).with_for_update()
        )).scalars().all()
        result.planned += len(devices)
        if dry_run:
            continue
        for device in devices:
            db.add(DeviceArchiveLog(
                run_id=run_id, batch="AI_HOLD", device_id=device.id, action="ai_hold", reason="Suspension IA avant validation",
                previous_validation_status=device.validation_status, previous_status=device.status,
                previous_user_quality_decision=device.user_quality_decision,
                previous_ai_rewrite_status=device.ai_rewrite_status, previous_tags=list(device.tags or []),
            ))
            device.ai_rewrite_status = AI_HELD_STATUS
            result.ai_held += 1
        await db.flush()
    if not dry_run:
        await db.commit()
    return result


async def restore(
    db: AsyncSession, *, run_id: str, batch: Optional[str] = None, device_ids: Optional[list[str]] = None, dry_run: bool = True,
) -> dict[str, int]:
    """Remet les anciennes valeurs journalisées (exactes) et marque les entrées restaurées."""
    query = select(DeviceArchiveLog).where(DeviceArchiveLog.run_id == run_id, DeviceArchiveLog.restored_at.is_(None))
    if batch:
        query = query.where(DeviceArchiveLog.batch == batch)
    if device_ids:
        query = query.where(DeviceArchiveLog.device_id.in_([UUID(str(d)) for d in device_ids]))
    entries = (await db.execute(query.with_for_update())).scalars().all()
    stats = {"entries": len(entries), "restored": 0, "refs_restored": 0}
    if dry_run:
        return stats
    for entry in entries:
        device = (await db.execute(select(Device).where(Device.id == entry.device_id).with_for_update())).scalar_one_or_none()
        if device is None:
            continue
        if entry.action == "archive":
            device.validation_status = entry.previous_validation_status
            device.status = entry.previous_status
            device.user_quality_decision = entry.previous_user_quality_decision
            device.tags = list(entry.previous_tags or [])
            if entry.moved_references and entry.merged_into_id:
                await _restore_user_references(db, device.id, entry.merged_into_id, entry.moved_references)
                stats["refs_restored"] += sum(len(v) for v in entry.moved_references.values())
        device.ai_rewrite_status = entry.previous_ai_rewrite_status
        entry.restored_at = datetime.now(timezone.utc)
        stats["restored"] += 1
    await db.commit()
    return stats


def summarize(plan: Plan, rows: list[dict]) -> dict[str, Any]:
    """Résumé lisible : volumes par lot, par validation, hash d'empreinte."""
    by_id = {r["id"]: r for r in rows}
    summary: dict[str, Any] = {}
    for batch, ids in sorted(plan.batches.items()):
        summary[batch] = {
            "count": len(ids),
            "fingerprint": plan.fingerprint(batch),
            "by_validation": dict(Counter(by_id[i]["validation_status"] for i in ids if i in by_id)),
            "by_status": dict(Counter(by_id[i]["status"] for i in ids if i in by_id)),
            "ai_pending": sum(1 for i in ids if by_id.get(i, {}).get("ai_rewrite_status") == "pending"),
        }
    return summary
