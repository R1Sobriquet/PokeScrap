-- =====================================================================
--  DOWN — Module « PokéStock FR » (rollback réversible)
-- =====================================================================
-- Annule UNIQUEMENT les tables ajoutées par PokéStock FR. N'altère aucune
-- table partagée (products, alerts, settings, job_runs… restent intactes).
-- Les settings/retailers seedés étant additifs, ce down ne touche pas la
-- table `settings` (les clés retail_*/telegram_* sont inoffensives ; les
-- supprimer manuellement si souhaité — voir README).
--
-- Exécution manuelle (PowerShell / Docker) :
--   Get-Content db\migrations\down_pokestock_fr.sql | docker compose exec -T db mysql -u root -p"$Env:DB_ROOT_PASSWORD" "$Env:DB_NAME"
--
-- Ordre = inverse des dépendances FK.
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS retail_stock_events;
DROP TABLE IF EXISTS retail_offers;
DROP TABLE IF EXISTS releases;
DROP TABLE IF EXISTS retailers;
SET FOREIGN_KEY_CHECKS = 1;
