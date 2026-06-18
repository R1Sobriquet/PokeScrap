-- Down / rollback du moat de données marché (réversible, NON auto-exécuté).
-- Tables additives uniquement : aucune feature existante n'en dépend.
-- À jouer manuellement (PowerShell : docker compose exec db mysql ... < ce fichier).

DROP TABLE IF EXISTS match_review;
DROP TABLE IF EXISTS data_quarantine;
DROP TABLE IF EXISTS market_price_snapshots;

-- Les réglages associés peuvent être retirés (optionnel) :
-- DELETE FROM settings WHERE setting_key LIKE 'marketdata\_%'
--   OR setting_key IN ('match_confidence_threshold','alert_digest_enabled',
--   'alert_digest_hour','restock_debounce_min','source_health_fresh_max_age_h',
--   'source_health_min_volume','sanity_bounds_eur');
