"""
DATA HIGHWAY PROTOTYPE — Step 1: Batch Load Reference Data into HANA Cloud
=============================================================================
Loads all non-streaming data directly into HANA Cloud tables.
Run this AFTER creating tables with hana_ddl.sql.

Usage:
    pip install hdbcli pandas python-dotenv
    python 01_load_reference_data.py

What it loads (in order):
    1. equipment_master.csv          → EQUIPMENT_MASTER
    2. maintenance_work_orders.csv   → MAINTENANCE_WORK_ORDERS
    3. failure_history.csv           → FAILURE_HISTORY
    4. compliance_inspections.csv    → COMPLIANCE_INSPECTIONS
    5. compliance_certificates.csv   → COMPLIANCE_CERTIFICATES
    6. oem_maintenance_specs.csv     → OEM_MAINTENANCE_SPECS
    7. warranty_records.csv          → WARRANTY_RECORDS
    8. oem_bulletins.csv             → OEM_BULLETINS
    9. spare_parts_catalog.csv       → SPARE_PARTS_CATALOG
    10. pi_load_readings.csv         → PI_LOAD_READINGS

NOTE: pi_sensor_readings.csv is NOT loaded here — it goes through
      the streaming pipeline (Event Hubs → Azure Function → HANA).
      To bulk-load it for testing, use 01b_load_pi_bulk.py instead.
"""

import os
import sys
import pandas as pd
import numpy as np
from hdbcli import dbapi
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# ============================================================
# CONNECTION
# ============================================================
def get_hana_connection():
    """Connect to SAP HANA Cloud trial instance."""
    conn = dbapi.connect(
        address=os.getenv("HANA_HOST"),
        port=int(os.getenv("HANA_PORT", 443)),
        user=os.getenv("HANA_USER"),
        password=os.getenv("HANA_PASSWORD"),
        encrypt=True,
        sslValidateCertificate=False
        # If using the DigiCert root CA certificate:
        # sslTrustStore=os.getenv("HANA_CERT_PATH", "./DigiCertGlobalRootCA.pem"),
    )
    print(f"  ✓ Connected to HANA Cloud: {os.getenv('HANA_HOST')}")
    return conn


# ============================================================
# GENERIC BATCH INSERT
# ============================================================
def load_csv_to_hana(conn, csv_path, table_name, column_mapping, batch_size=500):
    """
    Load a CSV file into a HANA Cloud table using batch INSERT.
    
    Args:
        conn: HANA connection object
        csv_path: Path to CSV file
        table_name: Target HANA table (schema-qualified)
        column_mapping: dict mapping CSV column names → HANA column names
        batch_size: Number of rows per INSERT batch
    """
    schema = os.getenv("HANA_SCHEMA", "DATA_HIGHWAY")
    full_table = f'"{schema}"."{table_name}"'
    
    # Read CSV
    df = pd.read_csv(csv_path)
    print(f"\n  Loading {csv_path}")
    print(f"    → Target: {full_table}")
    print(f"    → Rows to load: {len(df):,}")
    
    # Map columns
    hana_cols = list(column_mapping.values())
    csv_cols = list(column_mapping.keys())
    
    # Verify all CSV columns exist
    missing = [c for c in csv_cols if c not in df.columns]
    if missing:
        print(f"    ✗ MISSING CSV COLUMNS: {missing}")
        return 0
    
    # Build INSERT statement
    col_list = ", ".join([f'"{c}"' for c in hana_cols])
    placeholders = ", ".join(["?" for _ in hana_cols])
    insert_sql = f'INSERT INTO {full_table} ({col_list}) VALUES ({placeholders})'
    
    cursor = conn.cursor()
    
    # Truncate existing data
    try:
        cursor.execute(f'DELETE FROM {full_table}')
        conn.commit()
        print(f"    → Cleared existing data")
    except Exception as e:
        print(f"    → Table may be empty: {e}")
    
    # Batch insert
    rows_loaded = 0
    errors = 0
    
    for start in range(0, len(df), batch_size):
        batch = df.iloc[start:start + batch_size]
        batch_data = []
        
        for _, row in batch.iterrows():
            values = []
            for csv_col, hana_col in column_mapping.items():
                val = row[csv_col]
                # Handle NaN/None
                if pd.isna(val):
                    values.append(None)
                # Handle numpy types
                elif isinstance(val, (np.integer,)):
                    values.append(int(val))
                elif isinstance(val, (np.floating,)):
                    values.append(float(val))
                else:
                    values.append(str(val) if val != "" else None)
            batch_data.append(values)
        
        try:
            cursor.executemany(insert_sql, batch_data)
            conn.commit()
            rows_loaded += len(batch_data)
        except Exception as e:
            errors += len(batch_data)
            print(f"    ✗ Batch error at row {start}: {e}")
            # Try individual inserts to find the bad row
            for values in batch_data:
                try:
                    cursor.execute(insert_sql, values)
                    conn.commit()
                    rows_loaded += 1
                    errors -= 1
                except Exception as e2:
                    print(f"      ✗ Row error: {e2} — values: {values[:3]}...")
    
    print(f"    ✓ Loaded: {rows_loaded:,} rows ({errors} errors)")
    return rows_loaded


# ============================================================
# TABLE-SPECIFIC COLUMN MAPPINGS
# CSV column name → HANA column name
# ============================================================

TABLES = [
    {
        "csv": "equipment_master.csv",
        "table": "EQUIPMENT_MASTER",
        "mapping": {
            "equipment_number": "EQUIPMENT_NUMBER",
            "description": "DESCRIPTION",
            "equipment_type": "EQUIPMENT_TYPE",
            "functional_location": "FUNCTIONAL_LOCATION",
            "plant": "PLANT",
            "planning_plant": "PLANNING_PLANT",
            "cost_center": "COST_CENTER",
            "manufacturer": "MANUFACTURER",
            "model_number": "MODEL_NUMBER",
            "serial_number": "SERIAL_NUMBER",
            "installation_date": "INSTALLATION_DATE",
            "age_years": "AGE_YEARS",
            "lifecycle_stage": "LIFECYCLE_STAGE",
            "criticality": "CRITICALITY",
            "abc_indicator": "ABC_INDICATOR",
            "warranty_end_date": "WARRANTY_END_DATE",
            "weight_kg": "WEIGHT_KG",
            "status": "STATUS",
        },
    },
    {
        "csv": "maintenance_work_orders.csv",
        "table": "MAINTENANCE_WORK_ORDERS",
        "mapping": {
            "work_order": "WORK_ORDER",
            "equipment_number": "EQUIPMENT_NUMBER",
            "order_type": "ORDER_TYPE",
            "order_type_desc": "ORDER_TYPE_DESC",
            "activity_type": "ACTIVITY_TYPE",
            "priority": "PRIORITY",
            "status": "STATUS",
            "short_text": "SHORT_TEXT",
            "created_date": "CREATED_DATE",
            "scheduled_start": "SCHEDULED_START",
            "actual_start": "ACTUAL_START",
            "actual_finish": "ACTUAL_FINISH",
            "downtime_hours": "DOWNTIME_HOURS",
            "total_cost_usd": "TOTAL_COST_USD",
            "functional_location": "FUNCTIONAL_LOCATION",
            "planner_group": "PLANNER_GROUP",
            "work_center": "WORK_CENTER",
        },
    },
    {
        "csv": "failure_history.csv",
        "table": "FAILURE_HISTORY",
        "mapping": {
            "failure_id": "FAILURE_ID",
            "equipment_number": "EQUIPMENT_NUMBER",
            "equipment_name": "EQUIPMENT_NAME",
            "equipment_type": "EQUIPMENT_TYPE",
            "failure_date": "FAILURE_DATE",
            "failure_mode": "FAILURE_MODE",
            "failed_component": "FAILED_COMPONENT",
            "root_cause": "ROOT_CAUSE",
            "corrective_action": "CORRECTIVE_ACTION",
            "severity": "SEVERITY",
            "detection_method": "DETECTION_METHOD",
            "detection_to_failure_hrs": "DETECTION_TO_FAILURE_HRS",
            "time_to_repair_hrs": "TIME_TO_REPAIR_HRS",
            "total_downtime_hrs": "TOTAL_DOWNTIME_HRS",
            "production_loss_bbl": "PRODUCTION_LOSS_BBL",
            "repair_cost_usd": "REPAIR_COST_USD",
            "was_predictable": "WAS_PREDICTABLE",
            "linked_work_order": "LINKED_WORK_ORDER",
        },
    },
    {
        "csv": "compliance_inspections.csv",
        "table": "COMPLIANCE_INSPECTIONS",
        "mapping": {
            "inspection_id": "INSPECTION_ID",
            "equipment_number": "EQUIPMENT_NUMBER",
            "equipment_name": "EQUIPMENT_NAME",
            "regulatory_standard": "REGULATORY_STANDARD",
            "inspection_type": "INSPECTION_TYPE",
            "inspection_date": "INSPECTION_DATE",
            "next_due_date": "NEXT_DUE_DATE",
            "inspector": "INSPECTOR",
            "inspection_company": "INSPECTION_COMPANY",
            "result": "RESULT",
            "finding": "FINDING",
            "corrective_action_required": "CORRECTIVE_ACTION_REQUIRED",
            "corrective_action_due_date": "CORRECTIVE_ACTION_DUE_DATE",
            "corrective_action_status": "CORRECTIVE_ACTION_STATUS",
            "risk_ranking": "RISK_RANKING",
            "functional_location": "FUNCTIONAL_LOCATION",
        },
    },
    {
        "csv": "compliance_certificates.csv",
        "table": "COMPLIANCE_CERTIFICATES",
        "mapping": {
            "certificate_id": "CERTIFICATE_ID",
            "equipment_number": "EQUIPMENT_NUMBER",
            "equipment_name": "EQUIPMENT_NAME",
            "certification_standard": "CERTIFICATION_STANDARD",
            "certificate_description": "CERTIFICATE_DESCRIPTION",
            "issuing_body": "ISSUING_BODY",
            "certificate_number": "CERTIFICATE_NUMBER",
            "issue_date": "ISSUE_DATE",
            "expiry_date": "EXPIRY_DATE",
            "days_to_expiry": "DAYS_TO_EXPIRY",
            "status": "STATUS",
            "renewal_required": "RENEWAL_REQUIRED",
            "document_ref": "DOCUMENT_REF",
        },
    },
    {
        "csv": "oem_maintenance_specs.csv",
        "table": "OEM_MAINTENANCE_SPECS",
        "mapping": {
            "spec_id": "SPEC_ID",
            "equipment_number": "EQUIPMENT_NUMBER",
            "equipment_name": "EQUIPMENT_NAME",
            "equipment_type": "EQUIPMENT_TYPE",
            "manufacturer": "MANUFACTURER",
            "task_name": "TASK_NAME",
            "frequency": "FREQUENCY",
            "interval_days": "INTERVAL_DAYS",
            "estimated_duration_hrs": "ESTIMATED_DURATION_HRS",
            "last_performed_date": "LAST_PERFORMED_DATE",
            "next_due_date": "NEXT_DUE_DATE",
            "overdue": "OVERDUE",
            "oem_notes": "OEM_NOTES",
            "skill_required": "SKILL_REQUIRED",
            "requires_shutdown": "REQUIRES_SHUTDOWN",
            "oem_manual_ref": "OEM_MANUAL_REF",
        },
    },
    {
        "csv": "warranty_records.csv",
        "table": "WARRANTY_RECORDS",
        "mapping": {
            "warranty_id": "WARRANTY_ID",
            "equipment_number": "EQUIPMENT_NUMBER",
            "equipment_name": "EQUIPMENT_NAME",
            "equipment_type": "EQUIPMENT_TYPE",
            "manufacturer": "MANUFACTURER",
            "purchase_date": "PURCHASE_DATE",
            "installation_date": "INSTALLATION_DATE",
            "standard_warranty_start": "STANDARD_WARRANTY_START",
            "standard_warranty_end": "STANDARD_WARRANTY_END",
            "extended_warranty": "EXTENDED_WARRANTY",
            "extended_warranty_end": "EXTENDED_WARRANTY_END",
            "warranty_status": "WARRANTY_STATUS",
            "coverage_type": "COVERAGE_TYPE",
            "exclusions": "EXCLUSIONS",
            "warranty_provider": "WARRANTY_PROVIDER",
            "total_claims_filed": "TOTAL_CLAIMS_FILED",
            "total_claims_value_usd": "TOTAL_CLAIMS_VALUE_USD",
            "contract_ref": "CONTRACT_REF",
        },
    },
    {
        "csv": "oem_bulletins.csv",
        "table": "OEM_BULLETINS",
        "mapping": {
            "bulletin_id": "BULLETIN_ID",
            "equipment_number": "EQUIPMENT_NUMBER",
            "equipment_name": "EQUIPMENT_NAME",
            "manufacturer": "MANUFACTURER",
            "title": "TITLE",
            "severity": "SEVERITY",
            "summary": "SUMMARY",
            "action_required": "ACTION_REQUIRED",
            "issue_date": "ISSUE_DATE",
            "compliance_deadline": "COMPLIANCE_DEADLINE",
            "compliance_status": "COMPLIANCE_STATUS",
        },
    },
    {
        "csv": "spare_parts_catalog.csv",
        "table": "SPARE_PARTS_CATALOG",
        "mapping": {
            "spare_id": "SPARE_ID",
            "equipment_number": "EQUIPMENT_NUMBER",
            "equipment_name": "EQUIPMENT_NAME",
            "part_name": "PART_NAME",
            "part_number": "PART_NUMBER",
            "manufacturer_part_number": "MANUFACTURER_PART_NUMBER",
            "unit_cost_usd": "UNIT_COST_USD",
            "quantity_on_hand": "QUANTITY_ON_HAND",
            "minimum_stock_qty": "MINIMUM_STOCK_QTY",
            "reorder_required": "REORDER_REQUIRED",
            "lead_time_weeks": "LEAD_TIME_WEEKS",
            "storage_location": "STORAGE_LOCATION",
            "last_used_date": "LAST_USED_DATE",
            "criticality": "CRITICALITY",
            "notes": "NOTES",
        },
    },
    {
        "csv": "pi_load_readings.csv",
        "table": "PI_LOAD_READINGS",
        "mapping": {
            "timestamp": "TIMESTAMP_UTC",
            "tag_name": "TAG_NAME",
            "asset_id": "ASSET_ID",
            "value": "VALUE",
            "unit": "UNIT",
            "quality": "QUALITY",
        },
    },
]


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 60)
    print("DATA HIGHWAY — Batch Load Reference Data into HANA Cloud")
    print("=" * 60)
    
    data_dir = os.getenv("DATA_DIR", "./sample_data")
    
    # Verify data files exist
    print(f"\n  Data directory: {data_dir}")
    for table_def in TABLES:
        csv_path = os.path.join(data_dir, table_def["csv"])
        exists = "✓" if os.path.exists(csv_path) else "✗ MISSING"
        print(f"    {exists}  {table_def['csv']}")
    
    # Connect to HANA
    print(f"\n  Connecting to HANA Cloud...")
    try:
        conn = get_hana_connection()
    except Exception as e:
        print(f"\n  ✗ CONNECTION FAILED: {e}")
        print(f"\n  Troubleshooting:")
        print(f"    1. Is your HANA Cloud trial instance RUNNING? (auto-stops after inactivity)")
        print(f"    2. Check HANA_HOST in .env — should be: <instance>.hana.trial-us10.hanacloud.ondemand.com")
        print(f"    3. Check HANA_PORT — should be 443 for HANA Cloud trial")
        print(f"    4. Check HANA_USER/HANA_PASSWORD — DBADMIN is the default admin user")
        print(f"    5. Verify your IP is whitelisted in HANA Cloud: BTP Cockpit → HANA Cloud → Manage → Allow All IPs")
        sys.exit(1)
    
    # Set schema
    schema = os.getenv("HANA_SCHEMA", "DATA_HIGHWAY")
    cursor = conn.cursor()
    try:
        cursor.execute(f'SET SCHEMA "{schema}"')
    except:
        print(f"\n  ✗ Schema '{schema}' not found. Run hana_ddl.sql first!")
        sys.exit(1)
    
    # Load each table
    total_rows = 0
    results = []
    
    for table_def in TABLES:
        csv_path = os.path.join(data_dir, table_def["csv"])
        if not os.path.exists(csv_path):
            print(f"\n  ⊘ Skipping {table_def['csv']} — file not found")
            continue
        
        rows = load_csv_to_hana(
            conn=conn,
            csv_path=csv_path,
            table_name=table_def["table"],
            column_mapping=table_def["mapping"],
            batch_size=500,
        )
        total_rows += rows
        results.append((table_def["table"], rows))
    
    # Verify
    print(f"\n{'=' * 60}")
    print(f"LOAD COMPLETE")
    print(f"{'=' * 60}")
    print(f"\n  Total rows loaded: {total_rows:,}\n")
    
    # Query row counts from HANA
    print(f"  HANA Cloud verification:")
    for table_name, expected in results:
        try:
            cursor.execute(f'SELECT COUNT(*) FROM "{schema}"."{table_name}"')
            actual = cursor.fetchone()[0]
            match = "✓" if actual == expected else "⚠"
            print(f"    {match}  {table_name:<35s}  {actual:>8,} rows")
        except Exception as e:
            print(f"    ✗  {table_name:<35s}  Error: {e}")
    
    conn.close()
    print(f"\n  Connection closed. Reference data is loaded and query-ready.")
    print(f"\n  NEXT STEP: Run 02_pi_simulator.py to stream sensor data via Event Hubs")


if __name__ == "__main__":
    main()
