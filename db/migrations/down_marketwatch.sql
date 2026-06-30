-- Down / rollback de la couche Market Intelligence (réversible, NON auto-exécuté).
-- Tables additives uniquement : aucune feature existante n'en dépend.
-- À jouer manuellement (PowerShell : docker compose exec db mysql ... < ce fichier).

DROP TABLE IF EXISTS daily_signals;
DROP TABLE IF EXISTS card_price_snapshot;
DROP TABLE IF EXISTS catalyst_event;
DROP TABLE IF EXISTS popularity_tier;
DROP TABLE IF EXISTS tcgdex_card;

-- Pont ajouté sur products (index puis colonne) :
ALTER TABLE products DROP INDEX idx_products_tcgdex;
ALTER TABLE products DROP COLUMN tcgdex_id;

-- Les réglages associés peuvent être retirés (optionnel) :
-- DELETE FROM settings WHERE setting_key LIKE 'marketwatch\_%';
