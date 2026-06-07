# Runbook — Checklist de go-live

À exécuter **une fois** sur la machine 24/7 (ce que le sandbox ne peut pas faire).

## 1. Stack en marche
- [ ] `docker compose up -d --build` → **6 services healthy** (`docker compose ps`).
- [ ] Schéma appliqué sur le vrai MySQL : `SELECT COUNT(*) FROM settings;` > 80,
      14 tables, 4 paliers.
- [ ] `curl 127.0.0.1:8000/health` → `db: ok` ; `GET /status` cohérent.

## 2. Boucle complète (Free)
- [ ] Clé **PokeTrace Free** + **token Discord** dans `.env`.
- [ ] `record-deposit 150`.
- [ ] Insérer une **annonce de test** (dashboard `POST /listings` ou
      `app.cli load-test-listings`) → l'alerte d'achat arrive dans **#achats** avec
      ses boutons.
- [ ] Cliquer **[Acheté]** + remplir le modal → `transactions`/`lots` se remplissent,
      le **cash baisse** (vérifier au cockpit).

## 3. Scraper réel (un cycle)
- [ ] Laisser le scraper tourner un cycle (`SCRAPE_INTERVAL_MIN`).
- [ ] Vérifier que des **annonces réelles** remontent et sont évaluées.
- [ ] Si 0 résultat / `tech_error` « sélecteurs à mettre à jour » → ajuster
      `scraper/selectors.yaml` (cf. `docs/jalon6_preflight.md`), rebuild scraper.

## 4. Sauvegardes
- [ ] `scripts/backup.sh` → un fichier chiffré dans `BACKUP_DIR` + offsite.
- [ ] `scripts/restore_test.sh` → **vert** (tables ≥ 14, `transactions` OK).
- [ ] Crons hôte installés (backup 03:00, restore_test mensuel).

## 5. Sécurité
- [ ] `.env` en `chmod 600`, non commité.
- [ ] Aucun port public (tout sur `127.0.0.1`) ; accès distant via **Tailscale**.
- [ ] `restart: unless-stopped` sur les 6 services (survit reboot/coupure).

## 6. Passage payant (Free → Pro)
- [ ] Mettre la **clé Pro** dans `.env`.
- [ ] `python scripts/check_pro_readiness.py` → **PRÊT** (EU/Cardmarket, ventilation
      FR, tiers gradés, history, EUR, feature flags).
- [ ] Dashboard → **Réglages → « Passer en Pro »** (atomique, confirmé).
- [ ] Vérifier au prochain run de job : prix EU, grading actif, `valuation_market=EU`.

> Tant que `check_pro_readiness.py` n'est pas vert, **ne pas** payer ni basculer.
