from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.billing_service import ensure_feature
from app.services.match_service import match_project

router = APIRouter(prefix="/api/v1/match", tags=["match"])

ALLOWED_EXTENSIONS = {"pdf", "pptx", "ppt", "txt", "md"}
MAX_SIZE_MB = 10


@router.get("/status")
async def match_status():
    return {"ready": True, "message": None}


@router.post("/")
async def match_from_document(
    file: UploadFile = File(...),
    limit: int = Query(default=15, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await ensure_feature(db, current_user, "matching_ai")

    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Format non supporté. Formats acceptés : {', '.join(sorted(ALLOWED_EXTENSIONS)).upper()}",
        )

    content = await file.read()
    if len(content) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=422, detail=f"Fichier trop volumineux (max {MAX_SIZE_MB} Mo).")

    try:
        result = await match_project(db, file.filename, content, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse : {e}")

    return result
