import asyncio
import json

from sqlalchemy import text

from app.database import AsyncSessionLocal


AFRICA_COUNTRIES = (
    "Afrique",
    "Afrique du Sud",
    "South Africa",
    "Benin",
    "Bénin",
    "Burkina Faso",
    "Cameroun",
    "Cameroon",
    "Ghana",
    "Guinee",
    "Guinée",
    "Kenya",
    "Madagascar",
    "Mali",
    "Maroc",
    "Morocco",
    "Mauritanie",
    "Niger",
    "Rwanda",
    "Senegal",
    "Sénégal",
    "Togo",
    "Tunisie",
    "Tunisia",
    "Ethiopie",
    "Ethiopia",
    "Nigeria",
    "Ouganda",
    "Uganda",
    "Tanzanie",
    "Tanzania",
    "Zambie",
    "Zambia",
    "International",
)


def _quality_flags(row: dict) -> list[str]:
    flags: list[str] = []
    if len(row.get("short_description") or "") < 140:
        flags.append("resume_court")
    if len(row.get("eligibility") or "") < 80:
        flags.append("criteres_faibles")
    if not row.get("funding"):
        flags.append("montant_absent")
    if not row.get("source_url"):
        flags.append("source_absente")
    if not row.get("close_date") and row.get("status") not in {"recurring", "standby"}:
        flags.append("date_ambigue")
    title = (row.get("title") or "").lower()
    if any(marker in title for marker in ["funding opportunity", "call for applications", "opens "]):
        flags.append("titre_anglais")
    return flags


async def main() -> None:
    async with AsyncSessionLocal() as session:
        query = text(
            """
            SELECT
                d.id::text,
                d.title,
                d.organism,
                d.country,
                d.device_type,
                d.status,
                d.close_date::text,
                COALESCE(d.amount_max::text, '') AS amount_max,
                LEFT(COALESCE(d.short_description, ''), 260) AS short_description,
                LEFT(COALESCE(d.eligibility_criteria, ''), 220) AS eligibility,
                LEFT(COALESCE(d.funding_details, ''), 220) AS funding,
                d.source_url,
                COALESCE(src.name, '') AS source_name
            FROM devices d
            LEFT JOIN sources src ON src.id = d.source_id
            WHERE d.validation_status != 'rejected'
              AND d.status IN ('open', 'recurring', 'standby')
              AND (
                d.country = ANY(:countries)
                OR COALESCE(d.zone, '') ILIKE '%afrique%'
                OR COALESCE(d.geographic_scope, '') ILIKE '%afrique%'
                OR COALESCE(src.name, '') ILIKE ANY(ARRAY[
                    '%Africa%', '%Afrique%', '%AECF%', '%AWDF%', '%Orange Corners%',
                    '%Villgro%', '%TLcom%', '%Janngo%', '%I&P%', '%Global South%'
                ])
              )
            ORDER BY
              CASE
                WHEN d.close_date IS NOT NULL AND d.close_date >= CURRENT_DATE THEN 0
                WHEN d.status = 'recurring' THEN 1
                ELSE 2
              END,
              d.close_date NULLS LAST,
              d.updated_at DESC
            LIMIT 30
            """
        )
        rows = (await session.execute(query, {"countries": list(AFRICA_COUNTRIES)})).mappings().all()
        payload = []
        for row in rows:
            item = dict(row)
            item["quality_flags"] = _quality_flags(item)
            item["premium_ready"] = len(item["quality_flags"]) == 0
            payload.append(item)

        summary = {
            "sample_size": len(payload),
            "premium_ready": sum(1 for item in payload if item["premium_ready"]),
            "needs_review": sum(1 for item in payload if not item["premium_ready"]),
            "flags": {},
        }
        for item in payload:
            for flag in item["quality_flags"]:
                summary["flags"][flag] = summary["flags"].get(flag, 0) + 1

        print(json.dumps({"summary": summary, "items": payload}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
