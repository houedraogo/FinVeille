from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from unidecode import unidecode

from app.utils.text_utils import has_recurrence_evidence, sanitize_text


@dataclass(frozen=True)
class DeadlineClassification:
    key: str
    status: str | None
    is_recurring: bool | None
    validation_status: str | None
    tag: str
    note: str
    confidence: int


def _text_blob(device: dict[str, Any]) -> str:
    return sanitize_text(
        " ".join(
            str(device.get(field) or "")
            for field in (
                "title",
                "organism",
                "device_type",
                "short_description",
                "full_description",
                "eligibility_criteria",
                "funding_details",
                "recurrence_notes",
                "source_raw",
            )
        )
    )


def _has_unknown_deadline_signal(text: str) -> bool:
    sample = f" {unidecode(text.lower())} "
    return any(
        marker in sample
        for marker in (
            " cloture non communiquee ",
            " date limite non communiquee ",
            " sans date limite communiquee ",
            " aucune date limite communiquee ",
            " calendrier non communique ",
            " deadline not specified ",
            " no deadline specified ",
        )
    )


def classify_deadline(device: dict[str, Any], *, today: date | None = None) -> DeadlineClassification:
    """Classifie l'etat de cloture sans inventer de date.

    Cette classification est volontairement explicite pour l'IA: une absence de
    date n'a pas la meme signification selon qu'il s'agit d'un dispositif
    permanent, d'un projet institutionnel ou d'une fiche a verifier.
    """

    today = today or date.today()
    close_date = device.get("close_date")
    status = str(device.get("status") or "").lower()
    device_type = str(device.get("device_type") or "").lower()
    is_recurring = bool(device.get("is_recurring"))
    text = _text_blob(device)

    if close_date:
        parsed = close_date
        if not isinstance(parsed, date):
            parsed = date.fromisoformat(str(parsed)[:10])
        if parsed < today:
            return DeadlineClassification(
                key="expired",
                status="expired",
                is_recurring=False,
                validation_status=None,
                tag="deadline:expired",
                note="Date de cloture connue et depassee.",
                confidence=95,
            )
        return DeadlineClassification(
            key="known",
            status="open",
            is_recurring=False,
            validation_status=None,
            tag="deadline:known",
            note="Date limite connue et exploitable.",
            confidence=95,
        )

    if status in {"expired", "closed"}:
        return DeadlineClassification(
            key="expired_without_date",
            status=status,
            is_recurring=False,
            validation_status=None,
            tag="deadline:expired",
            note="Fiche cloturee ou expiree sans date exploitable conservee.",
            confidence=75,
        )

    if is_recurring or status == "recurring" or (
        has_recurrence_evidence(text) and not _has_unknown_deadline_signal(text)
    ):
        return DeadlineClassification(
            key="permanent",
            status="recurring",
            is_recurring=True,
            validation_status=None,
            tag="deadline:permanent",
            note="Dispositif permanent ou recurrent, sans fenetre de cloture unique.",
            confidence=85,
        )

    if device_type == "institutional_project":
        return DeadlineClassification(
            key="institutional_project",
            status="standby",
            is_recurring=False,
            validation_status="pending_review",
            tag="deadline:institutional_project",
            note=(
                "Projet institutionnel sans date de candidature exploitable. "
                "Ne pas le traiter comme un appel ouvert classique."
            ),
            confidence=80,
        )

    if _has_unknown_deadline_signal(text) or status == "standby":
        return DeadlineClassification(
            key="not_communicated",
            status="standby",
            is_recurring=False,
            validation_status="pending_review",
            tag="deadline:not_communicated",
            note="Date limite non communiquee par la source: verification manuelle requise.",
            confidence=70,
        )

    return DeadlineClassification(
        key="needs_review",
        status="standby",
        is_recurring=False,
        validation_status="pending_review",
        tag="deadline:needs_review",
        note="Date de cloture absente et nature de l'absence non qualifiee.",
        confidence=45,
    )
