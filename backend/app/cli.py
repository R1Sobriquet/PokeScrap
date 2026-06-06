"""Commandes de gestion (hors API).

Usage (dans le conteneur backend) ::

    python -m app.cli seed-catalog --file /seed/watchlist.yaml
    python -m app.cli refresh-prices
    python -m app.cli record-deposit 150
    python -m app.cli evaluate-listing 1
    python -m app.cli load-test-listings --file /seed/test_listings.yaml
    python -m app.cli pe-scan

``seed-catalog`` et ``refresh-prices`` requièrent une clé PokeTrace valide
(``POKETRACE_API_KEY``) car ils appellent l'API réelle.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys

import yaml

from app.db import SessionLocal
from app.models import SourcingListing
from app.services.buy_evaluation import evaluate_listing
from app.services.catalog_seed import seed_catalog
from app.services.ingestion import ingest_watchlist_prices
from app.services.kpi_snapshot import run_kpi_snapshot
from app.services.ledger import compute_kpis
from app.services.pe_signal_service import run_pe_accumulation_scan
from app.services.portfolio import record_deposit
from app.services.runtime_settings import ensure_runtime_settings
from app.services.selling_service import evaluate_position_sales

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] cli: %(message)s")
logger = logging.getLogger("cli")


def _load_entries(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or []
    if not isinstance(data, list):
        raise SystemExit(f"Le fichier {path} doit contenir une liste d'entrées.")
    return data


def cmd_seed_catalog(args: argparse.Namespace) -> None:
    entries = _load_entries(args.file)
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        result = seed_catalog(db, entries)
    logger.info("seed-catalog: %s", result)


def cmd_refresh_prices(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        written = ingest_watchlist_prices(db)
    logger.info("refresh-prices: %s snapshots écrits", written)


def cmd_record_deposit(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        tx = record_deposit(db, args.amount)
    logger.info("record-deposit: +%.2f€ (transaction #%s)", args.amount, tx.id)


def cmd_evaluate_listing(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        result = evaluate_listing(db, args.listing_id)
    logger.info("evaluate-listing #%s: %s", args.listing_id, result)


def cmd_load_test_listings(args: argparse.Namespace) -> None:
    entries = _load_entries(args.file)
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        for entry in entries:
            listing = SourcingListing(
                platform=entry.get("platform", "vinted"),
                url=entry.get("url", "https://example.test/listing"),
                raw_title=entry["raw_title"],
                asking_price=entry["asking_price"],
                shipping_cost=entry.get("shipping_cost", 0),
                protection_cost=entry.get("protection_cost", 0),
                currency=entry.get("currency", "EUR"),
                location=entry.get("location"),
                estimated_total_cards=entry.get("estimated_total_cards", 0),
                detected_products=entry.get("detected_products", []),
                status="new",
                detected_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
            )
            db.add(listing)
            db.commit()
            result = evaluate_listing(db, listing.id)
            logger.info("  %s → %s", entry["raw_title"][:50], result["status"])


def cmd_pe_scan(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        result = run_pe_accumulation_scan(db)
    logger.info("pe-scan: %s", result)


def cmd_evaluate_sales(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        result = evaluate_position_sales(db)
    logger.info("evaluate-sales: %s", result)


def cmd_kpis(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        logger.info("kpis: %s", compute_kpis(db))


def cmd_kpi_snapshot(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        ensure_runtime_settings(db)
        result = run_kpi_snapshot(db)
    logger.info("kpi-snapshot: %s", result)


def cmd_purge_sourcing(args: argparse.Namespace) -> None:
    from app.services.sourcing import purge_old_sourcing

    with SessionLocal() as db:
        ensure_runtime_settings(db)
        purged = purge_old_sourcing(db)
    logger.info("purge-sourcing: %s annonces supprimées", purged)


def cmd_intake_lot(args: argparse.Namespace) -> None:
    from app.services.liquidation_service import intake_lot

    with SessionLocal() as db:
        ensure_runtime_settings(db)
        logger.info("intake-lot #%s: %s", args.lot_id, intake_lot(db, args.lot_id))


def cmd_segment_lot(args: argparse.Namespace) -> None:
    from app.services.liquidation_service import segment_lot

    with SessionLocal() as db:
        ensure_runtime_settings(db)
        logger.info("segment-lot #%s: %s", args.lot_id, segment_lot(db, args.lot_id))


def cmd_promote_item(args: argparse.Namespace) -> None:
    from app.services.liquidation_service import promote_to_position

    with SessionLocal() as db:
        ensure_runtime_settings(db)
        logger.info("promote-item #%s: %s", args.item_id, promote_to_position(db, args.item_id))


def cmd_grading_scan(args: argparse.Namespace) -> None:
    from app.services.grading_service import run_grading_scan

    with SessionLocal() as db:
        ensure_runtime_settings(db)
        logger.info("grading-scan: %s", run_grading_scan(db))


def cmd_verify_cert(args: argparse.Namespace) -> None:
    from app.services.grading_service import verify_slab

    with SessionLocal() as db:
        ensure_runtime_settings(db)
        logger.info("verify-cert %s: %s", args.cert_number, verify_slab(db, args.cert_number))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed-catalog", help="Peuple products + watchlist depuis un YAML")
    p_seed.add_argument("--file", default="/seed/watchlist.yaml", help="Chemin du watchlist.yaml")
    p_seed.set_defaults(func=cmd_seed_catalog)

    p_refresh = sub.add_parser("refresh-prices", help="Ingestion immédiate des prix watchlist")
    p_refresh.set_defaults(func=cmd_refresh_prices)

    p_dep = sub.add_parser("record-deposit", help="Amorce le capital (transaction d'ajustement)")
    p_dep.add_argument("amount", type=float, help="Montant du dépôt en €")
    p_dep.set_defaults(func=cmd_record_deposit)

    p_eval = sub.add_parser("evaluate-listing", help="Évalue une annonce existante")
    p_eval.add_argument("listing_id", type=int)
    p_eval.set_defaults(func=cmd_evaluate_listing)

    p_load = sub.add_parser("load-test-listings", help="Charge + évalue des annonces de test")
    p_load.add_argument("--file", default="/seed/test_listings.yaml")
    p_load.set_defaults(func=cmd_load_test_listings)

    p_pe = sub.add_parser("pe-scan", help="Évalue le signal d'accumulation Prismatic Evolutions")
    p_pe.set_defaults(func=cmd_pe_scan)

    p_sales = sub.add_parser("evaluate-sales", help="Émet les alertes de vente (moteur S5)")
    p_sales.set_defaults(func=cmd_evaluate_sales)

    p_kpis = sub.add_parser("kpis", help="Affiche les 5 KPIs + cascade de trésorerie")
    p_kpis.set_defaults(func=cmd_kpis)

    p_snap = sub.add_parser("kpi-snapshot", help="Écrit le snapshot KPI + transitions de palier")
    p_snap.set_defaults(func=cmd_kpi_snapshot)

    p_purge = sub.add_parser("purge-sourcing", help="Purge les annonces dismissed/expired anciennes")
    p_purge.set_defaults(func=cmd_purge_sourcing)

    p_intake = sub.add_parser("intake-lot", help="Pré-remplit lot_items depuis la détection")
    p_intake.add_argument("lot_id", type=int)
    p_intake.set_defaults(func=cmd_intake_lot)

    p_seg = sub.add_parser("segment-lot", help="Segmente un lot (individuelles + vrac sans doublon)")
    p_seg.add_argument("lot_id", type=int)
    p_seg.set_defaults(func=cmd_segment_lot)

    p_prom = sub.add_parser("promote-item", help="Promeut un lot_item en position suivie")
    p_prom.add_argument("item_id", type=int)
    p_prom.set_defaults(func=cmd_promote_item)

    p_grade = sub.add_parser("grading-scan", help="Scan grading (no-op hors mode Pro)")
    p_grade.set_defaults(func=cmd_grading_scan)

    p_cert = sub.add_parser("verify-cert", help="Vérifie l'authenticité d'un cert PSA")
    p_cert.add_argument("cert_number")
    p_cert.set_defaults(func=cmd_verify_cert)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    args.func(args)


if __name__ == "__main__":
    main()
