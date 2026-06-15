-- ============================================================
-- DATA HIGHWAY PROTOTYPE — SAP HANA Cloud Table Definitions
-- ============================================================
-- Run this in HANA Database Explorer (SQL Console)
-- These tables map to all 6 data source boxes in the architecture
-- ============================================================

-- Create a dedicated schema
CREATE SCHEMA DATA_HIGHWAY;
SET SCHEMA DATA_HIGHWAY;

-- ============================================================
-- TABLE 1: PI_SENSOR_READINGS
-- Source: OSI Pi via AVEVA Adapter → Event Hubs → Azure Function
-- This is the STREAMING table — real-time inserts from the pipeline
-- ============================================================
CREATE COLUMN TABLE PI_SENSOR_READINGS (
    ID              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    TIMESTAMP_UTC   TIMESTAMP NOT NULL,
    TAG_NAME        NVARCHAR(100) NOT NULL,
    ASSET_ID        NVARCHAR(20) NOT NULL,
    VALUE           DOUBLE NOT NULL,
    UNIT            NVARCHAR(20),
    QUALITY         NVARCHAR(50) DEFAULT 'Good',
    INGESTED_AT     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for real-time queries by asset
CREATE INDEX IDX_PI_ASSET_TS ON PI_SENSOR_READINGS (ASSET_ID, TIMESTAMP_UTC DESC);
-- Index for tag-level queries
CREATE INDEX IDX_PI_TAG_TS ON PI_SENSOR_READINGS (TAG_NAME, TIMESTAMP_UTC DESC);


-- ============================================================
-- TABLE 2: PI_LOAD_READINGS
-- Source: Supplemental load % sensor data
-- Same structure as PI_SENSOR_READINGS for consistency
-- ============================================================
CREATE COLUMN TABLE PI_LOAD_READINGS (
    ID              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    TIMESTAMP_UTC   TIMESTAMP NOT NULL,
    TAG_NAME        NVARCHAR(100) NOT NULL,
    ASSET_ID        NVARCHAR(20) NOT NULL,
    VALUE           DOUBLE NOT NULL,
    UNIT            NVARCHAR(20),
    QUALITY         NVARCHAR(50) DEFAULT 'Good',
    INGESTED_AT     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IDX_LOAD_ASSET_TS ON PI_LOAD_READINGS (ASSET_ID, TIMESTAMP_UTC DESC);


-- ============================================================
-- TABLE 3: EQUIPMENT_MASTER
-- Source: SAP S/4HANA RISE → Integration Suite iFlow
-- The ASSET_MASTER_DIM from the architecture
-- ============================================================
CREATE COLUMN TABLE EQUIPMENT_MASTER (
    EQUIPMENT_NUMBER    NVARCHAR(20) PRIMARY KEY,
    DESCRIPTION         NVARCHAR(200),
    EQUIPMENT_TYPE      NVARCHAR(100),
    FUNCTIONAL_LOCATION NVARCHAR(100),
    PLANT               NVARCHAR(10),
    PLANNING_PLANT      NVARCHAR(10),
    COST_CENTER         NVARCHAR(50),
    MANUFACTURER        NVARCHAR(100),
    MODEL_NUMBER        NVARCHAR(50),
    SERIAL_NUMBER       NVARCHAR(50),
    INSTALLATION_DATE   DATE,
    AGE_YEARS           INTEGER,
    LIFECYCLE_STAGE     NVARCHAR(30),
    CRITICALITY         NVARCHAR(20),
    ABC_INDICATOR       NVARCHAR(5),
    WARRANTY_END_DATE   DATE,
    WEIGHT_KG           INTEGER,
    STATUS              NVARCHAR(10),
    LOADED_AT           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- TABLE 4: MAINTENANCE_WORK_ORDERS
-- Source: SAP S/4HANA RISE PM Module → OData V4
-- Maps to ASSET_MAINTENANCE_SUMMARY in the architecture
-- ============================================================
CREATE COLUMN TABLE MAINTENANCE_WORK_ORDERS (
    WORK_ORDER          NVARCHAR(20) PRIMARY KEY,
    EQUIPMENT_NUMBER    NVARCHAR(20),
    ORDER_TYPE          NVARCHAR(10),
    ORDER_TYPE_DESC     NVARCHAR(100),
    ACTIVITY_TYPE       NVARCHAR(50),
    PRIORITY            NVARCHAR(30),
    STATUS              NVARCHAR(10),
    SHORT_TEXT          NVARCHAR(500),
    CREATED_DATE        DATE,
    SCHEDULED_START     DATE,
    ACTUAL_START        NVARCHAR(30),
    ACTUAL_FINISH       NVARCHAR(30),
    DOWNTIME_HOURS      DOUBLE,
    TOTAL_COST_USD      DOUBLE,
    FUNCTIONAL_LOCATION NVARCHAR(100),
    PLANNER_GROUP       NVARCHAR(20),
    WORK_CENTER         NVARCHAR(20),
    LOADED_AT           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IDX_WO_EQUIP ON MAINTENANCE_WORK_ORDERS (EQUIPMENT_NUMBER);
CREATE INDEX IDX_WO_DATE ON MAINTENANCE_WORK_ORDERS (CREATED_DATE DESC);


-- ============================================================
-- TABLE 5: FAILURE_HISTORY
-- Source: SAP EAM / PM — Root cause analysis log
-- 3-year lookback for AI pattern recognition
-- ============================================================
CREATE COLUMN TABLE FAILURE_HISTORY (
    FAILURE_ID              NVARCHAR(20) PRIMARY KEY,
    EQUIPMENT_NUMBER        NVARCHAR(20),
    EQUIPMENT_NAME          NVARCHAR(200),
    EQUIPMENT_TYPE          NVARCHAR(100),
    FAILURE_DATE            DATE,
    FAILURE_MODE            NVARCHAR(200),
    FAILED_COMPONENT        NVARCHAR(100),
    ROOT_CAUSE              NVARCHAR(500),
    CORRECTIVE_ACTION       NVARCHAR(500),
    SEVERITY                NVARCHAR(20),
    DETECTION_METHOD        NVARCHAR(100),
    DETECTION_TO_FAILURE_HRS DOUBLE,
    TIME_TO_REPAIR_HRS      DOUBLE,
    TOTAL_DOWNTIME_HRS      DOUBLE,
    PRODUCTION_LOSS_BBL     DOUBLE,
    REPAIR_COST_USD         DOUBLE,
    WAS_PREDICTABLE         NVARCHAR(20),
    LINKED_WORK_ORDER       NVARCHAR(20),
    LOADED_AT               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IDX_FAIL_EQUIP ON FAILURE_HISTORY (EQUIPMENT_NUMBER);
CREATE INDEX IDX_FAIL_DATE ON FAILURE_HISTORY (FAILURE_DATE DESC);
CREATE INDEX IDX_FAIL_MODE ON FAILURE_HISTORY (FAILURE_MODE);


-- ============================================================
-- TABLE 6: COMPLIANCE_INSPECTIONS
-- Source: Compliance DB — Regulatory inspection logs
-- ============================================================
CREATE COLUMN TABLE COMPLIANCE_INSPECTIONS (
    INSPECTION_ID               NVARCHAR(20) PRIMARY KEY,
    EQUIPMENT_NUMBER            NVARCHAR(20),
    EQUIPMENT_NAME              NVARCHAR(200),
    REGULATORY_STANDARD         NVARCHAR(50),
    INSPECTION_TYPE             NVARCHAR(200),
    INSPECTION_DATE             DATE,
    NEXT_DUE_DATE               DATE,
    INSPECTOR                   NVARCHAR(200),
    INSPECTION_COMPANY          NVARCHAR(100),
    RESULT                      NVARCHAR(50),
    FINDING                     NVARCHAR(500),
    CORRECTIVE_ACTION_REQUIRED  NVARCHAR(5),
    CORRECTIVE_ACTION_DUE_DATE  NVARCHAR(20),
    CORRECTIVE_ACTION_STATUS    NVARCHAR(20),
    RISK_RANKING                NVARCHAR(20),
    FUNCTIONAL_LOCATION         NVARCHAR(100),
    LOADED_AT                   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IDX_INSP_EQUIP ON COMPLIANCE_INSPECTIONS (EQUIPMENT_NUMBER);
CREATE INDEX IDX_INSP_DUE ON COMPLIANCE_INSPECTIONS (NEXT_DUE_DATE);


-- ============================================================
-- TABLE 7: COMPLIANCE_CERTIFICATES
-- Source: Compliance DB — Equipment certifications
-- ============================================================
CREATE COLUMN TABLE COMPLIANCE_CERTIFICATES (
    CERTIFICATE_ID          NVARCHAR(20) PRIMARY KEY,
    EQUIPMENT_NUMBER        NVARCHAR(20),
    EQUIPMENT_NAME          NVARCHAR(200),
    CERTIFICATION_STANDARD  NVARCHAR(50),
    CERTIFICATE_DESCRIPTION NVARCHAR(200),
    ISSUING_BODY            NVARCHAR(100),
    CERTIFICATE_NUMBER      NVARCHAR(100),
    ISSUE_DATE              DATE,
    EXPIRY_DATE             DATE,
    DAYS_TO_EXPIRY          INTEGER,
    STATUS                  NVARCHAR(30),
    RENEWAL_REQUIRED        NVARCHAR(5),
    DOCUMENT_REF            NVARCHAR(50),
    LOADED_AT               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IDX_CERT_EQUIP ON COMPLIANCE_CERTIFICATES (EQUIPMENT_NUMBER);
CREATE INDEX IDX_CERT_EXPIRY ON COMPLIANCE_CERTIFICATES (EXPIRY_DATE);


-- ============================================================
-- TABLE 8: OEM_MAINTENANCE_SPECS
-- Source: External — OEM recommended maintenance intervals
-- ============================================================
CREATE COLUMN TABLE OEM_MAINTENANCE_SPECS (
    SPEC_ID                 NVARCHAR(20) PRIMARY KEY,
    EQUIPMENT_NUMBER        NVARCHAR(20),
    EQUIPMENT_NAME          NVARCHAR(200),
    EQUIPMENT_TYPE          NVARCHAR(100),
    MANUFACTURER            NVARCHAR(100),
    TASK_NAME               NVARCHAR(200),
    FREQUENCY               NVARCHAR(30),
    INTERVAL_DAYS           INTEGER,
    ESTIMATED_DURATION_HRS  DOUBLE,
    LAST_PERFORMED_DATE     DATE,
    NEXT_DUE_DATE           DATE,
    OVERDUE                 NVARCHAR(5),
    OEM_NOTES               NVARCHAR(500),
    SKILL_REQUIRED          NVARCHAR(50),
    REQUIRES_SHUTDOWN       NVARCHAR(5),
    OEM_MANUAL_REF          NVARCHAR(50),
    LOADED_AT               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IDX_OEM_EQUIP ON OEM_MAINTENANCE_SPECS (EQUIPMENT_NUMBER);
CREATE INDEX IDX_OEM_DUE ON OEM_MAINTENANCE_SPECS (NEXT_DUE_DATE);


-- ============================================================
-- TABLE 9: WARRANTY_RECORDS
-- Source: External — Warranty coverage and claims
-- ============================================================
CREATE COLUMN TABLE WARRANTY_RECORDS (
    WARRANTY_ID             NVARCHAR(20) PRIMARY KEY,
    EQUIPMENT_NUMBER        NVARCHAR(20),
    EQUIPMENT_NAME          NVARCHAR(200),
    EQUIPMENT_TYPE          NVARCHAR(100),
    MANUFACTURER            NVARCHAR(100),
    PURCHASE_DATE           DATE,
    INSTALLATION_DATE       DATE,
    STANDARD_WARRANTY_START DATE,
    STANDARD_WARRANTY_END   DATE,
    EXTENDED_WARRANTY       NVARCHAR(5),
    EXTENDED_WARRANTY_END   NVARCHAR(20),
    WARRANTY_STATUS         NVARCHAR(20),
    COVERAGE_TYPE           NVARCHAR(50),
    EXCLUSIONS              NVARCHAR(500),
    WARRANTY_PROVIDER       NVARCHAR(200),
    TOTAL_CLAIMS_FILED      INTEGER,
    TOTAL_CLAIMS_VALUE_USD  DOUBLE,
    CONTRACT_REF            NVARCHAR(30),
    LOADED_AT               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IDX_WARR_EQUIP ON WARRANTY_RECORDS (EQUIPMENT_NUMBER);


-- ============================================================
-- TABLE 10: OEM_BULLETINS
-- Source: External — Manufacturer service bulletins
-- ============================================================
CREATE COLUMN TABLE OEM_BULLETINS (
    ID                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    BULLETIN_ID             NVARCHAR(20),
    EQUIPMENT_NUMBER        NVARCHAR(20),
    EQUIPMENT_NAME          NVARCHAR(200),
    MANUFACTURER            NVARCHAR(100),
    TITLE                   NVARCHAR(500),
    SEVERITY                NVARCHAR(30),
    SUMMARY                 NVARCHAR(1000),
    ACTION_REQUIRED         NVARCHAR(1000),
    ISSUE_DATE              DATE,
    COMPLIANCE_DEADLINE     NVARCHAR(20),
    COMPLIANCE_STATUS       NVARCHAR(30),
    LOADED_AT               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IDX_BULL_EQUIP ON OEM_BULLETINS (EQUIPMENT_NUMBER);


-- ============================================================
-- TABLE 11: SPARE_PARTS_CATALOG
-- Source: External — Critical spare parts inventory
-- ============================================================
CREATE COLUMN TABLE SPARE_PARTS_CATALOG (
    SPARE_ID                    NVARCHAR(20) PRIMARY KEY,
    EQUIPMENT_NUMBER            NVARCHAR(20),
    EQUIPMENT_NAME              NVARCHAR(200),
    PART_NAME                   NVARCHAR(200),
    PART_NUMBER                 NVARCHAR(50),
    MANUFACTURER_PART_NUMBER    NVARCHAR(50),
    UNIT_COST_USD               DOUBLE,
    QUANTITY_ON_HAND            INTEGER,
    MINIMUM_STOCK_QTY           INTEGER,
    REORDER_REQUIRED            NVARCHAR(5),
    LEAD_TIME_WEEKS             INTEGER,
    STORAGE_LOCATION            NVARCHAR(20),
    LAST_USED_DATE              DATE,
    CRITICALITY                 NVARCHAR(20),
    NOTES                       NVARCHAR(500),
    LOADED_AT                   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IDX_SPARE_EQUIP ON SPARE_PARTS_CATALOG (EQUIPMENT_NUMBER);


-- ============================================================
-- TABLE 12: ASSET_REALTIME_FEATURES (Computed)
-- This is the AI-ready feature table — populated by Stream Analytics
-- or by the batch feature computation script for the prototype
-- ============================================================
CREATE COLUMN TABLE ASSET_REALTIME_FEATURES (
    ASSET_ID            NVARCHAR(20) NOT NULL,
    COMPUTED_AT         TIMESTAMP NOT NULL,
    -- Sensor aggregates (5-min window)
    TEMPERATURE_C       DOUBLE,
    VIBRATION_MMS       DOUBLE,
    PRESSURE_BAR        DOUBLE,
    FLOW_RATE           DOUBLE,
    LOAD_PCT            DOUBLE,
    -- Maintenance context
    OPEN_WO_COUNT       INTEGER,
    LAST_FAILURE_DAYS_AGO INTEGER,
    MTBF_DAYS           DOUBLE,
    -- Asset metadata
    LIFECYCLE_STAGE     NVARCHAR(30),
    AGE_YEARS           INTEGER,
    CRITICALITY         NVARCHAR(20),
    -- Computed health inputs
    SENSOR_ANOMALY_SCORE DOUBLE,
    FAILURE_HISTORY_INDEX DOUBLE,
    LIFECYCLE_FACTOR    DOUBLE,
    -- Output
    HEALTH_SCORE        DOUBLE,
    HEALTH_STATUS       NVARCHAR(20),
    PRIMARY KEY (ASSET_ID, COMPUTED_AT)
);

CREATE INDEX IDX_RT_ASSET ON ASSET_REALTIME_FEATURES (ASSET_ID, COMPUTED_AT DESC);


-- ============================================================
-- VERIFICATION: List all tables
-- ============================================================
SELECT TABLE_NAME, RECORD_COUNT 
FROM M_TABLES 
WHERE SCHEMA_NAME = 'DATA_HIGHWAY' 
ORDER BY TABLE_NAME;
