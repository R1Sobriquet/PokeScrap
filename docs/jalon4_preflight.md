# Jalon 4 — Pré-vol : discord.py 2.x

Composants interactifs requis (`discord.ui.View`, `Button`, `Modal`, `TextInput`,
`discord.app_commands`) **confirmés disponibles en 2.x** (vérifié contre 2.7.1 ;
l'API composants/modals est stable depuis 2.0, incompatible 1.x).

**Version retenue : `discord.py>=2.4,<3`** (pin dans `bot/requirements.txt`).

> Note d'architecture : le dispatcher et les services d'interaction backend **ne
> dépendent pas** de discord.py. Ils manipulent des specs neutres
> (`app/notifications/specs.py`) ; seul l'adapter `adapters/discord_notifier.py`
> et `bot/bot.py` importent discord.py. Les tests backend (qui n'installent pas
> discord.py) restent donc exécutables.
