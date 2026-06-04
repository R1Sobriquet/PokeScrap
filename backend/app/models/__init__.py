"""Modèles ORM / DTO.

Jalon 1 ne déclare que les tables réellement utilisées par les fondations
(``settings``, ``tiers_config``). La source de vérité du schéma reste
``db/schema.sql`` ; les autres tables seront mappées au fil des jalons 2+.
"""

from app.models.setting import Setting
from app.models.tier import TierConfig

__all__ = ["Setting", "TierConfig"]
