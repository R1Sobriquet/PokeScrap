"""Tests PokéStock FR Phase C : achat ASSISTÉ (plafonds, dry-run, kill-switch,
dégradation deep-link, idempotence). JAMAIS de paiement automatisé."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select

from app.models import Alert, BuyAttempt, BuyRule, Retailer, RetailOffer
from app.services.assisted_buy import CartBlocked, attempt_buy
from tests.conftest import insert_setting


def _setup(db, *, price="40.00", max_price="50.00", qty=1, enabled=True, retailer_kwargs=None):
    insert_setting(db, "assisted_buy_enabled", "true" if enabled else "false", "bool")
    r = Retailer(code="cultura", name="Cultura", is_active=1, **(retailer_kwargs or {}))
    db.add(r)
    db.flush()
    o = RetailOffer(retailer_id=r.id, url="https://c/p/etb.html", title="ETB",
                    current_stock_state="in_stock", current_price=Decimal(price),
                    is_watched=1, product_type="etb")
    db.add(o)
    db.flush()
    rule = BuyRule(scope="offer", scope_value=str(o.id), max_price=Decimal(max_price),
                   max_quantity=qty, is_enabled=1)
    db.add(rule)
    db.commit()
    return r, o, rule


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_price_ceiling_skips_and_audits(db_session):
    r, o, _ = _setup(db_session, price="100.00", max_price="50.00")  # prix > plafond
    insert_setting(db_session, "assisted_buy_dry_run", "false", "bool")
    res = attempt_buy(db_session, offer=o, retailer=r)
    assert res["status"] == "skipped" and res["reason"] == "price_ceiling"
    att = db_session.scalar(select(BuyAttempt))
    assert att.status == "skipped" and att.reason == "price_ceiling"
    assert _count(db_session, Alert) == 0  # on ne carte PAS un prix gonflé


def test_dry_run_carts_nothing_but_alerts(db_session):
    r, o, _ = _setup(db_session)
    insert_setting(db_session, "assisted_buy_dry_run", "true", "bool")
    called = []
    res = attempt_buy(db_session, offer=o, retailer=r,
                      cart_poster=lambda *a, **k: called.append(1))
    assert res["status"] == "dry_run" and not called  # AUCUN carting réel
    att = db_session.scalar(select(BuyAttempt))
    assert att.status == "dry_run"
    alert = db_session.scalar(select(Alert))
    assert alert.payload["subtype"] == "ASSISTED_BUY" and alert.payload["cart_url"]


def test_kill_switch_disables_everything(db_session):
    r, o, _ = _setup(db_session, enabled=False)
    res = attempt_buy(db_session, offer=o, retailer=r, cart_poster=lambda *a, **k: "x")
    assert res["status"] == "disabled"
    assert _count(db_session, BuyAttempt) == 0 and _count(db_session, Alert) == 0


def test_no_rule_no_action(db_session):
    insert_setting(db_session, "assisted_buy_enabled", "true", "bool")
    r = Retailer(code="cultura", name="Cultura", is_active=1)
    db_session.add(r)
    db_session.flush()
    o = RetailOffer(retailer_id=r.id, url="https://c/p/x.html", title="X",
                    current_stock_state="in_stock", current_price=Decimal("40"), is_watched=1)
    db_session.add(o)
    db_session.commit()
    assert attempt_buy(db_session, offer=o, retailer=r)["status"] == "no_rule"


def test_blocked_falls_back_to_deeplink(db_session):
    # dry off, mais pas d'endpoint/cookie → blocked + deep-link produit.
    r, o, _ = _setup(db_session)
    insert_setting(db_session, "assisted_buy_dry_run", "false", "bool")
    res = attempt_buy(db_session, offer=o, retailer=r)
    assert res["status"] == "blocked" and res["reason"] == "no_endpoint"
    att = db_session.scalar(select(BuyAttempt))
    assert att.status == "blocked" and att.cart_url == o.url


def test_anti_bot_block_degrades(db_session):
    r, o, _ = _setup(db_session, retailer_kwargs={
        "cart_add_url_template": "https://c/api/cart?sku={sku}&qty={qty}",
        "cart_view_url": "https://c/cart"})
    insert_setting(db_session, "assisted_buy_dry_run", "false", "bool")
    insert_setting(db_session, "assisted_buy_cookie_cultura", "session=abc", "string")

    def blocking_poster(*a, **k):
        raise CartBlocked("http_403")

    res = attempt_buy(db_session, offer=o, retailer=r, cart_poster=blocking_poster)
    assert res["status"] == "blocked" and res["reason"] == "anti_bot"
    att = db_session.scalar(select(BuyAttempt).where(BuyAttempt.status == "blocked"))
    assert att.cart_url == o.url  # dégrade en deep-link produit


def test_carted_success_with_session(db_session):
    r, o, _ = _setup(db_session, qty=2, retailer_kwargs={
        "cart_add_url_template": "https://c/api/cart?sku={sku}&qty={qty}",
        "cart_view_url": "https://c/cart"})
    insert_setting(db_session, "assisted_buy_dry_run", "false", "bool")
    insert_setting(db_session, "assisted_buy_cookie_cultura", "session=abc", "string")

    def poster(template, cookie, *, url, sku, qty, cart_view):
        assert cookie == "session=abc" and qty == 2  # session de l'utilisateur, cap qté
        return cart_view

    res = attempt_buy(db_session, offer=o, retailer=r, cart_poster=poster)
    assert res["status"] == "carted" and res["cart_url"] == "https://c/cart"
    att = db_session.scalar(select(BuyAttempt).where(BuyAttempt.status == "carted"))
    assert att.cart_url == "https://c/cart"
    alert = db_session.scalar(select(Alert))
    assert "3DS" in alert.payload["message"]  # rappel : l'humain finalise


def test_idempotent_no_double_cart(db_session):
    r, o, _ = _setup(db_session)
    insert_setting(db_session, "assisted_buy_dry_run", "true", "bool")
    attempt_buy(db_session, offer=o, retailer=r)
    res2 = attempt_buy(db_session, offer=o, retailer=r)
    assert res2["status"] == "duplicate"
    assert _count(db_session, BuyAttempt) == 1  # pas de double-panier
