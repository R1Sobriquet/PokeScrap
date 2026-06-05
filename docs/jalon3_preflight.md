# Jalon 3 — Pré-vol : vérification du mapping PokeTrace

> Tâche bloquante exécutée **avant** le moteur d'achat : on ne construit pas
> l'arbitrage sur des prix non vérifiés.

## Méthode

Les pages `https://poketrace.com/docs` et `/docs/cards` renvoient **HTTP 403** au
fetcher (protection anti-bot Cloudflare). La structure a donc été reconstituée à
partir du contenu indexé de la documentation officielle (recherche web) et
recoupée avec le schéma `price_snapshots` (présence d'une colonne `marketplace`).

Sources :
- PokeTrace — Cards API Docs : https://poketrace.com/docs/cards
- PokeTrace — Developers : https://poketrace.com/developers
- PokeTrace — Pricing (plans Free/Pro/Scale) : https://poketrace.com/pricing

Un smoke-test réel (`scripts/smoke_poketrace.py`) permet de confirmer
définitivement la structure dès qu'une `POKETRACE_API_KEY` est disponible.

## Confirmé (aucun changement nécessaire)

| Élément | Statut |
|---|---|
| Base URL `api.poketrace.com/v1`, auth header `X-API-Key` | ✅ conforme |
| Plans : Free 250/j (US + brut), Pro 10 000/j (EU + gradé) | ✅ conforme |
| Champs d'un point de prix : `avg`, `low`, `high`, `saleCount`, `approxSaleCount`, `avg1d`, `avg7d`, `avg30d` | ✅ conforme |
| Clés de tiers gradés : `PSA_10`, `BGS_9.5`, `CGC_10`, … (PSA/BGS/CGC/SGC/ACE/TAG) | ✅ conforme |
| Tiers bruts : `NEAR_MINT`…`DAMAGED` | ✅ conforme |
| `approxSaleCount` : `true` pour sources instables (eBay), `false` pour stables (TCGplayer) | ✅ conforme |

## Corrigé (écart réel détecté)

**`prices` est imbriqué par _marketplace_ puis par _tier_** — et **non** un dict
plat de tiers comme le supposait l'adapter du Jalon 2 :

```jsonc
// AVANT (hypothèse Jalon 2, incorrecte)
"prices": { "NEAR_MINT": { "avg": 165, ... } }

// APRÈS (structure réelle confirmée)
"prices": {
  "tcgplayer": { "NEAR_MINT": { "avg": 165, ... }, "PSA_10": { ... } },
  "ebay":      { "NEAR_MINT": { ... } }
}
```

- Cartes **US** → marketplaces `tcgplayer` + `ebay`.
- Cartes **EU** → marketplace `cardmarket`.

### Changements apportés

| Fichier | Correction |
|---|---|
| `adapters/poketrace.py` | Docstring corrigée + nouvel utilitaire `iter_price_points(card)` qui aplatit `prices: {marketplace: {tier: point}}` en triplets `(marketplace, tier, point)`. |
| `services/ingestion.py` | `_snapshot_rows_from_card` itère désormais via `iter_price_points` et **renseigne la colonne `marketplace`** (1 ligne par couple marketplace × tier). |
| `services/prices.py` | `get_latest_price` prend un paramètre `marketplace` (défaut : réglage `valuation_marketplace`) → la valorisation est déterministe. |
| `db/schema.sql` + `runtime_settings.py` | Nouveau réglage `valuation_marketplace` (`tcgplayer` en US prototype, `cardmarket` en EU). |
| `tests/fakes.py`, `tests/test_ingestion.py`, `tests/test_prices.py` | `SAMPLE_CARD` passé en structure imbriquée ; comptes de lignes et filtres ajustés (Free : tcgplayer{NM,LP}+ebay{NM} = 3 lignes ; gradé activé = 5 lignes). |

### Champ non vérifiable hors clé API

Le détail exact de l'objet **carte** (`id`, `name`, `set`, `number`, `refs`) n'a
pas pu être confirmé champ par champ (docs 403). L'adapter et `catalog_seed`
conservent un parsing **défensif** (`.get()` + fallbacks) ; le smoke-test
affichera `id`/`refs` réels dès qu'une clé sera fournie, et tout ajustement
résiduel se fera à ce moment.

## Smoke-test

```bash
python scripts/smoke_poketrace.py
```

- Sans clé : `[skip]` propre, exit 0 (n'empêche pas le build). ✅ vérifié.
- Avec clé : appels réels, assertions de types, et tableau
  « marketplace / tier → grade_company / grade / condition → price_avg / avg_7d / sales ».

## Impact tests

`pytest` reste vert (39 cas) après correction du mapping. Les nouveaux cas du
Jalon 3 (moteur d'achat) s'ajoutent par-dessus.
