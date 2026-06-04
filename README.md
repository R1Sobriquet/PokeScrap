# Pokémon Arbitrage & Portfolio — Jalon 1 (Fondations)

Application personnelle, mono-utilisateur, auto-hébergée d'aide à la décision pour
l'investissement dans les cartes Pokémon (arbitrage, portefeuille, alertes).

> **Jalon 1 = fondations uniquement.** Toute la plomberie et la topologie sont en
> place : les 6 services tournent ensemble, la base est créée et seedée,
> l'authentification fonctionne, et chaque service prouve qu'il est branché.
> **Aucune logique métier** (la règle des 50 %, les filtres, le moteur de vente,
> l'ingestion de prix, le scraping réel, les KPIs arrivent aux jalons 2+). Les
> adapters externes sont des stubs qui lèvent `NotImplementedError("jalon 2")`.

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
