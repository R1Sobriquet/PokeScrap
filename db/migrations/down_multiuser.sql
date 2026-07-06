-- Down / rollback de la Phase B multi-utilisateurs (réversible, NON auto-exécuté).
-- Restaure le modèle mono-user : colonnes user_id retirées, unicités globales
-- restaurées, overlays per-user supprimés. À jouer AVANT down_users.sql.
-- (PowerShell : docker compose exec db mysql ... < ce fichier)

-- Tables overlay per-user
DROP TABLE IF EXISTS user_listing_status;
DROP TABLE IF EXISTS user_watched_stores;
DROP TABLE IF EXISTS user_watched_offers;
DROP TABLE IF EXISTS user_settings;

-- Unicités : retour aux contraintes globales mono-user
ALTER TABLE watchlist DROP INDEX uq_watch_user_product;
ALTER TABLE watchlist ADD UNIQUE uq_watch_product (product_id);
ALTER TABLE account_snapshots DROP INDEX uq_snapshot_user_date;
ALTER TABLE account_snapshots ADD UNIQUE uq_snapshot_date (snapshot_date);
ALTER TABLE tracked_sets DROP INDEX uq_tracked_user_slug;
ALTER TABLE tracked_sets ADD UNIQUE uq_tracked_set_slug (set_slug);

-- Colonnes user_id (FK implicites supprimées avec la colonne : nommées fk_<t>_user
-- uniquement sur volume neuf ; sur base migrée il n'y a pas de FK, juste l'index).
ALTER TABLE positions             DROP COLUMN user_id;
ALTER TABLE transactions          DROP COLUMN user_id;
ALTER TABLE lots                  DROP COLUMN user_id;
ALTER TABLE lot_items             DROP COLUMN user_id;
ALTER TABLE account_snapshots     DROP COLUMN user_id;
ALTER TABLE alerts                DROP COLUMN user_id;
ALTER TABLE grading_opportunities DROP COLUMN user_id;
ALTER TABLE buy_rules             DROP COLUMN user_id;
ALTER TABLE watchlist             DROP COLUMN user_id;
ALTER TABLE tracked_sets          DROP COLUMN user_id;
