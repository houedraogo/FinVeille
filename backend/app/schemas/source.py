from datetime import datetime
from typing import Any, Literal, Optional
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, model_validator


SourceKind = Literal[
    "listing",
    "single_program_page",
    "pdf_manual",
    "institutional_project",
    "editorial_funding",
    "manual_import",
    "qualified_manual",
]


def _looks_like_homepage(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    path = (parsed.path or "/").strip()
    if not path or path == "/":
        return True
    normalized = path.rstrip("/")
    homepage_paths = {"", "/fr", "/en", "/francais", "/english", "/home", "/accueil"}
    return normalized in homepage_paths


def _has_minimal_html_config(config: Optional[dict[str, Any]]) -> bool:
    cfg = config or {}
    return bool(
        cfg.get("list_selector")
        or cfg.get("item_title_selector")
        or cfg.get("item_description_selector")
        or cfg.get("detail_fetch")
    )


class _SourceBase(BaseModel):
    name: str
    organism: str
    country: str
    region: Optional[str] = None
    source_type: str
    category: str = "public"
    level: int = 2
    url: str
    collection_mode: str
    source_kind: SourceKind = "listing"
    check_frequency: str = "daily"
    reliability: int = 3
    is_active: bool = True
    config: Optional[dict[str, Any]] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_source_shape(self):
        if self.source_kind in {"pdf_manual", "manual_import", "qualified_manual"} and self.collection_mode != "manual":
            raise ValueError("Une source manuelle ou qualifiee doit utiliser le mode de collecte manual.")

        if self.collection_mode != "html":
            return self

        if self.source_kind in {"single_program_page", "institutional_project", "editorial_funding"}:
            return self

        if _looks_like_homepage(self.url) and not _has_minimal_html_config(self.config):
            raise ValueError(
                "Une source HTML pointant vers une page d'accueil doit fournir une config minimale "
                "ou etre creee comme single_program_page."
            )
        return self


class SourceCreate(_SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    organism: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    source_type: Optional[str] = None
    category: Optional[str] = None
    level: Optional[int] = None
    url: Optional[str] = None
    collection_mode: Optional[str] = None
    source_kind: Optional[SourceKind] = None
    check_frequency: Optional[str] = None
    reliability: Optional[int] = None
    is_active: Optional[bool] = None
    config: Optional[dict[str, Any]] = None
    notes: Optional[str] = None


class SourceResponse(BaseModel):
    id: UUID
    name: str
    organism: str
    country: str
    region: Optional[str]
    source_type: str
    category: str
    level: int
    url: str
    collection_mode: str
    source_kind: SourceKind = "listing"
    check_frequency: str
    reliability: int
    is_active: bool
    last_checked_at: Optional[datetime]
    last_success_at: Optional[datetime]
    consecutive_errors: int
    config: Optional[dict[str, Any]]
    notes: Optional[str]
    last_error: Optional[str] = None
    health_score: int = 0
    health_label: str = "critique"
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceTestRequest(_SourceBase):
    name: str = "Test source"
    organism: str = "Test"
    country: str = "France"
    source_type: str = "portail_officiel"


class SourceTestResponse(BaseModel):
    success: bool
    message: str
    collection_mode: str
    items_found: int
    sample_titles: list[str]
    sample_urls: list[str]
    can_activate: bool
    preview: Optional[dict[str, Any]] = None
