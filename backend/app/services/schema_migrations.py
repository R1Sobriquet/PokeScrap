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


# --------------------------------------------------------- PokéStock FR
# Veille restock : tables additives, ne touchent aucune table partagée.
_RETAILERS_DDL = """
CREATE TABLE IF NOT EXISTS retailers (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code         VARCHAR(32)  NOT NULL,
    name         VARCHAR(128) NOT NULL,
    base_url     VARCHAR(255) NULL,
    sitemap_url  VARCHAR(512) NULL,
    is_active    TINYINT(1)   NOT NULL DEFAULT 1,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_retailer_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_RETAIL_OFFERS_DDL = """
CREATE TABLE IF NOT EXISTS retail_offers (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    retailer_id         BIGINT UNSIGNED NOT NULL,
    retailer_sku        VARCHAR(128) NULL,
    url                 VARCHAR(512) NOT NULL,
    title               VARCHAR(255) NULL,
    image_url           VARCHAR(512) NULL,
    product_type        VARCHAR(16)  NOT NULL DEFAULT 'autre',
    current_stock_state ENUM('in_stock','out_of_stock','preorder','unknown') NOT NULL DEFAULT 'unknown',
    current_price       DECIMAL(8,2) NULL,
    currency            CHAR(3)      NOT NULL DEFAULT 'EUR',
    is_watched          TINYINT(1)   NOT NULL DEFAULT 0,
    product_id          BIGINT UNSIGNED NULL,
    first_seen_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_checked_at     DATETIME     NULL,
    last_changed_at     DATETIME     NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_retail_offer_url (url),
    KEY idx_retailer_watched (retailer_id, is_watched),
    KEY idx_stock_state (current_stock_state),
    CONSTRAINT fk_offer_retailer FOREIGN KEY (retailer_id) REFERENCES retailers (id) ON DELETE CASCADE,
    CONSTRAINT fk_offer_product FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_RETAIL_STOCK_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS retail_stock_events (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    offer_id    BIGINT UNSIGNED NOT NULL,
    from_state  VARCHAR(16)  NULL,
    to_state    VARCHAR(16)  NOT NULL,
    price       DECIMAL(8,2) NULL,
    detected_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_offer_detected (offer_id, detected_at),
    CONSTRAINT fk_event_offer FOREIGN KEY (offer_id) REFERENCES retail_offers (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_RELEASES_DDL = """
CREATE TABLE IF NOT EXISTS releases (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    set_name      VARCHAR(255) NULL,
    product_name  VARCHAR(255) NOT NULL,
    product_type  VARCHAR(16)  NULL,
    release_date  DATE         NULL,
    preorder_date DATE         NULL,
    source_note   VARCHAR(512) NULL,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_release_date (release_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

#: Seed best-effort des détaillants V1. ``sitemap_url`` est à CONFIRMER via le
#: robots.txt de chaque site au go-live (éditable en base/UI) — voir README.
_RETAILERS_SEED = """
INSERT IGNORE INTO retailers (code, name, base_url, sitemap_url, is_active) VALUES
    ('cultura',    'Cultura',    'https://www.cultura.com',     'https://www.cultura.com/sitemap.xml',     1),
    ('fnac',       'Fnac',       'https://www.fnac.com',        'https://www.fnac.com/sitemap_index.xml',  1),
    ('micromania', 'Micromania', 'https://www.micromania.fr',   'https://www.micromania.fr/sitemap.xml',   1)
"""


def ensure_schema_upgrades(engine: Engine) -> None:
    """Applique les upgrades manquants (MySQL uniquement)."""
    if engine.dialect.name != "mysql":
        return
    with engine.begin() as conn:
        db_name = conn.execute(text("SELECT DATABASE()")).scalar()
        conn.execute(text(_TRACKED_SETS_DDL))
        conn.execute(text(_JOB_RUNS_DDL))
        # PokéStock FR — tables additives + seed détaillants.
        conn.execute(text(_RETAILERS_DDL))
        conn.execute(text(_RETAIL_OFFERS_DDL))
        conn.execute(text(_RETAIL_STOCK_EVENTS_DDL))
        conn.execute(text(_RELEASES_DDL))
        conn.execute(text(_RETAILERS_SEED))
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

        # PokéStock FR — étend l'ENUM alerts.alert_type (additif : valeurs existantes
        # conservées) pour router les alertes restock/new_sku via le pipeline existant.
        alert_type = conn.execute(
            text(
                "SELECT COLUMN_TYPE FROM information_schema.columns "
                "WHERE table_schema = :db AND table_name = 'alerts' AND column_name = 'alert_type'"
            ),
            {"db": db_name},
        ).scalar()
        if alert_type and "'restock'" not in alert_type:
            conn.execute(text(
                "ALTER TABLE alerts MODIFY alert_type ENUM("
                "'buy','sell_x2','sell_25_50_25','sell_forced','sell_reminder',"
                "'cash_min','anti_pump','anti_fomo','illiquid','grading','reinvest',"
                "'tax_provision','palier_up','palier_down','auction_reminder',"
                "'lot_summary','tech_error','restock','new_sku') NOT NULL"
            ))
            logger.info("Migration : valeurs ENUM alerts.alert_type restock/new_sku ajoutées.")

        # PokéAlpha — image produit sur les offres retail (JSON-LD/og:image).
        img_col = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = :db AND table_name = 'retail_offers' AND column_name = 'image_url'"
            ),
            {"db": db_name},
        ).scalar()
        if not img_col:
            conn.execute(text(
                "ALTER TABLE retail_offers ADD COLUMN image_url VARCHAR(512) NULL AFTER title"
            ))
            logger.info("Migration : colonne retail_offers.image_url ajoutée.")
