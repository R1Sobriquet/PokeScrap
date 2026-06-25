-- Down / rollback PokéStock FR Phase B (dispo magasin) — réversible, additif.
-- À jouer manuellement. Aucune feature existante n'en dépend.

DROP TABLE IF EXISTS offer_store_availability;
DROP TABLE IF EXISTS store_locations;
ALTER TABLE retail_stock_events DROP COLUMN store_id;
ALTER TABLE retailers DROP COLUMN store_availability_url_template;

-- Enseignes magasin ajoutées (optionnel ; supprime aussi leurs offres) :
-- DELETE FROM retailers WHERE code IN ('king-jouet','joueclub','lagranderecre');
-- Réglages associés (optionnel) :
-- DELETE FROM settings WHERE setting_key IN (
--   'retail_store_stock_enabled','retail_store_check_interval_min',
--   'retail_store_request_cap_per_run');
