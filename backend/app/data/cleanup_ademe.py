import asyncio
import json
from datetime import date
from unidecode import unidecode

from sqlalchemy import or_, select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness


SOURCE_NAME = "ADEME - aides aux projets de recherche"


def _extract_payload(source_raw: str | None) -> tuple[str, dict]:
    raw = (source_raw or "").strip()
    if not raw:
        return "", {}
    parts = raw.split("\n\n", 1)
    label = clean_editorial_text(parts[0]) if parts else ""
    payload = {}
    if len(parts) > 1:
        try:
            payload = json.loads(parts[1])
        except json.JSONDecodeError:
            payload = {}
    return label, payload


def _format_country(country: str | None) -> str:
    label = clean_editorial_text(country or "")
    return label or "France"


def _format_date_fr(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = date.fromisoformat(str(value)[:10])
    except ValueError:
        return clean_editorial_text(str(value))
    return parsed.strftime("%d/%m/%Y")


def _project_reference(payload: dict) -> str:
    ref = clean_editorial_text(payload.get("reference_du_projet") or "")
    if not ref:
        return ""
    return f"Référence projet : {ref}."


def _research_summary(device: Device, label: str, payload: dict) -> str:
    carrier = clean_editorial_text(payload.get("organisme_du_porteur") or "")
    start_date = _format_date_fr(payload.get("date_de_debut_du_projet"))
    end_date = _format_date_fr(payload.get("date_de_fin_du_projet"))
    country = _format_country(device.country)
    parts = [f"{device.title} correspond à un projet de {label.lower()} soutenu par l'ADEME en {country}."]
    if carrier:
        parts.append(f"Le porteur identifié dans la source est {carrier}.")
    if start_date and end_date:
        parts.append(f"Le projet s'est déroulé du {start_date} au {end_date}.")
    elif end_date:
        parts.append(f"La clôture repérée dans la source est fixée au {end_date}.")
    reference = _project_reference(payload)
    if reference:
        parts.append(reference)
    parts.append("Cette fiche décrit un projet de recherche historique et non un appel actuellement ouvert.")
    return " ".join(part.strip() for part in parts if part).strip()[:500]


def _research_eligibility(payload: dict) -> str:
    carrier = clean_editorial_text(payload.get("organisme_du_porteur") or "")
    parts = []
    if carrier:
        parts.append(f"La source rattache ce projet à l'organisme porteur suivant : {carrier}.")
    parts.append(
        "Il s'agit d'un projet de recherche déjà attribué ; la fiche ne documente donc pas de critères d'éligibilité comparables à un appel à candidatures en cours."
    )
    return " ".join(parts)


def _research_funding(label: str, payload: dict) -> str:
    reference = clean_editorial_text(payload.get("reference_du_projet") or "")
    if reference:
        return (
            f"La source conserve surtout une référence administrative ({reference}) pour ce projet {label.lower()}. "
            "Aucun montant directement exploitable n'est publié dans le flux actuel."
        )
    return "Aucun montant directement exploitable n'est publié dans le flux actuel pour ce projet de recherche."


def _research_procedure() -> str:
    return (
        "Cette fiche est conservée pour mémoire et traçabilité. Pour identifier des aides ADEME actuellement mobilisables, il faut consulter les pages actives du portail ADEME."
    )


def _recurring_summary(device: Device) -> str:
    maximum = ""
    if device.amount_max:
        amount = float(device.amount_max)
        maximum = f"{int(amount):,}".replace(",", " ") if amount.is_integer() else f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    parts = [
        "La subvention rénovation énergétique PME est une aide récurrente relayée par l'ADEME et les Régions pour accompagner les diagnostics énergétiques et les travaux de rénovation des locaux professionnels.",
        "Elle vise principalement les PME qui souhaitent réduire leurs consommations d'énergie et améliorer la performance thermique de leurs bâtiments.",
    ]
    if maximum:
        parts.append(f"Le taux et le niveau d'aide varient selon la région, avec un repère de montant pouvant aller jusqu'à {maximum} EUR lorsque la fiche locale le prévoit.")
    else:
        parts.append("Le taux et le niveau d'aide varient selon la région et doivent être confirmés auprès du guichet local compétent.")
    parts.append("Le dispositif fonctionne sans fenêtre unique de clôture nationale publiée.")
    return " ".join(parts)


def _recurring_eligibility() -> str:
    return (
        "Le dispositif cible principalement les PME engageant un diagnostic énergétique ou des travaux de rénovation thermique de leurs locaux professionnels. "
        "Les critères précis, dépenses éligibles et conditions territoriales doivent être confirmés selon la région concernée."
    )


def _recurring_funding(device: Device) -> str:
    if device.amount_max:
        amount = float(device.amount_max)
        amount_label = f"{int(amount):,}".replace(",", " ") if amount.is_integer() else f"{amount:,.2f}".replace(",", " ").replace(".", ",")
        return f"Le montant ou le plafond d'aide peut atteindre {amount_label} EUR selon les modalités locales. Le taux exact reste à confirmer selon la région."
    return "Le taux et le montant d'aide sont variables selon la région et la nature des travaux. Ils doivent être confirmés sur la page officielle."


def _recurring_procedure() -> str:
    return (
        "La demande se prépare à partir des parcours ADEME et des relais régionaux compétents. Il faut vérifier localement les pièces attendues, les plafonds et la disponibilité effective du guichet."
    )


async def run() -> dict:
    gate = DeviceQualityGate()
    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == SOURCE_NAME))).scalar_one_or_none()
        if source is None:
            raise RuntimeError(f"Source introuvable: {SOURCE_NAME}")

        devices = (
            await db.execute(
                select(Device)
                .where(Device.source_id == source.id)
                .where(
                    or_(
                        Device.validation_status == "pending_review",
                        Device.title.in_(
                            [
                                "AMI IA DECHETS - OPCOGENERATION",
                                "AMI IA DECHETS N° 2 : projet CYCLAPROV",
                                "AMI IA DECHETS N° 2 projet CYCLAPROV",
                                "CaReWood - Cascading Recovered Wood",
                                "Subvention Rénovation Énergétique PME — ADEME + Régions",
                            ]
                        ),
                    )
                )
                .order_by(Device.title.asc())
            )
        ).scalars().all()

        updated = 0
        preview: list[dict] = []

        for device in devices:
            changed = False
            normalized_title = unidecode(clean_editorial_text(device.title).lower())
            if "subvention renovation energetique pme" in normalized_title:
                if device.status != "recurring":
                    device.status = "recurring"
                    changed = True
                if not device.is_recurring:
                    device.is_recurring = True
                    changed = True
                notes = "Aide ADEME relayée avec déclinaisons régionales, sans date de clôture nationale unique."
                if device.recurrence_notes != notes:
                    device.recurrence_notes = notes
                    changed = True
                summary = _recurring_summary(device)
                eligibility = _recurring_eligibility()
                funding = _recurring_funding(device)
                procedure = _recurring_procedure()
            else:
                label, payload = _extract_payload(device.source_raw)
                summary = _research_summary(device, label or "programme recherche", payload)
                eligibility = _research_eligibility(payload)
                funding = _research_funding(label or "programme recherche", payload)
                procedure = _research_procedure()

            full_description = build_structured_sections(
                presentation=summary,
                eligibility=eligibility,
                funding=funding,
                open_date=device.open_date,
                close_date=device.close_date,
                procedure=procedure,
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

            payload_dict = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
            decision = gate.evaluate(payload_dict)
            if decision.validation_status != device.validation_status:
                device.validation_status = decision.validation_status
                changed = True
            if device.validation_status == "pending_review":
                device.validation_status = "auto_published"
                changed = True

            payload_dict = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
            device.completeness_score = compute_completeness(payload_dict)

            if changed:
                updated += 1
                if len(preview) < 12:
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
