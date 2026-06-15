namespace asset.intel;

entity Assets {
  key ASSET_ID            : String(20);
      ASSET_NAME          : String(200);
      ASSET_TYPE          : String(60);
      MANUFACTURER        : String(60);
      MODEL               : String(60);
      SERIAL_NUMBER       : String(40);
      INSTALL_DATE        : Date;
      LAST_OVERHAUL_DATE  : Date;
      EXPECTED_LIFE_YEARS : Integer;
      CRITICALITY         : String(2);
      LOCATION            : String(80);
      STATUS              : String(20);
      OPERATING_HOURS     : Integer;
}
entity SensorReadings {
  key READING_ID  : Integer64;
      ASSET_ID    : String(20);
      TAG_NAME    : String(40);
      TAG_VALUE   : Decimal(18,4);
      UOM         : String(20);
      READING_TS  : Timestamp;
      QUALITY     : String(15);
}
entity WorkOrders {
  key WO_ID           : String(20);
      ASSET_ID        : String(20);
      WO_TYPE         : String(10);
      PRIORITY        : Integer;
      STATUS          : String(20);
      DESCRIPTION     : String(500);
      CREATED_DATE    : Date;
      DUE_DATE        : Date;
      COMPLETION_DATE : Date;
      LABOR_HOURS     : Decimal(8,2);
      COST            : Decimal(14,2);
      TECHNICIAN      : String(60);
}
entity FailureHistory {
  key FAILURE_ID       : String(20);
      ASSET_ID         : String(20);
      FAILURE_DATE     : Date;
      FAILURE_CODE     : String(40);
      FAILURE_MODE     : String(100);
      ROOT_CAUSE       : LargeString;
      DOWNTIME_HOURS   : Decimal(8,2);
      REPAIR_COST      : Decimal(14,2);
      DETECTED_BY      : String(40);
      RESOLUTION_NOTES : LargeString;
}
entity ProcessTrends {
  key TREND_ID     : Integer64;
      ASSET_ID     : String(20);
      PARAMETER    : String(40);
      UOM          : String(20);
      TREND_DATE   : Date;
      AVG_VALUE    : Decimal(18,4);
      MIN_VALUE    : Decimal(18,4);
      MAX_VALUE    : Decimal(18,4);
      STDDEV_VALUE : Decimal(18,4);
}
entity ComplianceDocs {
  key DOC_ID            : String(20);
      ASSET_ID          : String(20);
      DOC_TYPE          : String(40);
      DOC_TITLE         : String(300);
      DOC_DATE          : Date;
      VALIDITY_END_DATE : Date;
      STATUS            : String(20);
      REGULATION_REF    : String(60);
      CONTENT           : LargeString;
}
entity Inspections {
  key INSPECTION_ID        : String(20);
      ASSET_ID             : String(20);
      INSPECTION_DATE      : Date;
      INSPECTION_TYPE      : String(40);
      INSPECTOR            : String(60);
      FINDINGS             : String(1000);
      RESULT               : String(40);
      NEXT_INSPECTION_DATE : Date;
}

entity AssetHealthScores {
  key ASSET_ID      : String(20);
      HEALTH_SCORE  : Integer;
      SENSOR_SCORE  : Decimal(8,2);
      MAINT_SCORE   : Decimal(8,2);
      FAILURE_SCORE : Decimal(8,2);
      AGE_SCORE     : Decimal(8,2);
      FAILURE_PROB  : Decimal(8,4);
      RUL_DAYS      : Integer;
      STATUS        : String(20);
      LATEST_TEMP   : Decimal(8,2);
      LATEST_VIB    : Decimal(8,4);
      LATEST_PRES   : Decimal(8,2);
      SCORE_ENGINE  : String(20);
}

entity AssetThresholds {
  key ASSET_ID   : String(20);
  key TAG_NAME   : String(50);
      SAFE_LO    : Decimal(12,4);
      SAFE_HI    : Decimal(12,4);
      WARN_LO    : Decimal(12,4);
      WARN_HI    : Decimal(12,4);
      CRIT       : Decimal(12,4);
      UNIT       : String(10);
      METHOD     : String(40);
      CONFIDENCE : String(10);
}

entity AssetFinancials {
  key ASSET_ID              : String(20);
      DESIGN_LIFE_YRS       : Integer;
      PM_FREQ_DAYS          : Integer;
      REPLACEMENT_COST      : Decimal(15,2);
      DOWNTIME_COST_PER_DAY : Decimal(15,2);
      ANNUAL_PM_COST        : Decimal(15,2);
      CONSEQUENCE           : Integer;
      LIFECYCLE_STAGE       : Integer;
      DATA_SOURCE           : String(20);
      GENERATED_AT          : Timestamp;
}
