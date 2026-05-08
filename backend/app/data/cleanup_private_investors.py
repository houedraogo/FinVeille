import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.utils.text_utils import clean_editorial_text, compute_completeness


PROFILES = {
    "TLcom Capital - pitch us": {
        "title": "TLcom Capital - Pitch Us",
        "organism": "TLcom Capital",
        "device_type": "investissement",
        "country": "Afrique",
        "sectors": ["Numerique", "Fintech", "Sante", "Mobilite", "B2B"],
        "beneficiaries": ["startup", "pme"],
        "summary": (
            "TLcom Capital investit dans des startups technologiques africaines capables de construire des entreprises scalables "
            "sur de grands marches. La prise de contact se fait via la page officielle Pitch Us, sans fenetre de cloture unique."
        ),
        "eligibility": (
            "Le fonds cible principalement des fondateurs et startups technologiques operant en Afrique ou pour les marches africains. "
            "La priorite porte sur des equipes ambitieuses, des modeles scalables, une traction commerciale credible et un potentiel "
            "de croissance regional ou continental. Les criteres exacts de stade, de secteur et de geographie doivent etre confirmes "
            "directement avec TLcom Capital."
        ),
        "funding": (
            "Financement en investissement, generalement sous forme de capital ou quasi-capital, a confirmer avec TLcom Capital. "
            "Le ticket, la dilution, le calendrier d'instruction et les conditions d'accompagnement ne sont pas publics sur la page source "
            "et doivent etre verifies avant prise de contact."
        ),
        "procedure": (
            "Presenter l'entreprise via la page officielle de contact ou de pitch de TLcom Capital, avec un dossier clair sur l'equipe, "
            "le marche, la traction, le besoin de financement et l'utilisation prevue des fonds."
        ),
        "checks": (
            "Verifier le stade d'investissement actuellement recherche, les pays couverts, les tickets ouverts et les documents attendus."
        ),
    },
    "Villgro Africa - apply now": {
        "title": "Villgro Africa - Incubation Program",
        "organism": "Villgro Africa",
        "device_type": "accompagnement",
        "country": "Afrique",
        "sectors": ["Sante", "Medtech", "Biotech", "Impact"],
        "beneficiaries": ["startup", "porteur_projet"],
        "summary": (
            "Villgro Africa accompagne des innovations de sante, medtech et sciences de la vie en Afrique avec un appui business, "
            "technique et investisseurs. Les candidatures sont presentees comme ouvertes en continu ou selon evaluation progressive."
        ),
        "eligibility": (
            "Le programme vise des innovateurs, startups et entreprises africaines developpant des solutions de sante, medtech, "
            "biotech ou sciences de la vie. Les projets doivent montrer un potentiel d'impact, une solution testable ou deja en "
            "developpement, une equipe capable d'executer et une pertinence pour les besoins sanitaires africains. Les criteres "
            "definitifs doivent etre confirmes sur la page officielle."
        ),
        "funding": (
            "L'appui peut combiner incubation, accompagnement strategique, preparation a l'investissement, mentorat et acces au reseau. "
            "Le montant financier direct, les tickets eventuels et les conditions de participation ne sont pas communiques clairement "
            "dans la fiche source et doivent etre confirmes par Villgro Africa."
        ),
        "procedure": (
            "Soumettre une candidature via la page officielle Apply Now, en mettant en avant le probleme de sante adresse, la solution, "
            "la traction, l'equipe, le besoin d'accompagnement et le potentiel d'impact."
        ),
        "checks": (
            "Verifier si la candidature est ouverte au moment du depot, les pays eligibles, le stade attendu et les avantages precis."
        ),
    },
}


def _full_description(profile: dict[str, object]) -> str:
    return "\n\n".join(
        [
            f"## Presentation\n{profile['summary']}",
            f"## Criteres d'eligibilite\n{profile['eligibility']}",
            f"## Montant / avantages\n{profile['funding']}",
            "## Calendrier\nDispositif recurrent ou page de contact sans date limite unique publiee.",
            f"## Demarche\n{profile['procedure']}",
            f"## Points a verifier\n{profile['checks']}",
        ]
    )


def _sections(profile: dict[str, object]) -> dict[str, str]:
    return {
        "presentation": str(profile["summary"]),
        "eligibilite": str(profile["eligibility"]),
        "montant_avantages": str(profile["funding"]),
        "calendrier": "Dispositif recurrent ou page de contact sans date limite unique publiee.",
        "demarche": str(profile["procedure"]),
        "points_a_verifier": str(profile["checks"]),
    }


async def run() -> dict:
    stats = {"sources": 0, "devices_seen": 0, "updated": 0}
    preview: list[dict[str, str]] = []
    async with AsyncSessionLocal() as db:
        for source_name, profile in PROFILES.items():
            source = (
                await db.execute(select(Source).where(Source.name == source_name))
            ).scalar_one_or_none()
            if source is None:
                continue
            stats["sources"] += 1

            devices = (
                await db.execute(
                    select(Device).where(
                        Device.source_id == source.id,
                        Device.validation_status != "rejected",
                    )
                )
            ).scalars().all()

            for device in devices:
                stats["devices_seen"] += 1
                title = clean_editorial_text(device.title or "")
                is_generic = (
                    "contact us" in title.lower()
                    or "apply now" in title.lower()
                    or device.device_type in {None, "", "autre"}
                    or len(clean_editorial_text(device.eligibility_criteria or "")) < 120
                    or len(clean_editorial_text(device.funding_details or "")) < 80
                )
                if not is_generic:
                    continue

                device.title = str(profile["title"])
                device.organism = str(profile["organism"])
                device.device_type = str(profile["device_type"])
                device.country = str(profile["country"])
                device.sectors = profile["sectors"]
                device.beneficiaries = profile["beneficiaries"]
                device.short_description = str(profile["summary"])
                device.eligibility_criteria = str(profile["eligibility"])
                device.funding_details = str(profile["funding"])
                device.full_description = _full_description(profile)
                device.content_sections_json = _sections(profile)
                device.ai_rewritten_sections_json = _sections(profile)
                device.ai_rewrite_status = "done"
                device.ai_rewrite_model = "manual-profile"
                device.ai_rewrite_checked_at = datetime.now(timezone.utc)
                device.status = "recurring"
                device.is_recurring = True
                device.recurrence_notes = "Source investisseur ou incubateur sans fenetre de cloture unique publiee."
                device.validation_status = "auto_published"
                device.completeness_score = compute_completeness(
                    {column.name: getattr(device, column.name) for column in Device.__table__.columns}
                )
                stats["updated"] += 1
                if len(preview) < 10:
                    preview.append(
                        {
                            "source": source_name,
                            "title": device.title,
                            "type": device.device_type,
                            "status": device.status,
                        }
                    )

        await db.commit()

    return {"stats": stats, "preview": preview}


def main() -> None:
    print(asyncio.run(run()))


if __name__ == "__main__":
    main()
