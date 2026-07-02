"""Synchronisation du registre canonique ``tcgdex_card`` depuis TCGdex.

TCGdex est gratuit, sans clé, multilingue. On récupère les sets puis le détail de
chaque set (liste de cartes : id, numéro local, nom) pour chaque langue cible, et
on **fusionne par ``card_id``** les noms EN/FR/JP. Upsert idempotent.

HTTP injectable (``http``) pour les tests ; borné par ``set_cap`` + délai poli.
Best-effort : une langue/un set indisponible n'interrompt pas la synchro.
"""

from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.marketdata.http import JsonGet, httpx_json_get
from app.models import TcgdexCard

logger = logging.getLogger("marketwatch.registry")

TCGDEX_BASE = "https://api.tcgdex.net/v2"
# langue TCGdex → colonne tcgdex_card
_LANG_COL = {"en": "name_en", "fr": "name_fr", "ja": "name_jp", "jp": "name_jp"}


def _pokemon_base(name: str | None) -> str | None:
    """Nom de base approximatif (1er mot) pour le tier de popularité par Pokémon."""
    if not name:
        return None
    return name.split()[0] if name.split() else None


def sync_registry(
    db: Session,
    *,
    http: JsonGet | None = None,
    langs: tuple[str, ...] = ("en", "fr"),
    set_cap: int | None = None,
    delay_ms: int = 0,
) -> dict:
    """Peuple/actualise ``tcgdex_card``. Renvoie un résumé {sets, cards, langs}."""
    get = http or httpx_json_get
    acc: dict[str, dict] = {}
    seen_sets: set[str] = set()

    for lang in langs:
        col = _LANG_COL.get(lang)
        if col is None:
            continue
        status, sets = get(f"{TCGDEX_BASE}/{lang}/sets", headers=None, params=None)
        if status >= 400 or not isinstance(sets, list):
            logger.info("registry: sets %s indisponibles (status %s).", lang, status)
            continue
        rows = [s for s in sets if isinstance(s, dict) and s.get("id")]
        if set_cap is not None:
            rows = rows[:set_cap]
        for s in rows:
            sid = str(s.get("id"))
            seen_sets.add(sid)
            st, detail = get(f"{TCGDEX_BASE}/{lang}/sets/{sid}", headers=None, params=None)
            if st >= 400 or not isinstance(detail, dict):
                continue
            set_name = detail.get("name") or s.get("name")
            for c in detail.get("cards") or []:
                if not isinstance(c, dict) or not c.get("id"):
                    continue
                cid = str(c.get("id"))
                rec = acc.setdefault(cid, {"set_id": sid, "set_name": set_name,
                                           "number": c.get("localId"), "rarity": c.get("rarity"),
                                           "names": {}})
                rec["names"][col] = c.get("name")
                # on complète les champs vides au fil des langues
                rec["set_name"] = rec.get("set_name") or set_name
                rec["number"] = rec.get("number") or c.get("localId")
                rec["rarity"] = rec.get("rarity") or c.get("rarity")
            if delay_ms:
                time.sleep(delay_ms / 1000.0)

    upserted = _persist(db, acc)
    return {"sets": len(seen_sets), "cards": upserted, "langs": list(langs),
            "summary": f"registre TCGdex: {upserted} cartes / {len(seen_sets)} sets ({','.join(langs)})"}


def _persist(db: Session, acc: dict[str, dict]) -> int:
    count = 0
    for cid, rec in acc.items():
        names = rec["names"]
        name_en = names.get("name_en")
        name_fr = names.get("name_fr")
        name_jp = names.get("name_jp")
        existing = db.get(TcgdexCard, cid)
        if existing is None:
            db.add(TcgdexCard(
                card_id=cid, set_id=rec.get("set_id"), set_name=rec.get("set_name"),
                number=(str(rec["number"]) if rec.get("number") is not None else None),
                rarity=rec.get("rarity"), pokemon=_pokemon_base(name_en or name_fr or name_jp),
                name_en=name_en, name_fr=name_fr, name_jp=name_jp,
            ))
        else:  # idempotent : on complète sans écraser par du vide
            existing.set_id = existing.set_id or rec.get("set_id")
            existing.set_name = existing.set_name or rec.get("set_name")
            if rec.get("number") is not None:
                existing.number = str(rec["number"])
            existing.rarity = existing.rarity or rec.get("rarity")
            existing.name_en = name_en or existing.name_en
            existing.name_fr = name_fr or existing.name_fr
            existing.name_jp = name_jp or existing.name_jp
            existing.pokemon = existing.pokemon or _pokemon_base(name_en or name_fr or name_jp)
        count += 1
    db.commit()
    return count


def load_registry(db: Session) -> list:
    """Charge le registre en mémoire (liste de ``RegistryCard``) pour le matcher."""
    from app.marketwatch.domain import RegistryCard

    out: list[RegistryCard] = []
    for c in db.query(TcgdexCard).all():
        out.append(RegistryCard(
            card_id=c.card_id, set_id=c.set_id, set_name=c.set_name, number=c.number,
            name_en=c.name_en, name_fr=c.name_fr, name_jp=c.name_jp,
        ))
    return out
