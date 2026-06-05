"""Commandes de gestion (hors API).

Usage (dans le conteneur backend) ::

    python -m app.cli seed-catalog --file /seed/watchlist.yaml
    python -m app.cli refresh-prices

``seed-catalog`` et ``refresh-prices`` requièrent une clé PokeTrace valide
(``POKETRACE_API_KEY``) car ils appellent l'API réelle.
"""

from __future__ import annotations

import argparse
import logging
import sys

import yaml

from app.db import SessionLocal
from app.services.catalog_seed import seed_catalog
from app.services.ingestion import ingest_watchlist_prices
from app.services.runtime_settings import ensure_runtime_settings

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed-catalog", help="Peuple products + watchlist depuis un YAML")
    p_seed.add_argument("--file", default="/seed/watchlist.yaml", help="Chemin du watchlist.yaml")
    p_seed.set_defaults(func=cmd_seed_catalog)

    p_refresh = sub.add_parser("refresh-prices", help="Ingestion immédiate des prix watchlist")
    p_refresh.set_defaults(func=cmd_refresh_prices)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    args.func(args)


if __name__ == "__main__":
    main()
