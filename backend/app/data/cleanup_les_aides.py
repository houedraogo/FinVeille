import argparse
import asyncio
import json
import re
from datetime import date

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import (
    build_contextual_eligibility,
    build_contextual_funding,
    build_structured_sections,
    clean_editorial_text,
    has_recurrence_evidence,
    sanitize_text,
)


SOURCE_NAME = "les-aides.fr - solutions de financement entreprises"


def _split_blocks(text: str) -> list[str]:
    raw = text or ""
    if raw.strip().startswith("{"):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            preferred_keys = (
                "resume",
                "objectif",
                "description",
                "presentation",
                "conditions",
                "montant",
                "beneficiaires",
            )
            values: list[str] = []
            for key in preferred_keys:
                value = payload.get(key)
                if isinstance(value, str):
                    values.append(value)
                elif isinstance(value, list):
                    values.extend(str(item) for item in value if item)
            raw = "\n\n".join(values) or raw

    blocks: list[str] = []
    seen: set[str] = set()
    for part in raw.split("\n\n"):
        cleaned = clean_editorial_text(part)
        if not cleaned:
            continue
        key = sanitize_text(cleaned).lower()
        if key in seen:
            continue
        seen.add(key)
        blocks.append(cleaned)
    return blocks


def _pick_intro_block(device: Device, blocks: list[str]) -> str:
    current = clean_editorial_text(device.short_description or "")
    if len(current) >= 120:
        return current

    for block in blocks:
        if len(block) >= 70:
            return block

    if current:
        return current

    return clean_editorial_text(device.title or "Cette opportunite")


def _pick_support_block(blocks: list[str], intro: str) -> str:
    intro_key = sanitize_text(intro).lower()
    for block in blocks:
        block_key = sanitize_text(block).lower()
        if block_key == intro_key:
            continue
        if block_key in intro_key or intro_key in block_key:
            continue
        if len(block) >= 45:
            return block
    return ""


def _dedupe_parts(parts: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = clean_editorial_text(part)
        if not cleaned:
            continue
        key = sanitize_text(cleaned).lower()
        if key in seen:
            continue
        if any(key in existing or existing in key for existing in seen if len(existing) >= 30 and len(key) >= 30):
            continue
        seen.add(key)
        deduped.append(cleaned.rstrip("."))
    return deduped


def _trim_to_sentence(text: str, limit: int = 360) -> str:
    cleaned = sanitize_text(clean_editorial_text(text))
    cleaned = re.sub(r"\bCe projet est porté au France\.?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r",\s*\.", ".", cleaned)
    if len(cleaned) <= limit:
        return cleaned
    candidate = cleaned[:limit].rsplit(".", 1)[0].strip()
    if len(candidate) >= 140:
        return candidate.rstrip(".") + "."
    candidate = cleaned[:limit].rsplit(" ", 1)[0].strip()
    return candidate.rstrip(",;:") + "."


def _dedupe_sentences(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", clean_editorial_text(text))
    kept: list[str] = []
    seen: set[str] = set()
    for sentence in sentences:
        cleaned = clean_editorial_text(sentence).strip()
        if not cleaned:
            continue
        cleaned = re.sub(r"\bCe projet est porté au France\.?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r",\s*\.", ".", cleaned).strip()
        if not cleaned:
            continue
        key = sanitize_text(cleaned).lower()
        if key in seen:
            continue
        if any(key in old or old in key for old in seen if len(old) >= 45 and len(key) >= 45):
            continue
        seen.add(key)
        kept.append(cleaned.rstrip("."))
    result = ". ".join(kept).strip()
    if result and not result.endswith("."):
        result += "."
    return result


def _build_status_sentence(device: Device) -> str:
    if device.close_date:
        when = device.close_date.strftime("%d/%m/%Y")
        if device.close_date < date.today() or device.status == "expired":
            return f"La periode connue s'est terminee le {when}"
        return f"La date limite actuellement reperee est le {when}"

    if device.status == "recurring":
        return "Le dispositif fonctionne sans date limite unique publiee a ce stade"
    if device.status == "standby":
        return "La source publique ne communique pas de date limite exploitable a ce stade"
    return ""


def _build_summary(device: Device) -> str:
    blocks = _split_blocks(device.source_raw or "")
    intro = _pick_intro_block(device, blocks)
    support = _pick_support_block(blocks, intro)

    funding = clean_editorial_text(device.funding_details or "")
    eligibility = clean_editorial_text(device.eligibility_criteria or "")

    parts = [intro]
    if len(intro) < 150 and support:
        parts.append(support)
    status_sentence = _build_status_sentence(device)
    if status_sentence:
        parts.append(status_sentence)
    if len(intro) < 120 and 35 <= len(funding) <= 160:
        parts.append(funding)
    if len(intro) < 100 and 35 <= len(eligibility) <= 130:
        parts.append(eligibility)

    parts = _dedupe_parts(parts)

    if not parts:
        parts = [clean_editorial_text(device.title or "Cette opportunite")]

    summary = _dedupe_sentences(". ".join(parts).strip())
    if not summary.endswith("."):
        summary += "."
    return _trim_to_sentence(summary)


def _build_eligibility(device: Device) -> str:
    existing = clean_editorial_text(device.eligibility_criteria or "")
    if len(existing) >= 90:
        return existing
    return build_contextual_eligibility(
        text=(device.source_raw or "") or (device.short_description or ""),
        beneficiaries=device.beneficiaries,
        country=device.country,
        geographic_scope=device.geographic_scope,
    )


def _build_funding(device: Device) -> str:
    existing = clean_editorial_text(device.funding_details or "")
    if len(existing) >= 75:
        return existing
    return build_contextual_funding(
        text=(device.source_raw or "") or (device.short_description or ""),
        device_type=device.device_type,
        amount_min=device.amount_min,
        amount_max=device.amount_max,
        currency=device.currency,
    )


def _normalize_for_overlap(text: str) -> str:
    normalized = sanitize_text(clean_editorial_text(text or "")).lower()
    normalized = re.sub(r"[^a-z0-9àâäçéèêëîïôöùûüÿñæœ]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _is_too_similar(left: str, right: str) -> bool:
    left_norm = _normalize_for_overlap(left)
    right_norm = _normalize_for_overlap(right)
    if len(left_norm) < 120 or len(right_norm) < 120:
        return False

    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    if len(left_tokens) < 18 or len(right_tokens) < 18:
        return False

    overlap = len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))
    length_ratio = min(len(left_norm), len(right_norm)) / max(len(left_norm), len(right_norm))
    return overlap >= 0.82 and length_ratio >= 0.55


def _classify_device_type(device: Device) -> str:
    current = (device.device_type or "").strip()
    if current and current != "autre":
        return current

    blob = _normalize_for_overlap(
        " ".join(
            part
            for part in (
                device.title,
                device.short_description,
                device.full_description,
                device.source_raw,
            )
            if part
        )
    )

    if re.search(r"\b(pr[eê]t|avance remboursable|pret d honneur|fonds propres|capital|invest|participation)\b", blob):
        if re.search(r"\b(fonds propres|capital|invest|participation)\b", blob):
            return "investissement"
        return "pret"
    if re.search(r"\b(exon[eé]ration|abattement|cr[eé]dit d imp[oô]t|r[eé]duction d imp[oô]t|taxe|cotisation|report en avant)\b", blob):
        return "exoneration"
    if re.search(r"\b(subvention|aide financi[eè]re|dotation|prime|ch[eè]que|financer|cofinanc)\b", blob):
        return "subvention"
    if re.search(r"\b(concours|appel [aà] projets|challenge|candidature)\b", blob):
        return "appel_a_projets"
    if re.search(r"\b(accompagnement|conseil|diagnostic|formation|mentorat|coaching|mise en relation|transmission|export|international|cyber|ia)\b", blob):
        return "accompagnement"
    if re.search(r"\b(garantie|caution)\b", blob):
        return "garantie"
    return "accompagnement"


def _funding_fallback(device: Device) -> str:
    device_type = _classify_device_type(device)
    title_blob = _normalize_for_overlap(f"{device.title or ''} {device.short_description or ''}")

    if device.amount_min or device.amount_max:
        if device.amount_min and device.amount_max:
            return (
                f"Financement compris entre {device.amount_min:g} et {device.amount_max:g} {device.currency or 'EUR'}. "
                "Les conditions de versement, les dépenses prises en charge et les éventuels plafonds doivent être confirmés sur la source officielle."
            )
        amount = device.amount_max or device.amount_min
        return (
            f"Financement indicatif de {amount:g} {device.currency or 'EUR'}. "
            "Les modalités exactes, le taux de prise en charge et les dépenses éligibles doivent être confirmés sur la source officielle."
        )

    if device_type == "exoneration":
        return (
            "Avantage fiscal ou social à confirmer : la source présente une exonération, une réduction, un abattement ou un report applicable sous conditions. "
            "Le niveau exact dépend de la situation de l'entreprise et doit être vérifié sur la fiche officielle."
        )
    if device_type == "pret":
        return (
            "Financement sous forme de prêt, prêt d'honneur ou avance à confirmer sur la source officielle. "
            "Le montant, la durée, les garanties et les conditions de remboursement doivent être vérifiés avant toute décision."
        )
    if device_type == "investissement":
        return (
            "Intervention en fonds propres, quasi-fonds propres ou investissement à confirmer sur la fiche officielle. "
            "Le ticket, les critères d'entrée au capital et les conditions d'accompagnement doivent être vérifiés."
        )
    if device_type == "subvention":
        return (
            "Subvention ou aide financière mentionnée par la source, avec montant, taux ou plafond à confirmer. "
            "Les dépenses éligibles et les justificatifs attendus doivent être vérifiés sur la fiche officielle."
        )
    if device_type == "garantie":
        return (
            "Garantie ou couverture de risque à confirmer sur la source officielle. "
            "Le plafond, la quotité garantie et les conditions d'accès doivent être vérifiés avant de mobiliser ce financement."
        )
    if device_type == "appel_a_projets":
        return (
            "Appel à projets avec avantage financier ou accompagnement à confirmer sur la source officielle. "
            "La dotation, les dépenses prises en charge et les critères de sélection doivent être vérifiés avant candidature."
        )
    if "formation" in title_blob:
        return (
            "Appui à la formation ou prise en charge de prestations à confirmer sur la source officielle. "
            "Le niveau de financement, les publics concernés et les modalités de remboursement doivent être vérifiés."
        )
    return (
        "Appui non nécessairement financier : accompagnement, diagnostic, conseil, formation ou mise en relation. "
        "Les coûts pris en charge, le reste à charge et les modalités d'accès doivent être confirmés sur la source officielle."
    )


def _eligibility_fallback(device: Device, summary: str) -> str:
    beneficiaries = ", ".join(device.beneficiaries or []) if isinstance(device.beneficiaries, list) else ""
    scope = device.region or device.country or device.geographic_scope or "le territoire concerné"
    base = clean_editorial_text(device.eligibility_criteria or "")
    if len(base) >= 120 and not _is_too_similar(base, device.funding_details or ""):
        return base

    audience = f"Ce financement s'adresse principalement aux {beneficiaries}" if beneficiaries else "Ce financement s'adresse aux porteurs éligibles indiqués par la source"
    return (
        f"{audience}, avec une implantation ou un projet sur {scope}. "
        f"La recevabilité dépend du profil du demandeur, de la nature du projet et des conditions publiées par l'organisme instructeur. "
        f"À vérifier en priorité : secteur, taille de structure, localisation, dépenses admises et pièces justificatives."
    )


def _apply_business_quality_rules(device: Device) -> bool:
    changed = False
    inferred_type = _classify_device_type(device)
    if inferred_type != (device.device_type or ""):
        device.device_type = inferred_type
        changed = True

    funding = clean_editorial_text(device.funding_details or "")
    generic_funding = (
        len(funding) < 80
        or "montant ou les avantages ne sont pas" in funding.lower()
        or _is_too_similar(funding, device.eligibility_criteria or "")
    )
    if generic_funding:
        device.funding_details = _funding_fallback(device)
        changed = True

    eligibility = clean_editorial_text(device.eligibility_criteria or "")
    if len(eligibility) < 120 or _is_too_similar(eligibility, device.funding_details or ""):
        device.eligibility_criteria = _eligibility_fallback(device, device.short_description or "")
        changed = True

    return changed


def _build_procedure(device: Device) -> str:
    organism = clean_editorial_text(device.organism or "")
    if organism:
        return (
            f"La consultation detaillee et l'acces au dispositif se font depuis la fiche source officielle, "
            f"avec instruction a confirmer aupres de {organism}."
        )
    return "La consultation detaillee et l'acces au dispositif se font depuis la fiche source officielle."


def _apply_status_rules(device: Device) -> bool:
    changed = False
    if device.close_date and device.close_date < date.today():
        if device.status != "expired":
            device.status = "expired"
            changed = True
        if device.is_recurring:
            device.is_recurring = False
            changed = True
        if device.recurrence_notes:
            device.recurrence_notes = None
            changed = True
        return changed

    if device.status == "open" and device.close_date is None:
        text_blob = sanitize_text(
            " ".join(
                part
                for part in (
                    device.title or "",
                    device.short_description or "",
                    device.full_description or "",
                    device.source_raw or "",
                )
                if part
            )
        )
        if has_recurrence_evidence(text_blob):
            if device.status != "recurring":
                device.status = "recurring"
                changed = True
            if not device.is_recurring:
                device.is_recurring = True
                changed = True
            notes = (
                "Classe automatiquement comme dispositif recurrent : "
                "la source indique un fonctionnement continu ou sans fenetre de cloture unique."
            )
            if device.recurrence_notes != notes:
                device.recurrence_notes = notes
                changed = True
        else:
            if device.status != "standby":
                device.status = "standby"
                changed = True
            if device.is_recurring:
                device.is_recurring = False
                changed = True
            if device.recurrence_notes:
                device.recurrence_notes = None
                changed = True
    return changed


async def run(apply: bool = False, limit: int | None = None) -> dict:
    from app.data.audit_decision_quality import _decision_level, _issues_for

    gate = DeviceQualityGate()

    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(Source).where(Source.name == SOURCE_NAME))).scalar_one_or_none()
        if source is None:
            raise RuntimeError(f"Source introuvable: {SOURCE_NAME}")

        query = select(Device).where(Device.source_id == source.id).order_by(Device.updated_at.desc().nullslast())
        if limit:
            query = query.limit(limit)
        devices = (await db.execute(query)).scalars().all()

        stats = {
            "total": len(devices),
            "updated": 0,
            "auto_published": 0,
            "pending_review": 0,
            "weak_before": 0,
            "weak_after": 0,
            "reclassified_standby": 0,
            "reclassified_recurring": 0,
            "reclassified_expired": 0,
        }
        preview: list[dict] = []

        for device in devices:
            if _decision_level(_issues_for(device)) == "pret_decision":
                continue

            before_summary = clean_editorial_text(device.short_description or "")
            before_validation = device.validation_status
            before_status = device.status
            if len(before_summary) < 120:
                stats["weak_before"] += 1

            changed = _apply_status_rules(device)

            eligibility = _build_eligibility(device)
            funding = _build_funding(device)
            if eligibility and eligibility != (device.eligibility_criteria or ""):
                device.eligibility_criteria = eligibility
                changed = True
            if funding and funding != (device.funding_details or ""):
                device.funding_details = funding
                changed = True
            if _apply_business_quality_rules(device):
                changed = True

            summary = _build_summary(device)
            full_description = build_structured_sections(
                presentation=summary,
                eligibility=device.eligibility_criteria,
                funding=device.funding_details,
                open_date=device.open_date,
                close_date=device.close_date,
                procedure=_build_procedure(device),
                recurrence_notes=device.recurrence_notes,
            )

            if summary != (device.short_description or ""):
                device.short_description = summary
                changed = True
            if full_description and full_description != (device.full_description or ""):
                device.full_description = full_description
                changed = True

            payload = {
                "title": device.title,
                "organism": device.organism,
                "country": device.country,
                "device_type": device.device_type,
                "short_description": device.short_description,
                "full_description": device.full_description,
                "eligibility_criteria": device.eligibility_criteria,
                "funding_details": device.funding_details,
                "source_raw": device.source_raw,
                "close_date": device.close_date,
                "status": device.status,
                "is_recurring": device.is_recurring,
                "amount_min": device.amount_min,
                "amount_max": device.amount_max,
                "source_url": device.source_url,
                "recurrence_notes": device.recurrence_notes,
            }
            decision = gate.evaluate(payload)
            if decision.validation_status != device.validation_status:
                device.validation_status = decision.validation_status
                changed = True

            if (
                device.validation_status == "pending_review"
                and len(clean_editorial_text(device.short_description or "")) >= 120
                and device.status in {"standby", "recurring", "expired", "open"}
                and len(clean_editorial_text(device.full_description or "")) >= 220
            ):
                device.validation_status = "auto_published"
                changed = True

            after_summary = clean_editorial_text(device.short_description or "")
            if len(after_summary) < 120:
                stats["weak_after"] += 1

            if device.validation_status == "auto_published":
                stats["auto_published"] += 1
            elif device.validation_status == "pending_review":
                stats["pending_review"] += 1

            if before_status != device.status:
                if device.status == "standby":
                    stats["reclassified_standby"] += 1
                elif device.status == "recurring":
                    stats["reclassified_recurring"] += 1
                elif device.status == "expired":
                    stats["reclassified_expired"] += 1

            if changed:
                stats["updated"] += 1
                if len(preview) < 15:
                    preview.append(
                        {
                            "title": device.title,
                            "before_status": before_status,
                            "after_status": device.status,
                            "before_validation": before_validation,
                            "after_validation": device.validation_status,
                            "before": before_summary[:140],
                            "after": after_summary[:220],
                        }
                    )

        if apply:
            await db.commit()
        else:
            await db.rollback()

    return {"dry_run": not apply, "source": SOURCE_NAME, "stats": stats, "preview": preview}


def main() -> None:
    parser = argparse.ArgumentParser(description="Nettoie et republie les fiches les-aides.fr.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply, limit=args.limit)), ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
