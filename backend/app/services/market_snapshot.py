"""Job ``market-snapshot-daily`` — tire les prix marché vers le moat.

Watched-only, plafonné par source (``RequestBudget``, honore le quota free —
ex. PPT 90<100/j avec un run/jour), délai+jitter, circuit breaker (réutilise
``app/retail/politeness``). Chaque prix passe les garde-fous (``market_ingest``)
puis upsert idempotent. Télémétrie de run persistée pour le moniteur santé.
"""

from __future__ import annotations

import datetime as dt
import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.marketdata.domain import WatchItem
from app.marketdata.http import MarketBlocked
from app.marketdata.sources import build_sources
from app.models import Product, Watchlist
from app.retail import politeness
from app.services.market_ingest import ingest_quote
from app.services.source_health import record_source_run

logger = logging.getLogger("services.market_snapshot")

TIER_RANK = {"S++": 0, "S": 1, "A": 2, "B": 3, "C": 4}


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _watch_items(db: Session) -> list[WatchItem]:
    rows = db.execute(
        select(Watchlist, Product).join(Product, Watchlist.product_id == Product.id)
        .where(Watchlist.is_active == 1)
    ).all()
    rows.sort(key=lambda wp: TIER_RANK.get(wp[0].tier, 9))  # priorité par tier (quota)
    return [
        WatchItem(product_ref=str(p.id), name=p.name, product_type=p.product_type,
                  set_name=p.set_name, number=p.card_number)
        for _w, p in rows
    ]


def run_market_snapshot(db: Session, *, sources: dict | None = None) -> dict:
    if not bool(get_setting("marketdata_enabled", default=False)):
        return {"summary": "moat désactivé (marketdata_enabled=false)"}

    sources = sources if sources is not None else build_sources()
    quote_sources = {c: s for c, s in sources.items() if "quotes" in s.capabilities}
    items = _watch_items(db)
    now = _utcnow()
    min_delay = int(get_setting("marketdata_min_delay_ms", default=1500))
    max_err = int(get_setting("marketdata_circuit_max_errors", default=5))
    cooldown_cap = int(get_setting("scrape_blocked_cooldown_min", default=120))

    overall = {"sources": {}, "stored": 0, "quarantined": 0, "upgrade_required": False}

    for code, source in quote_sources.items():
        cap = int(get_setting(f"marketdata_request_cap_per_run_{code}", default=40))
        st = {"requests": 0, "stored": 0, "quarantined": 0, "errors": 0,
              "blocked": 0, "truncated": False}

        if politeness.circuit_open(db, f"mkt_{code}", now, max_err):
            st["blocked"] = 1
            logger.info("market: circuit ouvert pour %s — source ignorée.", code)
            record_source_run(db, code, st, now=now)
            overall["sources"][code] = st
            continue

        budget = politeness.RequestBudget(cap)
        for item in items:
            if not budget.allow():
                st["truncated"] = len(items) > cap
                break
            st["requests"] += 1
            try:
                quotes = source.fetch_quotes([item])
            except MarketBlocked as exc:
                mins = politeness.record_retailer_error(db, f"mkt_{code}", now,
                                                        cooldown_cap_min=cooldown_cap)
                logger.warning("market: %s bloqué (%s) — backoff %s min.", code, exc.reason, mins)
                st["blocked"] += 1
                break
            except Exception:  # noqa: BLE001 - une page KO ne casse pas le run
                logger.exception("market: échec fetch %s sur %s", item.product_ref, code)
                st["errors"] += 1
                continue

            politeness.clear_retailer_errors(db, f"mkt_{code}")
            for q in quotes:
                st[ingest_quote(db, q, now)] += 1
            db.commit()
            delay = politeness.jittered_delay_s(min_delay)
            if delay:
                time.sleep(delay)

        if st["truncated"]:
            overall["upgrade_required"] = True
        record_source_run(db, code, st, now=now)
        overall["sources"][code] = st
        overall["stored"] += st["stored"]
        overall["quarantined"] += st["quarantined"]

    parts = [f"{c}:{s['stored']}↑/{s['quarantined']}⌀" for c, s in overall["sources"].items()]
    up = " — UPGRADE quota requis (watched > cap)" if overall["upgrade_required"] else ""
    overall["summary"] = f"snapshots {' '.join(parts) or '—'}{up}"
    return overall
