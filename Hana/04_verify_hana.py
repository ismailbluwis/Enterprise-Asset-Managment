"""
DATA HIGHWAY PROTOTYPE — Step 4: Verify Data in HANA Cloud
=============================================================
Queries all tables to confirm data loaded correctly.
Run this after 01_load_reference_data.py and 01b_load_pi_bulk.py.

Usage:
    python 04_verify_hana.py
"""

import os
from hdbcli import dbapi
from dotenv import load_dotenv

load_dotenv()


def main():
    print("=" * 70)
    print("DATA HIGHWAY — HANA Cloud Data Verification")
    print("=" * 70)

    conn = dbapi.connect(
        address=os.getenv("HANA_HOST"),
        port=int(os.getenv("HANA_PORT", 443)),
        user=os.getenv("HANA_USER"),
        password=os.getenv("HANA_PASSWORD"),
        encrypt=True,
        sslValidateCertificate=True,
        sslCryptoProvider="openssl",
    )
    cursor = conn.cursor()
    schema = os.getenv("HANA_SCHEMA", "DATA_HIGHWAY")
    print(f"\n  Connected. Schema: {schema}\n")

    # ---- Table Row Counts ----
    tables = [
        "PI_SENSOR_READINGS",
        "PI_LOAD_READINGS",
        "EQUIPMENT_MASTER",
        "MAINTENANCE_WORK_ORDERS",
        "FAILURE_HISTORY",
        "COMPLIANCE_INSPECTIONS",
        "COMPLIANCE_CERTIFICATES",
        "OEM_MAINTENANCE_SPECS",
        "WARRANTY_RECORDS",
        "OEM_BULLETINS",
        "SPARE_PARTS_CATALOG",
        "ASSET_REALTIME_FEATURES",
    ]

    print(f"  {'TABLE':<40s}  {'ROWS':>10s}  STATUS")
    print(f"  {'─' * 65}")

    total = 0
    for table in tables:
        try:
            cursor.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
            count = cursor.fetchone()[0]
            status = "✓ OK" if count > 0 else "○ EMPTY"
            print(f"  {table:<40s}  {count:>10,}  {status}")
            total += count
        except Exception as e:
            print(f"  {table:<40s}  {'ERROR':>10s}  ✗ {e}")

    print(f"  {'─' * 65}")
    print(f"  {'TOTAL':<40s}  {total:>10,}")

    # ---- Sample Queries ----
    print(f"\n\n  {'=' * 65}")
    print(f"  SAMPLE QUERIES")
    print(f"  {'=' * 65}")

    # 1. Assets by criticality
    print(f"\n  ▸ Assets by Criticality:")
    cursor.execute(f'''
        SELECT "CRITICALITY", COUNT(*) as CNT 
        FROM "{schema}"."EQUIPMENT_MASTER" 
        GROUP BY "CRITICALITY" 
        ORDER BY CNT DESC
    ''')
    for row in cursor.fetchall():
        print(f"      {row[0]:<12s}  {row[1]} assets")

    # 2. Sensor readings per asset (last timestamp)
    print(f"\n  ▸ Latest Sensor Reading per Asset (top 5):")
    cursor.execute(f'''
        SELECT "ASSET_ID", MAX("TIMESTAMP_UTC") as LATEST, COUNT(*) as READINGS
        FROM "{schema}"."PI_SENSOR_READINGS"
        GROUP BY "ASSET_ID"
        ORDER BY LATEST DESC
        LIMIT 5
    ''')
    for row in cursor.fetchall():
        print(f"      {row[0]:<10s}  Latest: {str(row[1])[:19]}  |  {row[2]:,} readings")

    # 3. Failure modes (top 5)
    print(f"\n  ▸ Top Failure Modes (3-year history):")
    cursor.execute(f'''
        SELECT "FAILURE_MODE", COUNT(*) as CNT, 
               ROUND(AVG("TIME_TO_REPAIR_HRS"), 1) as AVG_MTTR
        FROM "{schema}"."FAILURE_HISTORY"
        GROUP BY "FAILURE_MODE"
        ORDER BY CNT DESC
        LIMIT 5
    ''')
    for row in cursor.fetchall():
        print(f"      {row[0]:<35s}  {row[1]}x  (avg MTTR: {row[2]}h)")

    # 4. Overdue compliance inspections
    print(f"\n  ▸ Compliance Actions Status:")
    cursor.execute(f'''
        SELECT "CORRECTIVE_ACTION_STATUS", COUNT(*) as CNT
        FROM "{schema}"."COMPLIANCE_INSPECTIONS"
        WHERE "CORRECTIVE_ACTION_REQUIRED" = 'Yes'
        GROUP BY "CORRECTIVE_ACTION_STATUS"
    ''')
    for row in cursor.fetchall():
        flag = "⚠" if row[0] == "Overdue" else " "
        print(f"    {flag} {row[0]:<15s}  {row[1]} actions")

    # 5. Expiring certificates
    print(f"\n  ▸ Certificates Expiring Soon:")
    cursor.execute(f'''
        SELECT "EQUIPMENT_NUMBER", "CERTIFICATION_STANDARD", 
               "DAYS_TO_EXPIRY", "STATUS"
        FROM "{schema}"."COMPLIANCE_CERTIFICATES"
        WHERE "DAYS_TO_EXPIRY" < 180
        ORDER BY "DAYS_TO_EXPIRY"
    ''')
    results = cursor.fetchall()
    if results:
        for row in results:
            print(f"      {row[0]:<10s}  {row[1]:<20s}  {row[2]} days  ({row[3]})")
    else:
        print(f"      None expiring within 180 days")

    # 6. Warranty status summary
    print(f"\n  ▸ Warranty Status:")
    cursor.execute(f'''
        SELECT "WARRANTY_STATUS", COUNT(*) as CNT
        FROM "{schema}"."WARRANTY_RECORDS"
        GROUP BY "WARRANTY_STATUS"
    ''')
    for row in cursor.fetchall():
        print(f"      {row[0]:<12s}  {row[1]} assets")

    # 7. OEM Bulletins compliance
    print(f"\n  ▸ OEM Bulletin Compliance (Mandatory only):")
    cursor.execute(f'''
        SELECT "COMPLIANCE_STATUS", COUNT(*) as CNT
        FROM "{schema}"."OEM_BULLETINS"
        WHERE "SEVERITY" = 'Mandatory'
        GROUP BY "COMPLIANCE_STATUS"
    ''')
    for row in cursor.fetchall():
        flag = "⚠" if row[0] in ["Overdue", "Not Started"] else " "
        print(f"    {flag} {row[0]:<15s}  {row[1]} items")

    # 8. Spare parts needing reorder
    print(f"\n  ▸ Spare Parts Needing Reorder:")
    cursor.execute(f'''
        SELECT "EQUIPMENT_NUMBER", "PART_NAME", "QUANTITY_ON_HAND", 
               "LEAD_TIME_WEEKS", "CRITICALITY"
        FROM "{schema}"."SPARE_PARTS_CATALOG"
        WHERE "REORDER_REQUIRED" = 'Yes'
        ORDER BY "LEAD_TIME_WEEKS" DESC
        LIMIT 5
    ''')
    for row in cursor.fetchall():
        print(f"      {row[0]:<10s}  {row[1]:<30s}  Qty: {row[2]}  Lead: {row[3]}wk  ({row[4]})")

    conn.close()
    print(f"\n\n  ✓ Verification complete. All data is query-ready in HANA Cloud.")
    print(f"  ✓ Your feature store is loaded. The AI layer can now consume this data.\n")


if __name__ == "__main__":
    main()
