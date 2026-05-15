import asyncio
import logging
import re
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from app.tasks.celery_app import celery_app
from app.utils.text_utils import extract_close_date, localize_investment_text, looks_english_text

logger = logging.getLogger(__name__)

_NON_PUBLIC_URL_PATTERNS = (
    "%/api/%",
    "https://api.%",
    "http://api.%",
    "%localhost%",
    "%127.0.0.1%",
    "%/oauth/%",
    "%/login%",
    "%token=%",
)

# ── Patterns d'extraction ─────────────────────────────────────────────────────

# Montants : "jusqu'à 500 000 €", "2,5 M€", "entre 10k et 2M EUR", etc.
_AMOUNT_PATTERNS = [
    r"jusqu['\u2019]à\s*([\d\s,.]+)\s*([MmKk]?)\s*(?:€|EUR|euros?)",
    r"([\d\s,.]+)\s*([MmKk]?)\s*(?:€|EUR|euros?)\s*(?:maximum|max|plafond)",
    r"montant\s*(?:maximum|max|plafond)\s*[:\-]?\s*([\d\s,.]+)\s*([MmKk]?)\s*(?:€|EUR|euros?)",
    r"aide\s*(?:de|d['\u2019])\s*([\d\s,.]+)\s*([MmKk]?)\s*(?:€|EUR|euros?)",
    r"subvention\s*(?:de|jusqu['\u2019]à)?\s*([\d\s,.]+)\s*([MmKk]?)\s*(?:€|EUR|euros?)",
    r"([\d\s,.]+)\s*([MmKk]€)",   # "500k€", "2M€"
]

# Dates de clôture
_DATE_PATTERNS = [
    r"(?:clôture|cloture|date\s*limite|dépôt|depot|candidature(?:s)?)\s*[:\-]?\s*(?:le\s+|au\s+)?(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})",
    r"(?:jusqu['\u2019]au|avant\s+le)\s+(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})",
    r"(\d{1,2})\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})",
    r"(?:deadline|closing\s+date)\s*[:\-]?\s*(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})",
]

_FR_MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}

_SCRAPE_SKIP_TAGS = {
    "script", "style", "nav", "footer", "header", "aside",
    "noscript", "iframe", "form", "button", "svg", "img",
}
_SECTION_ELIGIBILITY_KEYWORDS = [
    "Ã©ligib", "eligib", "bÃ©nÃ©ficiaire", "beneficiaire", "qui peut",
    "conditions", "critÃ¨re", "critere", "exigence", "prÃ©requis",
    "profil", "cible", "destinÃ©", "destine", "pour qui",
]
_SECTION_AMOUNT_KEYWORDS = [
    "montant", "financement", "subvention", "aide", "dotation",
    "budget", "plafond", "jusqu'Ã ", "jusqu'a", "entre ",
]
_SECTION_DATE_KEYWORDS = [
    "date", "clÃ´ture", "cloture", "dÃ©lai", "delai", "dÃ©pÃ´t",
    "dossier", "candidature", "ouverture", "fermeture",
]
_SECTION_PROCEDURE_KEYWORDS = [
    "comment postuler", "dossier", "dÃ©marche", "dÃ©marches",
    "Ã©tapes", "procedure", "procÃ©dure", "comment bÃ©nÃ©ficier",
    "comment candidater", "soumettre",
]


def _parse_amount(value_str: str, multiplier: str) -> float | None:
    """Convertit une chaîne de montant en float."""
    try:
        clean = value_str.replace(" ", "").replace("\u202f", "").replace(",", ".")
        amount = float(clean)
        m = multiplier.upper()
        if m in ("M", "M€"):
            amount *= 1_000_000
        elif m in ("K", "K€"):
            amount *= 1_000
        return amount if amount > 0 else None
    except (ValueError, TypeError):
        return None


def _extract_amount(text: str) -> float | None:
    """Extrait le montant maximum depuis un texte."""
    for pattern in _AMOUNT_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            groups = m.groups()
            if len(groups) >= 2:
                amount = _parse_amount(groups[0], groups[1])
                if amount and 100 <= amount <= 1_000_000_000:
                    return amount
            elif len(groups) == 1:
                # Pattern "500k€" avec tout dans le groupe 1
                raw = groups[0].replace(" ", "")
                for suffix, mult in [("M€", 1e6), ("K€", 1e3), ("m€", 1e6), ("k€", 1e3)]:
                    if raw.endswith(suffix):
                        try:
                            v = float(raw[:-len(suffix)].replace(",", ".")) * mult
                            if 100 <= v <= 1_000_000_000:
                                return v
                        except ValueError:
                            pass
    return None


def _extract_date(text: str) -> date | None:
    """Extrait la première date de clôture depuis un texte."""
    # Patterns numériques : JJ/MM/AAAA ou JJ-MM-AAAA
    for pattern in _DATE_PATTERNS[:3]:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            groups = m.groups()
            try:
                if len(groups) == 3 and groups[1].isdigit():
                    day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                    if year < 100:
                        year += 2000
                    d = date(year, month, day)
                    if d >= date.today():
                        return d
            except (ValueError, TypeError):
                pass

    # Pattern littéral : "15 mars 2026"
    pat = r"(\d{1,2})\s+(janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[ûu]t|septembre|octobre|novembre|d[ée]cembre)\s+(\d{4})"
    for m in re.finditer(pat, text, re.IGNORECASE):
        try:
            day = int(m.group(1))
            month = _FR_MONTHS.get(m.group(2).lower())
            year = int(m.group(3))
            if month:
                d = date(year, month, day)
                if d >= date.today():
                    return d
        except (ValueError, TypeError):
            pass
    return None


def _clean_scraped_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _extract_text_block(el) -> str:
    text = el.get_text(" ", strip=True)
    if not text:
        return ""
    if el.name == "li":
        return f"- {text}"
    return text


def _pick_main_content(soup):
    selectors = [
        "main article",
        "main .column_content",
        "main .node__content",
        "main .content-wrapper",
        "main .article-content",
        "main .entry-content",
        "main .rich-text",
        "main .wysiwyg",
        "main .prose",
        "main .page-body",
        "main",
    ]

    best = None
    best_len = 0
    for selector in selectors:
        for node in soup.select(selector):
            text_len = len(node.get_text(" ", strip=True))
            if text_len > best_len:
                best = node
                best_len = text_len

    return best or soup.find("main") or soup.body or soup


def _extract_scraped_sections(soup) -> dict:
    for tag in soup.find_all(_SCRAPE_SKIP_TAGS):
        tag.decompose()
    for tag in soup.find_all(attrs={"class": re.compile(
        r"(cookie|banner|popup|modal|menu|breadcrumb|sidebar|widget|social|share|comment)",
        re.I,
    )}):
        tag.decompose()

    main = _pick_main_content(soup)
    sections: dict[str, list[str]] = {}
    current_title = "description"
    current_parts: list[str] = []

    for el in main.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        if el.name in ("h1", "h2", "h3", "h4"):
            if current_parts:
                sections.setdefault(current_title, []).extend(current_parts)
            current_title = el.get_text(strip=True).lower()
            current_parts = []
        else:
            txt = _extract_text_block(el)
            if len(txt) > 20:
                current_parts.append(txt)

    if current_parts:
        sections.setdefault(current_title, []).extend(current_parts)

    if not sections:
        fallback_parts = []
        for el in main.find_all(["p", "li"]):
            txt = _extract_text_block(el)
            if len(txt) > 20:
                fallback_parts.append(txt)
        if fallback_parts:
            sections["description"] = fallback_parts

    eligibility_parts: list[str] = []
    amount_parts: list[str] = []
    date_parts: list[str] = []
    procedure_parts: list[str] = []
    description_parts: list[str] = []

    for title, parts in sections.items():
        if any(kw in title for kw in _SECTION_ELIGIBILITY_KEYWORDS):
            eligibility_parts.extend(parts)
        elif any(kw in title for kw in _SECTION_AMOUNT_KEYWORDS):
            amount_parts.extend(parts)
        elif any(kw in title for kw in _SECTION_DATE_KEYWORDS):
            date_parts.extend(parts)
        elif any(kw in title for kw in _SECTION_PROCEDURE_KEYWORDS):
            procedure_parts.extend(parts)
        else:
            description_parts.extend(parts)

    if not description_parts:
        fallback_parts = []
        for el in main.find_all(["p", "li"]):
            txt = _extract_text_block(el)
            if len(txt) > 30:
                fallback_parts.append(txt)
        description_parts.extend(fallback_parts[:16])

    full_desc_parts = []
    if description_parts:
        full_desc_parts.append("## Présentation\n" + "\n".join(description_parts[:8]))
    if amount_parts:
        full_desc_parts.append("## Montants & financement\n" + "\n".join(amount_parts[:6]))
    if eligibility_parts:
        full_desc_parts.append("## Critères d'éligibilité\n" + "\n".join(eligibility_parts[:10]))
    if date_parts:
        full_desc_parts.append("## Dates & délais\n" + "\n".join(date_parts[:6]))
    if procedure_parts:
        full_desc_parts.append("## Comment postuler\n" + "\n".join(procedure_parts[:8]))

    return {
        "full_description": _clean_scraped_text("\n\n".join(full_desc_parts))[:8000] or None,
        "eligibility_criteria": _clean_scraped_text("\n".join(eligibility_parts))[:3000] if eligibility_parts else None,
        "eligible_expenses": _clean_scraped_text("\n".join(amount_parts))[:2000] if amount_parts else None,
        "text": _clean_scraped_text(main.get_text(separator=" ", strip=True))[:12000],
    }


@asynccontextmanager
async def _fresh_db():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.config import settings
    engine = create_async_engine(settings.DATABASE_URL, pool_size=3, max_overflow=5)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
    await engine.dispose()


@celery_app.task
def update_expired_devices():
    asyncio.run(_update_expired_async())


@celery_app.task
def weekly_quality_report():
    asyncio.run(_weekly_quality_async())


@celery_app.task
def daily_quality_audit():
    asyncio.run(_daily_quality_audit_async())


@celery_app.task
def daily_catalog_quality_control():
    asyncio.run(_daily_catalog_quality_control_async())


async def _update_expired_async():
    from sqlalchemy import update, and_
    from datetime import date, datetime, timezone
    from app.models.device import Device

    async with _fresh_db() as db:
        today = date.today()
        result = await db.execute(
            update(Device)
            .where(and_(Device.close_date < today, Device.status == "open"))
            .values(status="expired", updated_at=datetime.now(timezone.utc))
            .returning(Device.id)
        )
        updated = result.fetchall()
        await db.commit()
        logger.info(f"[Quality] {len(updated)} dispositifs passés en 'expired'")


@celery_app.task(bind=True, max_retries=0)
def enrich_missing_fields(self, batch_size: int = 50):
    """Enrichit les dispositifs sans montant ou sans date via scraping de leur source_url."""
    asyncio.run(_enrich_missing_async(batch_size))


async def _enrich_missing_async(batch_size: int = 50):
    import httpx
    from bs4 import BeautifulSoup
    from sqlalchemy import select, or_, and_, update, delete
    from datetime import datetime, timezone
    from app.models.device import Device
    from app.services.device_service import DeviceService

    async def fetch_page_content(url: str) -> dict:
        """Récupère le texte brut d'une page, robuste aux erreurs."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Accept-Language": "fr-FR,fr;q=0.9",
        }
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True,
                                         verify=False, headers=headers) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")
                return _extract_scraped_sections(soup)
        except Exception as e:
            logger.debug(f"[Enrich] Fetch error {url}: {e}")
            return {}

    async with _fresh_db() as db:
        # Sélectionner les dispositifs enrichissables :
        # - URL valide (commence par http)
        # - manque montant OU date de clôture
        # - pas déjà scraped récemment (last_verified_at > 7 jours)
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        q = (
            select(
                Device.id,
                Device.source_url,
                Device.source_raw,
                Device.device_type,
                Device.amount_max,
                Device.amount_min,
                Device.close_date,
                Device.short_description,
                Device.full_description,
                Device.eligibility_criteria,
                Device.eligible_expenses,
            )
            .where(
                Device.source_url.ilike("http%"),
                Device.validation_status != "rejected",
                Device.last_verified_at < cutoff,
                or_(
                    and_(Device.amount_max.is_(None), Device.amount_min.is_(None)),
                    Device.close_date.is_(None),
                    Device.full_description.is_(None),
                    Device.eligibility_criteria.is_(None),
                    Device.eligible_expenses.is_(None),
                ),
            )
            .order_by(Device.last_verified_at.asc())
            .limit(batch_size)
        )
        rows = (await db.execute(q)).all()

        if not rows:
            logger.info("[Enrich] Aucun dispositif à enrichir")
            return

        logger.info(f"[Enrich] {len(rows)} dispositifs à enrichir")
        enriched = skipped = errors = deleted = 0

        for row in rows:
            (
                device_id,
                url,
                source_raw,
                device_type,
                amount_max,
                amount_min,
                close_date,
                short_desc,
                full_description,
                eligibility_criteria,
                eligible_expenses,
            ) = row
            current_short = (short_desc or "").strip()
            is_thin_before = DeviceService.has_thin_description(current_short)
            scraped = await fetch_page_content(url)
            text = (scraped.get("text") or "").strip()
            if not text:
                if is_thin_before:
                    await db.execute(delete(Device).where(Device.id == device_id))
                    deleted += 1
                    continue
                errors += 1
                continue

            if device_type == "investissement":
                for field in ("full_description", "eligibility_criteria", "eligible_expenses"):
                    value = scraped.get(field)
                    if value and looks_english_text(value):
                        scraped[field] = localize_investment_text(value)

            updates: dict = {"last_verified_at": datetime.now(timezone.utc)}
            changed = False

            # Enrichir le montant si manquant
            if amount_max is None and amount_min is None:
                found_amount = _extract_amount(text)
                if found_amount:
                    updates["amount_max"] = found_amount
                    changed = True

            # Enrichir la date de clôture si manquante
            if close_date is None:
                found_date = extract_close_date(source_raw or "")
                if not found_date:
                    found_date = extract_close_date(text)
                if found_date:
                    updates["close_date"] = found_date
                    updates["status"] = "expired" if found_date < date.today() else "open"
                    changed = True

            if not full_description and scraped.get("full_description"):
                updates["full_description"] = scraped["full_description"]
                changed = True

            if not eligibility_criteria and scraped.get("eligibility_criteria"):
                updates["eligibility_criteria"] = scraped["eligibility_criteria"]
                changed = True

            if not eligible_expenses and scraped.get("eligible_expenses"):
                updates["eligible_expenses"] = scraped["eligible_expenses"]
                changed = True

            # Enrichir la description courte si trop courte
            if not short_desc or len(short_desc) < 80:
                # Prendre les 3 premières phrases du texte
                source_for_summary = scraped.get("full_description") or text[:2000]
                sentences = re.split(r'[.!?]\s+', source_for_summary)
                clean = [s.strip().lstrip("- ").strip() for s in sentences if len(s.strip()) > 40]
                if clean:
                    summary = ". ".join(clean[:3])[:500].rstrip(".")
                    updates["short_description"] = f"{summary}."
                    changed = True

            new_short = updates.get("short_description", current_short)
            if DeviceService.has_thin_description(new_short):
                await db.execute(delete(Device).where(Device.id == device_id))
                deleted += 1
                continue

            if changed:
                updates["updated_at"] = datetime.now(timezone.utc)
                enriched += 1
            else:
                skipped += 1

            await db.execute(
                update(Device).where(Device.id == device_id).values(**updates)
            )

        await db.commit()
        logger.info(
            f"[Enrich] Terminé — enrichis:{enriched} inchangés:{skipped} erreurs:{errors}"
        )


async def _weekly_quality_async():
    await _log_quality_audit(
        "[Quality Audit][weekly]",
        source_window_days=14,
        recent_source_days=30,
    )


async def _daily_quality_audit_async():
    await _log_quality_audit(
        "[Quality Audit][daily]",
        source_window_days=7,
        recent_source_days=21,
    )


async def _daily_catalog_quality_control_async():
    await _log_catalog_quality_control("[Catalog Quality][daily]")


async def build_quality_audit(db, *, source_window_days: int = 14, recent_source_days: int = 30, sample_limit: int = 5):
    from sqlalchemy import and_, func, or_, select
    from app.models.collection_log import CollectionLog
    from app.models.device import Device
    from app.models.source import Source

    today = date.today()
    now = datetime.utcnow()
    recent_source_cutoff = now - timedelta(days=recent_source_days)
    log_cutoff = now - timedelta(days=source_window_days)

    weak_condition = or_(
        Device.short_description.is_(None),
        func.length(func.trim(func.coalesce(Device.short_description, ""))) < 80,
        and_(
            or_(Device.full_description.is_(None), func.length(func.trim(func.coalesce(Device.full_description, ""))) < 120),
            or_(Device.eligibility_criteria.is_(None), func.length(func.trim(func.coalesce(Device.eligibility_criteria, ""))) < 80),
            or_(Device.eligible_expenses.is_(None), func.length(func.trim(func.coalesce(Device.eligible_expenses, ""))) < 80),
        ),
    )

    weak_count = (
        await db.execute(select(func.count()).select_from(Device).where(weak_condition))
    ).scalar() or 0
    weak_rows = (
        await db.execute(
            select(Device.id, Device.title, Device.organism)
            .where(weak_condition)
            .order_by(Device.updated_at.desc().nullslast())
            .limit(sample_limit)
        )
    ).all()

    non_public_condition = or_(*[Device.source_url.ilike(pattern) for pattern in _NON_PUBLIC_URL_PATTERNS])
    non_public_count = (
        await db.execute(select(func.count()).select_from(Device).where(non_public_condition))
    ).scalar() or 0
    non_public_rows = (
        await db.execute(
            select(Device.id, Device.title, Device.source_url)
            .where(non_public_condition)
            .order_by(Device.updated_at.desc().nullslast())
            .limit(sample_limit)
        )
    ).all()

    expired_open_condition = and_(Device.status == "open", Device.close_date.is_not(None), Device.close_date < today)
    expired_open_count = (
        await db.execute(select(func.count()).select_from(Device).where(expired_open_condition))
    ).scalar() or 0
    expired_open_rows = (
        await db.execute(
            select(Device.id, Device.title, Device.close_date)
            .where(expired_open_condition)
            .order_by(Device.close_date.asc())
            .limit(sample_limit)
        )
    ).all()

    noisy_sources = []
    recent_sources = (
        await db.execute(
            select(Source.id, Source.name, Source.organism, Source.created_at, Source.consecutive_errors)
            .where(and_(Source.is_active.is_(True), Source.created_at >= recent_source_cutoff))
        )
    ).all()

    for source in recent_sources:
        logs = (
            await db.execute(
                select(
                    CollectionLog.status,
                    CollectionLog.items_found,
                    CollectionLog.items_new,
                    CollectionLog.items_updated,
                    CollectionLog.items_error,
                )
                .where(
                    and_(
                        CollectionLog.source_id == source.id,
                        CollectionLog.started_at >= log_cutoff,
                    )
                )
            )
        ).all()

        if not logs:
            continue

        total_runs = len(logs)
        failed_runs = sum(1 for log in logs if log.status in {"failed", "partial"})
        total_found = sum(int(log.items_found or 0) for log in logs)
        total_new = sum(int(log.items_new or 0) for log in logs)
        total_updated = sum(int(log.items_updated or 0) for log in logs)
        total_errors = sum(int(log.items_error or 0) for log in logs)

        is_noisy = (
            int(source.consecutive_errors or 0) >= 2
            or failed_runs >= 2
            or (total_runs >= 3 and failed_runs / total_runs >= 0.5)
            or (total_found >= 20 and total_new + total_updated == 0)
            or total_errors >= 10
        )
        if not is_noisy:
            continue

        noisy_sources.append(
            {
                "id": str(source.id),
                "name": source.name,
                "organism": source.organism,
                "total_runs": total_runs,
                "failed_runs": failed_runs,
                "consecutive_errors": int(source.consecutive_errors or 0),
                "items_found": total_found,
                "items_changed": total_new + total_updated,
                "items_error": total_errors,
            }
        )

    noisy_sources.sort(
        key=lambda item: (
            item["consecutive_errors"],
            item["failed_runs"],
            item["items_error"],
            -item["items_changed"],
        ),
        reverse=True,
    )

    return {
        "generated_at": now.isoformat() + "Z",
        "windows": {
            "source_window_days": source_window_days,
            "recent_source_days": recent_source_days,
        },
        "weak_devices": {
            "count": int(weak_count),
            "examples": [{"id": str(row.id), "title": row.title, "organism": row.organism} for row in weak_rows],
        },
        "non_public_urls": {
            "count": int(non_public_count),
            "examples": [{"id": str(row.id), "title": row.title, "source_url": row.source_url} for row in non_public_rows],
        },
        "open_with_past_close_date": {
            "count": int(expired_open_count),
            "examples": [
                {"id": str(row.id), "title": row.title, "close_date": row.close_date.isoformat() if row.close_date else None}
                for row in expired_open_rows
            ],
        },
        "noisy_recent_sources": {
            "count": len(noisy_sources),
            "examples": noisy_sources[:sample_limit],
        },
    }


def _audit_action_from_score(score: int, flags: list[str]) -> str:
    if "inactive_never_collected" in flags or "expired_unreachable" in flags:
        return "a_purger"
    if "source_errors" in flags or "too_many_non_public_urls" in flags:
        return "source_a_revoir"
    if "pending_review" in flags or "open_without_date" in flags or "recurring_ambiguous" in flags:
        return "a_verifier"
    if "weak_text" in flags or "english_text" in flags or "html_raw" in flags or "institutional_non_actionable" in flags:
        return "a_enrichir"
    if score >= 70:
        return "source_a_revoir"
    return "ok"


async def build_catalog_audit(db, *, sample_limit: int = 8, source_limit: int = 80):
    """Audit global du catalogue, orientÃ© exploitation et nettoyage source par source."""
    from sqlalchemy import and_, case, func, or_, select
    from app.models.collection_log import CollectionLog
    from app.models.device import Device
    from app.models.source import Source

    async def count_scalar(statement) -> int:
        result = await db.execute(statement)
        return int(result.scalar() or 0)

    today = date.today()
    now = datetime.utcnow()
    recent_cutoff = now - timedelta(days=30)

    weak_condition = or_(
        Device.short_description.is_(None),
        func.length(func.trim(func.coalesce(Device.short_description, ""))) < 80,
        and_(
            func.length(func.trim(func.coalesce(Device.full_description, ""))) < 160,
            func.length(func.trim(func.coalesce(Device.eligibility_criteria, ""))) < 80,
            func.length(func.trim(func.coalesce(Device.funding_details, ""))) < 80,
        ),
    )
    generic_condition = or_(
        Device.short_description.ilike("%criteres detailles ne sont pas fournis%"),
        Device.short_description.ilike("%page officielle%doit etre consultee%"),
        Device.full_description.ilike("%criteres detailles ne sont pas fournis%"),
        Device.full_description.ilike("%source officielle pour confirmer%"),
    )
    english_condition = or_(
        Device.language == "en",
        Device.short_description.op("~*")(r"\m(the|and|with|funding|deadline|project|program)\M"),
        Device.full_description.op("~*")(r"\m(the|and|with|funding|deadline|project|program)\M"),
    )
    html_condition = or_(
        Device.short_description.ilike("%<div%"),
        Device.short_description.ilike("%<p%"),
        Device.full_description.ilike("%<div%"),
        Device.full_description.ilike("%&lt;%"),
    )
    institutional_non_actionable_condition = or_(
        Device.device_type == "institutional_project",
        Device.short_description.ilike("%projet institutionnel%"),
        Device.full_description.ilike("%projet institutionnel%"),
        Device.eligibility_criteria.ilike("%pas un appel% candidatures direct%"),
        Device.funding_details.ilike("%ne representent pas une aide directement attribuable%"),
        Device.funding_details.ilike("%ne représentent pas une aide directement attribuable%"),
    )
    non_public_condition = or_(*[Device.source_url.ilike(pattern) for pattern in _NON_PUBLIC_URL_PATTERNS])
    open_without_date_condition = and_(
        Device.status == "open",
        Device.close_date.is_(None),
        Device.is_recurring.is_not(True),
    )
    open_with_past_close_date_condition = and_(
        Device.status.in_(["open", "recurring"]),
        Device.close_date.is_not(None),
        Device.close_date < today,
    )
    expired_unreachable_condition = and_(
        Device.status == "expired",
        or_(Source.is_active.is_(False), Source.consecutive_errors >= 2, non_public_condition),
    )
    recurring_ambiguous_condition = and_(
        or_(Device.status == "recurring", Device.is_recurring.is_(True)),
        Device.close_date.is_(None),
        or_(
            Device.recurrence_notes.is_(None),
            func.length(func.trim(func.coalesce(Device.recurrence_notes, ""))) < 40,
        ),
    )

    total_devices = await count_scalar(select(func.count(Device.id)))
    total_sources = await count_scalar(select(func.count(Source.id)))
    active_sources = await count_scalar(select(func.count(Source.id)).where(Source.is_active.is_(True)))

    async def grouped(column, label_key: str, limit: int = 20):
        rows = (
            await db.execute(
                select(column.label(label_key), func.count(Device.id).label("count"))
                .group_by(column)
                .order_by(func.count(Device.id).desc())
                .limit(limit)
            )
        ).all()
        return [{label_key: row[0] or "Non renseigne", "count": int(row.count or 0)} for row in rows]

    by_status = await grouped(Device.status, "status")
    by_type = await grouped(Device.device_type, "device_type")
    by_country = await grouped(Device.country, "country")
    by_quality = [
        {
            "bucket": "haute",
            "count": await count_scalar(select(func.count(Device.id)).where(Device.completeness_score >= 75)),
        },
        {
            "bucket": "moyenne",
            "count": await count_scalar(select(func.count(Device.id)).where(and_(Device.completeness_score >= 45, Device.completeness_score < 75))),
        },
        {
            "bucket": "faible",
            "count": await count_scalar(select(func.count(Device.id)).where(Device.completeness_score < 45)),
        },
    ]

    risk_counts = {
        "missing_close_date": await count_scalar(select(func.count(Device.id)).where(Device.close_date.is_(None))),
        "weak_text": await count_scalar(select(func.count(Device.id)).where(weak_condition)),
        "generic_text": await count_scalar(select(func.count(Device.id)).where(generic_condition)),
        "english_text": await count_scalar(select(func.count(Device.id)).where(english_condition)),
        "html_raw": await count_scalar(select(func.count(Device.id)).where(html_condition)),
        "institutional_non_actionable": await count_scalar(select(func.count(Device.id)).where(institutional_non_actionable_condition)),
        "non_public_urls": await count_scalar(select(func.count(Device.id)).where(non_public_condition)),
        "open_without_date": await count_scalar(select(func.count(Device.id)).where(open_without_date_condition)),
        "open_with_past_close_date": await count_scalar(select(func.count(Device.id)).where(open_with_past_close_date_condition)),
        "expired_unreachable": await count_scalar(select(func.count(Device.id)).select_from(Device).outerjoin(Source).where(expired_unreachable_condition)),
        "pending_review": await count_scalar(select(func.count(Device.id)).where(Device.validation_status == "pending_review")),
        "recurring_ambiguous": await count_scalar(select(func.count(Device.id)).where(recurring_ambiguous_condition)),
    }

    duplicate_groups = (
        await db.execute(
            select(
                func.coalesce(Device.title_normalized, func.lower(Device.title)).label("key"),
                func.count(Device.id).label("count"),
            )
            .group_by(func.coalesce(Device.title_normalized, func.lower(Device.title)))
            .having(func.count(Device.id) > 1)
            .order_by(func.count(Device.id).desc())
            .limit(sample_limit)
        )
    ).all()
    risk_counts["duplicate_groups"] = await count_scalar(
        select(func.count()).select_from(
            select(func.coalesce(Device.title_normalized, func.lower(Device.title)).label("key"))
            .group_by(func.coalesce(Device.title_normalized, func.lower(Device.title)))
            .having(func.count(Device.id) > 1)
            .subquery()
        ),
    )

    sample_specs = {
        "weak_text": weak_condition,
        "generic_text": generic_condition,
        "english_text": english_condition,
        "html_raw": html_condition,
        "institutional_non_actionable": institutional_non_actionable_condition,
        "open_without_date": open_without_date_condition,
        "open_with_past_close_date": open_with_past_close_date_condition,
        "expired_unreachable": expired_unreachable_condition,
        "pending_review": Device.validation_status == "pending_review",
        "recurring_ambiguous": recurring_ambiguous_condition,
    }
    samples = {}
    for key, condition in sample_specs.items():
        rows = (
            await db.execute(
                select(Device.id, Device.title, Device.organism, Device.country, Device.status, Device.close_date)
                .select_from(Device)
                .outerjoin(Source)
                .where(condition)
                .order_by(Device.updated_at.desc().nullslast())
                .limit(sample_limit)
            )
        ).all()
        samples[key] = [
            {
                "id": str(row.id),
                "title": row.title,
                "organism": row.organism,
                "country": row.country,
                "status": row.status,
                "close_date": row.close_date.isoformat() if row.close_date else None,
            }
            for row in rows
        ]
    samples["duplicate_groups"] = [{"title_key": row.key, "count": int(row.count or 0)} for row in duplicate_groups]

    source_rows = (
        await db.execute(
            select(
                Source.id,
                Source.name,
                Source.organism,
                Source.country,
                Source.category,
                Source.is_active,
                Source.last_checked_at,
                Source.last_success_at,
                Source.consecutive_errors,
                func.count(Device.id).label("device_count"),
                func.sum(case((Device.close_date.is_(None), 1), else_=0)).label("missing_dates"),
                func.sum(case((weak_condition, 1), else_=0)).label("weak_texts"),
                func.sum(case((generic_condition, 1), else_=0)).label("generic_texts"),
                func.sum(case((english_condition, 1), else_=0)).label("english_texts"),
                func.sum(case((html_condition, 1), else_=0)).label("html_raws"),
                func.sum(case((institutional_non_actionable_condition, 1), else_=0)).label("institutional_non_actionables"),
                func.sum(case((non_public_condition, 1), else_=0)).label("non_public_urls"),
                func.sum(case((open_without_date_condition, 1), else_=0)).label("open_without_dates"),
                func.sum(case((Device.validation_status == "pending_review", 1), else_=0)).label("pending_reviews"),
                func.sum(case((Device.validation_status == "auto_published", 1), else_=0)).label("published_devices"),
                func.sum(case((Device.close_date.is_not(None), 1), else_=0)).label("dated_devices"),
                func.sum(case((Device.status.in_(["open", "recurring"]), 1), else_=0)).label("active_devices"),
                func.sum(case((recurring_ambiguous_condition, 1), else_=0)).label("recurring_ambiguous"),
                func.avg(Device.completeness_score).label("avg_completeness"),
                func.avg(Device.confidence_score).label("avg_confidence"),
            )
            .select_from(Source)
            .outerjoin(Device, Device.source_id == Source.id)
            .group_by(Source.id)
            .order_by(func.count(Device.id).desc())
            .limit(source_limit)
        )
    ).all()

    log_rows = (
        await db.execute(
            select(
                CollectionLog.source_id,
                func.count(CollectionLog.id).label("runs"),
                func.sum(case((CollectionLog.status.in_(["failed", "partial"]), 1), else_=0)).label("failed_runs"),
                func.max(CollectionLog.error_message).label("last_error"),
            )
            .where(CollectionLog.started_at >= recent_cutoff)
            .group_by(CollectionLog.source_id)
        )
    ).all()
    logs_by_source = {
        row.source_id: {
            "runs": int(row.runs or 0),
            "failed_runs": int(row.failed_runs or 0),
            "last_error": row.last_error,
        }
        for row in log_rows
    }

    source_priorities = []
    for row in source_rows:
        device_count = int(row.device_count or 0)
        missing_dates = int(row.missing_dates or 0)
        weak_texts = int(row.weak_texts or 0)
        generic_texts = int(row.generic_texts or 0)
        english_texts = int(row.english_texts or 0)
        html_raws = int(row.html_raws or 0)
        institutional_non_actionables = int(row.institutional_non_actionables or 0)
        non_public_urls = int(row.non_public_urls or 0)
        open_without_dates = int(row.open_without_dates or 0)
        pending_reviews = int(row.pending_reviews or 0)
        published_devices = int(row.published_devices or 0)
        dated_devices = int(row.dated_devices or 0)
        active_devices = int(row.active_devices or 0)
        recurring_ambiguous = int(row.recurring_ambiguous or 0)
        log_info = logs_by_source.get(row.id, {"runs": 0, "failed_runs": 0, "last_error": None})
        publishable_rate = round(published_devices / max(device_count, 1) * 100, 1)
        date_rate = round(dated_devices / max(device_count, 1) * 100, 1)
        error_rate = round(log_info["failed_runs"] / max(log_info["runs"], 1) * 100, 1)

        flags = []
        if not row.is_active and device_count == 0:
            flags.append("inactive_never_collected")
        if int(row.consecutive_errors or 0) >= 2 or log_info["failed_runs"] >= 2:
            flags.append("source_errors")
        if device_count and missing_dates / max(device_count, 1) >= 0.6:
            flags.append("open_without_date")
        if device_count and weak_texts / max(device_count, 1) >= 0.25:
            flags.append("weak_text")
        if generic_texts:
            flags.append("generic_text")
        if english_texts:
            flags.append("english_text")
        if html_raws:
            flags.append("html_raw")
        if institutional_non_actionables:
            flags.append("institutional_non_actionable")
        if non_public_urls:
            flags.append("too_many_non_public_urls")
        if pending_reviews:
            flags.append("pending_review")
        if recurring_ambiguous:
            flags.append("recurring_ambiguous")

        score = (
            min(40, log_info["failed_runs"] * 12 + int(row.consecutive_errors or 0) * 8)
            + min(25, round((weak_texts + generic_texts + html_raws + institutional_non_actionables) / max(device_count, 1) * 25))
            + min(20, round(missing_dates / max(device_count, 1) * 20))
            + min(15, pending_reviews * 3 + recurring_ambiguous * 2 + non_public_urls * 2)
        )
        if "inactive_never_collected" in flags:
            score += 40

        source_priorities.append(
            {
                "source_id": str(row.id),
                "source_name": row.name,
                "organism": row.organism,
                "country": row.country,
                "category": row.category,
                "is_active": bool(row.is_active),
                "device_count": device_count,
                "published_devices": published_devices,
                "active_devices": active_devices,
                "date_rate": date_rate,
                "publishable_rate": publishable_rate,
                "error_rate_30d": error_rate,
                "avg_completeness": round(float(row.avg_completeness or 0), 1),
                "avg_confidence": round(float(row.avg_confidence or 0), 1),
                "issues": {
                    "missing_dates": missing_dates,
                    "weak_texts": weak_texts,
                    "generic_texts": generic_texts,
                    "english_texts": english_texts,
                    "html_raws": html_raws,
                    "institutional_non_actionables": institutional_non_actionables,
                    "non_public_urls": non_public_urls,
                    "open_without_dates": open_without_dates,
                    "pending_reviews": pending_reviews,
                    "recurring_ambiguous": recurring_ambiguous,
                    "consecutive_errors": int(row.consecutive_errors or 0),
                    "failed_runs_30d": log_info["failed_runs"],
                },
                "flags": flags,
                "priority_score": score,
                "recommended_action": _audit_action_from_score(score, flags),
                "last_checked_at": row.last_checked_at.isoformat() if row.last_checked_at else None,
                "last_success_at": row.last_success_at.isoformat() if row.last_success_at else None,
                "last_error": log_info["last_error"],
            }
        )

    source_priorities.sort(key=lambda item: item["priority_score"], reverse=True)

    action_counts = {}
    for item in source_priorities:
        action_counts[item["recommended_action"]] = action_counts.get(item["recommended_action"], 0) + 1

    return {
        "generated_at": now.isoformat() + "Z",
        "totals": {
            "devices": int(total_devices),
            "sources": int(total_sources),
            "active_sources": int(active_sources),
        },
        "distributions": {
            "by_source": source_priorities[:source_limit],
            "by_status": by_status,
            "by_type": by_type,
            "by_country": by_country,
            "by_quality": by_quality,
        },
        "risk_counts": risk_counts,
        "samples": samples,
        "source_priorities": source_priorities[:source_limit],
        "action_counts": action_counts,
        "action_labels": {
            "a_enrichir": "A enrichir",
            "a_purger": "A purger",
            "a_verifier": "A verifier",
            "source_a_revoir": "Source a revoir",
            "ok": "OK",
        },
        "source_report": {
            "columns": [
                "source_name",
                "device_count",
                "publishable_rate",
                "date_rate",
                "error_rate_30d",
                "avg_completeness",
                "recommended_action",
            ],
            "rows": source_priorities[:source_limit],
        },
    }


async def _log_catalog_quality_control(prefix: str):
    async with _fresh_db() as db:
        audit = await build_catalog_audit(db, sample_limit=5, source_limit=120)

    risk = audit["risk_counts"]
    actions = audit["action_counts"]
    logger.warning(
        "%s devices=%s sources=%s weak=%s english=%s open_without_date=%s past_open=%s actions=%s",
        prefix,
        audit["totals"]["devices"],
        audit["totals"]["sources"],
        risk.get("weak_text", 0),
        risk.get("english_text", 0),
        risk.get("open_without_date", 0),
        risk.get("open_with_past_close_date", 0),
        actions,
    )

    for source in audit["source_priorities"][:10]:
        if source["recommended_action"] == "ok":
            continue
        logger.warning(
            "[Catalog Quality][source] action=%s score=%s source=%s devices=%s publishable=%s%% dates=%s%% errors=%s%% flags=%s",
            source["recommended_action"],
            source["priority_score"],
            source["source_name"],
            source["device_count"],
            source["publishable_rate"],
            source["date_rate"],
            source["error_rate_30d"],
            ",".join(source["flags"]),
        )

    return audit


async def _log_quality_audit(prefix: str, *, source_window_days: int, recent_source_days: int):
    async with _fresh_db() as db:
        audit = await build_quality_audit(
            db,
            source_window_days=source_window_days,
            recent_source_days=recent_source_days,
        )

    summary = (
        f"{prefix} weak_devices={audit['weak_devices']['count']} "
        f"non_public_urls={audit['non_public_urls']['count']} "
        f"open_with_past_close_date={audit['open_with_past_close_date']['count']} "
        f"noisy_recent_sources={audit['noisy_recent_sources']['count']}"
    )

    if any(
        audit[key]["count"] > 0
        for key in ("weak_devices", "non_public_urls", "open_with_past_close_date", "noisy_recent_sources")
    ):
        logger.warning(summary)
    else:
        logger.info(summary)

    for weak in audit["weak_devices"]["examples"]:
        logger.warning("[Quality Audit][weak_device] %s | %s", weak["organism"], weak["title"])
    for device in audit["non_public_urls"]["examples"]:
        logger.warning("[Quality Audit][non_public_url] %s | %s", device["title"], device["source_url"])
    for device in audit["open_with_past_close_date"]["examples"]:
        logger.warning("[Quality Audit][open_past_close] %s | %s", device["title"], device["close_date"])
    for source in audit["noisy_recent_sources"]["examples"]:
        logger.warning(
            "[Quality Audit][noisy_source] %s runs=%s failed=%s changed=%s errors=%s consecutive=%s",
            source["name"],
            source["total_runs"],
            source["failed_runs"],
            source["items_changed"],
            source["items_error"],
            source["consecutive_errors"],
        )

    return audit
