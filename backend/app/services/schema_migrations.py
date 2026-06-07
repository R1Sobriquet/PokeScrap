"""Migrations légères et idempotentes pour les bases déjà déployées.

``db/schema.sql`` ne s'applique qu'à l'init d'un volume neuf ; ces upgrades
ajoutent les colonnes/tables introduites après coup, sans perdre de données. Ne
s'exécutent que sur MySQL (en test SQLite, ``Base.metadata.create_all`` suffit).
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("services.schema_migrations")

_TRACKED_SETS_DDL = """
CREATE TABLE IF NOT EXISTS tracked_sets (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    set_slug        VARCHAR(128) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
    min_value_eur   DECIMAL(12,2) NOT NULL DEFAULT 0,
    include_single  TINYINT(1)   NOT NULL DEFAULT 1,
    include_sealed  TINYINT(1)   NOT NULL DEFAULT 1,
    included_families JSON       NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_tracked_set_slug (set_slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


_JOB_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS job_runs (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    job_name     VARCHAR(64)  NOT NULL,
    status       VARCHAR(16)  NOT NULL DEFAULT 'running',
    started_at   DATETIME     NOT NULL,
    finished_at  DATETIME     NULL,
    result_json  JSON         NULL,
    error_text   TEXT         NULL,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_job_name_status (job_name, status),
    KEY idx_job_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def ensure_schema_upgrades(engine: Engine) -> None:
    """Applique les upgrades manquants (MySQL uniquement)."""
    if engine.dialect.name != "mysql":
        return
    with engine.begin() as conn:
        db_name = conn.execute(text("SELECT DATABASE()")).scalar()
        conn.execute(text(_TRACKED_SETS_DDL))
        conn.execute(text(_JOB_RUNS_DDL))
        col = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = :db AND table_name = 'watchlist' AND column_name = 'source'"
            ),
            {"db": db_name},
        ).scalar()
        if not col:
            conn.execute(text(
                "ALTER TABLE watchlist ADD COLUMN source VARCHAR(16) NOT NULL DEFAULT 'manual'"
            ))
            logger.info("Migration : colonne watchlist.source ajoutée.")
