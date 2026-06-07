# Runbook — Déploiement (machine 24/7)

Auto-hébergement mono-utilisateur. **Point de défaillance unique** : la fiabilité
repose sur `restart: unless-stopped`, les healthchecks, les sauvegardes (offsite) et
le dead-man's switch.

## 1. Prérequis machine
- Docker + Docker Compose, fuseau `Europe/Paris`.
- **Tailscale** (ou WireGuard) installé → accès distant privé. **Jamais de
  port-forward** ni d'exposition publique : tous les ports sont bindés sur
  `127.0.0.1` et le réseau Docker interne.

## 2. Récupération & configuration
```bash
git clone <repo> && cd PokeScrap
cp .env.example .env
chmod 600 .env            # secrets : lecture propriétaire uniquement
```
Éditer `.env` : `JWT_SECRET`, `ADMIN_PASSWORD`, `DB_PASSWORD`, `DB_ROOT_PASSWORD`,
`POKETRACE_API_KEY` (Free au début), `DISCORD_*`, `BACKUP_*`, `LOG_LEVEL`.
> `.env` est dans `.gitignore` — **ne jamais le committer**.

## 3. Démarrage
```bash
docker compose up -d --build
docker compose ps          # les 6 services doivent être "healthy"
curl -s 127.0.0.1:8000/health   # {"status":"ok","db":"ok"}
```
Le schéma (`db/schema.sql`) est appliqué à l'init du volume MySQL ; `ensure_runtime_settings`
complète les réglages manquants au démarrage.

## 4. Amorçage
```bash
cp seed/watchlist.example.yaml seed/watchlist.yaml   # éditer
docker compose exec backend python -m app.cli seed-catalog --file /seed/watchlist.yaml
docker compose exec backend python -m app.cli record-deposit 150
docker compose exec backend python -m app.cli refresh-prices
```

## 5. Accès
- API : `http://127.0.0.1:8000` (via Tailscale : `http://<tailscale-ip>:8000`).
- Dashboard : `http://127.0.0.1:5173`.
- Discord : le bot poste dans `#systeme` au démarrage.

## 6. Mises à jour
```bash
git pull && docker compose up -d --build
```
Le volume `db_data` persiste les données entre rebuilds.

## 7. Observabilité
- `GET /status` (ou widget cockpit) : fraîcheur des jobs, dernière sauvegarde,
  blocages scraper, alertes en attente.
- Dead-man's switch (toutes les 30 min) : alerte `#systeme` si un job critique est
  silencieux > `job_heartbeat_max_age_min`.
- Logs JSON (`docker compose logs -f`), secrets masqués (`LOG_REDACT_SECRETS`).
