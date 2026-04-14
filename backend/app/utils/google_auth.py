import httpx
from fastapi import HTTPException, status
from app.config import settings


async def verify_google_credential(credential: str) -> dict:
    """Vérifie un token Google ID et retourne les infos utilisateur."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": credential},
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Google invalide",
        )

    data = response.json()

    # Vérifier que le token est destiné à notre application
    client_id = settings.GOOGLE_CLIENT_ID
    if client_id and data.get("aud") != client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Google non autorisé pour cette application",
        )

    if not data.get("email_verified") or data.get("email_verified") == "false":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email Google non vérifié",
        )

    return {
        "email": data.get("email"),
        "full_name": data.get("name", ""),
        "google_id": data.get("sub"),
    }
