"""Bot Discord — Jalon 4 (adapter Discord + boucle de dispatch).

Le bot est l'adapter Discord : il connecte la gateway, fournit un ``Notifier``,
exécute la boucle de dispatch (services backend, en thread pour rester sync), et
route les clics de boutons vers les handlers backend (mutations atomiques).
Aucune logique métier ici.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import os

import discord
from discord.ext import tasks

from app.adapters.discord_notifier import DiscordNotifier
from app.config import get_setting
from app.db import SessionLocal
from app.models import Alert, SourcingListing
from app.services.alert_dispatcher import dispatch_pending, flush_digest, is_digest_time
from app.services.interactions import (
    handle_buy_purchased,
    handle_ignore,
    handle_palier_confirm,
    handle_palier_later,
)
from app.services.runtime_settings import ensure_runtime_settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] bot: %(message)s"
)
logger = logging.getLogger("bot")

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
PING_USER_ID = os.getenv("DISCORD_PING_USER_ID", "")
CHANNELS = {
    "achats": os.getenv("DISCORD_CHANNEL_ACHATS", ""),
    "ventes": os.getenv("DISCORD_CHANNEL_VENTES", ""),
    "portefeuille": os.getenv("DISCORD_CHANNEL_PORTEFEUILLE", ""),
    "systeme": os.getenv("DISCORD_CHANNEL_SYSTEME", ""),
}

intents = discord.Intents.default()
client = discord.Client(intents=intents)
notifier: DiscordNotifier | None = None


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


# ----------------------------------------------------- bridges DB (en thread)
def _dispatch_once() -> None:
    with SessionLocal() as db:
        now = _utcnow()
        dispatch_pending(db, notifier, now=now)
        poll = int(get_setting("dispatcher_poll_sec", default=20))
        if is_digest_time(now, str(get_setting("digest_time", default="09:00")), poll):
            flush_digest(db, notifier, now=now)


def _default_price(alert_id: int) -> float:
    with SessionLocal() as db:
        alert = db.get(Alert, alert_id)
        if alert and alert.sourcing_listing_id:
            listing = db.get(SourcingListing, alert.sourcing_listing_id)
            if listing is not None:
                return float(listing.acquisition_cost_total or listing.asking_price or 0)
    return 0.0


def _run(fn, *args, **kwargs):
    with SessionLocal() as db:
        return fn(db, *args, **kwargs)


# --------------------------------------------------------------- modal achat
class BoughtModal(discord.ui.Modal, title="Achat enregistré"):
    def __init__(self, alert_id: int, default_price: float):
        super().__init__()
        self.alert_id = alert_id
        self.price = discord.ui.TextInput(label="Prix payé (€)", default=f"{default_price:.2f}")
        self.fees = discord.ui.TextInput(label="Frais (€)", default="0", required=False)
        self.add_item(self.price)
        self.add_item(self.fees)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            price = float(str(self.price.value).replace(",", "."))
            fees = float(str(self.fees.value or "0").replace(",", "."))
        except ValueError:
            await interaction.response.send_message("Montant invalide.", ephemeral=True)
            return
        res = await asyncio.to_thread(
            _run, handle_buy_purchased, self.alert_id, price_paid=price, fees=fees
        )
        if res["status"] == "already_processed":
            msg = "Déjà traité."
        elif res["status"] == "ok":
            msg = f"✅ Achat enregistré (lot #{res['lot_id']}, coût {res['total_cost']:.2f} €)."
        else:
            msg = "Alerte introuvable."
        await interaction.response.send_message(msg, ephemeral=True)


# --------------------------------------------------------- handler de clics
@client.event
async def on_interaction(interaction: discord.Interaction) -> None:
    if interaction.type != discord.InteractionType.component:
        return  # les soumissions de modal sont gérées par BoughtModal.on_submit
    custom_id = (interaction.data or {}).get("custom_id", "")
    if not custom_id.startswith("alert:"):
        return
    try:
        _, raw_id, _, action = custom_id.split(":")
        alert_id = int(raw_id)
    except ValueError:
        return

    if action == "bought":
        default_price = await asyncio.to_thread(_default_price, alert_id)
        await interaction.response.send_modal(BoughtModal(alert_id, default_price))
        return

    if action == "ignore":
        res = await asyncio.to_thread(_run, handle_ignore, alert_id)
    elif action == "confirm":
        res = await asyncio.to_thread(_run, handle_palier_confirm, alert_id)
    elif action == "later":
        res = await asyncio.to_thread(_run, handle_palier_later, alert_id)
    else:
        return

    already = res.get("status") == "already_processed"
    await interaction.response.send_message(
        "Déjà traité." if already else "✅ Pris en compte.", ephemeral=True
    )


# ----------------------------------------------------------------- boucle
@tasks.loop(seconds=20)
async def dispatch_loop() -> None:
    try:
        await asyncio.to_thread(_dispatch_once)
    except Exception:  # pragma: no cover - robustesse de la boucle
        logger.exception("Erreur dans la boucle de dispatch")


def _post_startup_test_alert() -> None:
    """Insère une alerte tech_error de démarrage (poussée par le dispatcher)."""
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        db.add(
            Alert(
                alert_type="tech_error",
                severity="warning",
                status="pending",
                title="Bot démarré — Jalon 4",
                payload={"message": "🟢 Dispatcher actif, canal #systeme opérationnel."},
            )
        )
        db.commit()


@client.event
async def on_ready() -> None:
    global notifier
    logger.info("Connecté en tant que %s.", client.user)
    notifier = DiscordNotifier(client, {k: v for k, v in CHANNELS.items() if v}, PING_USER_ID or None)

    await asyncio.to_thread(_post_startup_test_alert)

    if not dispatch_loop.is_running():
        poll = await asyncio.to_thread(lambda: int(get_setting("dispatcher_poll_sec", default=20)))
        dispatch_loop.change_interval(seconds=poll)
        dispatch_loop.start()
    logger.info("Boucle de dispatch démarrée.")


def main() -> None:
    if not TOKEN:
        logger.warning("Discord non configuré (DISCORD_BOT_TOKEN absent) — dispatch en dry-run.")
        import time

        while True:
            time.sleep(3600)
    client.run(TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
