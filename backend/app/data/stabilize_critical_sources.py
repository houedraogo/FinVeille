"""
Stabilise les sources critiques et rattache les fiches orphelines.

Usage:
    docker exec kafundo-backend python -m app.data.stabilize_critical_sources
    docker exec kafundo-backend python -m app.data.stabilize_critical_sources --apply
"""
import argparse
import asyncio
import json
import uuid
from typing import Any

from sqlalchemy import text

from app.database import AsyncSessionLocal


GSO_CONFIG = {
    "source_kind": "editorial_funding",
    "allow_english_text": True,
    "assume_standby_without_close_date": True,
    "close_date_fields": ["deadline", "application_deadline"],
    "status_fields": ["status"],
}


async def _ensure_source(
    db,
    *,
    name: str,
    organism: str,
    country: str,
    url: str,
    source_type: str = "autre",
    collection_mode: str = "manual",
    category: str = "public",
    level: int = 3,
    reliability: int = 2,
    is_active: bool = False,
    notes: str | None = None,
    config: dict[str, Any] | None = None,
) -> str:
    existing = (
        await db.execute(text("SELECT id FROM sources WHERE name = :name"), {"name": name})
    ).scalar()
    if existing:
        return str(existing)

    source_id = str(uuid.uuid4())
    await db.execute(
        text(
            """
            INSERT INTO sources (
                id, name, organism, country, source_type, level, url,
                collection_mode, check_frequency, reliability, category,
                is_active, consecutive_errors, config, notes
            )
            VALUES (
                :id, :name, :organism, :country, :source_type, :level, :url,
                :collection_mode, 'monthly', :reliability, :category,
                :is_active, 0, CAST(:config AS jsonb), :notes
            )
            """
        ),
        {
            "id": source_id,
            "name": name,
            "organism": organism,
            "country": country,
            "source_type": source_type,
            "level": level,
            "url": url,
            "collection_mode": collection_mode,
            "reliability": reliability,
            "category": category,
            "is_active": is_active,
            "config": json.dumps(config or {}),
            "notes": notes,
        },
    )
    return source_id


async def _source_id(db, name: str) -> str | None:
    value = (await db.execute(text("SELECT id FROM sources WHERE name = :name"), {"name": name})).scalar()
    return str(value) if value else None


async def _update(db, sql: str, params: dict[str, Any]) -> int:
    result = await db.execute(text(sql), params)
    return int(result.rowcount or 0)


async def run(*, apply: bool = False) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        stats: dict[str, Any] = {
            "sources_configured": 0,
            "gso_unknown_deadline_fixed": 0,
            "orphans_attached": {},
            "remaining_orphans": 0,
        }

        manual_source_id = await _ensure_source(
            db,
            name="Import manuel / historique",
            organism="Kafundo",
            country="International",
            url="https://kafundo.local/manual-import",
            source_type="autre",
            collection_mode="manual",
            category="public",
            level=3,
            reliability=2,
            is_active=False,
            notes=(
                "Source technique utilisee pour rattacher les fiches importees "
                "historiquement ou qualifiees manuellement, en attendant une source "
                "collectable dediee."
            ),
            config={"source_kind": "manual_import"},
        )
        google_source_id = await _ensure_source(
            db,
            name="Google for Startups - programmes Afrique",
            organism="Google for Startups",
            country="Afrique",
            url="https://startup.google.com/",
            source_type="fonds_prive",
            collection_mode="manual",
            category="private",
            level=2,
            reliability=3,
            is_active=False,
            notes="Source manuelle pour les programmes Google for Startups, a qualifier avant automatisation.",
            config={"source_kind": "single_program_page"},
        )
        cnc_source_id = await _ensure_source(
            db,
            name="CNC - aides et financements",
            organism="CNC",
            country="France",
            url="https://www.cnc.fr/professionnels/aides-et-financements",
            source_type="agence_nationale",
            collection_mode="manual",
            category="public",
            level=2,
            reliability=3,
            is_active=False,
            notes="Source manuelle creee pour rattacher les fiches CNC historiques.",
            config={"source_kind": "listing"},
        )
        idf_source_id = await _ensure_source(
            db,
            name="Region Ile-de-France - aides et appels",
            organism="Region Ile-de-France",
            country="France",
            url="https://www.iledefrance.fr/aides-et-appels-a-projets",
            source_type="institution_regionale",
            collection_mode="manual",
            category="public",
            level=2,
            reliability=3,
            is_active=False,
            notes="Source manuelle creee pour rattacher les fiches Ile-de-France historiques.",
            config={"source_kind": "listing"},
        )
        afdb_source_id = await _ensure_source(
            db,
            name="Banque Africaine de Developpement - opportunites",
            organism="Banque Africaine de Developpement",
            country="Afrique",
            url="https://www.afdb.org/",
            source_type="institution_regionale",
            collection_mode="manual",
            category="public",
            level=2,
            reliability=3,
            is_active=False,
            notes="Source manuelle creee pour rattacher les fiches BAD historiques.",
            config={"source_kind": "institutional_project"},
        )

        stats["sources_configured"] = 5

        stats["sources_configured"] += await _update(
            db,
            """
            UPDATE sources
            SET
                config = CAST(:config AS jsonb),
                notes = :notes,
                reliability = 3,
                updated_at = now()
            WHERE name = 'Global South Opportunities - Funding'
            """,
            {
                "config": json.dumps(GSO_CONFIG),
                "notes": (
                    "Flux RSS WordPress de la categorie Funding. Source relais/agregateur : "
                    "les fiches sans date limite explicite sont publiees en standby/pending_review "
                    "et doivent etre confirmees sur la source officielle."
                ),
            },
        )

        stats["sources_configured"] += await _update(
            db,
            """
            UPDATE sources
            SET
                is_active = false,
                config = CAST(COALESCE(config, '{}'::json)::jsonb || CAST(:config_patch AS jsonb) AS json),
                notes = :notes,
                updated_at = now()
            WHERE name = 'les-aides.fr - solutions de financement entreprises'
            """,
            {
                "config_patch": json.dumps({"assume_standby_without_close_date": True}),
                "notes": (
                    "Source critique conservee mais desactivee apres erreurs consecutives. "
                    "A reparer via test API/cle IDC ou remplacer par un connecteur fiable avant "
                    "reactivation. Les fiches existantes restent utilisables en stock historique."
                ),
            },
        )

        stats["gso_unknown_deadline_fixed"] = await _update(
            db,
            """
            UPDATE devices
            SET
                status = 'standby',
                is_recurring = false,
                validation_status = 'pending_review',
                recurrence_notes = COALESCE(
                    recurrence_notes,
                    'Date limite non communiquee par Global South Opportunities: verifier la source officielle avant publication.'
                ),
                tags = ARRAY(
                    SELECT DISTINCT value
                    FROM unnest(COALESCE(tags, ARRAY[]::text[]) || ARRAY['quality:unknown_deadline', 'source:aggregator']) AS value
                ),
                updated_at = now()
            WHERE organism = 'Global South Opportunities'
              AND status = 'open'
              AND close_date IS NULL
              AND validation_status != 'rejected'
            """,
            {},
        )

        attachment_rules: list[tuple[str, str | None, str, dict[str, Any]]] = []

        afd_source_id = await _source_id(db, "AFD - concours et appels a projets")
        bpi_source_id = await _source_id(db, "Bpifrance - appels a projets et concours")
        if afd_source_id:
            attachment_rules.append(("afd", afd_source_id, "source_url ILIKE '%afd.fr%'", {}))
        if bpi_source_id:
            attachment_rules.append(("bpifrance", bpi_source_id, "source_url ILIKE '%bpifrance%'", {}))
        attachment_rules.extend(
            [
                ("cnc", cnc_source_id, "source_url ILIKE '%cnc.fr%' OR organism = 'CNC'", {}),
                ("ile_de_france", idf_source_id, "source_url ILIKE '%iledefrance.fr%' OR organism ILIKE '%Ile-de-France%' OR organism ILIKE '%Île-de-France%'", {}),
                ("afdb", afdb_source_id, "source_url ILIKE '%afdb.org%' OR organism ILIKE '%Africaine de D%veloppement%'", {}),
                ("google_for_startups", google_source_id, "source_url ILIKE '%startup.google.com%'", {}),
            ]
        )

        for label, source_id, condition, params in attachment_rules:
            if not source_id:
                continue
            stats["orphans_attached"][label] = await _update(
                db,
                f"""
                UPDATE devices
                SET source_id = :source_id, updated_at = now()
                WHERE source_id IS NULL
                  AND ({condition})
                """,
                {"source_id": source_id, **params},
            )

        world_bank_sources = {
            "Maroc": await _source_id(db, "Banque Mondiale - projets Maroc"),
            "Tunisie": await _source_id(db, "Banque Mondiale - projets Tunisie"),
            "Mali": await _source_id(db, "Banque Mondiale - projets Mali"),
            "Côte d'Ivoire": await _source_id(db, "Banque Mondiale - projets Cote d'Ivoire"),
        }
        for country, source_id in world_bank_sources.items():
            if not source_id:
                continue
            stats["orphans_attached"][f"world_bank_{country}"] = await _update(
                db,
                """
                UPDATE devices
                SET source_id = :source_id, updated_at = now()
                WHERE source_id IS NULL
                  AND organism = 'World Bank Group'
                  AND country = :country
                """,
                {"source_id": source_id, "country": country},
            )

        stats["orphans_attached"]["manual_import_remaining"] = await _update(
            db,
            """
            UPDATE devices
            SET
                source_id = :source_id,
                validation_status = CASE
                    WHEN validation_status = 'auto_published' THEN 'pending_review'
                    ELSE validation_status
                END,
                tags = ARRAY(
                    SELECT DISTINCT value
                    FROM unnest(COALESCE(tags, ARRAY[]::text[]) || ARRAY['source:manual_import']) AS value
                ),
                updated_at = now()
            WHERE source_id IS NULL
            """,
            {"source_id": manual_source_id},
        )

        stats["remaining_orphans"] = int(
            (
                await db.execute(text("SELECT count(*) FROM devices WHERE source_id IS NULL"))
            ).scalar()
            or 0
        )

        if apply:
            await db.commit()
        else:
            await db.rollback()

        stats["dry_run"] = not apply
        return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Stabilise les sources critiques Kafundo.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
