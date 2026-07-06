"""Routes d'authentification v2 — sessions multi-utilisateurs.

``login`` pose le **refresh en cookie httpOnly** (path=/auth, jamais lisible en
JS) et renvoie un **access court** gardé en mémoire côté front. ``refresh``
tourne le refresh (rotation) et réémet un access. ``register`` est gaté par le
réglage global ``signup_enabled`` (fermé tant que la tenancy n'est pas livrée).
``forgot`` répond toujours 200 (pas d'énumération d'emails).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import secrets

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.email_notifier import send_email
from app.auth.security import (
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
    issue_refresh,
    revoke_refresh,
    rotate_refresh,
)
from app.config import get_setting, get_settings
from app.db import get_db
from app.models import AuthSession, EmailToken, User
from app.services.rate_limit import rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "pa_refresh"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")

_limit_login = rate_limit("login", max_calls=5, window_s=60)
_limit_register = rate_limit("register", max_calls=5, window_s=60)
_limit_forgot = rate_limit("forgot", max_calls=3, window_s=60)


# ------------------------------------------------------------------ schémas
class LoginRequest(BaseModel):
    username: str  # username OU email
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    plan: str


class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str = Field(min_length=8, max_length=128)


class TokenBody(BaseModel):
    token: str


class ForgotRequest(BaseModel):
    email: str


class ResetRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


# ------------------------------------------------------------------ helpers
def _public_origin() -> str:
    return os.getenv("PUBLIC_ORIGIN", "http://localhost:5173").rstrip("/")


def _set_refresh_cookie(response: Response, raw: str) -> None:
    s = get_settings()
    response.set_cookie(
        REFRESH_COOKIE, raw,
        httponly=True, samesite="lax", secure=s.cookie_secure,
        max_age=s.refresh_expire_days * 86400, path="/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/auth")


def _issue_email_token(db: Session, user: User, purpose: str, hours: int) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(EmailToken(
        user_id=user.id, purpose=purpose,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=(dt.datetime.now(dt.timezone.utc)
                    + dt.timedelta(hours=hours)).replace(tzinfo=None),
    ))
    db.commit()
    return raw


def _consume_email_token(db: Session, raw: str, purpose: str) -> User | None:
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    tok = db.scalar(select(EmailToken).where(
        EmailToken.token_hash == hashlib.sha256(raw.encode()).hexdigest(),
        EmailToken.purpose == purpose,
    ))
    if tok is None or tok.used_at is not None or tok.expires_at <= now:
        return None
    tok.used_at = now
    return db.get(User, tok.user_id)


# ---------------------------------------------------------------- sessions
@router.post("/login", response_model=TokenResponse, dependencies=[Depends(_limit_login)])
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    """Vérifie les identifiants → access JSON + refresh en cookie httpOnly."""
    user = authenticate_user(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Identifiants invalides")
    if user.status == "pending":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Email non vérifié — consulte ta boîte mail.")
    _set_refresh_cookie(response, issue_refresh(db, user))
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/refresh", response_model=TokenResponse)
def refresh(response: Response, db: Session = Depends(get_db),
            pa_refresh: str | None = Cookie(default=None)) -> TokenResponse:
    """Rotation du refresh (cookie) → nouvel access + nouveau cookie, ou 401."""
    if not pa_refresh:
        raise HTTPException(status_code=401, detail="Pas de session")
    rotated = rotate_refresh(db, pa_refresh)
    if rotated is None:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Session expirée")
    user, new_raw = rotated
    _set_refresh_cookie(response, new_raw)
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response, db: Session = Depends(get_db),
           pa_refresh: str | None = Cookie(default=None)) -> MessageResponse:
    """Révoque la session refresh et efface le cookie."""
    if pa_refresh:
        revoke_refresh(db, pa_refresh)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Déconnecté")


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)) -> MeResponse:
    """Route protégée : renvoie l'utilisateur courant (401 sans token valide)."""
    return MeResponse(id=user.id, username=user.username, email=user.email,
                      role=user.role, plan=user.plan)


# ------------------------------------------------------------- inscription
@router.post("/register", response_model=MessageResponse, status_code=201,
             dependencies=[Depends(_limit_register)])
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> MessageResponse:
    """Crée un compte ``pending`` + envoie l'email de vérification (24 h)."""
    if not bool(get_setting("signup_enabled", default=False)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Les inscriptions sont fermées pour le moment.")
    email = payload.email.strip().lower()
    username = payload.username.strip()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Email invalide")
    if not _USERNAME_RE.match(username):
        raise HTTPException(status_code=422,
                            detail="Identifiant invalide (3-32 car., lettres/chiffres/._-)")
    exists = db.scalar(select(User).where((User.email == email) | (User.username == username)))
    if exists is not None:
        raise HTTPException(status_code=409, detail="Email ou identifiant déjà utilisé")

    user = User(email=email, username=username,
                password_hash=hash_password(payload.password), status="pending")
    db.add(user)
    db.commit()
    raw = _issue_email_token(db, user, "verify", hours=24)
    send_email(email, "PokéAlpha — vérifie ton adresse",
               "Bienvenue ! Confirme ton adresse pour activer ton compte :\n"
               f"{_public_origin()}/verify?token={raw}\n\nCe lien expire dans 24 h.")
    return MessageResponse(message="Compte créé — vérifie ta boîte mail.")


@router.post("/verify", response_model=MessageResponse)
def verify(payload: TokenBody, db: Session = Depends(get_db)) -> MessageResponse:
    """Active le compte associé au jeton de vérification."""
    user = _consume_email_token(db, payload.token, "verify")
    if user is None:
        raise HTTPException(status_code=400, detail="Jeton invalide ou expiré")
    user.status = "active"
    user.email_verified_at = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    db.commit()
    return MessageResponse(message="Email vérifié — tu peux te connecter.")


# ----------------------------------------------------------- mot de passe
@router.post("/forgot", response_model=MessageResponse, dependencies=[Depends(_limit_forgot)])
def forgot(payload: ForgotRequest, db: Session = Depends(get_db)) -> MessageResponse:
    """Envoie un lien de reset si le compte existe. Toujours 200 (anti-énumération)."""
    user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if user is not None and user.status != "disabled":
        raw = _issue_email_token(db, user, "reset", hours=1)
        send_email(user.email, "PokéAlpha — réinitialise ton mot de passe",
                   "Pour choisir un nouveau mot de passe :\n"
                   f"{_public_origin()}/reset?token={raw}\n\nCe lien expire dans 1 h. "
                   "Si tu n'es pas à l'origine de la demande, ignore cet email.")
    return MessageResponse(message="Si ce compte existe, un email a été envoyé.")


@router.post("/reset", response_model=MessageResponse)
def reset(payload: ResetRequest, db: Session = Depends(get_db)) -> MessageResponse:
    """Applique le nouveau mot de passe et révoque toutes les sessions."""
    user = _consume_email_token(db, payload.token, "reset")
    if user is None:
        raise HTTPException(status_code=400, detail="Jeton invalide ou expiré")
    user.password_hash = hash_password(payload.password)
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    db.query(AuthSession).filter(
        AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)
    ).update({"revoked_at": now})
    db.commit()
    return MessageResponse(message="Mot de passe mis à jour — reconnecte-toi.")
