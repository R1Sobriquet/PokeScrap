"""Extraction de features — IDENTIQUE à l'entraînement et à l'inférence.

Parité train/serve garantie : on n'utilise QUE des features disponibles aussi
bien pour un produit historique (avec prix) que pour une sortie future (sans
prix). Les signaux de timing (jours avant sortie) ne sont donc PAS des features
du modèle — ils alimentent la confiance, calculée à part.
"""

from __future__ import annotations

#: Ordre figé des features (le vecteur dépend de cet ordre). Les features marché
#: valent 0 quand aucun snapshot n'existe (sorties futures incluses) → parité
#: train/serve : le modèle apprend du produit-only à défaut, du signal marché si
#: l'historique le permet.
FEATURE_NAMES = [
    "is_sealed", "is_single",
    "kw_upc", "kw_etb", "kw_display", "kw_bundle", "kw_booster",
    "lang_en", "lang_jp",
    "name_tokens",
    "mkt_has_data", "mkt_eu_us_spread", "mkt_volatility", "mkt_momentum",
]

_KW = {
    "kw_upc": ("upc", "ultra premium"),
    "kw_etb": ("etb", "coffret", "elite trainer"),
    "kw_display": ("display", "booster box"),
    "kw_bundle": ("bundle", "tin", "blister", "pack"),
    "kw_booster": ("booster",),
}
_SEALED_HINTS = ("etb", "coffret", "display", "booster box", "upc",
                 "bundle", "tin", "elite trainer", "blister")


def extract_features(*, product_type: str | None, name: str | None,
                     language: str | None = "EN", market: dict | None = None) -> list[float]:
    """Vecteur de features (floats) dans l'ordre ``FEATURE_NAMES``.

    ``market`` (optionnel) : ``{spread, volatility, momentum}`` dérivés des
    ``market_price_snapshots`` ; absent → bloc marché à 0 (parité train/serve).
    """
    ptype = (product_type or "").lower()
    blob = f"{ptype} {name or ''}".lower()

    is_sealed = 1.0 if (ptype == "sealed" or any(h in blob for h in _SEALED_HINTS)) else 0.0
    is_single = 1.0 if ptype == "single" else (0.0 if is_sealed else 1.0)

    kw = {key: (1.0 if any(n in blob for n in needles) else 0.0) for key, needles in _KW.items()}

    lang = (language or "").lower()
    lang_en = 1.0 if lang.startswith("en") else 0.0
    lang_jp = 1.0 if lang in ("jp", "ja", "jpn", "japanese") else 0.0

    name_tokens = min(len((name or "").split()), 12) / 12.0

    m = market or {}
    mkt_has = 1.0 if m else 0.0
    mkt_spread = float(m.get("spread", 0.0) or 0.0)
    mkt_vol = float(m.get("volatility", 0.0) or 0.0)
    mkt_mom = float(m.get("momentum", 0.0) or 0.0)

    return [
        is_sealed, is_single,
        kw["kw_upc"], kw["kw_etb"], kw["kw_display"], kw["kw_bundle"], kw["kw_booster"],
        lang_en, lang_jp,
        name_tokens,
        mkt_has, mkt_spread, mkt_vol, mkt_mom,
    ]
