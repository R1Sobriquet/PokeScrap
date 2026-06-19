"""Moat de données marché : port unique + sources interchangeables.

``ports`` : ``MarketDataPort`` (quotes / catalogue / sorties). ``sources/`` : un
adapter par fournisseur (PPT, TCGdex, eBay), tous derrière un flag ``settings`` +
quota. La politesse (cap/jour, jitter, circuit breaker) est portée par le JOB
(``app/services/market_snapshot.py``), pas par l'adapter — comme le retail.
"""
