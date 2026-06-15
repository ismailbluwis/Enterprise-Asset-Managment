# Data Highway Prototype — Setup Guide

## What You're Building

A working end-to-end pipeline that proves: **Sample Pi data → Azure Event Hubs → Azure Function → SAP HANA Cloud**, with all reference data (equipment master, compliance, OEM, failures, spares) pre-loaded in HANA Cloud and queryable.

## Prerequisites (You Already Have These)

- Azure subscription (free tier)
- SAP HANA Cloud trial instance
- Python 3.10+ on your laptop

## File Inventory

```
prototype/
├── hana_ddl.sql                  ← Run first: creates 12 tables in HANA Cloud
├── .env.template                 ← Copy to .env and fill in your credentials
├── requirements.txt              ← Python dependencies
├── 01_load_reference_data.py     ← Loads 10 reference CSVs into HANA
├── 01b_load_pi_bulk.py           ← (Optional) Bulk-loads Pi data directly into HANA
├── 02_pi_simulator.py            ← Streams Pi data into Azure Event Hubs
├── 03_azure_function.py          ← Event Hub trigger → normalize → HANA Cloud
├── 04_verify_hana.py             ← Queries HANA to confirm everything landed
└── sample_data/
    ├── pi_sensor_readings.csv    ← 311K rows, 108 tags, 30 days
    ├── pi_load_readings.csv      ← 34K rows, load % supplement
    ├── equipment_master.csv      ← 20 O&G assets
    ├── maintenance_work_orders.csv
    ├── failure_history.csv       ← 3-year root cause analysis
    ├── compliance_inspections.csv
    ├── compliance_certificates.csv
    ├── oem_maintenance_specs.csv
    ├── warranty_records.csv
    ├── oem_bulletins.csv
    └── spare_parts_catalog.csv
```

---

## Step 1: Set Up HANA Cloud (10 minutes)

### 1a. Start your HANA Cloud trial

1. Log into SAP BTP Trial Cockpit: https://cockpit.hanatrial.ondemand.com
2. Go to **SAP HANA Cloud** → check your instance is **Running** (click Start if stopped)
3. Click **Open in SAP HANA Database Explorer**

### 1b. Allow your IP address

1. In BTP Cockpit → SAP HANA Cloud → click your instance → **Manage Configuration**
2. Under **Allowed Connections**, add your current IP or select **Allow all IP addresses** (fine for prototype)

### 1c. Create the tables

1. Open **HANA Database Explorer** → click the SQL Console icon
2. Copy the entire contents of `hana_ddl.sql` into the SQL Console
3. Click **Run** (green play button)
4. You should see 12 tables created under the `DATA_HIGHWAY` schema
5. Verify by running: `SELECT TABLE_NAME FROM M_TABLES WHERE SCHEMA_NAME = 'DATA_HIGHWAY'`

### 1d. Get your connection details

You need these for the `.env` file:

| Setting | Where to Find It |
|---------|-----------------|
| HANA_HOST | BTP Cockpit → HANA Cloud → your instance → SQL Endpoint (hostname only, without port) |
| HANA_PORT | Usually `443` for HANA Cloud trial |
| HANA_USER | `DBADMIN` (default admin user) |
| HANA_PASSWORD | The password you set when creating the trial instance |

---

## Step 2: Set Up Azure Event Hubs (5 minutes)

1. Log into Azure Portal: https://portal.azure.com
2. Create a **Resource Group** called `datahighway-proto`
3. Inside it, create an **Event Hubs Namespace**:
   - Name: `dh-proto-eventhubs`
   - Pricing tier: Basic
   - Throughput Units: 1
   - Location: your nearest region
4. Inside the namespace, create an **Event Hub**:
   - Name: `pi-telemetry`
   - Partition Count: 2 (default)
   - Message Retention: 1 day
5. Go to the namespace → **Shared access policies** → **RootManageSharedAccessKey**
6. Copy the **Connection string — primary key**

---

## Step 3: Configure the Prototype (2 minutes)

```bash
# Clone or copy the prototype folder to your laptop
cd prototype

# Install Python dependencies
pip install -r requirements.txt

# Create your config file
cp .env.template .env
```

Edit `.env` with your actual values:

```
HANA_HOST=your-instance.hana.trial-us10.hanacloud.ondemand.com
HANA_PORT=443
HANA_USER=DBADMIN
HANA_PASSWORD=YourPassword123
HANA_SCHEMA=DATA_HIGHWAY

EVENTHUB_CONNECTION_STRING=Endpoint=sb://dh-proto-eventhubs.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=xxxx
EVENTHUB_NAME=pi-telemetry

DATA_DIR=./sample_data
```

---

## Step 4: Load Reference Data into HANA (5 minutes)

```bash
python 01_load_reference_data.py
```

This loads all 10 reference datasets (equipment master, work orders, failures, compliance, OEM, warranties, bulletins, spares, load readings) into HANA Cloud. You'll see progress for each table.

Expected output:
```
  ✓  EQUIPMENT_MASTER                        20 rows
  ✓  MAINTENANCE_WORK_ORDERS                146 rows
  ✓  FAILURE_HISTORY                        138 rows
  ✓  COMPLIANCE_INSPECTIONS                 197 rows
  ✓  COMPLIANCE_CERTIFICATES                 60 rows
  ✓  OEM_MAINTENANCE_SPECS                   98 rows
  ✓  WARRANTY_RECORDS                        20 rows
  ✓  OEM_BULLETINS                           20 rows
  ✓  SPARE_PARTS_CATALOG                     79 rows
  ✓  PI_LOAD_READINGS                    34,572 rows
```

---

## Step 5: Choose Your Pi Sensor Loading Path

### Option A: Bulk Load (Quick Test — Skip Event Hubs)

If you just want to get all data into HANA immediately:

```bash
python 01b_load_pi_bulk.py
```

This loads all 311,148 Pi sensor readings directly into HANA Cloud in about 5-10 minutes. No Event Hubs needed. Good for verifying queries, but doesn't prove the streaming pipeline.

### Option B: Stream via Event Hubs (The Real Demo)

This proves the full architecture: Pi → Event Hubs → Azure Function → HANA Cloud.

**Step 5b.1: Deploy the Azure Function**

1. In Azure Portal, create a **Function App**:
   - Runtime: Python 3.10+
   - Plan: Consumption (serverless)
   - Region: same as your Event Hubs
2. Add these **Application Settings** (Configuration → Application settings):
   - `EVENTHUB_CONNECTION_STRING` = your Event Hubs connection string
   - `HANA_HOST`, `HANA_PORT`, `HANA_USER`, `HANA_PASSWORD`, `HANA_SCHEMA`
3. Deploy `03_azure_function.py` as `function_app.py` using VS Code Azure Functions extension or Azure CLI
4. Add `hdbcli` and `azure-functions` to the Function App's `requirements.txt`

**Step 5b.2: Run the Simulator**

```bash
# Fast mode: ~1 batch/second, great for live demos
python 02_pi_simulator.py --speed fast

# Turbo mode: full speed, loads all 311K rows in minutes
python 02_pi_simulator.py --speed turbo

# Test with just 1000 rows first
python 02_pi_simulator.py --speed fast --max-rows 1000
```

Watch the Azure Function logs in Portal → Function App → Monitor to see events flowing through.

---

## Step 6: Verify Everything Landed (1 minute)

```bash
python 04_verify_hana.py
```

This runs sample queries across all 12 tables and confirms row counts, failure mode analysis, compliance status, expiring certificates, and spare parts reorder status.

---

## Step 7: Query the Data in HANA Database Explorer

Open HANA Database Explorer and try these queries:

```sql
-- How many readings per asset?
SELECT "ASSET_ID", COUNT(*) as READINGS
FROM "DATA_HIGHWAY"."PI_SENSOR_READINGS"
GROUP BY "ASSET_ID"
ORDER BY READINGS DESC;

-- GC-002 bearing temp degradation (the AI should catch this)
SELECT "TIMESTAMP_UTC", "VALUE"
FROM "DATA_HIGHWAY"."PI_SENSOR_READINGS"
WHERE "TAG_NAME" = 'GC-002.BEAR_TEMP'
ORDER BY "TIMESTAMP_UTC";

-- CP-004 seal failure event (day 22)
SELECT "TIMESTAMP_UTC", "TAG_NAME", "VALUE", "QUALITY"
FROM "DATA_HIGHWAY"."PI_SENSOR_READINGS"
WHERE "ASSET_ID" = 'CP-004' AND "TAG_NAME" LIKE '%.VIB_X'
ORDER BY "TIMESTAMP_UTC";

-- Cross-source query: asset + failures + warranty + open WOs
SELECT 
    e."EQUIPMENT_NUMBER",
    e."DESCRIPTION",
    e."CRITICALITY",
    e."AGE_YEARS",
    w."WARRANTY_STATUS",
    (SELECT COUNT(*) FROM "DATA_HIGHWAY"."FAILURE_HISTORY" f 
     WHERE f."EQUIPMENT_NUMBER" = e."EQUIPMENT_NUMBER") as TOTAL_FAILURES,
    (SELECT COUNT(*) FROM "DATA_HIGHWAY"."MAINTENANCE_WORK_ORDERS" wo 
     WHERE wo."EQUIPMENT_NUMBER" = e."EQUIPMENT_NUMBER" 
     AND wo."STATUS" NOT IN ('TECO')) as OPEN_WOS
FROM "DATA_HIGHWAY"."EQUIPMENT_MASTER" e
LEFT JOIN "DATA_HIGHWAY"."WARRANTY_RECORDS" w 
    ON e."EQUIPMENT_NUMBER" = w."EQUIPMENT_NUMBER"
ORDER BY TOTAL_FAILURES DESC;
```

---

## What You've Proven

When this prototype runs end-to-end, you've demonstrated:

1. **Pi data ingestion** — sensor telemetry flows from a simulated OSI Pi source through Azure Event Hubs
2. **Real-time normalization** — the Azure Function applies unit conversion, threshold checks, and quality tagging
3. **HANA Cloud landing** — all data arrives in structured, indexed, query-ready tables
4. **Cross-source joins** — sensor data, maintenance history, compliance records, and OEM specs all live in the same database and can be queried together
5. **AI-ready features** — the ASSET_REALTIME_FEATURES table is ready for SAP AI Core + Claude to consume

This is the exact same data flow as the production architecture — just with a Python simulator instead of the AVEVA Adapter, and an Azure Function instead of Stream Analytics.

---

## Next Steps → Intelligence Layer

Once the data is in HANA Cloud, the next layer is:

- **SAP AI Core** — train/deploy the health scoring model
- **Claude (Anthropic)** — anomaly explanation, maintenance recommendation reasoning
- **SAP Fiori Dashboard** — fleet health view, risk matrix
- **S/4HANA PM Auto-Actions** — AI-triggered work order creation

That's Layer 5 in your architecture diagram.
