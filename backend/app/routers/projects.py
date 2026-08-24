from datetime import date, timedelta, timezone, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.device import Device
from app.models.project import UserProject
from app.models.user import User

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    sectors: List[str] = []
    countries: List[str] = []
    stage: str = "ideation"
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    currency: str = "EUR"
    keywords: List[str] = []


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sectors: Optional[List[str]] = None
    countries: Optional[List[str]] = None
    stage: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    currency: Optional[str] = None
    keywords: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Matching engine
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    return text.lower().strip()


def _score_device(device: Device, project: UserProject) -> float:
    """Score 0-100 : compatibilité dispositif ↔ projet."""
    score = 0.0

    # Secteurs (40 pts)
    proj_sectors = [_normalize(s) for s in (project.sectors or [])]
    dev_sectors = [_normalize(s) for s in (device.sectors or [])]
    proj_keywords = [_normalize(k) for k in (project.keywords or [])]

    if proj_sectors and dev_sectors:
        matched = sum(
            1 for ps in proj_sectors
            if any(ps in ds or ds in ps for ds in dev_sectors)
        )
        score += min(40.0, matched / len(proj_sectors) * 40)
    elif proj_keywords and dev_sectors:
        matched = sum(
            1 for kw in proj_keywords
            if any(kw in ds or ds in kw for ds in dev_sectors)
        )
        score += min(20.0, matched / len(proj_keywords) * 20)

    # Pays (30 pts)
    proj_countries = [_normalize(c) for c in (project.countries or [])]
    if proj_countries:
        dev_country = _normalize(device.country or "")
        if any(pc in dev_country or dev_country in pc for pc in proj_countries):
            score += 30.0
    else:
        score += 15.0  # pas de filtre pays → bonus neutre

    # Budget (20 pts)
    if project.budget_max and device.amount_max:
        budget = float(project.budget_max)
        dev_max = float(device.amount_max)
        dev_min = float(device.amount_min or 0)
        if dev_min <= budget <= dev_max * 2:
            score += 20.0
        elif budget <= dev_max * 5:
            score += 10.0
    else:
        score += 10.0  # pas de contrainte budget → bonus neutre

    # Qualité du dispositif (10 pts)
    score += (device.confidence_score or 0) / 100 * 10

    return round(score, 1)


async def _run_match(db: AsyncSession, project: UserProject) -> dict:
    """Calcule les correspondances et retourne un résumé."""
    result = await db.execute(
        select(Device).where(
            and_(
                Device.status == "open",
                Device.validation_status != "rejected",
            )
        ).limit(500)
    )
    devices = result.scalars().all()

    scored = []
    for d in devices:
        s = _score_device(d, project)
        if s >= 20:  # seuil minimal de pertinence
            scored.append({
                "id": str(d.id),
                "title": d.title,
                "organism": d.organism,
                "country": d.country,
                "device_type": d.device_type,
                "amount_max": float(d.amount_max) if d.amount_max else None,
                "currency": d.currency,
                "close_date": d.close_date.isoformat() if d.close_date else None,
                "days_left": (d.close_date - date.today()).days if d.close_date else None,
                "score": s,
                "confidence_score": d.confidence_score,
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:20]

    # Score global projet = moyenne pondérée des 5 meilleurs
    top5 = scored[:5]
    global_score = round(sum(x["score"] for x in top5) / len(top5), 1) if top5 else 0.0

    # Financement potentiel = somme des amount_max des 5 meilleurs
    potential_funding = sum(
        x["amount_max"] for x in top5 if x["amount_max"]
    )

    # Actions recommandées
    next_actions = _build_next_actions(project, top)

    return {
        "matches": top,
        "global_score": global_score,
        "total_compatible": len(scored),
        "potential_funding": potential_funding,
        "next_actions": next_actions,
    }


def _build_next_actions(project: UserProject, matches: list) -> list:
    actions = []

    # Deadline imminente parmi les top matches
    urgent = [m for m in matches[:10] if m["days_left"] is not None and m["days_left"] <= 14]
    if urgent:
        d = urgent[0]
        actions.append({
            "type": "deadline",
            "priority": "high",
            "label": f"Déposer avant J-{d['days_left']} : {d['title'][:60]}",
            "href": f"/devices/{d['id']}",
        })

    # Profil incomplet
    if not project.description:
        actions.append({
            "type": "complete",
            "priority": "medium",
            "label": "Compléter la description du projet pour améliorer le matching",
            "href": f"/projects/{project.id}/edit",
        })

    if not (project.sectors or project.keywords):
        actions.append({
            "type": "complete",
            "priority": "medium",
            "label": "Ajouter des secteurs ou mots-clés pour affiner les résultats",
            "href": f"/projects/{project.id}/edit",
        })

    # Bon match disponible
    if matches and matches[0]["score"] >= 60:
        top = matches[0]
        actions.append({
            "type": "opportunity",
            "priority": "medium",
            "label": f"Aide très compatible détectée : {top['title'][:60]}",
            "href": f"/devices/{top['id']}",
        })

    return actions[:4]


# ---------------------------------------------------------------------------
# Serialization helper
# ---------------------------------------------------------------------------

def _serialize(p: UserProject) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "sectors": p.sectors or [],
        "countries": p.countries or [],
        "stage": p.stage,
        "budget_min": float(p.budget_min) if p.budget_min else None,
        "budget_max": float(p.budget_max) if p.budget_max else None,
        "currency": p.currency,
        "keywords": p.keywords or [],
        "cached_matches": p.cached_matches or [],
        "match_score": float(p.match_score) if p.match_score else None,
        "matched_at": p.matched_at.isoformat() if p.matched_at else None,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/")
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UserProject)
        .where(UserProject.user_id == current_user.id)
        .order_by(UserProject.updated_at.desc())
    )
    return [_serialize(p) for p in result.scalars().all()]


@router.post("/", status_code=201)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = UserProject(
        user_id=current_user.id,
        organization_id=getattr(current_user, "organization_id", None),
        **body.model_dump(),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    # Lance le matching immédiatement
    match_result = await _run_match(db, project)
    project.cached_matches = match_result["matches"]
    project.match_score = match_result["global_score"]
    project.matched_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(project)

    out = _serialize(project)
    out["match_summary"] = match_result
    return out


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_or_404(db, project_id, current_user)
    out = _serialize(project)

    # Reconstruit les actions depuis le cache
    out["match_summary"] = {
        "matches": project.cached_matches or [],
        "global_score": float(project.match_score) if project.match_score else 0,
        "total_compatible": len(project.cached_matches or []),
        "potential_funding": sum(
            m["amount_max"] for m in (project.cached_matches or [])[:5] if m.get("amount_max")
        ),
        "next_actions": _build_next_actions(project, project.cached_matches or []),
    }
    return out


@router.put("/{project_id}")
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_or_404(db, project_id, current_user)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return _serialize(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_or_404(db, project_id, current_user)
    await db.delete(project)
    await db.commit()


@router.post("/{project_id}/match")
async def refresh_match(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Relance le matching et met à jour le cache."""
    project = await _get_or_404(db, project_id, current_user)
    match_result = await _run_match(db, project)
    project.cached_matches = match_result["matches"]
    project.match_score = match_result["global_score"]
    project.matched_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(project)
    return match_result


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _get_or_404(db: AsyncSession, project_id: str, user: User) -> UserProject:
    result = await db.execute(
        select(UserProject).where(
            and_(
                UserProject.id == project_id,
                UserProject.user_id == user.id,
            )
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    return project
