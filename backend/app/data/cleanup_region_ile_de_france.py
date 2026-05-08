import asyncio
from decimal import Decimal

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness


SOURCE_NAME = "Region Ile-de-France - aides et appels"


def _format_amount(value: Decimal | None, currency: str | None) -> str:
    if value is None:
        return ""
    amount = float(value)
    if amount.is_integer():
        amount_str = f"{int(amount):,}".replace(",", " ")
    else:
        amount_str = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    return f"{amount_str} {(currency or 'EUR').strip()}".strip()


def _title_notes(device: Device) -> dict[str, str]:
    title = clean_editorial_text(device.title).lower()
    notes = {
        "presentation": "",
        "eligibility": "",
        "funding": "",
        "procedure": "",
        "recurrence": "Dispositif regional gere comme une offre recurrente ou sans fenetre unique de cloture publiee.",
    }

    if "pret croissance tpe" in title:
        notes.update(
            {
                "presentation": "Ce pret vise a soutenir la croissance des tres petites entreprises franciliennes avec un financement sans garantie sur les actifs ou sur le patrimoine du dirigeant.",
                "eligibility": "Le pret s'adresse en priorite aux TPE implantees en Ile-de-France qui portent un projet de developpement ou d'acceleration.",
                "funding": "Le soutien prend la forme d'un pret de croissance. Les modalites precises, le ticket et les conditions de cofinancement doivent etre verifies sur la page officielle.",
                "procedure": "La demande se prepare avec les interlocuteurs regionaux et Bpifrance a partir de la fiche officielle. Il faut verifier les pieces et les conditions d'instruction avant depot.",
                "recurrence": "Pret regional permanent ou active sans date unique de cloture publique.",
            }
        )
    elif "entrepreneuses" in title:
        notes.update(
            {
                "presentation": "Cette aide regionale soutient les entrepreneuses qui portent une initiative a impact social ou economique liee a la reduction des inegalites.",
                "eligibility": "Le dispositif cible les femmes entrepreneures ou porteuses de projet en Ile-de-France, avec une attention particuliere aux projets encore en phase de lancement.",
                "funding": "L'aide est presentee comme une subvention forfaitaire mobilisable en complement d'autres appuis. Le montant exact et les depenses eligibles doivent etre confirmes sur la source officielle.",
                "procedure": "La candidature se fait depuis la page regionale dediee. Il faut verifier les criteres de selection, les dates de releve et les justificatifs demandes.",
                "recurrence": "Aide regionale active sans date limite unique clairement publiee dans la fiche consolidee.",
            }
        )
    elif "innov'up" in title or "innov up" in title:
        notes.update(
            {
                "presentation": "Innov'up accompagne les entreprises innovantes franciliennes avec un soutien financier adapte aux projets d'innovation et a leur acceleration.",
                "eligibility": "Le dispositif cible des entreprises ou startups innovantes implantees en Ile-de-France, avec un passage en jury ou releves de decision regulierement annonces.",
                "funding": "La fiche fait etat d'un mix possible entre subvention et avance recuperable. Les montants et la ventilation exacte du soutien doivent etre verifies sur la page officielle.",
                "procedure": "Le dossier se prepare en lien avec la Region Ile-de-France selon un rythme de jury recurrent. Il faut verifier la prochaine session avant depot.",
                "recurrence": "Dispositif regional gere par jurys ou sessions regulieres plutot que par une cloture unique nationale.",
            }
        )
    elif "pm'up" in title or "pm up" in title:
        notes.update(
            {
                "presentation": "PM'up souverainete accompagne les PME franciliennes engagees dans une trajectoire de croissance, de relocalisation ou de transition strategique.",
                "eligibility": "Le dispositif vise surtout des PME implantees en Ile-de-France avec un projet de developpement, de souverainete productive ou de transformation.",
                "funding": "La fiche mentionne un accompagnement pouvant monter jusqu'a un niveau eleve de subvention. Le plafond exact, les taux et les depenses retenues doivent etre confirmes sur la source officielle.",
                "procedure": "La candidature se depose aupres de la Region sur le calendrier officiel du programme. Il faut verifier les sessions, les webinaires et les conditions d'instruction.",
                "recurrence": "Programme regional reconduit ou cadence par sessions, sans date unique exploitable dans la fiche stockee.",
            }
        )
    elif "tp'up" in title or "tp up" in title:
        notes.update(
            {
                "presentation": "TP'up souverainete soutient les tres petites entreprises franciliennes qui veulent investir, se structurer ou accelerer leur transition.",
                "eligibility": "Le dispositif s'adresse principalement aux TPE d'Ile-de-France engagees dans un projet de developpement ou de transition economique et energetique.",
                "funding": "Le soutien prend la forme d'une subvention regionale. Le plafond exact, le taux d'intervention et les depenses retenues doivent etre confirmes sur la page officielle.",
                "procedure": "La demande s'effectue via la plateforme de la Region Ile-de-France. Il faut verifier les conditions d'acces, les vagues de depot et les pieces attendues.",
                "recurrence": "Programme regional sans cloture unique de reference dans la fiche consolidee.",
            }
        )
    elif "fonds jv" in title or "jeu video" in title:
        notes.update(
            {
                "presentation": "Ce fonds regional soutient la creation de jeux video en Ile-de-France, avec une logique d'appui sectoriel dediee aux studios et porteurs de projets du secteur.",
                "eligibility": "Le dispositif cible les entreprises, studios ou equipes de creation lies au jeu video en Ile-de-France. Les criteres de maturite du projet et de rattachement regional doivent etre verifies sur la fiche officielle.",
                "funding": "L'aide prend la forme d'une subvention ou d'un fonds dedie au jeu video. Les montants, plafonds et sessions doivent etre confirmes sur la source officielle.",
                "procedure": "La candidature se construit selon le calendrier du fonds regional et les sessions annoncees par la Region. Il faut verifier la prochaine releve avant depot.",
                "recurrence": "Fonds sectoriel regional fonctionne par sessions ou campagnes recurrentes.",
            }
        )

    return notes


def _build_summary(device: Device) -> str:
    notes = _title_notes(device)
    parts = [f"{device.title} est une aide de la Region Ile-de-France proposee sans date de cloture unique exploitable dans la fiche actuelle."]
    if notes["presentation"]:
        parts.append(notes["presentation"])
    if device.amount_min is not None or device.amount_max is not None:
        minimum = _format_amount(device.amount_min, device.currency) if device.amount_min else ""
        maximum = _format_amount(device.amount_max, device.currency) if device.amount_max else ""
        if minimum and maximum and minimum != maximum:
            parts.append(f"Le niveau d'intervention repere se situe entre {minimum} et {maximum}.")
        else:
            parts.append(f"Le niveau d'intervention repere peut atteindre {maximum or minimum}.")
    parts.append("Le calendrier exact, les releves ou les sessions doivent etre confirmes sur la source officielle regionale.")
    return " ".join(part.strip() for part in parts if part).strip()[:500]


def _build_eligibility(device: Device) -> str:
    notes = _title_notes(device)
    parts = []
    if notes["eligibility"]:
        parts.append(notes["eligibility"])
    if device.beneficiaries:
        values = [clean_editorial_text(value).lower() for value in device.beneficiaries if clean_editorial_text(value)]
        if values:
            if len(values) == 1:
                parts.append(f"Beneficiaires identifies dans la fiche : {values[0]}.")
            else:
                parts.append(f"Beneficiaires identifies dans la fiche : {', '.join(values[:-1])} et {values[-1]}.")
    parts.append("Les criteres detailles d'eligibilite, de localisation et de maturite du projet doivent etre verifies sur la page officielle.")
    return " ".join(parts).strip()


def _build_funding(device: Device) -> str:
    notes = _title_notes(device)
    parts = []
    if device.amount_min is not None or device.amount_max is not None:
        minimum = _format_amount(device.amount_min, device.currency) if device.amount_min else ""
        maximum = _format_amount(device.amount_max, device.currency) if device.amount_max else ""
        if minimum and maximum and minimum != maximum:
            parts.append(f"Montant indicatif repere entre {minimum} et {maximum}.")
        else:
            parts.append(f"Montant indicatif repere : {maximum or minimum}.")
    if notes["funding"]:
        parts.append(notes["funding"])
    else:
        parts.append("Le montant exact, le taux d'intervention et les depenses eligibles doivent etre confirmes sur la page officielle.")
    return " ".join(parts).strip()


def _build_procedure(device: Device) -> str:
    notes = _title_notes(device)
    return notes["procedure"] or (
        "La demande se fait depuis la page officielle de la Region Ile-de-France. Il faut verifier le calendrier, les pieces et les modalites d'instruction avant depot."
    )


def _should_force_publish(device: Device) -> bool:
    return (
        len(clean_editorial_text(device.short_description or "")) >= 140
        and len(clean_editorial_text(device.full_description or "")) >= 260
        and len(clean_editorial_text(device.eligibility_criteria or "")) >= 90
        and len(clean_editorial_text(device.funding_details or "")) >= 70
        and device.status in {"recurring", "standby", "open", "expired"}
    )


async def run() -> dict:
    gate = DeviceQualityGate()
    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == SOURCE_NAME))).scalar_one_or_none()
        if source is None:
            raise RuntimeError(f"Source introuvable: {SOURCE_NAME}")

        devices = (await db.execute(select(Device).where(Device.source_id == source.id).order_by(Device.title.asc()))).scalars().all()

        updated = 0
        preview: list[dict] = []

        for device in devices:
            changed = False

            if device.status != "recurring":
                device.status = "recurring"
                changed = True
            if not device.is_recurring:
                device.is_recurring = True
                changed = True

            recurrence_notes = _title_notes(device)["recurrence"]
            if device.recurrence_notes != recurrence_notes:
                device.recurrence_notes = recurrence_notes
                changed = True

            summary = _build_summary(device)
            eligibility = _build_eligibility(device)
            funding = _build_funding(device)
            full_description = build_structured_sections(
                presentation=summary,
                eligibility=eligibility,
                funding=funding,
                open_date=device.open_date,
                close_date=device.close_date,
                procedure=_build_procedure(device),
                recurrence_notes=device.recurrence_notes,
            )

            if summary != (device.short_description or ""):
                device.short_description = summary
                changed = True
            if eligibility != (device.eligibility_criteria or ""):
                device.eligibility_criteria = eligibility
                changed = True
            if funding != (device.funding_details or ""):
                device.funding_details = funding
                changed = True
            if full_description != (device.full_description or ""):
                device.full_description = full_description
                changed = True

            payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
            decision = gate.evaluate(payload)
            if decision.validation_status != device.validation_status:
                device.validation_status = decision.validation_status
                changed = True

            if device.validation_status in {"pending_review", "rejected"} and _should_force_publish(device):
                device.validation_status = "auto_published"
                changed = True

            payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
            device.completeness_score = compute_completeness(payload)

            if changed:
                updated += 1
                if len(preview) < 10:
                    preview.append(
                        {
                            "title": device.title,
                            "status": device.status,
                            "validation_status": device.validation_status,
                            "short_description": device.short_description,
                        }
                    )

        await db.commit()
        return {"source": SOURCE_NAME, "updated": updated, "preview": preview}


def main() -> None:
    result = asyncio.run(run())
    print(result)


if __name__ == "__main__":
    main()
