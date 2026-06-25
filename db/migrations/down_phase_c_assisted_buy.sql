-- Down / rollback PokéStock FR Phase C (achat assisté) — réversible, additif.
-- À jouer manuellement. Aucune feature existante n'en dépend.

DROP TABLE IF EXISTS buy_attempts;
DROP TABLE IF EXISTS buy_rules;
ALTER TABLE retailers DROP COLUMN cart_add_url_template;
ALTER TABLE retailers DROP COLUMN cart_view_url;

-- Réglages associés (optionnel) :
-- DELETE FROM settings WHERE setting_key = 'assisted_buy_enabled'
--   OR setting_key = 'assisted_buy_dry_run'
--   OR setting_key LIKE 'assisted_buy_cookie\_%';
