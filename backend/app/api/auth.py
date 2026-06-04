"""Routes d'authentification : login (émission JWT) + me (route protégée)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.security import authenticate, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    username: str


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    """Vérifie les identifiants et renvoie un JWT, ou 401."""
    if not authenticate(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides",
        )
    return TokenResponse(access_token=create_access_token(payload.username))


@router.get("/me", response_model=MeResponse)
def me(username: str = Depends(get_current_user)) -> MeResponse:
    """Route protégée : renvoie l'utilisateur courant (401 sans token valide)."""
    return MeResponse(username=username)
