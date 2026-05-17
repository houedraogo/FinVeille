from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from unidecode import unidecode

from app.data.audit_english_titles import looks_english_title
from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.utils.text_utils import clean_editorial_text, normalize_title


SOURCE_NAME = "Global South Opportunities - Funding"

TITLE_MAP = {
    "Wild Wonder Foundation Micro Grants 2026: Funding for Nature Journaling Clubs Worldwide": "Micro-subventions Wild Wonder Foundation 2026 pour clubs de nature journaling",
    "Apply for the Fully Funded UK-German Study Visit 2026: Funded Teacher Exchange in Wales": "Visite d'étude UK-German 2026 entièrement financée pour enseignants",
    "University of Bayreuth Opens 2026 Funding Calls Through Humboldt Centre for International Research Collaboration": "Appels à financement 2026 de l'Université de Bayreuth via le Humboldt Centre",
    "Applications are Open for the New Community-Centered Connectivity Grant Program – Apply By 7 May 2026": "Programme de subvention pour la connectivité communautaire",
    "FAO World Food Forum 2026 Youth Research Prize: Funding Opportunity for Forest Restoration Innovation": "Prix Jeunes chercheurs FAO World Food Forum 2026 pour la restauration forestière",
    "MIT Solve 10 th Anniversary Global Challenge 2026: Scaling Solutions for a Better Future": "Challenge mondial MIT Solve 2026 pour solutions à fort impact",
    "MIT Solve – 10 th Anniversary Global Challenge (Solver Impact Fund)": "Challenge mondial MIT Solve - Solver Impact Fund",
    "National Geographic Climate Storytelling Grant 2026: Call for Proposals": "Subvention National Geographic 2026 pour récits climat",
    "FIFA Global Citizen Education Fund Applications Open for Grassroots Organizations Supporting Education and Sports – Apply By 28 May 2026": "Fonds FIFA Global Citizen Education pour organisations locales éducation et sport",
    "Sharjah Film Platform 2026: Short Film Production Grant for Filmmakers Worldwide": "Subvention Sharjah Film Platform 2026 pour production de courts métrages",
    "Inspiring Asia Micro Film Festival 2026: Global Call for Direct Film Submissions on Community Empowerment": "Appel Inspiring Asia Micro Film Festival 2026 pour films sur l'autonomisation communautaire",
    "Wellcome Accelerator Awards 2026: Up to £200,000 Research Funding for UK-Based Researchers": "Wellcome Accelerator Awards 2026 pour chercheurs basés au Royaume-Uni",
    "Challenge Zindi IA santé multilingue pour langues africaines": "Prix Zindi IA santé multilingue pour langues africaines",
    "Wellcome Accelerator Awards 2026 pour chercheurs sous-représentés au Royaume-Uni": "Prix Wellcome Accelerator 2026 pour chercheurs sous-représentés au Royaume-Uni",
    "Agog Open Call 2026: Up to $1M Funding for Climate Futures and Immersive Media Projects": "Appel Agog 2026 pour projets climat et médias immersifs",
    "Applications are Open: Connected Futures Cohort 2026 for U.S.-Based Social Impact Organisations": "Cohorte Connected Futures 2026 pour organisations à impact social",
    "Apply Now for the William A. Zoghbi Global Research Initiative – Upto $25, 000 in Funding": "Initiative de recherche William A. Zoghbi - financement jusqu'à 25 000 USD",
    "Apply for The Draper Richards Kaplan Foundation (DRK) Grants – Up to $300, 000 of Support": "Subventions Draper Richards Kaplan Foundation jusqu'à 300 000 USD",
    "Black Teacher Project Wellness Grant 2026: Supporting Black Educator Wellbeing and Educational Liberation": "Subvention Black Teacher Project Wellness 2026 pour le bien-être des éducateurs",
    "Call for Applications: Digital Energy Challenge 2026": "Appel à candidatures Digital Energy Challenge 2026",
    "Call for Applications: Forest Conservation Fund 2026": "Appel à candidatures Forest Conservation Fund 2026",
    "Call for Applications: NIHR Doctoral Award (Cohort 3) – Funding Opportunity": "Appel à candidatures NIHR Doctoral Award - cohorte 3",
    "Call for Applications: Reuters News Accelerator Program 2026 – A Career-Defining Opportunity for Mid-Career Journalists": "Programme Reuters News Accelerator 2026 pour journalistes confirmés",
    "Call for Applications: Subspace Foundation Grants Program for AI 3. 0 Innovation": "Programme de subventions Subspace Foundation pour l'innovation IA 3.0",
    "Change Makers Micro-grant Program: Round 3 Applications are Now open!": "Programme de micro-subventions Change Makers - cycle 3",
    "DIV Fund 2026 Request for Proposals: Funding for Innovations Tackling Global Poverty": "Fonds DIV 2026 pour innovations contre la pauvreté mondiale",
    "Driving Innovation for Impact: A Guide to the 2026 DIV Fund and How to Apply": "Guide du fonds DIV 2026 pour innovations à impact",
    "Elevate Prize 2027 Nominations Open – $300, 000 Funding for Global Social Impact Leaders": "Elevate Prize 2027 pour leaders mondiaux de l'impact social",
    "Funding Opportunity: Japanese Award for Most Innovative Development Project (MIDP) 2026": "Prix japonais MIDP 2026 pour projet de développement innovant",
    "Global Biodiversity Information Facility (GBIF) Graduate Researchers Award 2026 – €5, 000 Prize for Master’s and PhD Students in Biodiversity Research": "Prix GBIF 2026 pour jeunes chercheurs en biodiversité",
    "Heroes of Tomorrow: UN SDG Action Awards 2026": "UN SDG Action Awards 2026 - Heroes of Tomorrow",
    "Holohil Grant Program 2026: How Wildlife Researchers Can Get Funding for Conservation Tracking Projects": "Programme Holohil 2026 pour projets de suivi de la faune",
    "Next Wave Fund 2026: Technology Startup Accelerator and Crowdfunding Support Programme (Kickstarter & Google)": "Next Wave Fund 2026 pour startups technologiques et crowdfunding",
    "RELX Environmental Challenge 2026: $150,000 Global Innovation Prize for Water, Sanitation and Ocean Solutions": "RELX Environmental Challenge 2026 pour solutions eau, assainissement et océans",
    "Research Grant Schemes 2026: Advancing Human Rights and Peace in Southeast Asia": "Subventions de recherche 2026 pour droits humains et paix en Asie du Sud-Est",
    "SIPRA Challenge Fund Large Grants 2026": "Grandes subventions SIPRA Challenge Fund 2026",
    "TWAS–Fayzah M. Al-Kharafi Award 2026: Recognizing Women Scientists in Developing Countries": "Prix TWAS-Fayzah M. Al-Kharafi 2026 pour femmes scientifiques",
    "The Dana Foundation Opens 2026 Funding Applications for Locally Led Development Initiatives": "Financements 2026 de la Dana Foundation pour initiatives locales de développement",
    "Tolka Literary Journal Call for Submissions: Submit Original Non-Fiction Writing (€600 Payment Available)": "Appel à contributions Tolka Literary Journal pour textes non fictionnels",
    "Wellcome Launches Accelerator Awards 2026 for Black, Bangladeshi, and Pakistani Researchers in the UK": "Wellcome Accelerator Awards 2026 pour chercheurs sous-représentés au Royaume-Uni",
    "William T. Grant Foundation Opens 2026 Research Grants on Reducing Inequality in Youth Outcomes": "Subventions de recherche William T. Grant Foundation sur les inégalités des jeunes",
}


def _translate_title(device: Device) -> bool:
    current = clean_editorial_text(device.title or "")
    new_title = TITLE_MAP.get(current)
    if not new_title or new_title == current:
        return False
    device.title = new_title
    device.title_normalized = normalize_title(new_title)
    tags = list(device.tags or [])
    if "titre_francise" not in tags:
        tags.append("titre_francise")
    device.tags = tags
    analysis = dict(device.decision_analysis or {})
    analysis["title_cleanup"] = {
        "original_title": current,
        "title_fr_cleaned_at": datetime.now(timezone.utc).isoformat(),
        "source": "global_south_cleanup",
    }
    device.decision_analysis = analysis
    return True


def _hold_missing_date(device: Device) -> bool:
    if device.close_date is not None or device.validation_status == "pending_review":
        return False
    if device.status not in {"standby", "open"}:
        return False
    device.validation_status = "pending_review"
    tags = list(device.tags or [])
    for tag in ["source:global_south", "quality:missing_deadline", "needs_manual_deadline_check"]:
        if tag not in tags:
            tags.append(tag)
    device.tags = tags
    analysis = dict(device.decision_analysis or {})
    analysis.update(
        {
            "go_no_go": "a_verifier",
            "recommended_priority": "faible",
            "why_cautious": (
                "La source Global South Opportunities ne donne pas de date limite fiable dans les champs stockés. "
                "La fiche doit être vérifiée avant publication utilisateur."
            ),
            "recommended_action": "Vérifier la page officielle et confirmer l'échéance avant de recommander cette opportunité.",
        }
    )
    device.decision_analysis = analysis
    return True


def _mark_admin_only(device: Device, reason: str) -> bool:
    if device.validation_status == "admin_only":
        return False

    device.validation_status = "admin_only"
    tags = list(device.tags or [])
    for tag in ["source:global_south_admin_only", "visibility:admin_only", f"admin_only_reason:{reason}"]:
        if tag not in tags:
            tags.append(tag)
    device.tags = tags

    analysis = dict(device.decision_analysis or {})
    analysis.update(
        {
            "public_visibility": "admin_only",
            "admin_only_reason": reason,
            "go_no_go": "a_verifier",
            "recommended_priority": "faible",
            "why_cautious": (
                "La source Global South Opportunities donne un signal utile, mais la fiche doit etre qualifiee "
                "avant publication utilisateur."
            ),
            "recommended_action": "Verifier la page officielle, franciser le titre et confirmer l'echeance avant publication.",
        }
    )
    device.decision_analysis = analysis
    return True


def _should_be_admin_only(device: Device) -> str | None:
    title = clean_editorial_text(device.title or "")
    status = str(device.status or "").lower()
    device_type = str(device.device_type or "").lower()
    has_reliable_date = bool(device.close_date or device.is_recurring or status in {"expired", "closed", "recurring"})
    title_is_english = looks_english_title(title)
    generic_type = device_type in {"", "autre", "unknown"}
    tags_blob = unidecode(" ".join(device.tags or [])).lower()

    if title_is_english:
        return "english_title"
    if not has_reliable_date:
        return "missing_reliable_deadline"
    if status == "standby":
        return "standby_without_public_decision"
    if generic_type:
        return "generic_type"
    if "quality:english_content_remaining" in tags_blob:
        return "english_content"
    return None


async def run(dry_run: bool = True) -> dict[str, Any]:
    stats = {"seen": 0, "titles_changed": 0, "held_for_review": 0, "admin_only": 0}
    preview: list[dict[str, str | None]] = []

    async with AsyncSessionLocal() as db:
        source = (
            await db.execute(select(Source).where(Source.name == SOURCE_NAME))
        ).scalar_one()
        devices = (
            await db.execute(
                select(Device)
                .where(Device.source_id == source.id)
                .order_by(Device.title.asc())
            )
        ).scalars().all()

        for device in devices:
            stats["seen"] += 1
            before_title = device.title
            before_validation = device.validation_status
            title_changed = _translate_title(device)
            reason = _should_be_admin_only(device)
            hidden = _mark_admin_only(device, reason) if reason else False
            held = False if reason else _hold_missing_date(device)
            if title_changed:
                stats["titles_changed"] += 1
            if hidden:
                stats["admin_only"] += 1
            if held:
                stats["held_for_review"] += 1
            if (title_changed or held or hidden) and len(preview) < 80:
                preview.append(
                    {
                        "id": str(device.id),
                        "old_title": before_title,
                        "new_title": device.title,
                        "status": device.status,
                        "validation": f"{before_validation} -> {device.validation_status}",
                        "reason": reason,
                        "close_date": device.close_date.isoformat() if device.close_date else None,
                    }
                )

        if dry_run:
            await db.rollback()
        else:
            await db.commit()

    return {"dry_run": dry_run, "stats": stats, "preview": preview}


def main() -> None:
    parser = argparse.ArgumentParser(description="Nettoie Global South Opportunities.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(dry_run=not args.apply)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
