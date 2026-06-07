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
# Base : 14 tables, 4 paliers, registre settings > 80
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
