-- ============================================================================
-- Asset Intelligence - Bridge schema additions
-- Run as DBADMIN in HANA Database Explorer (one time), then grant to APP_USER.
--
-- These three tables close the gap between the data loaded in Phase 2a and the
-- metrics the BluWis dashboard renders:
--   1. ASSET_THRESHOLDS  - per asset+tag safe/warn/crit bands (filled by the
--                          smart algorithm in derive_thresholds.py)
--   2. ASSET_FINANCIALS  - the 6 fields the schema lacked (design life, PM
--                          frequency, 3 cost fields, consequence) - filled with
--                          realistic demo values by generate_demo_fields.py
--   3. ASSET_HEALTH_SCORES - the computed output the dashboard reads from
--                          (filled by compute_health_scores.py, every 5 min)
-- ============================================================================

-- 1. THRESHOLDS ---------------------------------------------------------------
CREATE TABLE "ASSET_MASTER"."ASSET_THRESHOLDS" (
    ASSET_ID    NVARCHAR(20)  NOT NULL,
    TAG_NAME    NVARCHAR(50)  NOT NULL,   -- TEMPERATURE | VIBRATION | PRESSURE
    SAFE_LO     DECIMAL(12,4),
    SAFE_HI     DECIMAL(12,4),
    WARN_LO     DECIMAL(12,4),            -- == SAFE_HI by construction
    WARN_HI     DECIMAL(12,4),            -- == CRIT    by construction
    CRIT        DECIMAL(12,4),
    UNIT        NVARCHAR(10),
    METHOD      NVARCHAR(40),             -- which algorithm layers shaped it
    CONFIDENCE  NVARCHAR(10),             -- HIGH | MEDIUM | LOW
    DERIVED_AT  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ASSET_ID, TAG_NAME)
);

-- 2. FINANCIALS / LIFECYCLE (the 6 previously-missing fields) -----------------
CREATE TABLE "ASSET_MASTER"."ASSET_FINANCIALS" (
    ASSET_ID              NVARCHAR(20) NOT NULL PRIMARY KEY,
    DESIGN_LIFE_YRS       INTEGER,        -- RUL denominator + age sub-score
    PM_FREQ_DAYS          INTEGER,        -- maintenance sub-score
    REPLACEMENT_COST      DECIMAL(15,2),  -- cost-at-risk
    DOWNTIME_COST_PER_DAY DECIMAL(15,2),  -- annual downtime risk
    ANNUAL_PM_COST        DECIMAL(15,2),  -- maintenance ROI
    CONSEQUENCE           INTEGER,        -- 1..5, risk-matrix consequence axis
    LIFECYCLE_STAGE       INTEGER,        -- 0..5 stepper (derived from age %)
    DATA_SOURCE           NVARCHAR(20) DEFAULT 'DEMO',  -- DEMO | SAP_CO | SAP_AM
    GENERATED_AT          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. HEALTH SCORE OUTPUT (what the dashboard reads) ---------------------------
CREATE TABLE "ASSET_MASTER"."ASSET_HEALTH_SCORES" (
    ASSET_ID            NVARCHAR(20) NOT NULL PRIMARY KEY,
    HEALTH_SCORE        INTEGER,         -- 0..100 (the gauge)
    SENSOR_SCORE        DECIMAL(6,2),    -- 40% component
    MAINT_SCORE         DECIMAL(6,2),    -- 25% component
    FAILURE_SCORE       DECIMAL(6,2),    -- 20% component
    AGE_SCORE           DECIMAL(6,2),    -- 15% component
    FAILURE_PROB        DECIMAL(6,4),    -- 0..1
    RUL_DAYS            INTEGER,
    STATUS              NVARCHAR(20),    -- Healthy|Monitored|At Risk|Critical
    LATEST_TEMP         DECIMAL(12,4),
    LATEST_VIB          DECIMAL(12,4),
    LATEST_PRES         DECIMAL(12,4),
    SCORE_ENGINE        NVARCHAR(20),    -- FORMULA | AICORE_ML  (formula now)
    COMPUTED_AT         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Grants so the CAP technical user can read/write -----------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON "ASSET_MASTER"."ASSET_THRESHOLDS"   TO APP_USER;
GRANT SELECT, INSERT, UPDATE, DELETE ON "ASSET_MASTER"."ASSET_FINANCIALS"   TO APP_USER;
GRANT SELECT, INSERT, UPDATE, DELETE ON "ASSET_MASTER"."ASSET_HEALTH_SCORES" TO APP_USER;
