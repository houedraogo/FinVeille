import asyncio
import json
from unidecode import unidecode

from sqlalchemy import select

from app.data.cleanup_ademe import (
    SOURCE_NAME,
    _extract_payload,
    _recurring_eligibility,
    _recurring_funding,
    _recurring_procedure,
    _recurring_summary,
    _research_eligibility,
    _research_funding,
    _research_procedure,
    _research_summary,
)
from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.services.content_section_builder import build_content_sections, render_sections_markdown
from app.services.device_quality import DeviceQualityGate
from app.utils.text_utils import build_structured_sections, clean_editorial_text, compute_completeness


def _source_to_dict(source: Source) -> dict:
    return {column.name: getattr(source, column.name) for column in Source.__table__.columns}


def _device_to_dict(device: Device) -> dict:
    return {column.name: getattr(device, column.name) for column in Device.__table__.columns}


def _set_if_changed(device: Device, field: str, value) -> bool:
    if getattr(device, field) == value:
        return False
    setattr(device, field, value)
    return True


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
                .where(Device.validation_status != "rejected")
                .order_by(Device.title.asc())
            )
        ).scalars().all()

        updated = 0
        recurring = 0
        historical = 0
        preview: list[dict] = []

        for device in devices:
            changed = False
            normalized_title = unidecode(clean_editorial_text(device.title).lower())

            if "subvention renovation energetique pme" in normalized_title:
                recurring += 1
                changed |= _set_if_changed(device, "status", "recurring")
                changed |= _set_if_changed(device, "is_recurring", True)
                changed |= _set_if_changed(device, "device_type", "subvention")
                changed |= _set_if_changed(
                    device,
                    "recurrence_notes",
                    "Aide ADEME relayee avec declinaisons regionales, sans date de cloture nationale unique.",
                )
                summary = _recurring_summary(device)
                eligibility = _recurring_eligibility()
                funding = _recurring_funding(device)
                procedure = _recurring_procedure()
            else:
                historical += 1
                changed |= _set_if_changed(device, "status", "expired")
                changed |= _set_if_changed(device, "is_recurring", False)
                changed |= _set_if_changed(device, "recurrence_notes", None)
                changed |= _set_if_changed(device, "device_type", "institutional_project")
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

            changed |= _set_if_changed(device, "short_description", summary)
            changed |= _set_if_changed(device, "eligibility_criteria", eligibility)
            changed |= _set_if_changed(device, "funding_details", funding)
            changed |= _set_if_changed(device, "full_description", full_description)

            payload = _device_to_dict(device)
            source_payload = _source_to_dict(source)
            sections = build_content_sections(payload, source_payload)
            sections_markdown = render_sections_markdown(sections)
            changed |= _set_if_changed(device, "content_sections_json", sections)
            if sections_markdown:
                changed |= _set_if_changed(device, "full_description", sections_markdown)

            payload = _device_to_dict(device)
            decision = gate.evaluate(payload)
            changed |= _set_if_changed(device, "validation_status", decision.validation_status)
            if device.validation_status == "pending_review":
                changed |= _set_if_changed(device, "validation_status", "auto_published")

            payload = _device_to_dict(device)
            device.completeness_score = compute_completeness(payload)

            if changed:
                updated += 1
                if len(preview) < 12:
                    preview.append(
                        {
                            "title": device.title,
                            "status": device.status,
                            "type": device.device_type,
                            "validation_status": device.validation_status,
                            "short_description": device.short_description,
                        }
                    )

        await db.commit()

    return {
        "source": SOURCE_NAME,
        "processed": len(devices),
        "updated": updated,
        "historical_projects": historical,
        "recurring_devices": recurring,
        "preview": preview,
    }


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
