"""Market Intelligence — couche de monitoring des cartes sous-valorisées.

Pipeline d'AIDE À LA DÉCISION uniquement (jamais d'achat automatique) :
ingestion multi-sources → série ``card_price_snapshot`` (clé canonique = ID
TCGdex) → signaux ``daily_signals`` → digest Discord hebdomadaire.

Port unique ``CardPriceSource.fetch() -> list[CardSnapshot]`` (``ports``) ; un
adapter par source dans ``sources/`` (Cardmarket fichier, PPT, eBay actif, JP
stub). La politesse/quotas/garde-fous vivent côté JOB (``services``), pas dans
l'adapter — comme le moat marché existant.
"""
