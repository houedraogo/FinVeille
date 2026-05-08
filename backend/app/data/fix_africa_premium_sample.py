import asyncio

from sqlalchemy import text

from app.database import AsyncSessionLocal


FIXES = [
    {
        "id": "579b2af2-b69d-416f-8048-6be045b09317",
        "title": "Subventions de recherche RWJF Health Equity 2026",
        "short_description": (
            "Le programme RWJF Health Equity Research Grants 2026 soutient des projets de recherche "
            "et d'impact communautaire autour de l'équité en santé. L'opportunité est relayée par "
            "Global South Opportunities et doit être confirmée sur la source officielle avant toute candidature."
        ),
        "eligibility_criteria": (
            "La fiche cible principalement des organisations ou équipes travaillant sur des enjeux "
            "d'équité en santé, de recherche appliquée et d'impact communautaire. Les critères précis "
            "d'éligibilité, les profils admissibles et les zones couvertes doivent être vérifiés sur la source officielle."
        ),
    },
    {
        "id": "c9cfff83-393b-43b5-a01c-1a37eea1675c",
        "title": "Subventions PTES Conservation Insight 2026",
        "short_description": (
            "Les PTES Conservation Insight Grants 2026 financent des initiatives liées à la conservation, "
            "à la biodiversité et à la production de connaissances utiles pour l'action terrain. "
            "La date limite repérée est le 28 mai 2026."
        ),
        "eligibility_criteria": (
            "L'opportunité s'adresse aux porteurs de projets, organisations ou équipes impliquées dans "
            "la conservation et la production de données utiles à la protection de la biodiversité. "
            "Les conditions détaillées doivent être confirmées sur la source officielle."
        ),
    },
]


MADAGASCAR_TITLE = "Madagascar - Least-Cost Electricity Access Development Project - LEAD"
MADAGASCAR_DESCRIPTION = (
    "Ce projet institutionnel de la Banque mondiale à Madagascar vise à soutenir le développement "
    "de l'accès à l'électricité au moindre coût. Il ne s'agit pas d'un appel à candidatures classique : "
    "les bénéficiaires, partenaires et modalités d'intervention doivent être vérifiés sur la page officielle. "
    "La clôture prévisionnelle est fixée au 29/06/2026."
)


async def main() -> None:
    async with AsyncSessionLocal() as session:
        updated = 0
        for item in FIXES:
            result = await session.execute(
                text(
                    """
                    UPDATE devices
                    SET title = :title,
                        short_description = :short_description,
                        eligibility_criteria = :eligibility_criteria,
                        updated_at = NOW()
                    WHERE id = :id
                    """
                ),
                item,
            )
            updated += result.rowcount or 0

        result = await session.execute(
            text(
                """
                UPDATE devices
                SET short_description = :short_description,
                    full_description = CASE
                        WHEN full_description IS NULL OR length(full_description) < 180
                        THEN :full_description
                        ELSE full_description
                    END,
                    updated_at = NOW()
                WHERE title = :title
                """
            ),
            {
                "title": MADAGASCAR_TITLE,
                "short_description": MADAGASCAR_DESCRIPTION,
                "full_description": (
                    "## Présentation\n"
                    f"{MADAGASCAR_DESCRIPTION}\n\n"
                    "## Conditions\n"
                    "La Banque mondiale ne publie pas ici de critères d'éligibilité comparables à un concours ou à une subvention ouverte. "
                    "Les modalités doivent être confirmées auprès de la source officielle.\n\n"
                    "## Source officielle\n"
                    "Consulter la fiche projet Banque mondiale pour confirmer le périmètre, les partenaires et les dates."
                ),
            },
        )
        updated += result.rowcount or 0
        await session.commit()
        print(f"{updated} fiche(s) africaines premium corrigée(s).")


if __name__ == "__main__":
    asyncio.run(main())
