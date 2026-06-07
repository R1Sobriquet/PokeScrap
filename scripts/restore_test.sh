#!/usr/bin/env bash
# Test de restauration : importe la dernière sauvegarde dans une base JETABLE et
# vérifie l'intégrité (nb de tables + compte de contrôle). Échoue bruyamment.
# « Une sauvegarde jamais testée n'existe pas. »  → job mensuel.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[ -f .env ] && set -a && . ./.env && set +a

: "${BACKUP_DIR:?BACKUP_DIR requis}"
: "${DB_ROOT_PASSWORD:?DB_ROOT_PASSWORD requis}"
TEST_DB="pokescrap_restore_test"
MIN_TABLES=14

LATEST="$(ls -t "$BACKUP_DIR"/pokescrap_*.sql.gz.* 2>/dev/null | head -n1 || true)"
[ -n "$LATEST" ] || { echo "[restore_test] AUCUNE sauvegarde trouvée dans $BACKUP_DIR" >&2; exit 1; }
echo "[restore_test] sauvegarde testée : $LATEST"

mysql_root() { docker compose exec -T db mysql -u root -p"$DB_ROOT_PASSWORD" "$@"; }

cleanup() { mysql_root -e "DROP DATABASE IF EXISTS \`$TEST_DB\`;" || true; }
trap cleanup EXIT

mysql_root -e "DROP DATABASE IF EXISTS \`$TEST_DB\`; CREATE DATABASE \`$TEST_DB\`;"
DB_NAME="$TEST_DB" scripts/restore.sh "$LATEST" "$TEST_DB"

TABLES="$(mysql_root -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$TEST_DB';")"
TX="$(mysql_root -N -e "SELECT COUNT(*) FROM \`$TEST_DB\`.transactions;")"
echo "[restore_test] tables=$TABLES transactions=$TX"

if [ "$TABLES" -lt "$MIN_TABLES" ]; then
  echo "[restore_test] ÉCHEC : $TABLES tables (< $MIN_TABLES)" >&2
  exit 1
fi
echo "[restore_test] OK : restauration vérifiée."
