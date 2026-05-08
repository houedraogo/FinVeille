"""
Ajoute la source I&P dans la base si elle n'existe pas deja.

Usage : docker exec finveille-backend python -m app.data.add_ietp_source
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.source import Source


IETP_SOURCE = {
    "name": "I&P - soumettre votre business plan",
    "organism": "Investisseurs & Partenaires",
    "country": "Afrique",
    "source_type": "fonds_prive",
    "category": "private",
    "level": 1,
    "reliability": 4,
    "url": "https://www.ietp.com/en/content/submit-your-business-plan",
    "collection_mode": "html",
    "check_frequency": "weekly",
    "is_active": True,
    "config": {
        "source_kind": "single_program_page",
        "list_selector": "html",
        "item_title_selector": "title, h1",
        "item_link_selector": "a[href='__none__']",
        "item_description_selector": "main, .site, .content",
        "detail_fetch": False,
        "detail_content_selector": "main, .field-name-body, .content, form.webform-client-form",
        "allow_english_text": True,
        "assume_recurring_without_close_date": True,
        "detail_max_chars": 14000,
        "pagination": {"max_pages": 1},
    },
    "notes": (
        "Page officielle I&P de soumission de business plan. "
        "Le HTML public expose les criteres PME/start-up Afrique subsaharienne, "
        "la fourchette de besoin de financement et le formulaire de prise de contact."
    ),
}


async def run() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Source).where(Source.name == IETP_SOURCE["name"])
        )
        source = existing.scalar_one_or_none()

        if source:
            for key, value in IETP_SOURCE.items():
                setattr(source, key, value)
            await db.commit()
            await db.refresh(source)
            print(f"[UPDATE] {source.name} mise a jour ({source.id})")
            return

        source = Source(**IETP_SOURCE)
        db.add(source)
        await db.commit()
        await db.refresh(source)
        print(f"[OK] {source.name} ajoutee ({source.id})")


if __name__ == "__main__":
    asyncio.run(run())
