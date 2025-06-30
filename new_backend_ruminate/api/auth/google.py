"""Google OAuth endpoints (mobile PKCE + web auth-code)."""
from __future__ import annotations

from datetime import datetime, timedelta
import os
import requests

from fastapi import APIRouter, HTTPException, status, Request, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from new_backend_ruminate.config import settings
from new_backend_ruminate.domain.user.repo import UserRepository
from new_backend_ruminate.dependencies import get_user_repository, get_session

router = APIRouter(prefix="/auth/google", tags=["auth"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SETTINGS = settings()
JWT_ALG = "HS256"
JWT_EXPIRES = timedelta(hours=SETTINGS.jwt_exp_hours)


def _issue_app_token(uid: str, email: str) -> str:
    now = datetime.utcnow()
    payload = {
        "uid": uid,
        "email": email,
        "iat": now,
        "exp": now + JWT_EXPIRES,
    }
    return jwt.encode(payload, SETTINGS.jwt_secret, algorithm=JWT_ALG)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class MobileTokenRequest(BaseModel):
    id_token: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Mobile endpoint – installed-app flow. The native app already exchanged code
# for tokens and sends us the Google *id_token*.
# ---------------------------------------------------------------------------

@router.post("/mobile-token", response_model=AuthTokenResponse)
async def mobile_token(
    body: MobileTokenRequest,
    user_repo: UserRepository = Depends(get_user_repository),
    db: AsyncSession = Depends(get_session),
):
    try:
        claims = google_id_token.verify_oauth2_token(
            body.id_token, google_requests.Request(), audience=None
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token")

    user = await user_repo.upsert_google_user(claims, db)
    app_jwt = _issue_app_token(str(user.id), user.email)
    return AuthTokenResponse(access_token=app_jwt)


# ---------------------------------------------------------------------------
# Web endpoint – receives ?code=… from Google, exchanges for tokens, issues JWT
# ---------------------------------------------------------------------------

@router.get("/callback")
async def google_callback(
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository),
    db: AsyncSession = Depends(get_session),
):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    data = {
        "code": code,
        "client_id": SETTINGS.google_web_client_id,
        "client_secret": os.getenv("GOOGLE_WEB_CLIENT_SECRET"),
        "redirect_uri": "https://myapp.com/api/auth/google/callback",  # adjust if env-specific
        "grant_type": "authorization_code",
    }
    r = requests.post("https://oauth2.googleapis.com/token", data=data, timeout=10)
    if r.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange code with Google")

    google_token = r.json().get("id_token")
    if not google_token:
        raise HTTPException(status_code=400, detail="Google response missing id_token")

    claims = google_id_token.verify_oauth2_token(
        google_token, google_requests.Request(), SETTINGS.google_web_client_id
    )
    user = await user_repo.upsert_google_user(claims, db)
    app_jwt = _issue_app_token(str(user.id), user.email)

    # Redirect to front-end with token in query; you may set a secure cookie instead.
    redirect_url = f"https://myapp.com/login-success?token={app_jwt}"
    return RedirectResponse(redirect_url)
