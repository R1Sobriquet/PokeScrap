"""Modèles ORM / DTO.

La source de vérité du schéma reste ``db/schema.sql``. On ne mappe ici que les
tables exploitées par les jalons en cours (le reste viendra au fil des jalons).
"""

from app.models.account_snapshot import AccountSnapshot
from app.models.alert import Alert
from app.models.grading_opportunity import GradingOpportunity
from app.models.job_run import JobRun
from app.models.data_quarantine import DataQuarantine
from app.models.lot import Lot
from app.models.lot_item import LotItem
from app.models.market_price_snapshot import MarketPriceSnapshot
from app.models.match_review import MatchReview
from app.models.ml_model import MlModel
from app.models.position import Position
from app.models.price_snapshot import PriceSnapshot
from app.models.product import Product
from app.models.psa_cert import PsaCert
from app.models.release import Release
from app.models.retail_offer import RetailOffer
from app.models.retail_stock_event import RetailStockEvent
from app.models.retailer import Retailer
from app.models.setting import Setting
from app.models.sourcing_listing import SourcingListing
from app.models.tier import TierConfig
from app.models.tracked_set import TrackedSet
from app.models.transaction import Transaction
from app.models.watchlist import Watchlist

__all__ = [
    "AccountSnapshot",
    "Alert",
    "DataQuarantine",
    "GradingOpportunity",
    "JobRun",
    "Lot",
    "LotItem",
    "MarketPriceSnapshot",
    "MatchReview",
    "MlModel",
    "Position",
    "PriceSnapshot",
    "Product",
    "PsaCert",
    "Release",
    "RetailOffer",
    "RetailStockEvent",
    "Retailer",
    "Setting",
    "SourcingListing",
    "TierConfig",
    "TrackedSet",
    "Transaction",
    "Watchlist",
]
