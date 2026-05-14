from __future__ import annotations

import asyncio
import json
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.data.audit_decision_quality import _decision_level, _issues_for
from app.database import AsyncSessionLocal
from app.models.device import Device


async def run() -> dict:
    async with AsyncSessionLocal() as db:
        devices = (
            await db.execute(
                select(Device)
                .options(selectinload(Device.source))
                .where(Device.validation_status != "rejected")
                .order_by(Device.updated_at.desc())
            )
        ).scalars().all()

    issue_counts: Counter[str] = Counter()
    rows: list[dict] = []
    for device in devices:
        issues = _issues_for(device)
        residuals = [issue for issue in issues if issue in {"reformulation_ia_absente", "texte_trop_long"}]
        if not residuals:
            continue
        issue_counts.update(residuals)
        rows.append(
            {
                "id": str(device.id),
                "title": device.title,
                "source": device.source.name if device.source else "Sans source",
                "status": device.status,
                "type": device.device_type,
                "decision_level": _decision_level(issues),
                "issues": residuals,
                "full_len": len(device.full_description or ""),
                "has_ai_rewrite": bool(device.ai_rewritten_sections_json),
            }
        )

    return {"issue_counts": dict(issue_counts), "items": rows}


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
