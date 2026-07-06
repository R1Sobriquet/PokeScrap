"""Primitives de sécurité : bcrypt, JWT court, refresh rotatif, dépendances.

Multi-utilisateurs (Phase A) : les identités vivent dans la table ``users``.
L'admin historique (``.env`` ``ADMIN_USERNAME``/``ADMIN_PASSWORD``) est migré
idempotemment vers une ligne ``users`` (``ensure_admin_user``) — son hash bcrypt
continue d'être amorcé dans ``settings.admin_password_hash`` (compat).

Modèle de session :
  * **access token** JWT HS256 court (15 min par défaut), ``sub`` = id utilisateur
    (compat transitoire : un ``sub`` non numérique est traité comme username) ;
  * **refresh token** opaque (43 chars urlsafe), stocké **hashé SHA-256** dans
    ``auth_sessions``, **rotation** à chaque usage, révocable ; la réutilisation
    d'un refresh déjà tourné révoque toutes les sessions de l'utilisateur
    (détection de vol).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets
from typing import Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings, invalidate_setting

_ADMIN_HASH_KEY = "admin_password_hash"
_ALGORITHM = "HS256"

# tokenUrl sert surtout à la doc OpenAPI / au bouton "Authorize".
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


# --------------------------------------------------------------------- bcrypt
def hash_password(password: str) -> str:
    """Hache un mot de passe en bcrypt et renvoie le hash encodé (utf-8)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Vérifie un mot de passe en clair contre un hash bcrypt."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# ------------------------------------------------------------------------ JWT
def create_access_token(subject: str) -> str:
    """Émet un JWT signé HS256 pour ``subject`` (id utilisateur, en str)."""
    settings = get_settings()
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.jwt_expire_min),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Décode et valide un JWT. Lève ``jwt.PyJWTError`` si invalide/expiré."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])


# ------------------------------------------------------- refresh (opaque)
def _sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_refresh(db: Session, user, user_agent: str | None = None) -> str:
    """Crée une session refresh pour ``user`` et renvoie le token EN CLAIR.

    Seule l'empreinte SHA-256 est persistée — le clair ne quitte le serveur que
    dans le cookie httpOnly posé par ``/auth/login`` / ``/auth/refresh``.
    """
    from app.models import AuthSession

    settings = get_settings()
    raw = secrets.token_urlsafe(32)
    db.add(AuthSession(
        user_id=user.id,
        refresh_hash=_sha256(raw),
        expires_at=(dt.datetime.now(dt.timezone.utc)
                    + dt.timedelta(days=settings.refresh_expire_days)).replace(tzinfo=None),
        user_agent=(user_agent or "")[:255] or None,
    ))
    db.commit()
    return raw


def rotate_refresh(db: Session, raw: str):
    """Valide un refresh, le révoque et en émet un neuf. Renvoie ``(user, new_raw)``.

    Renvoie ``None`` si inconnu/expiré. Un refresh **déjà révoqué** présenté à
    nouveau = réutilisation (vol probable) → toutes les sessions de l'utilisateur
    sont révoquées.
    """
    from app.models import AuthSession, User

    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    sess = db.scalar(select(AuthSession).where(AuthSession.refresh_hash == _sha256(raw)))
    if sess is None:
        return None
    if sess.revoked_at is not None:  # réutilisation → on coupe tout
        db.query(AuthSession).filter(
            AuthSession.user_id == sess.user_id, AuthSession.revoked_at.is_(None)
        ).update({"revoked_at": now})
        db.commit()
        return None
    if sess.expires_at <= now:
        return None

    user = db.get(User, sess.user_id)
    if user is None or user.status != "active":
        return None
    sess.revoked_at = now
    new_raw = issue_refresh(db, user)  # commit inclus
    return user, new_raw


def revoke_refresh(db: Session, raw: str) -> None:
    """Révoque la session associée à un refresh (logout). Silencieux si inconnue."""
    from app.models import AuthSession

    sess = db.scalar(select(AuthSession).where(AuthSession.refresh_hash == _sha256(raw)))
    if sess is not None and sess.revoked_at is None:
        sess.revoked_at = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        db.commit()


# --------------------------------------------------- amorçage du hash admin
def ensure_admin_hash() -> None:
    """Garantit que ``settings.admin_password_hash`` reflète ``ADMIN_PASSWORD``.

    Appelée au démarrage : si la clé est absente, ou si le mot de passe de
    ``.env`` a changé, (re)calcule le hash bcrypt et l'écrit dans la table.
    Idempotent.
    """
    from app.db import engine

    settings = get_settings()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT setting_value FROM settings WHERE setting_key = :k"),
            {"k": _ADMIN_HASH_KEY},
        ).first()

        stored = row[0] if row else None
        needs_write = stored is None or not verify_password(
            settings.admin_password, stored
        )
        if not needs_write:
            return

        new_hash = hash_password(settings.admin_password)
        conn.execute(
            text(
                "INSERT INTO settings (setting_key, setting_value, value_type, description) "
                "VALUES (:k, :v, 'string', 'Hash bcrypt du mot de passe admin (amorcé au boot)') "
                "ON DUPLICATE KEY UPDATE setting_value = :v"
            ),
            {"k": _ADMIN_HASH_KEY, "v": new_hash},
        )
    invalidate_setting(_ADMIN_HASH_KEY)


def _admin_hash(db: Session) -> str | None:
    row = db.execute(
        text("SELECT setting_value FROM settings WHERE setting_key = :k"),
        {"k": _ADMIN_HASH_KEY},
    ).first()
    return row[0] if row else None


def ensure_admin_user(db: Session):
    """Crée/synchronise idempotemment la ligne ``users`` de l'admin historique.

    Reprend le hash ``settings.admin_password_hash`` (source de vérité du mot de
    passe admin, resynchronisée par ``ensure_admin_hash``) et, à la création,
    le palier courant ``settings.current_tier_number`` de l'installation
    mono-user. Renvoie l'objet ``User`` admin.
    """
    from app.config import get_setting
    from app.models import User

    settings = get_settings()
    admin = db.scalar(select(User).where(User.username == settings.admin_username))
    pw_hash = _admin_hash(db) or hash_password(settings.admin_password)
    if admin is None:
        try:
            tier = int(get_setting("current_tier_number", default=1) or 1)
        except (TypeError, ValueError):
            tier = 1
        admin = User(
            email=settings.admin_email,
            username=settings.admin_username,
            password_hash=pw_hash,
            role="admin",
            plan="pro",
            status="active",
            email_verified_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
            current_tier=tier,
        )
        db.add(admin)
    else:  # resynchronise le hash si ADMIN_PASSWORD a changé dans .env
        admin.password_hash = pw_hash
        admin.role = "admin"
        admin.status = "active"
    db.commit()
    return admin


def authenticate(username: str, password: str) -> bool:
    """(Legacy mono-admin) Vérifie identifiant/mot de passe contre le hash stocké."""
    from app.db import engine

    settings = get_settings()
    if username != settings.admin_username:
        return False

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT setting_value FROM settings WHERE setting_key = :k"),
            {"k": _ADMIN_HASH_KEY},
        ).first()

    if row is None:
        return False
    return verify_password(password, row[0])


def authenticate_user(db: Session, identifier: str, password: str):
    """Authentifie par username OU email → ``User`` actif, sinon ``None``.

    Compat : si aucune ligne ``users`` n'existe pour l'admin ``.env`` mais que le
    couple legacy est valide, la ligne admin est créée à la volée (installations
    dont le boot n'a pas encore joué ``ensure_admin_user``).
    """
    from app.models import User

    user = db.scalar(select(User).where(
        (User.username == identifier) | (User.email == identifier)
    ))
    if user is not None:
        if user.status == "disabled":
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    settings = get_settings()
    if identifier == settings.admin_username and authenticate(identifier, password):
        return ensure_admin_user(db)
    return None


# ------------------------------------------------------------- dépendances
def _resolve_user(db: Session, sub: str):
    """``sub`` → ``User``. Compat : ``sub`` numérique = id, sinon username."""
    from app.models import User

    if sub.isdigit():
        return db.get(User, int(sub))
    user = db.scalar(select(User).where(User.username == sub))
    if user is None and sub == get_settings().admin_username:
        # Jeton legacy émis avant la migration : l'admin est créé à la volée.
        user = ensure_admin_user(db)
    return user


def get_current_user(token: str = Depends(oauth2_scheme)):
    """Dépendance FastAPI : renvoie l'objet ``User`` actif, ou 401.

    Ouvre sa propre session courte (indépendante du ``get_db`` de la route) :
    la dépendance est déclarée au niveau **router** sur 5 routers existants,
    dont certains endpoints n'injectent pas de session.
    """
    from app.db import SessionLocal

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise credentials_error
    sub = payload.get("sub")
    if not sub:
        raise credentials_error

    with SessionLocal() as db:
        user = _resolve_user(db, str(sub))
        if user is None or user.status == "disabled":
            raise credentials_error
        db.expunge(user)  # objet détaché, utilisable après fermeture de la session
    return user


def require_admin(user=Depends(get_current_user)):
    """Dépendance : réserve la route au rôle ``admin`` (403 sinon)."""
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Réservé à l'administrateur")
    return user
