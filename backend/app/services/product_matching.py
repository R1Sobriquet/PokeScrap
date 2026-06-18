"""Auto-matching produits (offre détaillant ↔ produit interne PokeTrace).

Ordre : ``set + numéro`` → fuzzy name normalisé (UPC quand dispo). Score de
confiance. ≥ seuil → **auto-accepté** (lie ``retail_offers.product_id``) ; < seuil
→ file ``match_review`` (basse priorité, surfacée au digest). **Rien ne bloque** :
un non-matché reste snapshotté sur sa propre identité. Stdlib only (difflib).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_setting
from app.models import MatchReview, Product, RetailOffer

logger = logging.getLogger("services.product_matching")

_STOP = {"pokemon", "pokémon", "the", "of", "fr", "en", "edition", "édition"}


def normalize(text: str | None) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    tokens = [w for w in t.split() if w and w not in _STOP]
    return " ".join(sorted(tokens))


def similarity(a: str | None, b: str | None) -> float:
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def _best_product(offer: RetailOffer, products: list[Product]) -> tuple[Product | None, float, str]:
    """Meilleur produit candidat → (produit, confiance, méthode)."""
    title = offer.title or ""
    best, best_score, method = None, 0.0, "fuzzy"
    for p in products:
        # set + numéro : signal fort si présents dans le titre.
        if p.set_name and p.card_number and normalize(p.set_name) in normalize(title) \
                and re.search(rf"\b{re.escape(str(p.card_number))}\b", title):
            return p, 0.97, "set_number"
        score = max(similarity(title, p.name), similarity(title, f"{p.name} {p.set_name or ''}"))
        if score > best_score:
            best, best_score, method = p, score, "fuzzy"
    return best, round(best_score, 2), method


def _queue_review(db: Session, offer: RetailOffer, product: Product | None,
                  confidence: float, method: str) -> bool:
    product_ref = f"offer:{offer.id}"
    if db.scalar(select(MatchReview).where(MatchReview.product_ref == product_ref,
                                           MatchReview.status == "pending")) is not None:
        return False
    db.add(MatchReview(product_ref=product_ref,
                       candidate_ref=str(product.id) if product else None,
                       source="retail", method=method, confidence=confidence,
                       payload={"title": offer.title, "url": offer.url,
                                "candidate": product.name if product else None}))
    return True


def run_match_products(db: Session) -> dict:
    """Matche les offres retail non liées. Renvoie un résumé."""
    threshold = float(get_setting("match_confidence_threshold", default=0.82))
    products = list(db.scalars(select(Product)).all())
    stats = {"scanned": 0, "auto": 0, "review": 0, "no_candidate": 0}

    if not products:
        return {**stats, "summary": "aucun produit interne — rien à matcher"}

    offers = db.scalars(select(RetailOffer).where(RetailOffer.product_id.is_(None))).all()
    for offer in offers:
        stats["scanned"] += 1
        product, confidence, method = _best_product(offer, products)
        if product is None or confidence <= 0:
            stats["no_candidate"] += 1
            continue
        if confidence >= threshold:
            offer.product_id = product.id  # enrichit (active le scalping plus tard)
            stats["auto"] += 1
        elif _queue_review(db, offer, product, confidence, method):
            stats["review"] += 1
    db.commit()
    stats["summary"] = (f"{stats['scanned']} offres / {stats['auto']} auto / "
                        f"{stats['review']} à revoir / {stats['no_candidate']} sans candidat")
    return stats
