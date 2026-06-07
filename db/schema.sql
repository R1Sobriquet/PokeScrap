-- =====================================================================
--  Pokémon Arbitrage & Portfolio App — Schéma consolidé FINAL (Phase 1)
--  MySQL 8.x | InnoDB | utf8mb4 | UTC applicatif
--  Intègre tous les amendements S5 (stages vente), S7 (cost_basis, cash),
--  S8 (grading pondéré), S9 (enum alertes étendu).
--  Les seeds tiers_config + settings = le "registre des paramètres figés".
-- =====================================================================

SET NAMES utf8mb4;
SET time_zone = '+00:00';

-- ----------------------------- 1. tiers_config ----------------------
CREATE TABLE tiers_config (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    tier_number     TINYINT UNSIGNED NOT NULL,
    name            VARCHAR(64)      NOT NULL,
    capital_min     DECIMAL(12,2)    NOT NULL,
    capital_max     DECIMAL(12,2)    NULL,
    alloc_stock_pct DECIMAL(5,2)     NULL,
    alloc_cash_pct  DECIMAL(5,2)     NULL,
    cash_min_pct    DECIMAL(5,2)     NOT NULL,
    strategy_mix    JSON             NULL,
    description     TEXT             NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_tier_number (tier_number),
    KEY idx_capital_band (capital_min, capital_max)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------- 2. settings --------------------------
CREATE TABLE settings (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    setting_key   VARCHAR(64)  NOT NULL,
    setting_value VARCHAR(255) NOT NULL,
    value_type    ENUM('int','decimal','bool','string','json') NOT NULL DEFAULT 'string',
    description   VARCHAR(255) NULL,
    updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_setting_key (setting_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------- 3. products --------------------------
CREATE TABLE products (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    product_type  ENUM('single','sealed') NOT NULL,
    name          VARCHAR(255) NOT NULL,
    set_name      VARCHAR(255) NULL,
    set_slug      VARCHAR(128) NULL,
    card_number   VARCHAR(32)  NULL,
    variant       VARCHAR(64)  NULL,
    rarity        VARCHAR(64)  NULL,
    language      ENUM('EN','JP','FR','DE','IT','ES','OTHER') NOT NULL DEFAULT 'EN',
    poketrace_id  VARCHAR(64)  NULL,
    cardmarket_id VARCHAR(32)  NULL,
    tcgplayer_id  VARCHAR(32)  NULL,
    image_url     VARCHAR(512) NULL,
    is_active     TINYINT(1)   NOT NULL DEFAULT 1,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_poketrace_id (poketrace_id),
    KEY idx_cardmarket_id (cardmarket_id),
    KEY idx_tcgplayer_id (tcgplayer_id),
    KEY idx_set_card (set_slug, card_number),
    KEY idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------- 4. price_snapshots -------------------
CREATE TABLE price_snapshots (
    id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    product_id        BIGINT UNSIGNED NOT NULL,
    source            ENUM('poketrace','psa','manual') NOT NULL,
    market            ENUM('US','EU') NULL,
    marketplace       VARCHAR(32) NULL,
    grade_company     ENUM('RAW','PSA','BGS','CGC','SGC','ACE','TAG') NOT NULL DEFAULT 'RAW',
    grade             VARCHAR(8)  NULL,
    condition_code    ENUM('NM','EX','LP','MP','HP','DMG') NULL,
    currency          CHAR(3)     NOT NULL,
    country_code      CHAR(2)     NULL,
    price_avg         DECIMAL(12,2) NULL,
    price_low         DECIMAL(12,2) NULL,
    price_high        DECIMAL(12,2) NULL,
    avg_1d            DECIMAL(12,2) NULL,
    avg_7d            DECIMAL(12,2) NULL,
    avg_30d           DECIMAL(12,2) NULL,
    sale_count        INT UNSIGNED  NULL,
    approx_sale_count TINYINT(1)    NOT NULL DEFAULT 0,
    captured_at       DATETIME      NOT NULL,
    created_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_product_time (product_id, captured_at),
    KEY idx_tier_lookup (product_id, grade_company, grade, market, captured_at),
    KEY idx_captured_at (captured_at),
    CONSTRAINT fk_snap_product FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------- 5. watchlist -------------------------
CREATE TABLE watchlist (
    id                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    product_id           BIGINT UNSIGNED NOT NULL,
    tier                 ENUM('S++','S','A','B','C') NOT NULL DEFAULT 'B',
    is_trinity           TINYINT(1)   NOT NULL DEFAULT 0,
    is_illustration_rare TINYINT(1)   NOT NULL DEFAULT 0,
    min_discount_pct     DECIMAL(5,2) NULL,
    target_resale_hours  INT UNSIGNED NULL,
    priority_coef        DECIMAL(5,2) NOT NULL DEFAULT 1.00,
    keywords             VARCHAR(512) NULL,
    notes                TEXT         NULL,
    is_active            TINYINT(1)   NOT NULL DEFAULT 1,
    created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_watch_product (product_id),
    KEY idx_tier (tier),
    KEY idx_trinity (is_trinity),
    CONSTRAINT fk_watch_product FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------- 6. sourcing_listings ----------------
CREATE TABLE sourcing_listings (
    id                     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    platform               ENUM('vinted','leboncoin','ebay','cardmarket','other') NOT NULL,
    external_id            VARCHAR(128) NULL,
    url                    VARCHAR(768) NOT NULL,
    raw_title              VARCHAR(512) NOT NULL,
    description            TEXT         NULL,
    asking_price           DECIMAL(12,2) NOT NULL,
    shipping_cost          DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    protection_cost        DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    acquisition_cost_total DECIMAL(12,2) AS (asking_price + shipping_cost + protection_cost) STORED,
    currency               CHAR(3)      NOT NULL DEFAULT 'EUR',
    location               VARCHAR(128) NULL,
    estimated_resale_value DECIMAL(12,2) NULL,
    ratio_pct              DECIMAL(6,2) NULL,
    passes_50_rule         TINYINT(1)   NULL,
    filter_flags           JSON         NULL,
    detected_products      JSON         NULL,
    estimated_total_cards  INT UNSIGNED NULL,
    status                 ENUM('new','flagged','blocked','watch','bought','dismissed','expired') NOT NULL DEFAULT 'new',
    listed_at              DATETIME     NULL,
    detected_at            DATETIME     NOT NULL,
    evaluated_at           DATETIME     NULL,
    created_at             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_platform_external (platform, external_id),
    KEY idx_status (status),
    KEY idx_detected_at (detected_at),
    KEY idx_passes_rule (passes_50_rule)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------- 7. lots ------------------------------
CREATE TABLE lots (
    id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source_listing_id BIGINT UNSIGNED NULL,
    label             VARCHAR(255) NULL,
    total_cost        DECIMAL(12,2) NOT NULL,
    currency          CHAR(3)      NOT NULL DEFAULT 'EUR',
    platform          ENUM('vinted','leboncoin','ebay','cardmarket','other') NULL,
    purchased_at      DATETIME     NOT NULL,
    status            ENUM('received','processing','segmented','liquidated') NOT NULL DEFAULT 'received',
    notes             TEXT         NULL,
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_lot_status (status),
    CONSTRAINT fk_lot_listing FOREIGN KEY (source_listing_id) REFERENCES sourcing_listings (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------- 8. lot_items -------------------------
CREATE TABLE lot_items (
    id                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    lot_id               BIGINT UNSIGNED NOT NULL,
    product_id           BIGINT UNSIGNED NULL,
    quantity             INT UNSIGNED NOT NULL DEFAULT 1,
    segmentation         ENUM('individual','bulk_theme') NOT NULL,
    estimated_unit_value DECIMAL(12,2) NULL,
    bulk_group_label     VARCHAR(128) NULL,
    target_platform      ENUM('cardmarket','ebay','vinted') NULL,
    status               ENUM('pending','listed','sold') NOT NULL DEFAULT 'pending',
    created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_lot (lot_id),
    KEY idx_item_status (status),
    CONSTRAINT fk_item_lot FOREIGN KEY (lot_id) REFERENCES lots (id) ON DELETE CASCADE,
    CONSTRAINT fk_item_product FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------- 9. positions -------------------------
CREATE TABLE positions (
    id                     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    product_id             BIGINT UNSIGNED NOT NULL,
    lot_id                 BIGINT UNSIGNED NULL,
    quantity               INT UNSIGNED NOT NULL DEFAULT 1,
    avg_cost               DECIMAL(12,2) NOT NULL,
    grade_company          ENUM('RAW','PSA','BGS','CGC','SGC','ACE','TAG') NOT NULL DEFAULT 'RAW',
    grade                  VARCHAR(8)   NULL,
    acquired_at            DATETIME     NOT NULL,
    target_sell_price      DECIMAL(12,2) NULL,
    initial_capital_basis  DECIMAL(12,2) NULL,
    is_speculative_reserve TINYINT(1)   NOT NULL DEFAULT 0,
    stage_capital_secured  TINYINT(1)   NOT NULL DEFAULT 0,   -- S5
    stage_structured       TINYINT(1)   NOT NULL DEFAULT 0,   -- S5
    stage_forced           TINYINT(1)   NOT NULL DEFAULT 0,   -- S5
    status                 ENUM('held','listed','partially_sold','sold') NOT NULL DEFAULT 'held',
    created_at             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_pos_product (product_id),
    KEY idx_pos_status (status),
    CONSTRAINT fk_pos_product FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE RESTRICT,
    CONSTRAINT fk_pos_lot FOREIGN KEY (lot_id) REFERENCES lots (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------- 10. transactions --------------------
CREATE TABLE transactions (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    tx_type         ENUM('buy','sell','fee','adjustment') NOT NULL,
    product_id      BIGINT UNSIGNED NULL,
    position_id     BIGINT UNSIGNED NULL,
    lot_id          BIGINT UNSIGNED NULL,
    quantity        INT UNSIGNED NOT NULL DEFAULT 1,
    gross_amount    DECIMAL(12,2) NOT NULL,
    platform_fees   DECIMAL(12,2) NOT NULL DEFAULT 0,
    shipping_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    net_amount      DECIMAL(12,2) NOT NULL,
    cost_basis      DECIMAL(12,2) NULL,                       -- S7 : COGS, profit auditable
    currency        CHAR(3)      NOT NULL DEFAULT 'EUR',
    platform        ENUM('vinted','leboncoin','ebay','cardmarket','other') NULL,
    occurred_at     DATETIME     NOT NULL,
    notes           TEXT         NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_tx_type_time (tx_type, occurred_at),
    KEY idx_tx_product (product_id),
    CONSTRAINT fk_tx_product  FOREIGN KEY (product_id)  REFERENCES products (id)  ON DELETE SET NULL,
    CONSTRAINT fk_tx_position FOREIGN KEY (position_id) REFERENCES positions (id) ON DELETE SET NULL,
    CONSTRAINT fk_tx_lot      FOREIGN KEY (lot_id)      REFERENCES lots (id)      ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------- 11. account_snapshots ---------------
CREATE TABLE account_snapshots (
    id                     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    snapshot_date          DATE          NOT NULL,
    total_portfolio_value  DECIMAL(12,2) NOT NULL,
    capital_invested       DECIMAL(12,2) NOT NULL,
    cash_available         DECIMAL(12,2) NOT NULL,       -- = cash_total
    cash_locked            DECIMAL(12,2) NOT NULL DEFAULT 0,  -- S7
    cash_active            DECIMAL(12,2) NULL,               -- S7
    realized_profit_net    DECIMAL(12,2) NOT NULL,
    capital_rotation_rate  DECIMAL(8,4)  NULL,
    turnover_cumulative    DECIMAL(12,2) NOT NULL DEFAULT 0,  -- S7 (CA)
    current_tier_id        BIGINT UNSIGNED NULL,
    tax_provision          DECIMAL(12,2) NULL,
    created_at             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_snapshot_date (snapshot_date),
    CONSTRAINT fk_snap_tier FOREIGN KEY (current_tier_id) REFERENCES tiers_config (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------- 12. psa_certs ------------------------
CREATE TABLE psa_certs (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    cert_number  VARCHAR(32)  NOT NULL,
    product_id   BIGINT UNSIGNED NULL,
    grade        VARCHAR(8)   NULL,
    grade_label  VARCHAR(64)  NULL,
    is_valid     TINYINT(1)   NULL,
    pop_data     JSON         NULL,
    raw_response JSON         NULL,
    verified_at  DATETIME     NULL,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_cert_number (cert_number),
    CONSTRAINT fk_cert_product FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------- 13. grading_opportunities -----------
CREATE TABLE grading_opportunities (
    id                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    product_id            BIGINT UNSIGNED NOT NULL,
    raw_value             DECIMAL(12,2) NULL,
    psa9_value            DECIMAL(12,2) NULL,
    psa10_value           DECIMAL(12,2) NULL,
    grading_cost          DECIMAL(12,2) NULL,
    premium_psa9_pct      DECIMAL(8,2)  NULL,
    premium_psa10_pct     DECIMAL(8,2)  NULL,
    expected_net_psa10    DECIMAL(12,2) NULL,             -- scénario optimiste
    grade_probability     JSON          NULL,             -- S8 : {"10":..,"9":..,"le8":..}
    expected_net_weighted DECIMAL(12,2) NULL,             -- S8 : espérance pondérée
    is_recommended        TINYINT(1)   NOT NULL DEFAULT 0,
    computed_at           DATETIME     NOT NULL,
    created_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_grad_product (product_id),
    KEY idx_grad_reco (is_recommended),
    CONSTRAINT fk_grad_product FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------- 14. alerts ---------------------------
CREATE TABLE alerts (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    alert_type          ENUM('buy','sell_x2','sell_25_50_25','sell_forced','sell_reminder',
                             'cash_min','anti_pump','anti_fomo','illiquid','grading','reinvest',
                             'tax_provision','palier_up','palier_down','auction_reminder',
                             'lot_summary','tech_error') NOT NULL,
    severity            ENUM('info','warning','critical') NOT NULL DEFAULT 'info',
    product_id          BIGINT UNSIGNED NULL,
    sourcing_listing_id BIGINT UNSIGNED NULL,
    position_id         BIGINT UNSIGNED NULL,
    title               VARCHAR(255) NOT NULL,
    payload             JSON         NULL,
    status              ENUM('pending','sent','acknowledged','dismissed') NOT NULL DEFAULT 'pending',
    sent_to_discord_at  DATETIME     NULL,
    created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_alert_status (status),
    KEY idx_alert_type_time (alert_type, created_at),
    CONSTRAINT fk_alert_product  FOREIGN KEY (product_id)          REFERENCES products (id)          ON DELETE SET NULL,
    CONSTRAINT fk_alert_listing  FOREIGN KEY (sourcing_listing_id) REFERENCES sourcing_listings (id) ON DELETE SET NULL,
    CONSTRAINT fk_alert_position FOREIGN KEY (position_id)         REFERENCES positions (id)         ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
--  SEED — Paliers
-- =====================================================================
INSERT INTO tiers_config
    (tier_number, name, capital_min, capital_max, alloc_stock_pct, alloc_cash_pct, cash_min_pct, strategy_mix, description)
VALUES
    (1, 'Étape 1 — Arbitrage pur',  150.00,  300.00, 66.67, 33.33, 10.00, JSON_OBJECT('arbitrage',100,'sealed',0,'graded',0), 'Flux tendu, arbitrage pur. Pas de grading, très peu de scellé.'),
    (2, 'Étape 2 — Arbitrage + PE', 300.00, 1000.00, NULL,  NULL,  10.00, NULL, 'Arbitrage continu + premiers stocks Prismatic Evolutions.'),
    (3, 'Étape 3 — Diversification',1000.00,2500.00, NULL,  NULL,   5.00, JSON_OBJECT('arbitrage',60,'sealed',40), 'Portefeuille diversifié, 60% arbitrage / 40% scellé.'),
    (4, 'Étape 4 — Institutionnel', 2500.00,5000.00, NULL,  NULL,   5.00, NULL, 'PE, Pokémon 151, Displays JP, cartes gradées PSA.');

-- =====================================================================
--  SEED — Registre complet des paramètres (settings)
-- =====================================================================
INSERT INTO settings (setting_key, setting_value, value_type, description) VALUES
-- S2 — Paliers & cash
('tier_basis','operational_capital_at_cost','string','Base de calcul palier = cash_active + capital_invested(coût)'),
('cash_min_basis','operational_capital_at_cost','string','Base du seuil de cash minimum'),
('tier_promote_requires_confirm','true','bool','Montée de palier nécessite confirmation Discord'),
('tier_demote_auto','true','bool','Descente de palier appliquée automatiquement'),
('tier_sustain_snapshots','3','int','Nb de snapshots consécutifs avant transition'),
('tier_hysteresis_pct','10','decimal','Hystérésis de rétrogradation (% sous capital_min)'),
('cash_min_below_150_pct','15','decimal','Garde-fou cash si capital < 150€'),
-- S3 — Achat & valorisation
('fifty_rule_threshold_pct','50','decimal','Règle des 50% : coût <= X% de la revente nette'),
('valuation_net_of_fees','true','bool','Valorisation nette des commissions'),
('fee_rate_cardmarket','5.0','decimal','Commission Cardmarket % (À VÉRIFIER)'),
('fee_rate_ebay','12.0','decimal','Commission eBay % (À VÉRIFIER)'),
('fee_rate_vinted','0.0','decimal','Commission Vinted vendeur % (À VÉRIFIER)'),
('default_sell_platform','cardmarket','string','Plateforme de revente par défaut'),
('bulk_value_per_card','0.05','decimal','Tarif plancher vrac (€/carte)'),
('min_match_confidence','0.70','decimal','Confiance min pour compter une carte comme identifiée'),
('lot_confidence_haircut','0.85','decimal','Haircut prudentiel sur la valeur de lot estimée'),
('ir_min_discount_pct','30','decimal','Plancher absolu de décote pour les IR (garde-fou)'),
('ir_lot_value_share','50','decimal','% de valeur IR pour classer un lot comme "lot IR"'),
('trinity_target_hours','48','int','Délai de revente visé Trinité S++'),
('w_margin','0.5','decimal','Poids marge dans opportunity_score'),
('w_liquidity','0.3','decimal','Poids liquidité dans opportunity_score'),
('w_tier','0.2','decimal','Poids tier dans opportunity_score'),
('pe_singles_rise_pct','15','decimal','Seuil de hausse des singles PE (avg_7d vs avg_30d)'),
('pe_signal_min_triggers','2','int','Nb de signaux PE concordants pour alerter'),
('pe_reprint_ended','false','bool','MANUEL : fin des réimpressions PE'),
('pe_stock_declining','false','bool','MANUEL/proxy : baisse des stocks PE'),
-- S4 — Filtres
('pump_rise_pct','40','decimal','Hausse déclenchant le blocage anti-pump'),
('pump_correction_pct','10','decimal','Tolérance de correction pour lever l''anti-pump'),
('pump_lookback_days','30','int','Fenêtre du plus-haut récent (anti-pump)'),
('min_sale_count','5','int','Volume minimal de ventes (illiquidité)'),
('illiquid_approx_multiplier','2','int','Exigence de volume x si sale_count approximatif'),
('fomo_freeze','false','bool','Disjoncteur anti-FOMO : gèle les recommandations'),
('fomo_freeze_reason','','string','Raison du gel FOMO'),
('fomo_freeze_until','','string','Fin du gel FOMO (ISO 8601)'),
('fomo_scope','global','string','Portée du gel : global | set'),
('fomo_trends_enabled','false','bool','Proxy Google Trends (signal faible)'),
('fomo_trends_spike_pct','100','decimal','Seuil de pic Trends'),
('default_profit_target','1.5','decimal','×coût pour le rappel de discipline si pas de cible'),
-- S5 — Vente
('double_multiple','2.0','decimal','Multiple déclenchant la règle du Double'),
('explosion_multiple','3.0','decimal','Multiple déclenchant le 25/50/25'),
('parabolic_multiple','4.0','decimal','Multiple déclenchant la vente forcée (+300%)'),
('partial_sell_pct','25','decimal','25/50/25 : part vendue'),
('hold_pct','50','decimal','25/50/25 : part conservée'),
('speculative_reserve_pct','25','decimal','25/50/25 : part spéculative réservée'),
('forced_sell_pct','50','decimal','Part vendue en dérisquage forcé'),
('structured_base','residual','string','Base du 25/50/25 : residual | original'),
('parabolic_threshold_pct','300','decimal','Hausse parabolique (référence, = ×4)'),
('speculation_volume_spike_pct','200','decimal','Pic de volume = signal de spéculation'),
('speculation_flag','false','bool','MANUEL : afflux spéculatif détecté'),
('auction_end_day','sunday','string','Jour de fin d''enchère eBay'),
('auction_end_time','21:00','string','Heure de fin d''enchère eBay'),
('timezone','Europe/Paris','string','Fuseau horaire de référence'),
-- S6 — Liquidation
('individual_threshold','5.00','decimal','> X€ → vente individuelle'),
('individual_ebay_threshold','50.00','decimal','>= X€ → eBay sinon Cardmarket'),
('graded_route','ebay','string','Routage des slabs gradés'),
('bulk_lot_target_size','75','int','Taille cible d''un lot vrac'),
('bulk_lot_min_size','50','int','Taille min d''un lot vrac'),
('bulk_lot_max_size','100','int','Taille max d''un lot vrac'),
('bulk_theme_strategy','set','string','Regroupement vrac : set | type | era | mixed'),
('bulk_min_theme_for_dedicated_lot','50','int','Seuil pour un lot thématique dédié'),
('bulk_lot_price_per_card','0.10','decimal','Prix suggéré vrac (€/carte)'),
('intake_prefill_from_detection','true','bool','Pré-remplir l''intake depuis la détection'),
('sourcing_retention_days','90','int','Purge des annonces dismissed/expired après N jours'),
-- S7 — Comptabilité
('reinvest_lock_pct','30','decimal','Verrouillage des bénéfices nets'),
('reinvest_active_pct','70','decimal','Réinjection dans le capital actif'),
('lock_only_positive_profit','true','bool','Ne verrouiller que les bénéfices positifs'),
('tax_provision_pct','12.3','decimal','Provision fiscale micro-entrepreneur (À VÉRIFIER URSSAF)'),
('tax_provision_mode','informative','string','informative | reserved'),
('rotation_basis','cogs','string','Base rotation : cogs | proceeds'),
('rotation_period','monthly','string','Période de rotation'),
('kpi_snapshot_time','23:55','string','Heure du snapshot KPI quotidien'),
-- S8 — Grading
('grading_psa_fee_eur','80','decimal','Frais PSA palier ouvert (À VÉRIFIER)'),
('grading_logistics_eur','40','decimal','Envoi A/R assuré + douane FR↔US (À VÉRIFIER)'),
('grading_min_card_value','100','decimal','Valeur brute plancher pour envisager le grading'),
('grading_min_uplift_eur','50','decimal','Uplift minimal en euros'),
('grading_min_uplift_pct','50','decimal','Uplift minimal en %'),
('grade_prob_source','pop_report','string','pop_report | default'),
('grade_prob_default','{"10":0.30,"9":0.45,"le8":0.25}','json','Probabilités de grade par défaut'),
('grading_scan_cadence','weekly','string','Cadence du scan grading'),
-- S9 — Notifications
('notify_mode','balanced','string','calm | balanced | all'),
('quiet_hours','23:00-08:00','string','Heures calmes (diffère le non-critique)'),
('digest_time','09:00','string','Heure du digest quotidien'),
('alert_cooldown_min','60','int','Cooldown par (type, cible)'),
-- S10 — Dashboard & modes data
('dashboard_poll_interval_sec','30','int','Polling du dashboard'),
('chart_history_days','90','int','Profondeur des graphiques'),
('display_currency','auto','string','auto | EUR | USD'),
('dashboard_scope','full','string','Périmètre dashboard'),
('poketrace_plan','free','string','free | pro (bascule au lancement réel)'),
('valuation_market','US','string','US (prototype) | EU (réel)'),
('valuation_condition','NEAR_MINT','string','Condition de valorisation'),
('feature_grading_enabled','false','bool','Module grading actif (Pro uniquement)'),
('feature_history_full','false','bool','Historique quotidien complet (Pro)'),
-- J2 — Ingestion & garde-quota PokeTrace
('price_cache_ttl_min','360','int','Ne pas re-requêter un prix plus jeune que N minutes'),
('poketrace_daily_limit','250','int','Quota requêtes/jour PokeTrace (Free 250, Pro 10000)'),
('poketrace_min_interval_ms','2000','int','Intervalle min entre requêtes (burst Free 1 req/2s, 333 en Pro)'),
('valuation_marketplace','tcgplayer','string','Marketplace de valorisation : tcgplayer|ebay (US) | cardmarket (EU)'),
-- J3 — Moteur d''achat
('fx_usd_eur','0.92','decimal','Conversion proxy US→EUR en mode prototype ; ignoré en mode EU'),
-- J4 — Dispatcher Discord
('dispatcher_poll_sec','20','int','Période de la boucle d''envoi des alertes (secondes)'),
-- J6 — Scraping / sourcing
('scrape_max_listings_per_run','40','int','Plafond d''annonces traitées par run de scraping'),
('scrape_blocked_cooldown_min','120','int','Cooldown max (min) après blocage plateforme (backoff)'),
('selector_break_threshold','30','int','% de cartes sans champ obligatoire = structure cassée'),
('saved_queries','["lot cartes pokemon","display prismatic evolutions"]','json','Requêtes de sourcing sauvegardées'),
-- J9 — Durcissement / observabilité / rétention
('job_heartbeat_max_age_min','720','int','Âge max (min) d''un job critique avant dead-man''s switch'),
('price_snapshot_detail_days','60','int','Fenêtre détaillée des price_snapshots (au-delà : 1/jour/tier)'),
('price_snapshot_pruning_enabled','false','bool','Active l''élagage intraday des price_snapshots'),
('log_redact_secrets','true','bool','Masque les secrets dans les logs');
