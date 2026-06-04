"""Primitives de sécurité : hachage bcrypt, JWT, dépendance d'authentification.

Modèle mono-utilisateur : l'identifiant vient de ``.env`` (``ADMIN_USERNAME``),
le mot de passe est fourni en clair dans ``.env`` puis **haché en bcrypt au
premier démarrage** et persisté dans la table ``settings`` sous la clé
``admin_password_hash``. Les connexions vérifient le mot de passe soumis contre
ce hash stocké (jamais contre la valeur en clair).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text

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
    """Émet un JWT signé HS256 pour ``subject`` (le username)."""
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


def authenticate(username: str, password: str) -> bool:
    """Vérifie un couple identifiant/mot de passe contre le hash stocké."""
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


# ------------------------------------------------------------- dépendance
def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Dépendance FastAPI protégeant une route : renvoie le username ou 401."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise credentials_error
    username = payload.get("sub")
    if not username:
        raise credentials_error
    return username
