#!/usr/bin/env bash
# Restauration d'une sauvegarde chiffrée dans la base de production.
# Usage : scripts/restore.sh <fichier .sql.gz.age|.gpg>   [DB_CIBLE]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[ -f .env ] && set -a && . ./.env && set +a

FILE="${1:?Chemin du fichier de sauvegarde requis}"
TARGET_DB="${2:-${DB_NAME:?DB_NAME requis}}"
: "${DB_ROOT_PASSWORD:?DB_ROOT_PASSWORD requis}"
[ -f "$FILE" ] || { echo "[restore] fichier introuvable : $FILE" >&2; exit 1; }

decrypt() {
  case "$FILE" in
    *.age) age -d -i "${AGE_IDENTITY_FILE:?AGE_IDENTITY_FILE requis pour déchiffrer}" "$FILE" ;;
    *.gpg) gpg --batch --yes -d "$FILE" ;;
    *) cat "$FILE" ;;
  esac
}

echo "[restore] $FILE → base '$TARGET_DB' (déchiffrement + import)"
decrypt | gunzip | docker compose exec -T db mysql -u root -p"$DB_ROOT_PASSWORD" "$TARGET_DB"
echo "[restore] terminé."
