# Runbook — Sauvegarde / Restauration

> **Une sauvegarde jamais testée n'existe pas.** Priorité des données sacrées :
> `transactions` / `positions` / `lots` (ledger auditable).

## Configuration (`.env`)
```
BACKUP_DIR=./backups
BACKUP_OFFSITE_TARGET=rclone:remote:pokescrap   # ou user@host:/path (scp)
BACKUP_ENCRYPTION_KEY=age1...                   # recipient age, ou clé/empreinte GPG
BACKUP_RETENTION_DAILY=7
BACKUP_RETENTION_WEEKLY=4
BACKUP_SCHEDULE=0 3 * * *
```
Chiffrement obligatoire : le script **refuse** d'écrire un dump en clair.

## Sauvegarde
```bash
scripts/backup.sh
```
`mysqldump` (--single-transaction) → `gzip` → chiffrement (age/gpg) → `BACKUP_DIR`
→ copie offsite → rétention locale → `record-backup` (horodatage pour `/status`).

### Cron hôte (03:00)
```cron
0 3 * * * cd /chemin/PokeScrap && scripts/backup.sh >> /var/log/pokescrap-backup.log 2>&1
```

## Restauration
```bash
# age : exporter AGE_IDENTITY_FILE (clé privée) ; gpg : clé importée dans le trousseau
scripts/restore.sh backups/pokescrap_AAAAMMJJ_HHMMSS.sql.gz.age
```

## Test de restauration (mensuel, obligatoire)
```bash
scripts/restore_test.sh
```
Importe la **dernière** sauvegarde dans une base **jetable** (`pokescrap_restore_test`),
vérifie le nombre de tables (≥ 14) + un compte de contrôle (`transactions`), puis
supprime la base. **Échoue bruyamment** sinon.

### Cron hôte (mensuel, 1er à 04:00)
```cron
0 4 1 * * cd /chemin/PokeScrap && scripts/restore_test.sh >> /var/log/pokescrap-restoretest.log 2>&1
```

## En cas de sinistre
1. Réinstaller Docker + cloner le repo + restaurer `.env` (hors VCS, conservé à part).
2. `docker compose up -d db` puis `scripts/restore.sh <dernière sauvegarde offsite>`.
3. `docker compose up -d` ; vérifier `/health`, `/status`, et `restore_test.sh`.
