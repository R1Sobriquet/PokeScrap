-- Down / rollback PokéStock FR Phase A (latence online) — réversible, additif.
-- À jouer manuellement. Aucune feature existante n'en dépend.

ALTER TABLE retail_offers DROP INDEX idx_offer_tier_watched;
ALTER TABLE retail_offers DROP COLUMN watch_tier;
ALTER TABLE retail_offers DROP COLUMN availability_etag;
ALTER TABLE retail_stock_events DROP COLUMN detected_to_alert_ms;
ALTER TABLE retailers DROP COLUMN availability_url_template;

-- Réglages associés (optionnel) :
-- DELETE FROM settings WHERE setting_key IN (
--   'retail_tier_hot_sec','retail_tier_normal_min','retail_tier_cold_min',
--   'retail_bucket_capacity','retail_bucket_refill_per_sec','retail_poll_interval_sec');
