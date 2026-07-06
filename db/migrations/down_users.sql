-- Down / rollback de la Phase A multi-utilisateurs (réversible, NON auto-exécuté).
-- Tables additives uniquement : l'auth mono-admin historique (.env + settings)
-- reste fonctionnelle sans elles.
-- À jouer manuellement (PowerShell : docker compose exec db mysql ... < ce fichier).

DROP TABLE IF EXISTS email_tokens;
DROP TABLE IF EXISTS auth_sessions;
DROP TABLE IF EXISTS users;

-- Réglage associé (optionnel) :
-- DELETE FROM settings WHERE setting_key = 'signup_enabled';
