#!/usr/bin/env bash
# Sauvegarde MySQL chiffrée + offsite + rétention (Jalon 9).
# Une sauvegarde jamais testée n'existe pas → voir restore_test.sh.
#
# Usage : scripts/backup.sh
# Cron (hôte) : voir BACKUP_SCHEDULE (défaut 03:00).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[ -f .env ] && set -a && . ./.env && set +a

: "${DB_NAME:?DB_NAME requis}"
: "${DB_ROOT_PASSWORD:?DB_ROOT_PASSWORD requis}"
: "${BACKUP_DIR:?BACKUP_DIR requis}"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY requis (age recipient ou clé GPG)}"
RETENTION_DAILY="${BACKUP_RETENTION_DAILY:-7}"

mkdir -p "$BACKUP_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
PLAIN="$BACKUP_DIR/pokescrap_${TS}.sql.gz"

echo "[backup] dump $DB_NAME → $PLAIN"
# Priorité documentée : transactions/positions/lots sont sacrés (dump complet).
docker compose exec -T db mysqldump -u root -p"$DB_ROOT_PASSWORD" \
  --single-transaction --routines --triggers "$DB_NAME" | gzip > "$PLAIN"

# Chiffrement : age si dispo (recipient age1...), sinon GPG.
if command -v age >/dev/null 2>&1; then
  ENC="${PLAIN}.age"
  age -r "$BACKUP_ENCRYPTION_KEY" -o "$ENC" "$PLAIN"
elif command -v gpg >/dev/null 2>&1; then
  ENC="${PLAIN}.gpg"
  gpg --batch --yes --trust-model always -r "$BACKUP_ENCRYPTION_KEY" -o "$ENC" --encrypt "$PLAIN"
else
  echo "[backup] ERREUR : ni 'age' ni 'gpg' disponible — refus de stocker en clair." >&2
  rm -f "$PLAIN"
  exit 1
fi
rm -f "$PLAIN"  # on ne garde jamais le clair
echo "[backup] chiffré → $ENC"

# Copie offsite (rclone:... ou cible scp user@host:/path).
if [ -n "${BACKUP_OFFSITE_TARGET:-}" ]; then
  if [[ "$BACKUP_OFFSITE_TARGET" == rclone:* ]]; then
    rclone copy "$ENC" "${BACKUP_OFFSITE_TARGET#rclone:}"
  else
    scp "$ENC" "$BACKUP_OFFSITE_TARGET"
  fi
  echo "[backup] copie offsite → $BACKUP_OFFSITE_TARGET"
fi

# Rétention quotidienne locale (les hebdo sont conservés côté offsite/snapshots).
find "$BACKUP_DIR" -name 'pokescrap_*.sql.gz.*' -type f -mtime "+${RETENTION_DAILY}" -delete

# Horodatage de la dernière sauvegarde (pour /status + dead-man's switch).
docker compose exec -T backend python -m app.cli record-backup || true
echo "[backup] terminé."
