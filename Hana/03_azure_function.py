"""
DATA HIGHWAY PROTOTYPE — Step 3: Azure Function (Event Hub → HANA Cloud)
=========================================================================
This Azure Function is triggered by Event Hub messages and writes
normalized sensor data into SAP HANA Cloud.

In the production architecture, this is Azure Stream Analytics.
For the prototype, an Azure Function does the same job with less setup.

DEPLOYMENT:
    1. Create an Azure Function App (Python, Consumption plan)
    2. Add these Application Settings:
         EVENTHUB_CONNECTION_STRING
         HANA_HOST
         HANA_PORT
         HANA_USER
         HANA_PASSWORD
         HANA_SCHEMA
    3. Deploy this function
    4. The Event Hub trigger auto-fires when 02_pi_simulator.py sends data

FILE STRUCTURE (in your Azure Function App):
    function_app.py          ← this file (rename to function_app.py)
    requirements.txt         ← see below
    host.json                ← see below
"""

import os
import json
import logging
from datetime import datetime
from hdbcli import dbapi
import azure.functions as func

app = func.FunctionApp()

# ============================================================
# HANA CONNECTION (reused across invocations)
# ============================================================
_hana_conn = None


def get_hana_connection():
    """Get or create HANA Cloud connection."""
    global _hana_conn
    try:
        if _hana_conn is None or not _hana_conn.isconnected():
            _hana_conn = dbapi.connect(
                address=os.getenv("HANA_HOST"),
                port=int(os.getenv("HANA_PORT", 443)),
                user=os.getenv("HANA_USER"),
                password=os.getenv("HANA_PASSWORD"),
                encrypt=True,
                sslValidateCertificate=True,
                sslCryptoProvider="openssl",
            )
            logging.info("Connected to HANA Cloud")
    except Exception as e:
        logging.error(f"HANA connection failed: {e}")
        raise
    return _hana_conn


# ============================================================
# TAG-TO-ASSET MAPPING (hardcoded for prototype)
# In production, this lives in a config table or comes from Pi AF
# ============================================================
# Simple unit normalization rules
UNIT_CONVERSIONS = {
    "degF": ("degC", lambda v: (v - 32) * 5 / 9),
    "psi":  ("bar",  lambda v: v * 0.0689476),
    "in/s": ("mm/s", lambda v: v * 25.4),
    "gpm":  ("m3/hr", lambda v: v * 0.2271),
}

# Threshold alerts (tag_suffix → max safe value)
THRESHOLDS = {
    "VIB_X":        7.1,    # mm/s — ISO 10816 Zone C boundary
    "BEAR_TEMP":    95.0,   # degC — bearing temperature alarm
    "EXHAUST_TEMP": 560.0,  # degC — gas turbine exhaust limit
    "WIND_TEMP":    120.0,  # degC — motor winding limit
    "LOAD_PCT":     95.0,   # % — overload threshold
}


def normalize_reading(message: dict) -> dict:
    """
    Normalize a raw Pi sensor reading.
    This is what Azure Stream Analytics would do in production:
      - Convert units to standard
      - Flag threshold breaches
      - Add processing metadata
    """
    tag = message.get("tag_name", "")
    value = message.get("value", 0)
    unit = message.get("unit", "")

    # Unit conversion (if needed)
    if unit in UNIT_CONVERSIONS:
        new_unit, converter = UNIT_CONVERSIONS[unit]
        value = round(converter(value), 2)
        unit = new_unit

    # Check thresholds
    tag_suffix = tag.split(".")[-1] if "." in tag else tag
    threshold = THRESHOLDS.get(tag_suffix)
    alert = None
    if threshold and value > threshold:
        alert = f"THRESHOLD_BREACH: {tag_suffix} = {value} > {threshold}"

    return {
        "timestamp": message.get("timestamp"),
        "tag_name": tag,
        "asset_id": message.get("asset_id"),
        "value": value,
        "unit": unit,
        "quality": message.get("quality", "Good"),
        "alert": alert,
    }


# ============================================================
# EVENT HUB TRIGGERED FUNCTION
# ============================================================
@app.function_name(name="PiToHana")
@app.event_hub_message_trigger(
    arg_name="events",
    event_hub_name="pi-telemetry",
    connection="EVENTHUB_CONNECTION_STRING",
    cardinality="many",
    consumer_group="$Default",
)
def pi_to_hana(events: func.EventHubEvent):
    """
    Triggered by Event Hub. Normalizes Pi readings and inserts into HANA Cloud.
    Processes events in batches for efficiency.
    """
    schema = os.getenv("HANA_SCHEMA", "DATA_HIGHWAY")

    # Parse events
    readings = []
    alerts = []

    for event in events:
        try:
            body = event.get_body().decode("utf-8")
            message = json.loads(body)
            normalized = normalize_reading(message)
            readings.append(normalized)

            if normalized.get("alert"):
                alerts.append(normalized)

        except Exception as e:
            logging.error(f"Failed to parse event: {e}")
            continue

    if not readings:
        return

    # Batch insert into HANA Cloud
    try:
        conn = get_hana_connection()
        cursor = conn.cursor()

        insert_sql = f'''
            INSERT INTO "{schema}"."PI_SENSOR_READINGS" 
            ("TIMESTAMP_UTC", "TAG_NAME", "ASSET_ID", "VALUE", "UNIT", "QUALITY")
            VALUES (?, ?, ?, ?, ?, ?)
        '''

        batch_data = [
            (r["timestamp"], r["tag_name"], r["asset_id"],
             r["value"], r["unit"], r["quality"])
            for r in readings
        ]

        cursor.executemany(insert_sql, batch_data)
        conn.commit()

        logging.info(f"Inserted {len(readings)} readings into HANA Cloud")

        # Log alerts
        for alert in alerts:
            logging.warning(f"⚠ {alert['alert']} — Asset: {alert['asset_id']}")

    except Exception as e:
        logging.error(f"HANA insert failed: {e}")
        raise


# ============================================================
# SUPPORTING FILES
# ============================================================
"""
--- requirements.txt ---
azure-functions
hdbcli
python-dotenv

--- host.json ---
{
  "version": "2.0",
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[4.*, 5.0.0)"
  },
  "logging": {
    "logLevel": {
      "default": "Information",
      "Host.Results": "Information",
      "Function": "Information"
    }
  }
}

--- local.settings.json (for local testing) ---
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "EVENTHUB_CONNECTION_STRING": "your-connection-string",
    "HANA_HOST": "your-instance.hana.trial-us10.hanacloud.ondemand.com",
    "HANA_PORT": "443",
    "HANA_USER": "DBADMIN",
    "HANA_PASSWORD": "your-password",
    "HANA_SCHEMA": "DATA_HIGHWAY"
  }
}
"""
