"""Flux d'événements temps réel (SSE) — pousse au lieu de faire poller.

``GET /events/stream`` tient une connexion ``text/event-stream`` et émet un
événement quand l'état observé change côté serveur (sondé en LOCAL sur la base,
ce qui est bon marché — contrairement aux N clients HTTP qui repollent) :

  * ``alerts``   — nouvelle alerte pending (max id / count a bougé) ;
  * ``offers``   — un ``retail_stock_event`` récent a changé un état de stock ;
  * heartbeat commenté (``: ping``) toutes les ~15 s pour garder le socket ouvert.

Chaque événement transporte ``{"paths": [...]}`` : les chemins d'API que le
frontend doit revalider (il garde son polling comme filet de sécurité).

Auth : EventSource ne peut pas poser d'en-tête Authorization → le JWT passe en
query string (``?token=``), vérifié par ``decode_token``. Acceptable ici :
app mono-utilisateur servie en local/Tailscale, jamais exposée publiquement.

``?once=true`` émet un instantané puis ferme (utilisé par les tests).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.auth import decode_token, get_current_user
from app.config import get_settings
from app.models import Alert, RetailStockEvent

logger = logging.getLogger("api.events")

router = APIRouter(tags=["events"])

_POLL_S = 3.0        # sonde DB locale (pas de coût réseau client)
_HEARTBEAT_S = 15.0  # commentaire keep-alive


def _snapshot() -> dict:
    """État observé : (max id, count) des alertes pending + dernier stock event."""
    from app.db import SessionLocal  # résolu à l'appel (respecte le patch de test)

    with SessionLocal() as db:
        alert_max, alert_count = db.execute(
            select(func.max(Alert.id), func.count()).where(Alert.status == "pending")
        ).one()
        last_stock = db.scalar(select(func.max(RetailStockEvent.id)))
    return {"alerts": (alert_max or 0, alert_count or 0), "stock": last_stock or 0}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _diff_events(prev: dict, cur: dict) -> list[str]:
    """Compare deux instantanés → messages SSE à émettre."""
    out: list[str] = []
    if cur["alerts"] != prev["alerts"]:
        out.append(_sse("alerts", {"paths": ["/alerts?status=pending"]}))
    if cur["stock"] != prev["stock"]:
        out.append(_sse("offers", {
            "paths": ["/retail/offers?watched=true", "/retail/opportunities"],
        }))
    return out


async def _stream(once: bool):
    prev = await asyncio.to_thread(_snapshot)
    # Instantané initial : dit au client que le flux est vivant.
    yield _sse("hello", {"ts": dt.datetime.now(dt.timezone.utc).isoformat()})
    if once:
        return
    elapsed = 0.0
    while True:
        await asyncio.sleep(_POLL_S)
        elapsed += _POLL_S
        try:
            cur = await asyncio.to_thread(_snapshot)
        except Exception:  # noqa: BLE001 - une base momentanément KO ne tue pas le flux
            logger.exception("events: snapshot en échec — on retentera.")
            continue
        for msg in _diff_events(prev, cur):
            yield msg
            elapsed = 0.0
        prev = cur
        if elapsed >= _HEARTBEAT_S:
            yield ": ping\n\n"
            elapsed = 0.0


@router.get("/events/ticket")
def events_ticket(user=Depends(get_current_user)) -> dict:
    """Ticket SSE éphémère (60 s, usage unique de facto).

    ``EventSource`` ne pose pas d'en-têtes : plutôt que d'exposer l'access token
    complet dans l'URL (logs, historiques), le front échange son Bearer contre ce
    ticket court à portée limitée (``purpose=sse``) juste avant d'ouvrir le flux.
    """
    settings = get_settings()
    now = dt.datetime.now(dt.timezone.utc)
    ticket = pyjwt.encode(
        {"sub": str(user.id), "purpose": "sse", "iat": now,
         "exp": now + dt.timedelta(seconds=60)},
        settings.jwt_secret, algorithm="HS256",
    )
    return {"ticket": ticket}


@router.get("/events/stream")
async def events_stream(token: str = Query(...), once: bool = Query(False)) -> StreamingResponse:
    """Flux SSE authentifié par ticket court (ou access token legacy en transition)."""
    try:
        payload = decode_token(token)
    except pyjwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Token invalide") from exc
    purpose = payload.get("purpose")
    if purpose is not None and purpose != "sse":
        raise HTTPException(status_code=401, detail="Jeton inadapté au flux")
    return StreamingResponse(
        _stream(once),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
