from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.data.audit_english_titles import (
    PUBLIC_VALIDATION_STATUSES,
    is_africa_related,
    looks_english_title,
)
from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import clean_editorial_text, normalize_title


EXACT_TITLES = {
    "GSMA Innovation Fund for Green Transition for Mobile": "GSMA Innovation Fund - transition verte par le mobile",
    "AfCFTA Startup Acceleration & Partnership Program 2026": "Programme d'accélération AfCFTA pour startups africaines 2026",
    "Carnegie Mellon University Africa Launches 2026 Business Incubation Program for African Tech Startups": "Programme d'incubation 2026 de Carnegie Mellon University Africa pour startups tech africaines",
    "Call for Applications: 2027 Agricultural Bursary Programme, South Africa": "Appel à candidatures : programme de bourses agricoles 2027 en Afrique du Sud",
    "Applications are now Open for TREES – EGAP Small Grants: Request for Letter of Inquiry": "Appel à candidatures : petites subventions TREES - EGAP",
    "Funguo Innovation Programme – #GreenCatalyst": "Programme d'innovation Funguo - GreenCatalyst",
    "THRIVE Global Impact Challenge 2026": "Challenge mondial d'impact THRIVE 2026",
    "PRIMA Young Innovators Award 2026": "Prix PRIMA Jeunes Innovateurs 2026",
    "Visa Africa FinTech Accelerator Program 6": "Programme d'accélération Visa Africa FinTech 6",
    "Breet Fintech Builder Grant is Hosting the Africa Technology Expo 2026 – Apply Now (up to $10, 000 in funding)": "Subvention Breet Fintech Builder - Africa Technology Expo 2026",
    "RAISEAfrica 2026 Accelerator Programme Opens Applications for Renewable Energy Startups": "Accélérateur RAISEAfrica 2026 pour startups des énergies renouvelables",
    "NRF–SSHRC Seed Grants 2026: South Africa–Canada Research Collaboration Opportunity": "Subventions d'amorçage NRF-SSHRC 2026 pour collaboration Afrique du Sud - Canada",
    "FCI 4 Africa Launches €400, 000 Open Call to Advance Fair and Inclusive Food Systems in Africa": "Appel FCI 4 Africa pour des systèmes alimentaires équitables et inclusifs",
    "Mastercard Foundation Fund for Resilience & Prosperity": "Fonds Mastercard Foundation pour la résilience et la prospérité",
    "YouthADAPT Challenge (BAD/GCA)": "Challenge YouthADAPT (BAD/GCA)",
    "Google for Startups Black Founders Fund Africa": "Fonds Google for Startups Black Founders Fund Africa",
    "USADF Grants": "Subventions USADF",
    "Cathay AfricInvest Innovation Fund": "Fonds Cathay AfricInvest Innovation",
    "Mastercard Foundation EdTech Fellowship - Benin": "Programme EdTech Fellowship de la Mastercard Foundation - Bénin",
    "LuxAid Challenge Fund Benin - cofinancement d'entreprises innovantes": "LuxAid Challenge Fund Bénin - cofinancement d'entreprises innovantes",
    "Digital Energy Challenge 2026 - PME énergie digitale en Afrique": "Digital Energy Challenge 2026 - PME de l'énergie digitale en Afrique",
    "Nice African Talents Awards - jeunes entrepreneurs en Cote d'Ivoire": "Nice African Talents Awards - jeunes entrepreneurs en Côte d'Ivoire",
    "PEEB Awards Burkina Faso - valorisation des entrepreneurs et industriels": "PEEB Awards Burkina Faso - valorisation des entrepreneurs et industriels",
    "Green RISE West Africa Fellowship": "Programme Green RISE Fellowship Afrique de l'Ouest",
    "PESP 7 Funding 2026–2027: National Arts Council (NAC) South Africa Opens Applications for Creative Projects": "Financement PESP 7 2026-2027 pour projets créatifs en Afrique du Sud",
    "Zindi Launches $5, 000 Multilingual Health AI Challenge for Low-Resource African Languages": "Challenge Zindi IA santé multilingue pour langues africaines",
    "PyCon Africa 2026 Opportunity Grants: Supporting Inclusive Participation in Kampala": "Subventions PyCon Africa 2026 pour participation inclusive à Kampala",
    "Call for Proposals: Global Resilience Partnership Innovation Challenge (Grants up to $50, 000) – Apply By 22 May 2026": "Appel à propositions Global Resilience Partnership Innovation Challenge",
    "Apply for the Accelerate Africa Startup Programme 2026: A Launchpad for Early-Stage African Founders": "Programme Accelerate Africa 2026 pour startups africaines en amorçage",
    "AECF - Digital Innovation Fund for Energy & Climate (DIFEC)": "AECF - fonds d'innovation numérique pour l'énergie et le climat (DIFEC)",
    "Villgro Africa - Incubation Program": "Villgro Africa - programme d'incubation",
    "Orange Corners Innovation Fund (OCIF)": "Orange Corners Innovation Fund (OCIF)",
    "Applications are open for The Trevor Noah Foundation Education Changemakers Program – 3 rd Cohort (East & Central Africa)": "Programme Education Changemakers de la Trevor Noah Foundation - Afrique de l'Est et centrale",
    "UNDP BRACE 4 PEACE Programme Launches Free Skills Training and Livelihood Support for Youth and Women in Kenya": "Programme BRACE 4 PEACE du PNUD - formation et appui aux jeunes et femmes au Kenya",
    "Fonds Google for Startups Black Founders Fund Africa": "Fonds Google for Startups pour fondateurs africains",
    "Orange Corners Innovation Fund (OCIF)": "Fonds d'innovation Orange Corners (OCIF)",
    "LuxAid Challenge Fund Bénin - cofinancement d'entreprises innovantes": "Fonds Challenge LuxAid Bénin - cofinancement d'entreprises innovantes",
    "GSMA Innovation Fund - transition verte par le mobile": "Fonds d'innovation GSMA - transition verte par le mobile",
    "Digital Energy Challenge 2026 - PME de l'énergie digitale en Afrique": "Challenge Digital Energy 2026 - PME de l'énergie digitale en Afrique",
    "Mastercard Foundation / CPCCAF - concours pour Benin": "Programme EdTech Fellowship de la Mastercard Foundation - Bénin",
    "VC 4 A - financement pour Tanzanie": "Programme d'innovation Funguo - GreenCatalyst",
    "Global South Opportunities - concours pour International": "Challenge Zindi IA santé multilingue pour langues africaines",
    "BAD / Global Centre on Adaptation - financement pour Afrique": "Challenge YouthADAPT pour l'adaptation climatique en Afrique",
}

PHRASE_REPLACEMENTS = [
    (r"^\s*applications?\s+are\s+(now\s+)?open\s+for\s+", "Appel à candidatures : "),
    (r"^\s*open\s+call\s+for\s+", "Appel à projets : "),
    (r"^\s*call\s+for\s+applications?\s*:\s*", "Appel à candidatures : "),
    (r"^\s*call\s+for\s+applications?\s+", "Appel à candidatures : "),
    (r"^\s*apply\s+now\s*[:\-]?\s*", "Appel à candidatures : "),
]

WORD_REPLACEMENTS = [
    (r"\bfunding opportunity\b", "opportunité de financement"),
    (r"\bfunding\b", "financement"),
    (r"\bsmall grants\b", "petites subventions"),
    (r"\bseed grants\b", "subventions d'amorçage"),
    (r"\bgrants\b", "subventions"),
    (r"\bgrant\b", "subvention"),
    (r"\baward\b", "prix"),
    (r"\bawards\b", "prix"),
    (r"\bchallenge\b", "challenge"),
    (r"\baccelerator programme\b", "programme d'accélération"),
    (r"\baccelerator program\b", "programme d'accélération"),
    (r"\bprogramme\b", "programme"),
    (r"\bprogram\b", "programme"),
    (r"\bfellowship\b", "programme de fellowship"),
    (r"\binnovation fund\b", "fonds d'innovation"),
    (r"\bbusiness incubation\b", "incubation d'entreprises"),
    (r"\bfor african\b", "pour les acteurs africains"),
    (r"\bfor africa\b", "pour l'Afrique"),
    (r"\bfor\b", "pour"),
    (r"\bopens applications\b", "ouvre les candidatures"),
    (r"\bis hosting\b", "organise"),
    (r"\bapply now\b", "candidatures ouvertes"),
    (r"\bopen call\b", "appel à projets"),
    (r"\bcall\b", "appel"),
]


def _source_name(device: Device) -> str:
    return device.source.name if device.source else "Import manuel / historique"


def _title_from_sections(device: Device) -> str | None:
    sections = device.ai_rewritten_sections_json or device.content_sections_json
    if isinstance(sections, dict):
        title = sections.get("title") or sections.get("titre")
        if isinstance(title, str) and len(title.strip()) > 8:
            return clean_editorial_text(title)
    return None


def translate_title(title: str, device: Device) -> str:
    cleaned = clean_editorial_text(title)
    if cleaned in EXACT_TITLES:
        return EXACT_TITLES[cleaned]

    from_sections = _title_from_sections(device)
    if from_sections and not looks_english_title(from_sections):
        return from_sections

    value = cleaned
    for pattern, replacement in PHRASE_REPLACEMENTS:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
    for pattern, replacement in WORD_REPLACEMENTS:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)

    value = value.replace("South Africa", "Afrique du Sud")
    value = value.replace("Cote d'Ivoire", "Côte d'Ivoire")
    value = value.replace("Benin", "Bénin")
    value = value.replace("–", "-")
    value = re.sub(r"\s+", " ", value).strip(" -")

    if value == cleaned or looks_english_title(value):
        type_label = {
            "subvention": "financement",
            "concours": "concours",
            "accompagnement": "programme d'accompagnement",
            "investissement": "fonds d'investissement",
            "aap": "appel à projets",
            "appel_a_projets": "appel à projets",
        }.get(str(device.device_type or "").lower(), "opportunité")
        organism = clean_editorial_text(device.organism or _source_name(device))
        country = clean_editorial_text(device.country or device.zone or "Afrique")
        return f"{organism} - {type_label} pour {country}"

    return value[:1].upper() + value[1:]


def _mark_title_cleanup(device: Device, old_title: str, new_title: str) -> None:
    device.title = new_title
    device.title_normalized = normalize_title(new_title)
    tags = list(device.tags or [])
    if "titre_francise" not in tags:
        tags.append("titre_francise")
    device.tags = tags
    notes = {
        "title_fr_cleaned_at": datetime.now(timezone.utc).isoformat(),
        "original_title": old_title,
    }
    analysis = dict(device.decision_analysis or {})
    analysis["title_cleanup"] = notes
    device.decision_analysis = analysis


async def run(dry_run: bool = True) -> dict[str, Any]:
    stats = {"seen": 0, "candidates": 0, "changed": 0, "skipped": 0}
    preview: list[dict[str, str]] = []

    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .where(Device.validation_status.in_(PUBLIC_VALIDATION_STATUSES))
                .order_by(Device.created_at.desc())
            )
        ).scalars().all()

        for device in devices:
            stats["seen"] += 1
            old_title = clean_editorial_text(device.title or "")
            if old_title not in EXACT_TITLES and (
                not is_africa_related(device) or not looks_english_title(device.title)
            ):
                continue

            stats["candidates"] += 1
            if "titre_francise" in (device.tags or []) and old_title not in EXACT_TITLES:
                stats["skipped"] += 1
                continue
            new_title = translate_title(old_title, device)
            if not new_title or new_title == old_title:
                stats["skipped"] += 1
                continue

            stats["changed"] += 1
            if len(preview) < 80:
                preview.append(
                    {
                        "id": str(device.id),
                        "source": _source_name(device),
                        "old_title": old_title,
                        "new_title": new_title,
                    }
                )
            if not dry_run:
                _mark_title_cleanup(device, old_title, new_title)

        if dry_run:
            await db.rollback()
        else:
            await db.commit()

    return {"dry_run": dry_run, "stats": stats, "preview": preview}


def main() -> None:
    parser = argparse.ArgumentParser(description="Francise les titres anglais publics, en priorité Afrique.")
    parser.add_argument("--apply", action="store_true", help="Applique les changements en base.")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(dry_run=not args.apply)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
