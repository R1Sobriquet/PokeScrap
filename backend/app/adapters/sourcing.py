"""Provider de sourcing — note d'architecture.

Les implémentations concrètes (Playwright) vivent dans le conteneur ``scraper/``
(``scraper/vinted.py``, ``scraper/leboncoin.py``) car elles importent Playwright,
absent de l'image backend. Le port ``SourcingProvider`` (interface ``scrape``) est
défini dans ``app.adapters.ports`` ; le parsing pur est dans ``app.scraping``.

Ce module ne contient donc plus de stub : il documente seulement où trouver les
adapters réels, afin d'éviter d'importer Playwright côté backend/tests.
"""
