from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness


LOCAL_MODEL = "local-final-decision-cleanup-v1"


def _section(key: str, title: str, content: str, confidence: int = 78) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "content": clean_editorial_text(content),
        "confidence": confidence,
        "source": "final_decision_cleanup",
    }


def _sections(
    *,
    presentation: str,
    eligibility: str,
    funding: str,
    calendar: str,
    procedure: str,
    checks: str,
) -> list[dict[str, Any]]:
    return [
        _section("presentation", "Présentation", presentation, 84),
        _section("eligibility", "Critères d'éligibilité", eligibility, 78),
        _section("funding", "Montant / avantages", funding, 76),
        _section("calendar", "Calendrier", calendar, 80),
        _section("procedure", "Démarche", procedure, 76),
        _section("checks", "Points à vérifier", checks, 72),
    ]


def _apply_asnom(device: Device) -> bool:
    if device.title != "ASNOM/FSSN - appel a projets sante locale 2027":
        return False

    presentation = (
        "L'appel à projets ASNOM/FSSN soutient des initiatives locales dans le domaine de la santé, "
        "notamment des projets de terrain portés par des structures capables d'intervenir auprès de publics fragiles."
    )
    eligibility = (
        "La fiche vise principalement des associations, organisations locales ou porteurs de projets santé. "
        "Les conditions exactes, les zones d'intervention et les pièces attendues doivent être confirmées sur la page officielle."
    )
    funding = (
        "Le montant de l'aide n'est pas publié de façon suffisamment précise dans les données disponibles. "
        "Il doit être vérifié auprès de l'ASNOM/FSSN avant toute préparation de dossier."
    )
    calendar = "Date limite identifiée : 30/05/2026."
    procedure = (
        "Consulter la source officielle, vérifier le règlement de l'appel et préparer le dossier selon les consignes publiées."
    )
    checks = "Confirmer le montant, les critères détaillés, le périmètre géographique et les documents demandés."
    sections = _sections(
        presentation=presentation,
        eligibility=eligibility,
        funding=funding,
        calendar=calendar,
        procedure=procedure,
        checks=checks,
    )

    device.short_description = presentation
    device.full_description = build_structured_sections(
        presentation=presentation,
        eligibility=eligibility,
        funding=funding,
        close_date=date(2026, 5, 30),
        procedure=procedure,
    )
    device.content_sections_json = sections
    device.ai_rewritten_sections_json = sections
    device.ai_rewrite_status = "done"
    device.ai_rewrite_model = LOCAL_MODEL
    device.ai_rewrite_checked_at = datetime.now(timezone.utc)
    device.close_date = date(2026, 5, 30)
    device.status = "open"
    device.validation_status = "auto_published"
    device.ai_readiness_score = max(device.ai_readiness_score or 0, 82)
    device.ai_readiness_label = "pret_pour_recommandation_ia"
    device.ai_readiness_reasons = ["résumé exploitable", "date limite connue", "points à vérifier explicites"]
    return True


def _apply_global_south(device: Device) -> bool:
    changed = False
    now = datetime.now(timezone.utc)

    if device.title == "Subventions de recherche RWJF Health Equity 2026":
        device.status = "expired"
        device.validation_status = "auto_published"
        presentation = (
            "Cette opportunité de recherche RWJF Health Equity est conservée comme appel expiré : "
            "la date limite repérée est passée. Elle ne doit plus être recommandée comme action immédiate."
        )
        eligibility = (
            "L'appel ciblait des équipes ou structures de recherche travaillant sur les inégalités de santé. "
            "Les critères détaillés doivent être consultés dans l'archive de la source officielle."
        )
        funding = clean_editorial_text(device.funding_details or "") or (
            "Le montant ou les avantages doivent être vérifiés sur la source officielle."
        )
        sections = _sections(
            presentation=presentation,
            eligibility=eligibility,
            funding=funding,
            calendar="Clôture passée : 14/05/2026.",
            procedure="Ne pas engager de candidature sans vérifier qu'une nouvelle session a été publiée.",
            checks="Surveiller une éventuelle prochaine édition avant de la remettre en opportunité active.",
        )
        device.short_description = presentation
        device.full_description = build_structured_sections(
            presentation=presentation,
            eligibility=eligibility,
            funding=funding,
            close_date=device.close_date,
            procedure="Surveiller une prochaine édition sur la source officielle.",
        )
        device.content_sections_json = sections
        device.ai_rewritten_sections_json = sections
        device.ai_rewrite_status = "done"
        device.ai_rewrite_model = LOCAL_MODEL
        device.ai_rewrite_checked_at = now
        device.ai_readiness_score = min(device.ai_readiness_score or 70, 70)
        device.ai_readiness_label = "utilisable_avec_prudence"
        device.ai_readiness_reasons = ["appel expiré", "utile en veille uniquement"]
        changed = True

    if device.title == "William T. Grant Foundation Opens 2026 Research Grants on Reducing Inequality in Youth Outcomes":
        presentation = (
            "Cette subvention de recherche soutient des travaux sur la réduction des inégalités dans les parcours des jeunes. "
            "Elle reste à vérifier avant recommandation, car la source ne permet pas encore de confirmer une fenêtre claire et actionnable."
        )
        eligibility = (
            "Elle concerne principalement des chercheurs, institutions académiques ou équipes de recherche. "
            "Les critères précis, pays éligibles et conditions de candidature doivent être confirmés sur la source officielle."
        )
        funding = clean_editorial_text(device.funding_details or "") or (
            "Montant ou avantages à confirmer sur la source officielle."
        )
        sections = _sections(
            presentation=presentation,
            eligibility=eligibility,
            funding=funding,
            calendar="Date limite non confirmée dans les données actuellement exploitables.",
            procedure="Vérifier la page officielle avant de l'ajouter à une liste de candidatures prioritaires.",
            checks="Confirmer l'éligibilité géographique, la date limite, le montant et le règlement de candidature.",
        )
        device.status = "standby"
        device.validation_status = "pending_review"
        device.short_description = presentation
        device.full_description = build_structured_sections(
            presentation=presentation,
            eligibility=eligibility,
            funding=funding,
            procedure="Vérifier la source officielle avant décision.",
        )
        device.content_sections_json = sections
        device.ai_rewritten_sections_json = sections
        device.ai_rewrite_status = "needs_review"
        device.ai_rewrite_model = LOCAL_MODEL
        device.ai_rewrite_checked_at = now
        device.ai_readiness_score = 62
        device.ai_readiness_label = "utilisable_avec_prudence"
        device.ai_readiness_reasons = ["date à confirmer", "source éditoriale", "revue manuelle nécessaire"]
        changed = True

    if device.title == "Carnegie Mellon University Africa Launches 2026 Business Incubation Program for African Tech Startups":
        presentation = (
            "Ce programme d'incubation accompagne des startups technologiques africaines dans la structuration de leur projet, "
            "leur accès au marché et leur préparation à la croissance."
        )
        eligibility = (
            "Il cible principalement des startups ou entrepreneurs tech africains. Les critères détaillés, pays éligibles "
            "et modalités de candidature doivent être confirmés sur la page officielle du programme."
        )
        funding = clean_editorial_text(device.funding_details or "") or (
            "L'appui prend surtout la forme d'un accompagnement. Les éventuels avantages financiers doivent être confirmés sur la source officielle."
        )
        sections = _sections(
            presentation=presentation,
            eligibility=eligibility,
            funding=funding,
            calendar=(
                f"Date limite repérée : {device.close_date:%d/%m/%Y}."
                if device.close_date
                else "Date limite à confirmer sur la source officielle."
            ),
            procedure="Consulter la page officielle, vérifier l'éligibilité et suivre le parcours de candidature indiqué.",
            checks="Confirmer la date limite, le périmètre géographique, les critères et les livrables attendus.",
        )
        device.short_description = presentation
        device.content_sections_json = sections
        device.ai_rewritten_sections_json = sections
        device.ai_rewrite_status = "done"
        device.ai_rewrite_model = LOCAL_MODEL
        device.ai_rewrite_checked_at = now
        changed = True

    if device.title == "Wellcome Accelerator Awards 2026: Up to £200,000 Research Funding for UK-Based Researchers":
        presentation = (
            "Les Wellcome Accelerator Awards soutiennent des projets de recherche à fort potentiel dans le domaine de la santé. "
            "Cette fiche est utile en veille, mais l'éligibilité semble centrée sur des chercheurs ou structures basées au Royaume-Uni."
        )
        eligibility = (
            "L'opportunité vise principalement des chercheurs, équipes académiques ou institutions de recherche répondant aux critères Wellcome. "
            "L'éligibilité géographique et institutionnelle doit être vérifiée avant toute recommandation à un utilisateur africain."
        )
        funding = (
            "Le financement annoncé peut aller jusqu'à 200 000 GBP selon la source. Le montant exact, les dépenses éligibles et les conditions "
            "d'attribution doivent être confirmés sur la page officielle."
        )
        sections = _sections(
            presentation=presentation,
            eligibility=eligibility,
            funding=funding,
            calendar="Fenêtre ou prochaine session à confirmer sur la source officielle.",
            procedure="Vérifier l'éligibilité sur la page officielle Wellcome avant d'ajouter cette piste à une sélection prioritaire.",
            checks="Confirmer le pays éligible, le statut du candidat, la date limite et le règlement complet.",
        )
        device.short_description = presentation
        device.content_sections_json = sections
        device.ai_rewritten_sections_json = sections
        device.ai_rewrite_status = "done"
        device.ai_rewrite_model = LOCAL_MODEL
        device.ai_rewrite_checked_at = now
        changed = True

    return changed


async def run() -> dict[str, Any]:
    titles = [
        "ASNOM/FSSN - appel a projets sante locale 2027",
        "Subventions de recherche RWJF Health Equity 2026",
        "William T. Grant Foundation Opens 2026 Research Grants on Reducing Inequality in Youth Outcomes",
        "Carnegie Mellon University Africa Launches 2026 Business Incubation Program for African Tech Startups",
        "Wellcome Accelerator Awards 2026: Up to £200,000 Research Funding for UK-Based Researchers",
    ]
    stats = {"scanned": 0, "updated": 0, "preview": []}
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .where(Device.title.in_(titles))
            )
        ).scalars().all()

        for device in devices:
            stats["scanned"] += 1
            before = {
                "title": device.title,
                "status": device.status,
                "validation": device.validation_status,
                "short": clean_editorial_text(device.short_description or "")[:120],
            }
            changed = _apply_asnom(device) or _apply_global_south(device)
            if changed:
                device.completeness_score = compute_completeness(
                    {column.name: getattr(device, column.name) for column in Device.__table__.columns}
                )
                device.updated_at = datetime.now(timezone.utc)
                stats["updated"] += 1
                stats["preview"].append(
                    {
                        "before": before,
                        "after": {
                            "status": device.status,
                            "validation": device.validation_status,
                            "short": clean_editorial_text(device.short_description or "")[:180],
                        },
                    }
                )

        await db.commit()

    return stats


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
