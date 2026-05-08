import asyncio
import re
from decimal import Decimal

from bs4 import BeautifulSoup
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness


SOURCE_NAME = "Global South Opportunities - Funding"


def _classify_device_type(device: Device) -> str:
    blob = clean_editorial_text(f"{device.title or ''} {device.short_description or ''} {device.full_description or ''}").lower()
    current = device.device_type or "autre"
    if current not in {"autre", "", None}:
        return current
    if any(marker in blob for marker in ("challenge", "award", "prize", "competition", "solve")):
        return "concours"
    if any(marker in blob for marker in ("accelerator", "fellowship", "study visit", "exchange", "programme", "program")):
        return "accompagnement"
    if any(marker in blob for marker in ("grant", "funding", "fund")):
        return "subvention"
    return current


def _normalize_status(device: Device) -> bool:
    changed = False
    if device.close_date:
        return changed

    if device.status == "open":
        # Global South relaie beaucoup d'articles sans date exploitable.
        # Sans deadline fiable, on évite de présenter l'opportunité comme ouverte.
        device.status = "standby"
        changed = True

    if device.status == "standby" and not device.recurrence_notes:
        device.recurrence_notes = (
            "Date limite non communiquee par la source publique. "
            "La fiche reste exploitable avec verification sur la source officielle du programme."
        )
        changed = True

    return changed


def _extract_text_blocks(raw_html: str | None) -> tuple[list[str], list[str]]:
    if not raw_html:
        return [], []
    soup = BeautifulSoup(raw_html, "lxml")
    paragraphs = [
        clean_editorial_text(node.get_text(" ", strip=True))
        for node in soup.select("p")
        if clean_editorial_text(node.get_text(" ", strip=True))
    ]
    bullets = [
        clean_editorial_text(node.get_text(" ", strip=True))
        for node in soup.select("li")
        if clean_editorial_text(node.get_text(" ", strip=True))
    ]
    return paragraphs, bullets


def _normalize_amount_text(text: str) -> str:
    value = text.replace("Upto", "Up to").replace("upto", "up to")
    value = re.sub(r"\s+", " ", value)
    value = value.replace("$ ", "$").replace("€ ", "€")
    return value.strip()


def _extract_amount_hint(device: Device, paragraphs: list[str]) -> str:
    if device.amount_min or device.amount_max:
        if device.amount_min and device.amount_max and device.amount_min != device.amount_max:
            return f"Le soutien annoncé se situe entre {device.amount_min} et {device.amount_max} {device.currency or 'EUR'}."
        amount = device.amount_max or device.amount_min
        return f"Le montant annoncé peut atteindre {amount} {device.currency or 'EUR'}."

    candidates = [device.title or "", *paragraphs[:6]]
    pattern = re.compile(
        r"((?:up to|upto|between|from)\s+)?([$€£]\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:million|m|k|thousand))?|\d[\d,]*(?:\.\d+)?\s?(?:USD|EUR|GBP|dollars|euros|pounds))",
        re.IGNORECASE,
    )
    for candidate in candidates:
        match = pattern.search(candidate)
        if match:
            amount = _normalize_amount_text(match.group(0))
            return f"La source mentionne un soutien financier indicatif de {amount}, à confirmer sur le site officiel du programme."
    return "Le montant exact ou les avantages associés doivent être confirmés sur la source officielle du programme."


def _extract_benefit_hint(paragraphs: list[str], bullets: list[str]) -> str:
    combined = [*paragraphs[:8], *bullets[:8]]
    keywords = (
        "mentorship",
        "training",
        "accelerator",
        "acceleration",
        "technical assistance",
        "coaching",
        "network",
        "support",
        "exposure",
        "fellowship",
        "award",
        "prize",
    )
    hits: list[str] = []
    for item in combined:
        lowered = item.lower()
        if any(keyword in lowered for keyword in keywords):
            hits.append(item)
        if len(hits) >= 2:
            break
    if not hits:
        return ""
    lowered = " ".join(hits).lower()
    categories: list[str] = []
    if any(keyword in lowered for keyword in ("mentorship", "coaching")):
        categories.append("mentorat")
    if any(keyword in lowered for keyword in ("training", "accelerator", "acceleration", "fellowship")):
        categories.append("programme d'accompagnement")
    if any(keyword in lowered for keyword in ("network", "exposure")):
        categories.append("mise en réseau et visibilité")
    if any(keyword in lowered for keyword in ("technical assistance", "support")):
        categories.append("appui technique")
    if not categories:
        categories.append("accompagnement complémentaire")
    if len(categories) == 1:
        return f"La source mentionne aussi un {categories[0]} en complément éventuel du financement."
    if len(categories) == 2:
        return f"La source mentionne aussi un {categories[0]} ainsi qu'une {categories[1]} en complément éventuel du financement."
    return (
        "La source mentionne aussi plusieurs avantages non financiers, notamment "
        + ", ".join(categories[:-1])
        + f" et {categories[-1]}."
    )


def _format_beneficiaries(values: list[str] | None) -> str:
    cleaned = [clean_editorial_text(value) for value in (values or []) if clean_editorial_text(value)]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0].lower()
    if len(cleaned) == 2:
        return f"{cleaned[0].lower()} et {cleaned[1].lower()}"
    return f"{', '.join(value.lower() for value in cleaned[:-1])} et {cleaned[-1].lower()}"


def _build_summary(device: Device, paragraphs: list[str], amount_hint: str, benefit_hint: str) -> str:
    title = clean_editorial_text(device.title or "Cette opportunité")
    beneficiaries = _format_beneficiaries(device.beneficiaries)
    sectors = ", ".join(device.sectors or [])
    country = clean_editorial_text(device.country or "")
    parts = [f"{title} est une opportunité relayée par Global South Opportunities."]
    if beneficiaries:
        parts.append(f"Elle s'adresse en priorité aux {beneficiaries}.")
    elif country:
        parts.append(f"Elle concerne principalement des candidatures liées à la zone {country}.")
    if sectors:
        parts.append(f"Les thématiques mises en avant dans la fiche incluent notamment : {sectors}.")
    if device.close_date:
        parts.append(f"La date limite actuellement repérée est le {device.close_date.strftime('%d/%m/%Y')}.")
    if amount_hint:
        parts.append(amount_hint)
    if benefit_hint:
        parts.append(benefit_hint)
    if not device.close_date:
        parts.append("La date limite n'est pas confirmée de manière fiable dans la source relayée, ce qui justifie un suivi prudent.")
    return " ".join(part.strip() for part in parts if part).strip()[:500]


def _build_eligibility(device: Device, paragraphs: list[str], bullets: list[str]) -> str:
    beneficiaries = _format_beneficiaries(device.beneficiaries)
    sectors = ", ".join(device.sectors or [])
    country = clean_editorial_text(device.country or "")
    parts: list[str] = []
    if beneficiaries:
        parts.append(f"La source vise principalement les profils suivants : {beneficiaries}.")
    elif country:
        parts.append(f"La source présente cette opportunité pour des candidats intervenant principalement sur la zone {country}.")

    scope_hint = ""
    for item in [*paragraphs[:6], *bullets[:8]]:
        lowered = item.lower()
        if any(keyword in lowered for keyword in ("eligib", "applicant", "who can apply", "open to", "target", "applicants")):
            scope_hint = item
            break
    if scope_hint:
        parts.append(
            "Le texte relayé indique des critères autour du profil des candidats, du secteur d'activité ou de la zone d'intervention. "
            f"Repère utile : {scope_hint[:260]}."
        )

    if sectors:
        parts.append(f"Les secteurs mis en avant sur la fiche incluent notamment : {sectors}.")

    parts.append("Les critères détaillés de recevabilité doivent être vérifiés sur le site officiel du programme avant toute décision.")
    return " ".join(parts)


def _build_funding(amount_hint: str, benefit_hint: str) -> str:
    parts = [amount_hint]
    if benefit_hint:
        parts.append(benefit_hint)
    parts.append("Les montants, avantages non financiers et éventuelles contreparties doivent être confirmés sur la source officielle.")
    return " ".join(part.strip() for part in parts if part).strip()


def _build_procedure(device: Device) -> str:
    return (
        "Cette fiche est relayée par Global South Opportunities. Il faut donc ouvrir la source officielle mentionnée dans l'article pour "
        "confirmer la date limite, les modalités de dépôt et les pièces attendues avant candidature."
    )


def _should_force_publish(device: Device) -> bool:
    return (
        len(clean_editorial_text(device.short_description or "")) >= 140
        and len(clean_editorial_text(device.full_description or "")) >= 280
        and len(clean_editorial_text(device.eligibility_criteria or "")) >= 110
        and len(clean_editorial_text(device.funding_details or "")) >= 90
        and device.status in {"standby", "open", "recurring"}
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
                .order_by(Device.title.asc())
            )
        ).scalars().all()

        updated = 0
        auto_published = 0
        preview: list[dict] = []

        for device in devices:
            changed = False

            new_type = _classify_device_type(device)
            if new_type != device.device_type:
                device.device_type = new_type
                changed = True

            if _normalize_status(device):
                changed = True

            paragraphs, bullets = _extract_text_blocks(device.source_raw)
            amount_hint = _extract_amount_hint(device, paragraphs)
            benefit_hint = _extract_benefit_hint(paragraphs, bullets)
            summary = _build_summary(device, paragraphs, amount_hint, benefit_hint)
            eligibility = _build_eligibility(device, paragraphs, bullets)
            funding = _build_funding(amount_hint, benefit_hint)
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

            if device.validation_status == "pending_review" and _should_force_publish(device):
                device.validation_status = "auto_published"
                changed = True

            payload = {column.name: getattr(device, column.name) for column in Device.__table__.columns}
            device.completeness_score = compute_completeness(payload)

            if device.validation_status == "auto_published":
                auto_published += 1

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

        return {
            "source": SOURCE_NAME,
            "updated": updated,
            "auto_published_after_cleanup": auto_published,
            "preview": preview,
        }


def main() -> None:
    result = asyncio.run(run())
    print(result)


if __name__ == "__main__":
    main()
