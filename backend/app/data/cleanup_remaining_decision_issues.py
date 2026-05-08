import asyncio
import json

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import build_structured_sections


FIXES = {
    "Baobab Network - accelerateur pour startups africaines": {
        "short_description": (
            "Accelerateur pan-africain pour startups tech, avec candidature en continu, "
            "ticket initial autour de 100 000 USD et accompagnement operationnel pour "
            "preparer la croissance."
        ),
    },
    "Mastercard Foundation (Young Africa Works)": {
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Programme institutionnel et partenarial sans fenetre de cloture publique unique.",
        "eligibility_criteria": (
            "Les opportunites liees a Young Africa Works ciblent generalement des jeunes, "
            "entrepreneurs, organisations de mise en oeuvre et partenaires travaillant sur "
            "l'emploi et l'inclusion economique en Afrique. Les criteres exacts dependent "
            "du pays, du programme et de l'appel partenaire publie."
        ),
        "funding_details": (
            "Le financement depend des appels, partenariats ou programmes pays associes. "
            "Les montants, modalites et formes d'appui doivent etre confirmes sur la "
            "source officielle ou aupres du partenaire de mise en oeuvre."
        ),
    },
    "Tunisia Integrated Disaster Resilience Program": {
        "short_description": (
            "Projet institutionnel de la Banque mondiale en Tunisie consacre a la resilience "
            "face aux catastrophes. La fiche sert surtout au suivi d'un projet public, "
            "pas a une candidature directe."
        ),
    },
    'Fonds direct "Breizh Invest PME"': {
        "short_description": (
            "Fonds d'investissement regional destine a renforcer les fonds propres de PME "
            "bretonnes en developpement ou transmission. Les modalites exactes doivent "
            "etre confirmees sur la source officielle."
        ),
        "eligibility_criteria": (
            "La fiche cible des PME implantees ou ayant un projet significatif en Bretagne, "
            "avec un besoin de renforcement en capital. Les criteres financiers, sectoriels "
            "et de maturite doivent etre confirmes directement aupres du fonds."
        ),
        "funding_details": (
            "L'appui prend la forme d'un investissement en capital ou quasi-fonds propres. "
            "Le ticket, la duree d'investissement et les conditions d'entree au capital "
            "doivent etre verifies sur la page officielle."
        ),
        "status": "standby",
    },
}


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device).where(Device.title.in_(list(FIXES.keys())))
            )
        ).scalars().all()

        updated = 0
        preview: list[dict] = []
        for device in devices:
            fix = FIXES.get(device.title, {})
            before = {
                "title": device.title,
                "status": device.status,
                "short": (device.short_description or "")[:120],
            }
            changed = False
            for field, value in fix.items():
                if getattr(device, field) != value:
                    setattr(device, field, value)
                    changed = True

            if device.title == "Mastercard Foundation (Young Africa Works)":
                full_description = build_structured_sections(
                    presentation=device.short_description,
                    eligibility=device.eligibility_criteria,
                    funding=device.funding_details,
                    procedure=(
                        "La verification doit se faire sur la page officielle Mastercard Foundation "
                        "ou via les partenaires pays qui publient les appels operationnels."
                    ),
                    recurrence_notes=device.recurrence_notes,
                )
                if device.full_description != full_description:
                    device.full_description = full_description
                    changed = True

            if device.title == 'Fonds direct "Breizh Invest PME"':
                full_description = build_structured_sections(
                    presentation=device.short_description,
                    eligibility=device.eligibility_criteria,
                    funding=device.funding_details,
                    procedure=(
                        "La prise de contact et la verification des criteres se font depuis "
                        "la source officielle Breizh Invest PME."
                    ),
                )
                if device.full_description != full_description:
                    device.full_description = full_description
                    changed = True

            if changed:
                updated += 1
                preview.append(
                    {
                        "before": before,
                        "after": {
                            "title": device.title,
                            "status": device.status,
                            "short": (device.short_description or "")[:180],
                        },
                    }
                )

        await db.commit()

    return {"updated": updated, "preview": preview}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
