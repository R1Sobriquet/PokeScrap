"""Bot Discord — Jalon 1.

Connexion gateway (sortante, aucun port entrant). Au démarrage, poste un message
de vie dans le salon ``#systeme`` et enregistre un handler d'interactions
(boutons) vide, prêt pour les jalons suivants. Aucune logique métier.
"""

from __future__ import annotations

import logging
import os

import discord

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] bot: %(message)s"
)
logger = logging.getLogger("bot")

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
SYSTEME_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_SYSTEME", "")

STARTUP_MESSAGE = "🟢 App démarrée — Jalon 1"

# Intents minimaux : pas besoin du contenu des messages au Jalon 1.
intents = discord.Intents.default()
client = discord.Client(intents=intents)


@client.event
async def on_ready() -> None:
    logger.info("Connecté en tant que %s.", client.user)
    channel = None
    if SYSTEME_CHANNEL_ID:
        try:
            channel = client.get_channel(int(SYSTEME_CHANNEL_ID)) or await client.fetch_channel(
                int(SYSTEME_CHANNEL_ID)
            )
        except (ValueError, discord.DiscordException) as exc:
            logger.warning("Salon #systeme introuvable (%s).", exc)

    if channel is not None:
        await channel.send(STARTUP_MESSAGE)
        logger.info("Message de démarrage posté dans #systeme.")
    else:
        logger.warning("DISCORD_CHANNEL_SYSTEME non configuré : message non posté.")


@client.event
async def on_interaction(interaction: discord.Interaction) -> None:
    """Handler d'interactions (boutons) — vide, prêt pour les jalons 2+."""
    logger.info("Interaction reçue (type=%s) — non gérée au Jalon 1.", interaction.type)


def main() -> None:
    if not TOKEN:
        logger.warning("DISCORD_BOT_TOKEN absent : le bot reste inactif (idle).")
        # On ne crash pas : permet à `restart: unless-stopped` de ne pas boucler.
        import time

        while True:
            time.sleep(3600)
    client.run(TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
