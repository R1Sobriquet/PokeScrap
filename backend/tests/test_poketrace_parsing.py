"""Tests du parsing des réponses PokeTrace (forme réelle : clé `data`)."""

from __future__ import annotations

import httpx

from app.adapters.poketrace import PokeTraceClient, PokeTracePriceProvider


def _provider(handler) -> PokeTracePriceProvider:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = PokeTraceClient("http://api.test/v1", "key", daily_limit=1000,
                             min_interval_ms=0, http_client=http)
    return PokeTracePriceProvider(client=client)


def test_search_reads_data_array():
    # Forme réelle : { "data": [...], "pagination": {...} }
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path.endswith("/cards")
        return httpx.Response(200, json={
            "data": [{"id": "u1", "name": "Charizard"}, {"id": "u2", "name": "Pikachu"}],
            "pagination": {"total": 2, "page": 1},
        })

    cards = _provider(handler).search_cards("Charizard", market="US", limit=5)
    assert [c["id"] for c in cards] == ["u1", "u2"]


def test_search_query_is_normalized():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["search"] = req.url.params.get("search")
        return httpx.Response(200, json={"data": []})

    _provider(handler).search_cards("  Charizard   EX  ", market="US")
    assert seen["search"] == "charizard ex"  # casse + espaces normalisés


def test_search_tolerates_bare_list():
    prov = _provider(lambda req: httpx.Response(200, json=[{"id": "u1"}]))
    assert prov.search_cards("x", market="US")[0]["id"] == "u1"


def test_get_card_unwraps_data_envelope():
    card = {"id": "u1", "prices": {"tcgplayer": {"NEAR_MINT": {"avg": 1}}}}

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": card})

    got = _provider(handler).get_card("u1", market="US")
    assert got["id"] == "u1" and "prices" in got


def test_get_card_flat_object_still_works():
    card = {"id": "u1", "prices": {}}
    got = _provider(lambda req: httpx.Response(200, json=card)).get_card("u1", market="US")
    assert got["id"] == "u1"


def test_history_reads_data_array():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"date": "2026-06-01", "avg": 10}]})

    hist = _provider(handler).get_price_history("u1", "NEAR_MINT", market="US")
    assert hist[0]["avg"] == 10
