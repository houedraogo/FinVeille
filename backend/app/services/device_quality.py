from dataclasses import dataclass
from typing import Any

from app.utils.text_utils import clean_editorial_text, looks_english_text


@dataclass(frozen=True)
class QualityDecision:
    decision: str
    validation_status: str
    score: int
    reasons: list[str]


class DeviceQualityGate:
    """Décide si une fiche peut être publiée automatiquement ou non."""

    def evaluate(self, device: dict[str, Any]) -> QualityDecision:
        reasons: list[str] = []

        short_description = clean_editorial_text(device.get("short_description") or "")
        full_description = clean_editorial_text(device.get("full_description") or "")
        eligibility_criteria = clean_editorial_text(device.get("eligibility_criteria") or "")
        funding_details = clean_editorial_text(device.get("funding_details") or "")
        status = str(device.get("status") or "open").lower()
        is_recurring = bool(device.get("is_recurring"))

        score = 0

        summary_ok = len(short_description) >= 90
        if summary_ok:
            score += 25
        else:
            reasons.append("summary_too_short")

        full_ok = len(full_description) >= 220
        if full_ok:
            score += 25
        else:
            reasons.append("full_description_too_short")

        criteria_ok = len(eligibility_criteria) >= 70
        if criteria_ok:
            score += 20
        else:
            reasons.append("missing_eligibility_criteria")

        reliable_status = bool(device.get("close_date")) or is_recurring or status in {"standby", "closed", "expired", "recurring"}
        if reliable_status:
            score += 20
        else:
            reasons.append("no_reliable_status_or_close_date")

        amount_ok = bool(device.get("amount_min") or device.get("amount_max"))
        confirm_signal = "confirmer" in funding_details.lower() or "confirm" in funding_details.lower()
        if amount_ok or confirm_signal or len(funding_details) >= 45:
            score += 10
        else:
            reasons.append("missing_funding_signal")

        still_english = any(
            looks_english_text(value)
            for value in (short_description, full_description)
            if value
        )
        if still_english:
            reasons.append("english_content_remaining")

        if not short_description or not device.get("title") or not device.get("source_url"):
            return QualityDecision(
                decision="reject",
                validation_status="rejected",
                score=score,
                reasons=["missing_required_fields", *reasons],
            )

        if score < 45:
            return QualityDecision(
                decision="reject",
                validation_status="rejected",
                score=score,
                reasons=reasons,
            )

        if status == "open" and not device.get("close_date") and not is_recurring:
            reasons.append("open_without_close_date")
            return QualityDecision(
                decision="pending_review",
                validation_status="pending_review",
                score=score,
                reasons=reasons,
            )

        if still_english:
            return QualityDecision(
                decision="pending_review",
                validation_status="pending_review",
                score=score,
                reasons=reasons,
            )

        if score < 70:
            return QualityDecision(
                decision="pending_review",
                validation_status="pending_review",
                score=score,
                reasons=reasons,
            )

        return QualityDecision(
            decision="publish",
            validation_status="auto_published",
            score=score,
            reasons=reasons,
        )
