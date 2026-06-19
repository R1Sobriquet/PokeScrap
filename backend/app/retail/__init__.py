"""Module « PokéStock FR » — veille restock / nouveaux SKU chez les détaillants.

Greffe hexagonale sur l'app d'arbitrage : domaine pur (``domain``), ports
(``ports``), et adapters de sourcing léger httpx (``politeness``/``sitemap``/
``fetch``/``parse``). Les notifications réutilisent le pipeline ``alerts`` →
dispatcher du bot (Discord + Telegram).
"""
