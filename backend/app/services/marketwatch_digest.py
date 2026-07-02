"""Digest hebdomadaire « cartes à cibler » → Discord (ou stdout en dry-run).

Regroupé par tranche budget (<10 € / 10–20 € / ≤50 €) + une section MOVERS
(plus fortes hausses 7 j en sortie de creux). Le ``payload`` JSON est la source
unique : l'embed du bot (``render.py``) et le rendu texte ``--dry-run`` en
dérivent tous deux (zéro duplication).

Livraison : le job crée une ``Alert`` (type ``marketwatch``, sévérité ``warning``
→ envoyée telle quelle par le dispatcher, sans être fondue dans le digest info) ;
le bot la poste sur le canal ``marketwatch``. ``--dry-run`` imprime sur stdout,
n'écrit rien, ne poste rien. Monitoring/aide à la décision — aucun achat auto.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Alert, DailySignal, TcgdexCard
from app.notifications.specs import COLOR_INFO, EmbedField, EmbedSpec
from app.services.marketwatch_score import select_targets

BAND_LABEL = {"lt10": "💶 Moins de 10 €", "10_20": "💶 10–20 €", "lte50": "💶 Jusqu'à 50 €"}
MOVERS_LIMIT = 5


def _money(v) -> str:
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return "—"


def _card_line(row: DailySignal, card: TcgdexCard | None) -> dict:
    name = (card.name_en or card.name_fr or card.name_jp) if card else row.card_id
    gap = round((1.0 - float(row.near_low or 0)) * 100)  # % au-dessus du plancher
    return {
        "card_id": row.card_id,
        "name": name or row.card_id,
        "rarity": (card.rarity if card else None) or "—",
        "set": (card.set_name if card else None) or "—",
        "lang": row.language,
        "price": _money(row.price_eur),
        "floor_gap_pct": gap,
        "cross": round(float(row.cross_lang or 0), 2),
        "buy_url": row.buy_url,
    }


def build_digest_payload(db: Session, day: dt.date) -> dict:
    """Construit le payload JSON du digest pour un jour de calcul donné."""
    bands = select_targets(db, day)
    ids = {r.card_id for band in bands.values() for r in band}

    movers_rows = db.scalars(
        select(DailySignal).where(
            DailySignal.computed_at == day,
            DailySignal.bottoming > 0,
            DailySignal.momentum_7d.is_not(None),
        ).order_by(DailySignal.momentum_7d.desc()).limit(MOVERS_LIMIT)
    ).all()
    ids.update(r.card_id for r in movers_rows)

    cards = {c.card_id: c for c in db.scalars(
        select(TcgdexCard).where(TcgdexCard.card_id.in_(ids or {""}))).all()}

    payload = {"date": day.isoformat(), "bands": {}, "movers": []}
    for band_key, rows in bands.items():
        payload["bands"][band_key] = [_card_line(r, cards.get(r.card_id)) for r in rows]
    for r in movers_rows:
        line = _card_line(r, cards.get(r.card_id))
        line["mom7_pct"] = round(float(r.momentum_7d or 0) * 100, 1)
        payload["movers"].append(line)
    return payload


def digest_is_empty(payload: dict) -> bool:
    return (not any(payload.get("bands", {}).values())) and not payload.get("movers")


def _fmt_line(c: dict) -> str:
    base = (f"**{c['name']}** · {c['rarity']} · {c['set']} · `{c['lang']}` · "
            f"**{c['price']} €** · ~{c['floor_gap_pct']}% au-dessus du plancher")
    if c.get("cross"):
        base += f" · arbitrage {c['cross']}"
    if c.get("buy_url"):
        base += f" · [acheter]({c['buy_url']})"
    return base


def digest_embed_from_payload(payload: dict) -> EmbedSpec:
    """Embed Discord (source unique) à partir du payload JSON."""
    fields: list[EmbedField] = []
    for band_key, label in BAND_LABEL.items():
        rows = payload.get("bands", {}).get(band_key) or []
        if not rows:
            continue
        value = "\n".join(_fmt_line(c) for c in rows)[:1024]
        fields.append(EmbedField(f"{label} ({len(rows)})", value, inline=False))

    movers = payload.get("movers") or []
    if movers:
        lines = [f"**{c['name']}** `{c['lang']}` · {c['price']} € · +{c.get('mom7_pct', 0)}% / 7j"
                 for c in movers]
        fields.append(EmbedField("📈 Movers (sortie de creux)", "\n".join(lines)[:1024], inline=False))

    return EmbedSpec(
        title=f"🎯 Cartes à cibler — {payload.get('date', '')}",
        description=("Short-list à **vérifier à la main**. Le score *classe* des "
                     "candidats, il ne prédit pas de prix. Monitoring — aucun achat auto."),
        color=COLOR_INFO,
        fields=tuple(fields),
        footer=f"Market Intelligence · {payload.get('date', '')}",
    )


def digest_text_from_payload(payload: dict) -> str:
    """Rendu texte lisible (pour ``--dry-run`` sur stdout)."""
    out = [f"🎯 Cartes à cibler — {payload.get('date', '')}",
           "Short-list à vérifier à la main (le score classe, ne prédit pas). Aucun achat auto.", ""]
    for band_key, label in BAND_LABEL.items():
        rows = payload.get("bands", {}).get(band_key) or []
        if not rows:
            continue
        out.append(f"== {label} ({len(rows)}) ==")
        for c in rows:
            out.append(f"  - {c['name']} · {c['rarity']} · {c['set']} · {c['lang']} · "
                       f"{c['price']} € · ~{c['floor_gap_pct']}% au-dessus du plancher"
                       + (f" · arbitrage {c['cross']}" if c.get('cross') else "")
                       + (f"\n    → {c['buy_url']}" if c.get('buy_url') else ""))
        out.append("")
    movers = payload.get("movers") or []
    if movers:
        out.append("== 📈 Movers (sortie de creux) ==")
        for c in movers:
            out.append(f"  - {c['name']} [{c['lang']}] {c['price']} € · +{c.get('mom7_pct', 0)}% / 7j")
        out.append("")
    return "\n".join(out).rstrip()


def run_digest(db: Session, *, dry_run: bool = False, day: dt.date | None = None) -> dict:
    """Génère le digest : crée l'alerte (bot) ou renvoie le texte (dry-run)."""
    if day is None:
        day = db.scalar(select(func.max(DailySignal.computed_at)))
    if day is None:
        return {"summary": "aucun signal calculé — digest impossible"}

    payload = build_digest_payload(db, day)
    if digest_is_empty(payload):
        return {"summary": f"digest {day} vide (aucune cible)"}

    n = sum(len(v) for v in payload["bands"].values())
    if dry_run:
        return {"summary": f"[dry-run] digest {day} : {n} cible(s) + {len(payload['movers'])} movers",
                "text": digest_text_from_payload(payload), "payload": payload}

    db.add(Alert(alert_type="marketwatch", severity="warning",
                 title=f"🎯 Cartes à cibler — {day}", payload=payload, status="pending"))
    db.commit()
    return {"summary": f"digest {day} en file : {n} cible(s) + {len(payload['movers'])} movers"}
