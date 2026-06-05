"""Modèles ORM / DTO.

La source de vérité du schéma reste ``db/schema.sql``. On ne mappe ici que les
tables exploitées par les jalons en cours (le reste viendra au fil des jalons).
"""

from app.models.alert import Alert
from app.models.price_snapshot import PriceSnapshot
from app.models.product import Product
from app.models.psa_cert import PsaCert
from app.models.setting import Setting
from app.models.tier import TierConfig
from app.models.watchlist import Watchlist

__all__ = [
    "Alert",
    "PriceSnapshot",
    "Product",
    "PsaCert",
    "Setting",
    "TierConfig",
    "Watchlist",
]
