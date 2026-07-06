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


_ML_MODELS_DDL = """
CREATE TABLE IF NOT EXISTS ml_models (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name        VARCHAR(64)  NOT NULL,
    payload     LONGBLOB     NULL,
    n_samples   INT          NOT NULL DEFAULT 0,
    metrics     JSON         NULL,
    trained_at  DATETIME     NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ml_model_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


_MARKET_SNAPSHOTS_DDL = """
CREATE TABLE IF NOT EXISTS market_price_snapshots (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    product_ref   VARCHAR(64)  NOT NULL,
    source        ENUM('ppt','tcgdex','ebay','poketrace') NOT NULL,
    market        ENUM('us','eu') NOT NULL,
    product_type  VARCHAR(16)  NULL,
    price         DECIMAL(8,2) NULL,
    currency      CHAR(3)      NOT NULL DEFAULT 'EUR',
    extra         JSON         NULL,
    captured_at   DATETIME     NOT NULL,
    captured_date DATE         NOT NULL,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_market_snapshot_day (product_ref, source, market, captured_date),
    KEY idx_market_ref_date (product_ref, captured_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_DATA_QUARANTINE_DDL = """
CREATE TABLE IF NOT EXISTS data_quarantine (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source      VARCHAR(16)  NOT NULL,
    product_ref VARCHAR(64)  NULL,
    raw         JSON         NULL,
    reason      VARCHAR(255) NOT NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_quarantine_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_MATCH_REVIEW_DDL = """
CREATE TABLE IF NOT EXISTS match_review (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    product_ref   VARCHAR(64)  NOT NULL,
    candidate_ref VARCHAR(64)  NULL,
    source        VARCHAR(16)  NULL,
    method        VARCHAR(16)  NULL,
    confidence    DECIMAL(5,2) NULL,
    payload       JSON         NULL,
    status        VARCHAR(16)  NOT NULL DEFAULT 'pending',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at   DATETIME     NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_match_review_pair (product_ref, candidate_ref),
    KEY idx_match_review_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


# ---------------------------------------------------------------------------
#  Market Intelligence (couche cartes sous-valorisées) — tables additives.
#  Clé canonique = card_id (ID TCGdex). Argent en DECIMAL (convention repo 12,2).
# ---------------------------------------------------------------------------

_TCGDEX_CARD_DDL = """
CREATE TABLE IF NOT EXISTS tcgdex_card (
    card_id    VARCHAR(40)  NOT NULL,
    set_id     VARCHAR(40)  NULL,
    set_name   VARCHAR(255) NULL,
    number     VARCHAR(32)  NULL,
    rarity     VARCHAR(64)  NULL,
    pokemon    VARCHAR(96)  NULL,
    name_en    VARCHAR(255) NULL,
    name_fr    VARCHAR(255) NULL,
    name_jp    VARCHAR(255) NULL,
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (card_id),
    KEY idx_tcgdex_set_number (set_id, number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_CARD_PRICE_SNAPSHOT_DDL = """
CREATE TABLE IF NOT EXISTS card_price_snapshot (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    card_id         VARCHAR(40) NOT NULL,
    source          ENUM('cardmarket','ppt','tcgplayer','ebay_active') NOT NULL,
    language        ENUM('EN','JP','FR') NOT NULL,
    condition_grade VARCHAR(12) NOT NULL DEFAULT 'NM_RAW',
    price_eur       DECIMAL(12,2) NOT NULL,
    price_native    DECIMAL(12,2) NULL,
    currency        CHAR(3)     NULL,
    trend_eur       DECIMAL(12,2) NULL,
    active_listings INT         NULL,
    watchers        INT         NULL,
    captured_at     DATE        NOT NULL,
    created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_card_price_day (card_id, source, language, condition_grade, captured_at),
    KEY idx_card_price_lookup (card_id, language, captured_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_POPULARITY_TIER_DDL = """
CREATE TABLE IF NOT EXISTS popularity_tier (
    id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    card_id    VARCHAR(40) NULL,
    pokemon    VARCHAR(96) NULL,
    tier       ENUM('S','A','B','C') NOT NULL,
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_popularity_card (card_id),
    UNIQUE KEY uq_popularity_pokemon (pokemon)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_CATALYST_EVENT_DDL = """
CREATE TABLE IF NOT EXISTS catalyst_event (
    id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    label      VARCHAR(255) NOT NULL,
    event_date DATE         NOT NULL,
    scope      VARCHAR(96)  NOT NULL DEFAULT 'global',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_catalyst_date (event_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_DAILY_SIGNALS_DDL = """
CREATE TABLE IF NOT EXISTS daily_signals (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    card_id      VARCHAR(40) NOT NULL,
    language     ENUM('EN','JP','FR') NOT NULL,
    price_eur    DECIMAL(12,2) NULL,
    near_low     DECIMAL(6,4) NULL,
    drawdown_sma DECIMAL(6,4) NULL,
    bottoming    DECIMAL(6,4) NULL,
    cross_lang   DECIMAL(6,4) NULL,
    liquidity    DECIMAL(6,4) NULL,
    momentum_7d  DECIMAL(7,4) NULL,
    score        DECIMAL(8,4) NOT NULL DEFAULT 0,
    budget_band  VARCHAR(8)  NULL,
    buy_url      VARCHAR(512) NULL,
    computed_at  DATE        NOT NULL,
    created_at   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_daily_signal_day (card_id, language, computed_at),
    KEY idx_daily_signal_rank (computed_at, score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


# ---------------------------------------------------------------------------
#  Multi-utilisateurs (Phase A) — identités, sessions refresh, jetons email.
#  L'admin historique (.env) est créé idempotemment au boot (ensure_admin_user).
# ---------------------------------------------------------------------------

_USERS_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    email             VARCHAR(255) NOT NULL,
    username          VARCHAR(64)  NOT NULL,
    password_hash     VARCHAR(255) NOT NULL,
    role              ENUM('admin','user') NOT NULL DEFAULT 'user',
    plan              ENUM('free','pro')   NOT NULL DEFAULT 'free',
    status            ENUM('pending','active','disabled') NOT NULL DEFAULT 'pending',
    email_verified_at DATETIME     NULL,
    current_tier      SMALLINT     NULL,
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_user_email (email),
    UNIQUE KEY uq_user_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_AUTH_SESSIONS_DDL = """
CREATE TABLE IF NOT EXISTS auth_sessions (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id      BIGINT UNSIGNED NOT NULL,
    refresh_hash CHAR(64)     NOT NULL,
    expires_at   DATETIME     NOT NULL,
    revoked_at   DATETIME     NULL,
    user_agent   VARCHAR(255) NULL,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_session_refresh (refresh_hash),
    KEY idx_session_user (user_id, expires_at),
    CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_EMAIL_TOKENS_DDL = """
CREATE TABLE IF NOT EXISTS email_tokens (
    id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id    BIGINT UNSIGNED NOT NULL,
    purpose    ENUM('verify','reset') NOT NULL,
    token_hash CHAR(64)  NOT NULL,
    expires_at DATETIME  NOT NULL,
    used_at    DATETIME  NULL,
    created_at DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_email_token (token_hash),
    KEY idx_email_token_user (user_id, purpose),
    CONSTRAINT fk_email_token_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def _add_col(conn, db_name: str, table: str, column: str, ddl: str) -> None:
    """ALTER ADD COLUMN gardé par information_schema (idempotent)."""
    exists = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = :db "
        "AND table_name = :t AND column_name = :c"
    ), {"db": db_name, "t": table, "c": column}).scalar()
    if not exists:
        conn.execute(text(ddl))
        logger.info("Migration : colonne %s.%s ajoutée.", table, column)


def _add_index(conn, db_name: str, table: str, index: str, ddl: str) -> None:
    """ALTER ADD INDEX gardé par information_schema (idempotent)."""
    exists = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = :db "
        "AND table_name = :t AND index_name = :i"
    ), {"db": db_name, "t": table, "i": index}).scalar()
    if not exists:
        conn.execute(text(ddl))
        logger.info("Migration : index %s.%s ajouté.", table, index)


_STORE_LOCATIONS_DDL = """
CREATE TABLE IF NOT EXISTS store_locations (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    retailer_id BIGINT UNSIGNED NOT NULL,
    store_code  VARCHAR(64)  NOT NULL,
    name        VARCHAR(128) NOT NULL,
    city        VARCHAR(96)  NULL,
    postal      VARCHAR(16)  NULL,
    is_watched  TINYINT(1)   NOT NULL DEFAULT 0,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_store_retailer_code (retailer_id, store_code),
    CONSTRAINT fk_store_retailer FOREIGN KEY (retailer_id) REFERENCES retailers (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_OFFER_STORE_DDL = """
CREATE TABLE IF NOT EXISTS offer_store_availability (
    id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    offer_id           BIGINT UNSIGNED NOT NULL,
    store_id           BIGINT UNSIGNED NOT NULL,
    availability_state ENUM('in_store','out_of_store','limited','unknown') NOT NULL DEFAULT 'unknown',
    price              DECIMAL(8,2) NULL,
    last_checked_at    DATETIME NULL,
    last_changed_at    DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_offer_store (offer_id, store_id),
    CONSTRAINT fk_osa_offer FOREIGN KEY (offer_id) REFERENCES retail_offers (id) ON DELETE CASCADE,
    CONSTRAINT fk_osa_store FOREIGN KEY (store_id) REFERENCES store_locations (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

# Seed enseignes (additif, INSERT IGNORE) — nouvelles enseignes magasin.
_STORE_RETAILERS_SEED = """
INSERT IGNORE INTO retailers (code, name, base_url, is_active) VALUES
    ('king-jouet',   'King Jouet',      'https://www.king-jouet.com', 1),
    ('joueclub',     'JouéClub',        'https://www.joueclub.fr',    1),
    ('lagranderecre','La Grande Récré', 'https://www.lagranderecre.fr', 1)
"""

# Seed magasins zone Agen. store_code = placeholder éditable (confirmé à l'inspection).
# Confirmés scrapables → is_watched=1 ; probables → is_watched=0.
_STORE_LOCATIONS_SEED = """
INSERT IGNORE INTO store_locations (retailer_id, store_code, name, city, postal, is_watched)
SELECT r.id, s.store_code, s.name, s.city, s.postal, s.is_watched FROM (
    SELECT 'micromania' rc, 'agen-boe'    store_code, 'Micromania Agen/Boé'  name, 'Boé'                 city, '47550' postal, 1 is_watched UNION ALL
    SELECT 'micromania', 'montauban',     'Micromania Montauban',            'Montauban',            '82000', 1 UNION ALL
    SELECT 'cultura',    'agen',          'Cultura Agen',                    'Agen',                 '47000', 1 UNION ALL
    SELECT 'cultura',    'montauban',     'Cultura Montauban',               'Montauban',            '82000', 1 UNION ALL
    SELECT 'king-jouet', 'boe-1111',      'King Jouet Boé',                  'Boé',                  '47550', 1 UNION ALL
    SELECT 'king-jouet', 'villeneuve-0330','King Jouet Villeneuve-sur-Lot',  'Villeneuve-sur-Lot',   '47300', 1 UNION ALL
    SELECT 'joueclub',   'boe',           'JouéClub Boé',                    'Boé',                  '47550', 0 UNION ALL
    SELECT 'lagranderecre','agen',        'La Grande Récré Agen',            'Agen',                 '47000', 0
) s JOIN retailers r ON r.code = s.rc
"""


_BUY_RULES_DDL = """
CREATE TABLE IF NOT EXISTS buy_rules (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    scope        ENUM('offer','product_type') NOT NULL,
    scope_value  VARCHAR(64)  NOT NULL,
    retailer_id  BIGINT UNSIGNED NULL,
    max_price    DECIMAL(8,2) NOT NULL,
    max_quantity INT          NOT NULL DEFAULT 1,
    is_enabled   TINYINT(1)   NOT NULL DEFAULT 0,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_buy_rule_scope (scope, scope_value),
    CONSTRAINT fk_buyrule_retailer FOREIGN KEY (retailer_id) REFERENCES retailers (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_BUY_ATTEMPTS_DDL = """
CREATE TABLE IF NOT EXISTS buy_attempts (
    id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    offer_id   BIGINT UNSIGNED NOT NULL,
    channel    ENUM('online','store') NOT NULL DEFAULT 'online',
    status     ENUM('carted','blocked','skipped','dry_run') NOT NULL,
    cart_url   VARCHAR(512) NULL,
    reason     VARCHAR(128) NULL,
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_buy_attempt_offer (offer_id, created_at),
    CONSTRAINT fk_buyattempt_offer FOREIGN KEY (offer_id) REFERENCES retail_offers (id) ON DELETE CASCADE
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
        conn.execute(text(_ML_MODELS_DDL))
        # Moat de données marché — tables additives.
        conn.execute(text(_MARKET_SNAPSHOTS_DDL))
        conn.execute(text(_DATA_QUARANTINE_DDL))
        conn.execute(text(_MATCH_REVIEW_DDL))
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
        if alert_type and ("'restock'" not in alert_type or "'health'" not in alert_type
                           or "'marketwatch'" not in alert_type):
            conn.execute(text(
                "ALTER TABLE alerts MODIFY alert_type ENUM("
                "'buy','sell_x2','sell_25_50_25','sell_forced','sell_reminder',"
                "'cash_min','anti_pump','anti_fomo','illiquid','grading','reinvest',"
                "'tax_provision','palier_up','palier_down','auction_reminder',"
                "'lot_summary','tech_error','restock','new_sku','health','marketwatch') NOT NULL"
            ))
            logger.info("Migration : valeurs ENUM alerts.alert_type restock/new_sku/health/marketwatch.")

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

        # PokéAlpha — image de vignette sur les annonces de sourcing (scraper).
        src_img = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = :db AND table_name = 'sourcing_listings' AND column_name = 'image_url'"
            ),
            {"db": db_name},
        ).scalar()
        if not src_img:
            conn.execute(text(
                "ALTER TABLE sourcing_listings ADD COLUMN image_url VARCHAR(768) NULL AFTER location"
            ))
            logger.info("Migration : colonne sourcing_listings.image_url ajoutée.")

        # PokéStock FR Phase A — hot-list, ETag, latence, endpoint dispo.
        _add_col(conn, db_name, "retail_offers", "watch_tier",
                 "ALTER TABLE retail_offers ADD COLUMN watch_tier VARCHAR(8) NOT NULL DEFAULT 'normal' AFTER is_watched")
        _add_col(conn, db_name, "retail_offers", "availability_etag",
                 "ALTER TABLE retail_offers ADD COLUMN availability_etag VARCHAR(255) NULL")
        _add_index(conn, db_name, "retail_offers", "idx_offer_tier_watched",
                   "ALTER TABLE retail_offers ADD INDEX idx_offer_tier_watched (watch_tier, is_watched)")
        _add_col(conn, db_name, "retail_stock_events", "detected_to_alert_ms",
                 "ALTER TABLE retail_stock_events ADD COLUMN detected_to_alert_ms INT NULL")
        _add_col(conn, db_name, "retailers", "availability_url_template",
                 "ALTER TABLE retailers ADD COLUMN availability_url_template VARCHAR(512) NULL AFTER sitemap_url")

        # PokéStock FR Phase B — dispo en magasin (zone Agen).
        conn.execute(text(_STORE_LOCATIONS_DDL))
        conn.execute(text(_OFFER_STORE_DDL))
        _add_col(conn, db_name, "retailers", "store_availability_url_template",
                 "ALTER TABLE retailers ADD COLUMN store_availability_url_template VARCHAR(512) NULL")
        _add_col(conn, db_name, "retail_stock_events", "store_id",
                 "ALTER TABLE retail_stock_events ADD COLUMN store_id BIGINT UNSIGNED NULL")
        conn.execute(text(_STORE_RETAILERS_SEED))
        conn.execute(text(_STORE_LOCATIONS_SEED))

        # PokéStock FR Phase C — achat assisté (allow-list + audit).
        conn.execute(text(_BUY_RULES_DDL))
        conn.execute(text(_BUY_ATTEMPTS_DDL))
        _add_col(conn, db_name, "retailers", "cart_add_url_template",
                 "ALTER TABLE retailers ADD COLUMN cart_add_url_template VARCHAR(512) NULL")
        _add_col(conn, db_name, "retailers", "cart_view_url",
                 "ALTER TABLE retailers ADD COLUMN cart_view_url VARCHAR(512) NULL")

        # Market Intelligence — registre TCGdex, série prix carte, refs & signaux.
        conn.execute(text(_TCGDEX_CARD_DDL))
        conn.execute(text(_CARD_PRICE_SNAPSHOT_DDL))
        conn.execute(text(_POPULARITY_TIER_DDL))
        conn.execute(text(_CATALYST_EVENT_DDL))
        conn.execute(text(_DAILY_SIGNALS_DDL))
        # Pont registre existant ↔ TCGdex (nullable, rempli par le matcher).
        _add_col(conn, db_name, "products", "tcgdex_id",
                 "ALTER TABLE products ADD COLUMN tcgdex_id VARCHAR(40) NULL AFTER tcgplayer_id")
        _add_index(conn, db_name, "products", "idx_products_tcgdex",
                   "ALTER TABLE products ADD INDEX idx_products_tcgdex (tcgdex_id)")

        # Multi-utilisateurs Phase A — identités, sessions refresh, jetons email.
        conn.execute(text(_USERS_DDL))
        conn.execute(text(_AUTH_SESSIONS_DDL))
        conn.execute(text(_EMAIL_TOKENS_DDL))
