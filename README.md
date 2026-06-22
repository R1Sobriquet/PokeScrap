# Pokémon Arbitrage & Portfolio

Application personnelle, mono-utilisateur, auto-hébergée d'aide à la décision pour
l'investissement dans les cartes Pokémon (arbitrage, portefeuille, alertes).

> **Jalon 1 — Fondations.** Plomberie et topologie : les 6 services tournent
> ensemble, la base est créée et seedée, l'authentification fonctionne, chaque
> service prouve qu'il est branché.
>
> **Jalon 2 — Socle données.** Adapters réels derrière les ports (PokeTrace,
> PSA), ingestion des prix vers `price_snapshots`, seeding du catalogue/watchlist,
> et service de lecture `get_latest_price`.
>
> **Jalon 3 — Moteur d'achat (`domain/`).** Toute la logique d'achat en
> **fonctions pures, zéro I/O** : paliers + garde-fou cash, règle des 50 % nette,
> valorisation de lot mixte, filtres anti-erreurs, scoring, signal d'accumulation
> PE. L'orchestration (couche application) fait l'I/O et écrit les alertes en base.
>
> **Jalon 4 — Discord & exécution.** Les alertes deviennent réelles et
> interactives : un dispatcher (boucle dans le process bot) pousse les
> `alerts(pending)` selon `notify_mode=balanced`. Boutons `buy` → [Voir] [Acheté]
> (modal → lot+transaction) [Ignorer].
>
> **Jalon 5 — Moteur de vente & KPIs.** Vente en fonctions pures (hiérarchie
> **forcé > x2 > 25/50/25**, idempotente par `stage_*`), comptabilité (cascade,
> **30/70**, 5 KPIs, provision fiscale), et snapshot KPI quotidien qui pilote les
> transitions de palier.
>
> **Jalon 6 — Scraping (sourcing).** Collecte automatique d'annonces
> Vinted/LeBoncoin (conteneur Playwright **isolé, sortant, best-effort**) →
> `sourcing_listings` (dédup) → matching mots-clés → `evaluate_listing` (J3).
>
> **Jalon 7 — Liquidation (Module B) & Grading (Module A).** Intake → segmentation
> (individuelles routées + lots vrac sans doublon) → `promote_to_position` ;
> comparateur de grading pondéré (gated Pro) + authenticité PSA (tous modes).
>
> **Jalon 8 — Dashboard React (8 écrans).** Interface de **revue, configuration et
> override** (l'exécution « chaud » reste sur Discord).
>
> **Jalon 9 — Durcissement & mise en production.** Sauvegardes chiffrées + offsite
> + **test de restauration**, observabilité (`/status` + **dead-man's switch** +
> logs JSON avec **redaction des secrets**), rétention (purge sourcing + élagage
> price_snapshots 1/jour/tier), validation **Free→Pro** scriptée, compose durci
> (localhost, `restart: unless-stopped`, healthchecks), et **runbooks** de go-live.

## PokéStock FR — veille restock (détaillants FR)

Module de veille stock pour collectionneurs : **détection de restock** sur une
watchlist d'offres scellées, **détection de nouveaux SKU**, alertes **Discord
(nouveau canal) + Telegram**. Cibles V1 : **Cultura, Fnac, Micromania**.

- **Sourcing hybride léger (httpx, pas de Playwright).** Radar nouveaux SKU via
  **sitemaps** ; état stock + prix via **fetch de la page produit** (JSON-LD
  `Product`/`Offer` prioritaire, **fallback DOM** si absent). Tourne dans les
  conteneurs existants (backend on-demand + scheduler).
- **Politesse OBLIGATOIRE** : respect `robots.txt`, UA réaliste, intervalle min +
  jitter, **plafond de requêtes/run**, **backoff exponentiel** sur 403/429 et
  **circuit breaker** par détaillant (réutilise `scrape_state`). **Fnac** =
  watchlist-only (jamais le catalogue). Aucune escalade anti-bot (pas de proxies,
  pas de captcha).
- **Tout est désactivable** : master switch `retail_sourcing_enabled` (défaut
  **off**), flag par détaillant `retail_<code>_enabled`, et **mode dry-run**
  `retail_dry_run` (défaut **on** : log les transitions sans alerter).
- **Notifications** : une transition crée une ligne `alerts` (type `restock` /
  `new_sku`) poussée par le dispatcher existant vers le canal Discord « restock »
  **et** Telegram (chaque canal activable indépendamment). Dédup par transition
  réelle + cooldown (`retail_restock_cooldown_min`).

**Nouvelles tables** : `retailers` (seed Cultura/Fnac/Micromania), `retail_offers`
(`product_id` nullable = hook scalping futur, `ON DELETE SET NULL`),
`retail_stock_events`, `releases` (calendrier curé). Migration **additive et
idempotente** (`CREATE TABLE IF NOT EXISTS`) ; rollback :
`db/migrations/down_pokestock_fr.sql`.

> ⚠️ **`sitemap_url` à confirmer au go-live.** Les URLs seedées sont best-effort :
> vérifie chacune dans le `robots.txt` du site (`curl.exe https://www.cultura.com/robots.txt`)
> et corrige-la dans l'écran **Détaillants** si besoin.

**Jobs (panel + scheduler, verrou `job_runs`)** :

```bash
docker compose exec backend python -m app.cli  # ou via le panel « Actions & Jobs »
# retail-check-restocks  : watchlist → fetch → transition → event + alerte
# retail-detect-new-skus : sitemaps → diff → nouvelles offres (unknown) + alerte
# retail-refresh-prices  : rafraîchit prix/état sans alerter
```

**Écrans** : *Veille restock* (offres watchées, ajout par URL), *Détaillants*
(activation, compteurs d'erreurs / circuit breaker), *Calendrier* (CRUD releases).

### Prérequis Telegram (@BotFather)

1. Sur Telegram, parler à **@BotFather** → `/newbot` → récupérer le **token**.
2. Récupérer le **chat_id** cible (envoyer un message au bot puis lire
   `https://api.telegram.org/bot<token>/getUpdates`, ou via **@userinfobot**).
3. Renseigner `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` dans `.env` (secrets, jamais
   en base) et passer le setting `telegram_enabled=true`. Idem côté Discord :
   `DISCORD_CHANNEL_RESTOCK`.

### Deal Analyzer (indice de scalping — v1)

Première brique du croisement **prix annoncé vs prix marché PokeTrace** :
`POST /retail/analyze` (`app/services/deal_analyzer.py`) récupère une annonce par
URL (parser JSON-LD/DOM réutilisé), recherche la carte/produit sur PokeTrace
(`card_value` : UNOPENED scellé / NEAR_MINT single), convertit en EUR
(`fx_usd_eur`) et calcule l'écart + un verdict (`STRONG BUY` … `OVERPRICED`).
Écran dashboard **Deal Analyzer** (`/analyzer`). Une seule requête sortante par
analyse (action manuelle). Le matching offre↔produit interne
(`retail_offers.product_id`, FK nullable) reste manuel/best-effort ; pas de
fuzzy-matching automatique persistant.

### Frontend PokéAlpha (reskin)

Le dashboard adopte le design **PokéAlpha** : 4 thèmes runtime (dark/light/holo/
ember), polices Outfit + JetBrains Mono, sélecteur de thème et **bascule de langue
FR/EN** (`src/i18n.jsx`, `src/ThemeContext.jsx`), landing publique (`/`), **Set
Explorer / Set Detail** (`/explorer`, `/set/:slug`) et **Future Radar** (`/future`).

### Future Radar — modèle ML (scikit-learn)

`app/ml/` entraîne trois régressseurs *gradient boosting* (`scikit-learn`) qui
prédisent **hype / popularité / ROI** d'une sortie à partir de features produit
(type, mots-clés ETB/UPC/booster…, langue). Les **cibles sont dérivées de
signaux réels** de `price_snapshots` : ROI = momentum prix (`avg_1d` vs `avg_30d`),
popularité = `sale_count`, hype = volatilité (`high−low`/`avg`). La **confiance**
combine la complétude des données de la sortie et la taille du jeu d'entraînement.
Le modèle est persisté en base (`ml_models`, payload joblib, caché par
`trained_at`) ; l'inférence remplace l'heuristique dès qu'un modèle existe, sinon
**repli automatique sur l'heuristique** (`app/services/release_scoring.py`).
(Ré)entraînement : job **`train-release-model`** (panel + hebdo scheduler) ;
en-deçà de 12 échantillons, l'entraînement est sauté (`données insuffisantes`).
Parité train/serve garantie (mêmes features). Upgradeable vers des modèles plus
riches sans changer l'interface (`scores` : `{hype, confidence, popularity, roi,
model}`).

### Veille restock = acheter au MSRP (flip value)

Le but d'un restock : un scellé redevient achetable au **prix officiel (~MSRP)** ;
si la **valeur marché** est supérieure, c'est une opportunité d'achat-revente.
`app/services/flip_value.py` croise `retail_offers.current_price` (MSRP) avec la
valeur marché du produit lié (snapshots marché **possédés** en priorité, sinon
PokeTrace) → **upside %** + verdict **STRONG BUY / BUY / FAIR / PASS**. Le matching
(`retail_offers.product_id`) active ce signal ; une offre non liée reste alertée
sans verdict. L'écran **Veille restock** affiche MSRP · marché · flip ; l'embed
Discord/Telegram porte le verdict. Réglage `restock_min_flip_pct` : seul un flip
≥ seuil déclenche l'**alerte instantanée** (les restocks sans marge partent au
digest) → on n'est pingé que sur les vrais coups. Verdict **net de frais**
(`resale_fee_pct`) — un +12% brut peut être nul après frais.

### Phase A — latence de détection online

Agressif sur le **planning**, léger sur les **requêtes** :
- **Hot-list à 3 niveaux** (`retail_offers.watch_tier` : `hot`/`normal`/`cold`) :
  le job de poll tourne court (`RETAIL_POLL_INTERVAL_SEC`, ~45 s) mais chaque
  offre n'est checkée qu'à l'intervalle de son tier (`retail_tier_hot_sec`,
  `retail_tier_normal_min`, `retail_tier_cold_min`). Le budget part sur le `hot`.
- **Endpoint XHR de dispo > page** : `retailers.availability_url_template`
  (`{sku}`/`{url}`) → JSON léger parsé en priorité, fallback page si absent. À
  **confirmer par enseigne au go-live** (comme `sitemap_url`) ; vide par défaut.
- **Requête conditionnelle ETag** : `If-None-Match` → `304` = inchangé, on saute
  le parsing (économie d'octets).
- **Anti-ban** : **token bucket par enseigne** (capacité/recharge en `settings`)
  + jitter + circuit breaker/backoff exponentiel sur 403/429 (réutilise
  `scrape_state`). Fnac : `hot` sur un set minuscule.
- **Latence instrumentée** : `retail_stock_events.detected_to_alert_ms`, moyenne
  par enseigne affichée sur l'écran **Détaillants**.
- **Déclencheur de re-check immédiat** : `POST /retail/offers/{id}/recheck`
  (bouton ↻) hors cadence tier ; un consommateur RSS/webhook reste un point
  d'extension off-by-default.

**Honnêteté** : depuis une IP maison, détection en **dizaines de secondes** sur
le `hot`, pas en temps réel. Battre des bots à fermes de proxys résidentiels est
**hors scope** — on vise « plus rapide qu'un humain qui navigue ».

### Flip Radar — où est l'argent maintenant

L'écran **Flip Radar** (`/flip`, `app/services/flip_radar.py`) classe en continu
les offres watchées **en stock** par **marge nette** (marché vs MSRP, frais
déduits) : MSRP · marché · flip net % · profit estimé · verdict. Le job
`flip-radar-scan` alerte **proactivement** au-delà de `flip_alert_min_pct` (ex.
le marché monte sans changement de stock — invisible aux alertes de transition),
avec dédup + cooldown. Marche sur les prix PokeTrace même sans le moat activé.

### Moat de données marché + automatisation auto-supervisée

On **possède son historique** : chaque jour on tire les prix scellés courants
multi-sources et on les stocke en `market_price_snapshots` (un snapshot par
`(product_ref, source, market, jour)` → idempotent). En quelques mois : série
longitudinale propriétaire qui nourrit le modèle Future Radar.

**Sources** (port unique `app/marketdata/`, interchangeables, OFF par défaut) :
- **PokemonPriceTracker** (`ppt`) — prix scellés USD (TCGplayer) + EUR
  (Cardmarket). Quota free 100 req/j → **watched-only** + cap/run (90<100). Clé :
  `settings ppt_api_key` ou `.env PPT_API_KEY`.
- **TCGdex** (`tcgdex`) — catalogue canonique FR + dates de sortie (gratuit, sans
  clé). Sert au matching et à l'auto-calendrier.
- **eBay Browse** (`ebay`) — annonces FR (OAuth) ; **agrégats dérivés uniquement**
  (nb/min/médiane) pour respecter la rétention eBay. `ebay_client_id/secret`.

**Tables** : `market_price_snapshots` (le moat), `data_quarantine` (prix rejetés
par les garde-fous), `match_review` (matchs ambigus, basse priorité).

**Jobs** (panel + scheduler, verrou `job_runs`) : `market-snapshot-daily`,
`calendar-sync` (auto-remplit `releases`), `match-products` (offre↔produit :
set+numéro → fuzzy, ≥ seuil auto, sinon `match_review` — rien ne bloque),
`source-health-check`.

**Automatisation auto-supervisée** — agressif sur le planning, léger sur les
requêtes :
- **Garde-fous d'ingestion** : bornes de sanité par `product_type`, cohérence
  devise/marché, dédup, outlier vs médiane → rejet en `data_quarantine`.
- **Footprint poli** : cap/run honorant les quotas, jitter, circuit breaker +
  backoff sur 403/429 (réutilise `app/retail/politeness`).
- **Hygiène d'alertes** : cooldown + **anti-flapping** (oscillation in/out ne
  spamme pas) ; **digest quotidien** optionnel (`alert_digest_enabled`) pour les
  events non urgents (nouveaux SKU, quarantaine, review).
- **Moniteur santé** (`source-health-check`, le seul moment où tu interviens) :
  pour chaque source, fraîcheur / erreurs / blocage / volume nul → alerte sur le
  **canal santé** (`DISCORD_CHANNEL_HEALTH` + Telegram). Les sources OK = silence.

**Settings clés** : `marketdata_enabled`, `marketdata_<source>_enabled`,
`marketdata_request_cap_per_run_<source>`, `match_confidence_threshold`,
`sanity_bounds_eur`, `alert_digest_enabled`, `source_health_*`. Rollback :
`db/migrations/down_marketdata_moat.sql`.

## Sourcing & auto-watchlist

- **Scraping auto désactivé par défaut** (`sourcing_scraping_enabled=false`) :
  Vinted (DataDome) et LeBoncoin (403) sont infranchissables sans course à
  l'armement (refusée). Le code reste en place pour réactivation. Le **sourcing
  manuel** (`POST /listings` / `evaluate_listing`) reste pleinement fonctionnel.
- **Auto-watchlist par set** (`tracked_sets`) : on déclare des sets cibles ; le job
  `sync-tracked-sets` (1×/jour, quota-aware) peuple la watchlist en **filtrant
  côté code** par `productType`/`productFamily` + valeur min (l'API ignore
  `?productType=sealed`). Le scellé est géré (`prices.tcgplayer.UNOPENED`). Les
  entrées `source='auto'` n'écrasent jamais les ajouts `source='manual'`.
- **Top movers** (`scan-movers`, écran « Sets & Movers ») : hausse `avg_7d/avg_30d`
  **confirmée par le volume** (anti-bruit). Le radar **signale**, il n'achète pas —
  les garde-fous (50 %, anti-pump, anti-FOMO, cash) restent souverains.

```bash
docker compose exec backend python -m app.cli sync-tracked-sets   # peuple la watchlist
docker compose exec backend python -m app.cli scan-movers         # top movers
python scripts/preflight_tracked_sets.py "prismatic evolutions"   # vérifie la forme API (clé requise)
```

## Jalon 9 — production

- **Sauvegardes** (`scripts/backup.sh` / `restore.sh` / `restore_test.sh`) :
  `mysqldump` → gzip → **chiffrement age/gpg** → local + offsite, rétention,
  **test de restauration mensuel** (base jetable, contrôle d'intégrité). Voir
  [`docs/runbook_backup_restore.md`](docs/runbook_backup_restore.md).
- **Observabilité** : `GET /status` (fraîcheur jobs/backup, blocages, alertes),
  **dead-man's switch** (`tech_error` si un job critique est silencieux >
  `job_heartbeat_max_age_min`), **logs JSON** avec redaction des secrets.
- **Rétention** : purge `sourcing_listings` (J6) + élagage optionnel des
  `price_snapshots` intraday (≥ 1/jour/tier préservé pour l'anti-pump).
- **Sécurité** : tout sur `127.0.0.1` / réseau Docker interne (accès distant
  **Tailscale**, jamais de port-forward) ; `.env` en `chmod 600`, jamais commité ;
  healthchecks par service ; mutations sensibles (achat/vente/30-70) en
  transactions atomiques.
- **Go-live** : [`docs/runbook_deploy.md`](docs/runbook_deploy.md),
  [`docs/runbook_go_live.md`](docs/runbook_go_live.md) ;
  `python scripts/check_pro_readiness.py` avant la bascule payante.

```bash
docker compose exec backend python -m app.cli status            # observabilité
scripts/backup.sh && scripts/restore_test.sh                    # sauvegarde + test
python scripts/check_pro_readiness.py                           # avant Free→Pro
```

## Jalon 8 — dashboard

- **Architecture** : zéro logique métier au frontend — React lit l'API et appelle
  des **endpoints d'action qui réutilisent les mêmes services** que le CLI et les
  interactions Discord (une seule source de vérité). JWT en mémoire (jamais en
  localStorage) ; aucune clé externe côté front.
- **Stack** : Vite + React + Tailwind + recharts, wrapper fetch authentifié, hook
  de polling (`dashboard_poll_interval_sec`).
- **API ajoutée** (toutes JWT) : lecture `/cockpit`, `/snapshots[/latest]`,
  `/positions`, `/lots[/{id}/items]`, `/opportunities`, `/transactions`,
  `/grading-opportunities`, `/alerts`, `/tiers`, `/settings`,
  `/ledger/export.csv` ; actions `PUT /settings/{key}` (invalide le cache),
  `POST /deposit|/intake|/lots/{id}/segment|/lot-items/{id}/promote|/alerts/{id}/confirm`,
  `PUT /watchlist/{id}`, `POST /settings/switch-pro` (atomique, confirmé).

```bash
docker compose up -d --build       # dashboard sur http://127.0.0.1:5173
cd frontend && npm install && npm test   # tests Vitest
```

## Jalon 7 — liquidation & grading

> **Pré-vol PSA** : forme réelle de l'API confirmée/corrigée —
> [`docs/jalon7_preflight.md`](docs/jalon7_preflight.md), `scripts/smoke_psa.py`.

**Module B** (`domain/liquidation.py` pur + `services/liquidation_service.py`) :
- `intake-lot` pré-remplit `lot_items` depuis la détection ; l'utilisateur corrige.
- `segment-lot` : `< individual_threshold` → vrac ; sinon individuelle routée
  (gradé/≥50€ → eBay, sinon Cardmarket). **Packing vrac sans doublon** garanti
  (`n ≥ max_copies`). Prix suggérés ; alerte `lot_summary`.
- `promote-item` : crée une `positions` (avg_cost pro-rata du coût du lot) — **seul
  pont B → portefeuille**, ensuite suivi par le moteur de vente J5.

**Module A** (`domain/grading.py` pur + `services/grading_service.py`) :
- `grading-scan` (hebdo) : espérance pondérée par les probas de grade ; **no-op
  propre hors mode Pro** (`feature_grading_enabled`). Payload honnête (coût élevé,
  capital immobilisé, biais de survie du pop report → défaut conservateur).
- `verify-cert` / `verify_slab` : **gratuit, tous modes**. Cert invalide →
  HARD_BLOCK ; valide → WARN (« cohérent ✔, inspection requise » — jamais
  « authentique garanti »). Hook : une annonce au cert invalide est bloquée avant
  l'achat.

```bash
docker compose exec backend python -m app.cli intake-lot 1
docker compose exec backend python -m app.cli segment-lot 1
docker compose exec backend python -m app.cli promote-item 5
docker compose exec backend python -m app.cli verify-cert 12345678
docker compose exec backend python -m app.cli grading-scan
```

## Jalon 6 — scraping & sourcing

> **Pré-vol** : sélecteurs externalisés + détection de casse — voir
> [`docs/jalon6_preflight.md`](docs/jalon6_preflight.md).

- **Posture** : scraping poli de listings publics. **Aucun** contournement
  (CAPTCHA / fingerprint / proxies d'évasion). Sur blocage → `tech_error` + backoff.
- **Sélecteurs** : tous dans `scraper/selectors.yaml` (zéro sélecteur en dur). La
  détection de casse (`selector_break_threshold`) alerte au lieu d'insérer du vide.
- **Pipeline** (`scrape_sourcing`, cron `SCRAPE_INTERVAL_MIN`) : collecte → dédup
  `(platform, external_id)` → matching (`services/matching.py`) → `evaluate_listing`.
- **Isolation** : le conteneur scraper est best-effort ; une panne n'affecte ni les
  prix ni les KPIs. **PII minimale**, rétention `sourcing_retention_days` (purge auto).
- **Session** : cookies optionnels via `.env` (`SCRAPE_VINTED_COOKIES`…), sinon
  anonyme. Jamais d'identifiants en clair.

```bash
docker compose exec backend python -m app.cli purge-sourcing   # purge manuelle
# La collecte tourne dans le conteneur scraper (Playwright) à l'intervalle .env.
```

Nouveaux réglages : `scrape_max_listings_per_run`, `scrape_blocked_cooldown_min`,
`selector_break_threshold`, `saved_queries`.

## Jalon 5 — vente & comptabilité

`domain/` (pur) : `selling.py` (hiérarchie de conflits, idempotence par `stage_*`)
et `accounting.py` (cascade, 30/70, KPIs). Orchestration `services/` :
`selling_service` émet les alertes `sell_*`, `ledger.compute_kpis` calcule les 5
KPIs, `kpi_snapshot` écrit `account_snapshots` + pilote les paliers.

```bash
docker compose exec backend python -m app.cli evaluate-sales   # émet les alertes de vente
docker compose exec backend python -m app.cli kpis             # affiche les 5 KPIs
docker compose exec backend python -m app.cli kpi-snapshot     # snapshot + transitions de palier
```

Flux de vente : alerte `sell_*` → bouton **[Exécutée]** → modal (brut, frais, qté)
→ `transactions(sell)` + `cost_basis`, position mise à jour, `stage_*` posé
(**uniquement à l'exécution**), 30/70 appliqué (`cash_locked` monte, jamais ne
baisse). Atomique et idempotent. Les transitions de palier réutilisent le
framework bouton du Jalon 4 (`palier_up` → [Confirmer] applique la promotion).

## Jalon 4 — Discord & exécution

> **Pré-vol** : discord.py 2.x — voir [`docs/jalon4_preflight.md`](docs/jalon4_preflight.md).

Architecture découplée : le **dispatcher** (`services/alert_dispatcher.py`) et les
**handlers d'interaction** (`services/interactions.py`) sont du backend pur (testés
sans Discord) ; ils produisent des specs neutres (`app/notifications/`). Seuls
l'adapter `adapters/discord_notifier.py` et `bot/bot.py` importent discord.py.

| Type d'alerte | Salon | Boutons |
|---|---|---|
| `buy` | #achats | Voir · Acheté (modal) · Ignorer |
| `sell_*` | #ventes | (Jalon 5) |
| `palier_*` / `grading` / `reinvest` / `tax_provision` | #portefeuille | Confirmer/Plus tard (palier, inerte jusqu'au J5) |
| `tech_error` | #systeme | — |

**Run réel** (premier jalon observable de bout en bout) : avec `DISCORD_BOT_TOKEN`
+ `POKETRACE_API_KEY` dans `.env`, faire une fois `docker compose up` →
`record-deposit 150` → `evaluate-listing` → l'alerte d'achat arrive dans #achats →
clic [Acheté] + modal → `lots`/`transactions` se remplissent, le cash baisse.
Sans token : le bot logge « Discord non configuré, dispatch en dry-run ».

Nouveau réglage : `dispatcher_poll_sec` (période de la boucle d'envoi).

## Jalon 3 — moteur d'achat

> **Pré-vol PokeTrace** : la structure de réponse a été vérifiée et corrigée avant
> de coder le moteur — voir [`docs/jalon3_preflight.md`](docs/jalon3_preflight.md)
> et le smoke-test `python scripts/smoke_poketrace.py`.

`domain/` (pur) : `tiers.py`, `valuation.py`, `buying.py`, `filters.py`,
`pe_signal.py`. L'orchestration `services/buy_evaluation.py::evaluate_listing`
rassemble prix + portefeuille + réglages, appelle le domaine, puis écrit le statut
de l'annonce (`flagged`/`blocked`) et l'alerte `buy` pending — en une transaction.

```bash
# Amorcer le capital (ton dépôt initial)
docker compose exec backend python -m app.cli record-deposit 150

# Évaluer des annonces de test (le scraper viendra au Jalon 6)
cp seed/test_listings.example.yaml seed/test_listings.yaml   # ajuster les product_id
docker compose exec backend python -m app.cli load-test-listings --file /seed/test_listings.yaml

# Ou via l'API (JWT) : POST /listings {raw_title, asking_price, detected_products, ...}
```

Nouveaux réglages : `valuation_marketplace` (tcgplayer/cardmarket) et `fx_usd_eur`
(conversion proxy US→EUR du mode prototype).

## Jalon 2 — couche données

### Modes pilotés par `settings` (zéro changement de code)

| Réglage | Prototype (actuel) | Réel (Pro) |
|---|---|---|
| `poketrace_plan` | `free` | `pro` |
| `valuation_market` | `US` | `EU` |
| `feature_grading_enabled` | `false` | `true` |
| `feature_history_full` | `false` | `true` |

Passer en Pro = éditer ces lignes en base (`UPDATE settings …`). L'adapter les lit
via `get_setting()`. Garde-quota : `poketrace_daily_limit` (250 Free),
`poketrace_min_interval_ms` (burst), `price_cache_ttl_min` (cache anti-gaspillage).

### Seeder le catalogue

```bash
cp seed/watchlist.example.yaml seed/watchlist.yaml   # puis éditer
docker compose exec backend python -m app.cli seed-catalog --file /seed/watchlist.yaml
```

### Ingestion des prix

- Automatique : job scheduler `refresh_prices` (cron `JOB_REFRESH_PRICES`).
- Manuelle : `docker compose exec backend python -m app.cli refresh-prices`.

### Routes de lecture (JWT requis)

```
GET /products
GET /watchlist
GET /products/{id}/prices/latest?grade_company=RAW&condition=NM
```

> Le scheduler partage la couche données du backend (`backend/app`) : son image
> est construite depuis la racine du repo (`context: .`).

## Architecture — ports & adapters (hexagonale)

- **`backend/app/domain/`** — le moteur de règles, en **fonctions pures** : reçoit
  des DTO, renvoie des décisions, **zéro I/O**. Vide au Jalon 1, prêt pour la suite.
- **`backend/app/adapters/`** — des **adapters derrière des ports** (interfaces) pour
  les sources externes (prix, certs, sourcing) et la notification.
- **Constantes métier en base** (table `settings`, lue via `get_setting()`), jamais
  en dur. **Infra & secrets dans `.env`**.
- Deux modes pilotés par config : **prototype** (données US gratuites) et **réel**
  (données EU / gradées payantes). Le code est indifférent au mode.

## Stack

FastAPI (Python 3.12) · MySQL 8 · React (Vite) · APScheduler · discord.py ·
Playwright · Docker Compose.

## Les 6 services

| Service     | Rôle                                   | Preuve de câblage (Jalon 1)                          | Ports |
|-------------|----------------------------------------|------------------------------------------------------|-------|
| `db`        | MySQL 8 (volume persistant)            | Schéma + seeds appliqués à l'init                    | 127.0.0.1 only |
| `backend`   | API FastAPI + auth                     | `GET /health` → DB `ok` ; vérifie 14 tables au boot  | 127.0.0.1:8000 |
| `scheduler` | APScheduler                            | Heartbeat loggé chaque minute                        | aucun |
| `bot`       | Discord (gateway sortant)              | Poste `🟢 App démarrée — Jalon 1` dans `#systeme`     | aucun |
| `scraper`   | Playwright (stub)                      | Logge `scraper prêt (stub)`                          | aucun |
| `frontend`  | React (Vite) — login + cockpit         | Login → page Cockpit « À venir »                     | 127.0.0.1:5173 |

Tous les services sont en `restart: unless-stopped`, sur le réseau interne
`appnet`. Aucun port n'est exposé publiquement (tout est borné à `127.0.0.1`).

## Démarrage

```bash
# 1. Configurer l'environnement
cp .env.example .env
# → éditer .env : JWT_SECRET, ADMIN_PASSWORD, DB_PASSWORD, DB_ROOT_PASSWORD,
#   et les identifiants Discord/PokeTrace/PSA si disponibles.

# 2. Lancer la stack
docker compose up -d --build

# 3. Suivre les logs
docker compose logs -f
```

Le mot de passe admin (`ADMIN_PASSWORD`) est fourni en clair dans `.env` puis
**haché en bcrypt au premier démarrage** et persisté dans la table `settings`
(clé `admin_password_hash`). Modifier `ADMIN_PASSWORD` puis redémarrer le backend
re-hache automatiquement.

## Vérifications (Definition of Done)

```bash
# Base : 18 tables (14 socle + 4 PokéStock FR), 4 paliers, registre settings > 80
docker compose exec db mysql -uroot -p"$DB_ROOT_PASSWORD" pokemon_arbitrage \
  -e "SELECT COUNT(*) AS settings FROM settings; SELECT COUNT(*) AS tiers FROM tiers_config;"

# Santé backend
curl -s 127.0.0.1:8000/health            # → {"status":"ok","db":"ok"}

# Auth : login renvoie un JWT
TOKEN=$(curl -s -X POST 127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"erwann","password":"<ADMIN_PASSWORD>"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# Route protégée : 401 sans token, 200 avec
curl -s -o /dev/null -w "%{http_code}\n" 127.0.0.1:8000/auth/me                                  # → 401
curl -s -o /dev/null -w "%{http_code}\n" 127.0.0.1:8000/auth/me -H "Authorization: Bearer $TOKEN" # → 200

# Frontend : http://127.0.0.1:5173 → login puis Cockpit
# Scheduler / scraper / bot : vérifier les logs
docker compose logs scheduler | grep heartbeat
docker compose logs scraper   | grep "scraper prêt"
docker compose logs bot       # message de démarrage dans #systeme
```

## Tests

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest          # 13 tests : /health, login OK/KO, /auth/me, get_setting typé
```

Les tests tournent **sans MySQL** (moteur SQLite en mémoire substitué à la couche
DB), ce qui les rend exécutables partout, y compris en CI.

## Structure du repo

```
.
├─ docker-compose.yml        # 6 services, réseau interne, ports localhost-only
├─ .env.example              # infra & secrets (à copier en .env)
├─ db/schema.sql             # 14 tables + seeds (4 paliers, registre settings)
├─ backend/                  # FastAPI
│  └─ app/{config,db,main}.py · auth/ · api/ · domain/ · adapters/ · models/
├─ scheduler/                # APScheduler (heartbeat + refresh_prices stub)
├─ bot/                      # discord.py (gateway sortant)
├─ scraper/                  # Playwright (stub)
└─ frontend/                 # React (Vite) — Login + Cockpit
```
