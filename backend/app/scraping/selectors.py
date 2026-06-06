"""Chargement des sélecteurs CSS externalisés (``scraper/selectors.yaml``).

Aucun sélecteur en dur dans le code : tout vient de ce fichier versionné, pour
absorber les changements fréquents de structure de Vinted/LeBoncoin.
"""

from __future__ import annotations

import os
from functools import lru_cache

import yaml

#: Emplacement par défaut (monté dans les conteneurs). Surchargable par env.
DEFAULT_PATH = os.getenv("SCRAPER_SELECTORS_PATH", "/app/selectors.yaml")


def load_selectors(path: str | None = None) -> dict:
    with open(path or DEFAULT_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache
def get_selectors(path: str | None = None) -> dict:
    return load_selectors(path)
