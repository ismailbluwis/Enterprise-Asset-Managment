"""
DATA HIGHWAY — Oil & Gas Sample Data Generator
================================================
Generates 3 datasets for the prototype pipeline:
  1. pi_sensor_readings.csv   — OSI Pi tag telemetry (15-min intervals, 30 days)
  2. equipment_master.csv     — SAP Equipment Master records (20 assets)
  3. maintenance_work_orders.csv — SAP PM Work Order history (30 days)

Design choices:
  - 20 assets across 8 O&G equipment classes
  - Realistic value ranges per sensor type
  - Gaussian noise + diurnal drift patterns
  - 2 assets with embedded degradation trends (for AI to catch later)
  - 1 asset with a sudden failure event mid-period
  - Maintenance WOs correlated to the degradation/failure patterns
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os

np.random.seed(42)

# ============================================================
# CONFIGURATION
# ============================================================
START_DATE = datetime(2026, 3, 16, 0, 0, 0)
END_DATE   = datetime(2026, 4, 15, 0, 0, 0)
INTERVAL_MIN = 15  # 15-minute readings
OUTPUT_DIR = "/home/claude/sample_data"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# ASSET REGISTRY — 20 Oil & Gas Assets
# ============================================================
ASSETS = [
    # Centrifugal Pumps (crude transfer, water injection)
    {"asset_id": "CP-001", "name": "Crude Transfer Pump A",        "type": "Centrifugal Pump",     "area": "Production",    "criticality": "High",   "age_years": 8,  "lifecycle": "Mid Life",     "manufacturer": "Sulzer"},
    {"asset_id": "CP-002", "name": "Crude Transfer Pump B",        "type": "Centrifugal Pump",     "area": "Production",    "criticality": "High",   "age_years": 8,  "lifecycle": "Mid Life",     "manufacturer": "Sulzer"},
    {"asset_id": "CP-003", "name": "Water Injection Pump",         "type": "Centrifugal Pump",     "area": "Injection",     "criticality": "Medium", "age_years": 5,  "lifecycle": "Early Life",   "manufacturer": "Flowserve"},
    {"asset_id": "CP-004", "name": "Seawater Lift Pump",           "type": "Centrifugal Pump",     "area": "Utilities",     "criticality": "Medium", "age_years": 12, "lifecycle": "Late Life",    "manufacturer": "Flowserve"},

    # Gas Compressors
    {"asset_id": "GC-001", "name": "Export Gas Compressor",        "type": "Gas Compressor",       "area": "Compression",   "criticality": "High",   "age_years": 6,  "lifecycle": "Mid Life",     "manufacturer": "Atlas Copco"},
    {"asset_id": "GC-002", "name": "Booster Compressor A",         "type": "Gas Compressor",       "area": "Compression",   "criticality": "High",   "age_years": 10, "lifecycle": "Mid Life",     "manufacturer": "Siemens"},
    {"asset_id": "GC-003", "name": "Vapor Recovery Compressor",    "type": "Gas Compressor",       "area": "Compression",   "criticality": "Medium", "age_years": 3,  "lifecycle": "Early Life",   "manufacturer": "Ariel"},

    # Heat Exchangers
    {"asset_id": "HX-001", "name": "Crude-Crude Heat Exchanger",   "type": "Heat Exchanger",       "area": "Processing",    "criticality": "Medium", "age_years": 9,  "lifecycle": "Mid Life",     "manufacturer": "Alfa Laval"},
    {"asset_id": "HX-002", "name": "Gas Cooler",                   "type": "Heat Exchanger",       "area": "Compression",   "criticality": "High",   "age_years": 6,  "lifecycle": "Mid Life",     "manufacturer": "Alfa Laval"},
    {"asset_id": "HX-003", "name": "Produced Water Cooler",        "type": "Heat Exchanger",       "area": "Utilities",     "criticality": "Low",    "age_years": 4,  "lifecycle": "Early Life",   "manufacturer": "Kelvion"},

    # Three-Phase Separators
    {"asset_id": "SP-001", "name": "1st Stage Separator",          "type": "Three-Phase Separator","area": "Processing",    "criticality": "High",   "age_years": 9,  "lifecycle": "Mid Life",     "manufacturer": "Exterran"},
    {"asset_id": "SP-002", "name": "2nd Stage Separator",          "type": "Three-Phase Separator","area": "Processing",    "criticality": "High",   "age_years": 9,  "lifecycle": "Mid Life",     "manufacturer": "Exterran"},
    {"asset_id": "SP-003", "name": "Test Separator",               "type": "Three-Phase Separator","area": "Well Testing",  "criticality": "Medium", "age_years": 7,  "lifecycle": "Mid Life",     "manufacturer": "HC Petroleum"},

    # Gas Turbines (power generation)
    {"asset_id": "GT-001", "name": "Power Gen Turbine A",          "type": "Gas Turbine",          "area": "Power Gen",     "criticality": "High",   "age_years": 11, "lifecycle": "Late Life",    "manufacturer": "GE"},
    {"asset_id": "GT-002", "name": "Power Gen Turbine B",          "type": "Gas Turbine",          "area": "Power Gen",     "criticality": "High",   "age_years": 7,  "lifecycle": "Mid Life",     "manufacturer": "Siemens"},

    # Electric Motors
    {"asset_id": "EM-001", "name": "Pump Drive Motor A",           "type": "Electric Motor",       "area": "Production",    "criticality": "High",   "age_years": 8,  "lifecycle": "Mid Life",     "manufacturer": "ABB"},
    {"asset_id": "EM-002", "name": "Compressor Drive Motor",       "type": "Electric Motor",       "area": "Compression",   "criticality": "High",   "age_years": 10, "lifecycle": "Mid Life",     "manufacturer": "Siemens"},

    # Control Valves
    {"asset_id": "CV-001", "name": "Separator Level Control Valve","type": "Control Valve",        "area": "Processing",    "criticality": "Medium", "age_years": 5,  "lifecycle": "Early Life",   "manufacturer": "Emerson"},
    {"asset_id": "CV-002", "name": "Compressor Anti-Surge Valve",  "type": "Control Valve",        "area": "Compression",   "criticality": "High",   "age_years": 6,  "lifecycle": "Mid Life",     "manufacturer": "Emerson"},

    # Fire Water Pump
    {"asset_id": "FP-001", "name": "Fire Water Pump",              "type": "Fire Water Pump",      "area": "Safety Systems","criticality": "High",   "age_years": 14, "lifecycle": "Late Life",    "manufacturer": "Ruhrpumpen"},
]

# ============================================================
# SENSOR TAG PROFILES PER EQUIPMENT TYPE
# Each tag: (tag_suffix, unit, base_value, noise_std, description)
# ============================================================
SENSOR_PROFILES = {
    "Centrifugal Pump": [
        ("DISCH_PRESS",  "bar",   45.0,  1.5,  "Discharge Pressure"),
        ("SUCT_PRESS",   "bar",   2.5,   0.3,  "Suction Pressure"),
        ("FLOW_RATE",    "m3/hr", 320.0, 15.0,  "Flow Rate"),
        ("VIB_X",        "mm/s",  3.2,   0.6,  "Vibration X-axis"),
        ("BEAR_TEMP",    "degC",  65.0,  2.0,  "Bearing Temperature"),
        ("MOT_CURRENT",  "A",     85.0,  3.0,  "Motor Current"),
    ],
    "Gas Compressor": [
        ("SUCT_PRESS",   "bar",   8.0,   0.5,  "Suction Pressure"),
        ("DISCH_PRESS",  "bar",   65.0,  2.0,  "Discharge Pressure"),
        ("VIB_X",        "mm/s",  4.5,   0.8,  "Vibration X-axis"),
        ("BEAR_TEMP",    "degC",  72.0,  2.5,  "Bearing Temperature"),
        ("GAS_FLOW",     "MMSCFD",12.0,  1.0,  "Gas Flow Rate"),
        ("LUBE_OIL_PRESS","bar",  4.2,   0.3,  "Lube Oil Pressure"),
    ],
    "Heat Exchanger": [
        ("INLET_TEMP",   "degC",  95.0,  3.0,  "Inlet Temperature"),
        ("OUTLET_TEMP",  "degC",  45.0,  2.0,  "Outlet Temperature"),
        ("PRESS_DROP",   "bar",   0.8,   0.1,  "Pressure Drop"),
        ("SHELL_TEMP",   "degC",  68.0,  2.0,  "Shell Temperature"),
        ("FLOW_RATE",    "m3/hr", 180.0, 10.0,  "Flow Rate"),
    ],
    "Three-Phase Separator": [
        ("LEVEL_PCT",    "%",     55.0,  5.0,  "Liquid Level"),
        ("PRESS",        "bar",   12.0,  0.5,  "Operating Pressure"),
        ("TEMP",         "degC",  82.0,  2.0,  "Operating Temperature"),
        ("OIL_FLOW",     "m3/hr", 95.0,  8.0,  "Oil Outlet Flow"),
        ("GAS_FLOW",     "MMSCFD",3.5,   0.4,  "Gas Outlet Flow"),
        ("WATER_FLOW",   "m3/hr", 40.0,  5.0,  "Water Outlet Flow"),
    ],
    "Gas Turbine": [
        ("SPEED_RPM",    "RPM",   9500,  50,   "Rotor Speed"),
        ("EXHAUST_TEMP", "degC",  520.0, 8.0,  "Exhaust Temperature"),
        ("VIB_X",        "mm/s",  5.0,   1.0,  "Vibration X-axis"),
        ("POWER_KW",     "kW",    18000, 500,  "Power Output"),
        ("FUEL_FLOW",    "kg/hr", 4200,  100,  "Fuel Gas Flow"),
    ],
    "Electric Motor": [
        ("CURRENT_A",    "A",     120.0, 5.0,  "Stator Current"),
        ("VOLTAGE_V",    "V",     4160,  20,   "Supply Voltage"),
        ("WIND_TEMP",    "degC",  78.0,  3.0,  "Winding Temperature"),
        ("VIB_X",        "mm/s",  2.8,   0.5,  "Vibration X-axis"),
        ("SPEED_RPM",    "RPM",   2980,  5,    "Shaft Speed"),
    ],
    "Control Valve": [
        ("POSITION_PCT", "%",     52.0,  8.0,  "Valve Position"),
        ("UPSTR_PRESS",  "bar",   14.0,  0.6,  "Upstream Pressure"),
        ("DNSTR_PRESS",  "bar",   10.0,  0.5,  "Downstream Pressure"),
        ("TEMP",         "degC",  75.0,  2.0,  "Process Temperature"),
    ],
    "Fire Water Pump": [
        ("DISCH_PRESS",  "bar",   10.0,  0.5,  "Discharge Pressure"),
        ("FLOW_RATE",    "m3/hr", 250.0, 10.0,  "Flow Rate"),
        ("VIB_X",        "mm/s",  2.5,   0.4,  "Vibration X-axis"),
        ("BEAR_TEMP",    "degC",  55.0,  2.0,  "Bearing Temperature"),
        ("MOT_CURRENT",  "A",     60.0,  2.0,  "Motor Current"),
    ],
}

# ============================================================
# ANOMALY SCENARIOS
# ============================================================
# Asset GC-002 (Booster Compressor A): gradual bearing degradation over last 15 days
# Asset GT-001 (Power Gen Turbine A):  gradual exhaust temp rise over last 10 days
# Asset CP-004 (Seawater Lift Pump):   sudden failure on day 22 (seal failure)

DEGRADATION_ASSETS = {
    "GC-002": {
        "tag": "BEAR_TEMP",
        "start_day": 15,     # degradation starts on day 15
        "ramp_per_day": 1.8, # +1.8 degC per day
        "noise_mult": 1.5,   # noise increases too
    },
    "GT-001": {
        "tag": "EXHAUST_TEMP",
        "start_day": 20,
        "ramp_per_day": 3.5,
        "noise_mult": 1.3,
    },
}

FAILURE_ASSET = {
    "asset_id": "CP-004",
    "failure_day": 22,
    "tags_affected": {
        "VIB_X":       {"spike_mult": 4.0, "post_value": 0.0},
        "FLOW_RATE":   {"spike_mult": 0.3, "post_value": 0.0},
        "BEAR_TEMP":   {"spike_mult": 2.0, "post_value": 25.0},  # ambient = shutdown
        "MOT_CURRENT": {"spike_mult": 2.5, "post_value": 0.0},
    },
    "downtime_days": 3,  # asset offline for 3 days after failure
}

# ============================================================
# GENERATE TIMESTAMPS
# ============================================================
timestamps = pd.date_range(start=START_DATE, end=END_DATE, freq=f"{INTERVAL_MIN}min")
n_steps = len(timestamps)
print(f"Generating {n_steps} time steps ({INTERVAL_MIN}-min intervals over 30 days)")

# ============================================================
# GENERATE Pi SENSOR READINGS
# ============================================================
print("\n[1/3] Generating OSI Pi sensor telemetry...")

rows = []
total_tags = 0

for asset in ASSETS:
    aid = asset["asset_id"]
    atype = asset["type"]
    tags = SENSOR_PROFILES[atype]
    total_tags += len(tags)

    for tag_suffix, unit, base, noise_std, desc in tags:
        tag_name = f"{aid}.{tag_suffix}"

        # Base signal with Gaussian noise
        values = base + np.random.normal(0, noise_std, n_steps)

        # Add diurnal pattern (±3% swing, peaks at 14:00)
        hours = np.array([t.hour + t.minute / 60 for t in timestamps])
        diurnal = base * 0.03 * np.sin(2 * np.pi * (hours - 6) / 24)
        values += diurnal

        # Add weekly pattern (slight load reduction on weekends, ±1.5%)
        weekdays = np.array([t.weekday() for t in timestamps])
        weekend_factor = np.where(weekdays >= 5, -base * 0.015, 0)
        values += weekend_factor

        # Apply degradation if applicable
        if aid in DEGRADATION_ASSETS:
            deg = DEGRADATION_ASSETS[aid]
            if tag_suffix == deg["tag"]:
                days_elapsed = np.array([(t - START_DATE).total_seconds() / 86400 for t in timestamps])
                ramp = np.where(days_elapsed >= deg["start_day"],
                                (days_elapsed - deg["start_day"]) * deg["ramp_per_day"],
                                0)
                values += ramp
                # Increase noise during degradation
                extra_noise = np.where(days_elapsed >= deg["start_day"],
                                       np.random.normal(0, noise_std * (deg["noise_mult"] - 1), n_steps),
                                       0)
                values += extra_noise

        # Apply failure scenario if applicable
        if aid == FAILURE_ASSET["asset_id"] and tag_suffix in FAILURE_ASSET["tags_affected"]:
            fail_cfg = FAILURE_ASSET["tags_affected"][tag_suffix]
            days_elapsed = np.array([(t - START_DATE).total_seconds() / 86400 for t in timestamps])
            fail_day = FAILURE_ASSET["failure_day"]
            down_days = FAILURE_ASSET["downtime_days"]

            # 2 hours before failure: erratic readings
            pre_fail = (days_elapsed >= fail_day - 0.08) & (days_elapsed < fail_day)
            values[pre_fail] *= (1 + np.random.uniform(-0.3, 0.5, pre_fail.sum()))

            # Failure moment: spike
            fail_moment = (days_elapsed >= fail_day) & (days_elapsed < fail_day + 0.01)
            values[fail_moment] = base * fail_cfg["spike_mult"]

            # Downtime: asset offline
            offline = (days_elapsed >= fail_day + 0.01) & (days_elapsed < fail_day + down_days)
            values[offline] = fail_cfg["post_value"]

            # Post-repair: comes back at slightly different baseline
            post_repair = days_elapsed >= fail_day + down_days
            values[post_repair] = base * 0.95 + np.random.normal(0, noise_std * 0.8, post_repair.sum())

        # Clamp to physically reasonable (no negatives for most sensors)
        if unit not in ["%"]:
            values = np.maximum(values, 0)
        if unit == "%":
            values = np.clip(values, 0, 100)

        # Round to realistic precision
        if unit in ["RPM", "kW", "V"]:
            values = np.round(values, 0)
        elif unit in ["A", "m3/hr", "kg/hr", "MMSCFD"]:
            values = np.round(values, 1)
        else:
            values = np.round(values, 2)

        for i in range(n_steps):
            rows.append({
                "timestamp": timestamps[i].strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tag_name": tag_name,
                "asset_id": aid,
                "value": values[i],
                "unit": unit,
                "quality": "Good" if not (aid == FAILURE_ASSET["asset_id"]
                                          and tag_suffix in FAILURE_ASSET["tags_affected"]
                                          and FAILURE_ASSET["failure_day"] <= (timestamps[i] - START_DATE).total_seconds() / 86400 < FAILURE_ASSET["failure_day"] + FAILURE_ASSET["downtime_days"])
                           else "Bad - Device Failure",
            })

    print(f"  ✓ {aid} ({atype}) — {len(tags)} tags")

df_pi = pd.DataFrame(rows)
pi_path = os.path.join(OUTPUT_DIR, "pi_sensor_readings.csv")
df_pi.to_csv(pi_path, index=False)
print(f"\n  Saved: {pi_path}")
print(f"  Total rows: {len(df_pi):,}")
print(f"  Total unique tags: {total_tags}")
print(f"  File size: {os.path.getsize(pi_path) / (1024*1024):.1f} MB")

# ============================================================
# GENERATE EQUIPMENT MASTER (SAP PM)
# ============================================================
print("\n[2/3] Generating SAP Equipment Master...")

eq_rows = []
for asset in ASSETS:
    install_date = datetime(2026 - asset["age_years"], 1, 15)
    eq_rows.append({
        "equipment_number": asset["asset_id"],
        "description": asset["name"],
        "equipment_type": asset["type"],
        "functional_location": f"OG-FIELD-{asset['area'].upper().replace(' ', '-')}",
        "plant": "1000",
        "planning_plant": "1000",
        "cost_center": f"CC-{asset['area'].upper().replace(' ', '-')}",
        "manufacturer": asset["manufacturer"],
        "model_number": f"{asset['manufacturer'][:3].upper()}-{np.random.randint(1000,9999)}",
        "serial_number": f"SN-{np.random.randint(100000,999999)}",
        "installation_date": install_date.strftime("%Y-%m-%d"),
        "age_years": asset["age_years"],
        "lifecycle_stage": asset["lifecycle"],
        "criticality": asset["criticality"],
        "abc_indicator": "A" if asset["criticality"] == "High" else ("B" if asset["criticality"] == "Medium" else "C"),
        "warranty_end_date": (install_date + timedelta(days=365*2)).strftime("%Y-%m-%d"),
        "weight_kg": np.random.randint(500, 15000),
        "status": "AVLB" if asset["asset_id"] != "CP-004" else "BRKD",
    })

df_eq = pd.DataFrame(eq_rows)
eq_path = os.path.join(OUTPUT_DIR, "equipment_master.csv")
df_eq.to_csv(eq_path, index=False)
print(f"  Saved: {eq_path}")
print(f"  Total assets: {len(df_eq)}")

# ============================================================
# GENERATE MAINTENANCE WORK ORDERS (SAP PM)
# ============================================================
print("\n[3/3] Generating SAP Maintenance Work Orders...")

wo_types = [
    ("PM01", "Corrective Maintenance",  "Breakdown"),
    ("PM02", "Preventive Maintenance",  "Scheduled"),
    ("PM03", "Condition-Based Maintenance", "CBM"),
    ("PM04", "Inspection",              "Routine"),
]

priority_map = {"High": "1-Emergency", "Medium": "2-Urgent", "Low": "3-Normal"}
wo_rows = []
wo_counter = 4000000

for asset in ASSETS:
    aid = asset["asset_id"]
    crit = asset["criticality"]

    # Scheduled PMs: every 7-14 days depending on criticality
    pm_interval = 7 if crit == "High" else (10 if crit == "Medium" else 14)
    pm_date = START_DATE + timedelta(days=np.random.randint(1, pm_interval))
    while pm_date < END_DATE:
        wo_counter += 1
        created = pm_date - timedelta(days=np.random.randint(2, 5))
        completed = pm_date + timedelta(hours=np.random.randint(2, 8))
        wo_rows.append({
            "work_order": f"WO-{wo_counter}",
            "equipment_number": aid,
            "order_type": "PM02",
            "order_type_desc": "Preventive Maintenance",
            "activity_type": "Scheduled",
            "priority": "3-Normal",
            "status": "TECO",
            "short_text": f"Scheduled PM - {asset['name']}",
            "created_date": created.strftime("%Y-%m-%d"),
            "scheduled_start": pm_date.strftime("%Y-%m-%d"),
            "actual_start": pm_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "actual_finish": completed.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "downtime_hours": round(np.random.uniform(1, 4), 1),
            "total_cost_usd": round(np.random.uniform(800, 5000), 2),
            "functional_location": f"OG-FIELD-{asset['area'].upper().replace(' ', '-')}",
            "planner_group": "MNT-01",
            "work_center": "MECH-01",
        })
        pm_date += timedelta(days=pm_interval + np.random.randint(-1, 2))

    # Random corrective WOs (1-3 per asset over 30 days)
    n_corrective = np.random.randint(0, 3) if crit != "High" else np.random.randint(1, 4)
    for _ in range(n_corrective):
        wo_counter += 1
        wo_date = START_DATE + timedelta(days=np.random.randint(1, 29))
        created = wo_date - timedelta(hours=np.random.randint(0, 4))
        duration_hrs = round(np.random.uniform(2, 24), 1)
        completed = wo_date + timedelta(hours=duration_hrs)

        fault_descriptions = [
            f"High vibration alarm on {asset['name']}",
            f"Abnormal noise detected - {asset['name']}",
            f"Seal leak repair - {asset['name']}",
            f"Bearing replacement - {asset['name']}",
            f"Instrument calibration issue - {asset['name']}",
            f"Lubrication system fault - {asset['name']}",
            f"Overtemperature trip - {asset['name']}",
        ]

        wo_rows.append({
            "work_order": f"WO-{wo_counter}",
            "equipment_number": aid,
            "order_type": "PM01",
            "order_type_desc": "Corrective Maintenance",
            "activity_type": "Breakdown",
            "priority": priority_map.get(crit, "3-Normal"),
            "status": "TECO",
            "short_text": np.random.choice(fault_descriptions),
            "created_date": created.strftime("%Y-%m-%d"),
            "scheduled_start": wo_date.strftime("%Y-%m-%d"),
            "actual_start": wo_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "actual_finish": completed.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "downtime_hours": duration_hrs,
            "total_cost_usd": round(np.random.uniform(2000, 25000), 2),
            "functional_location": f"OG-FIELD-{asset['area'].upper().replace(' ', '-')}",
            "planner_group": "MNT-01",
            "work_center": "MECH-01",
        })

    # CBM inspection WOs (1-2 per asset)
    for _ in range(np.random.randint(1, 3)):
        wo_counter += 1
        wo_date = START_DATE + timedelta(days=np.random.randint(1, 28))
        wo_rows.append({
            "work_order": f"WO-{wo_counter}",
            "equipment_number": aid,
            "order_type": "PM04",
            "order_type_desc": "Inspection",
            "activity_type": "Routine",
            "priority": "3-Normal",
            "status": "TECO",
            "short_text": f"Routine inspection - {asset['name']}",
            "created_date": (wo_date - timedelta(days=3)).strftime("%Y-%m-%d"),
            "scheduled_start": wo_date.strftime("%Y-%m-%d"),
            "actual_start": wo_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "actual_finish": (wo_date + timedelta(hours=np.random.randint(1, 3))).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "downtime_hours": 0,
            "total_cost_usd": round(np.random.uniform(200, 800), 2),
            "functional_location": f"OG-FIELD-{asset['area'].upper().replace(' ', '-')}",
            "planner_group": "MNT-01",
            "work_center": "INSP-01",
        })

# Add specific WOs for the degradation/failure assets
# GC-002: CBM work order raised on day 25 due to rising bearing temp
wo_counter += 1
cbm_date = START_DATE + timedelta(days=25)
wo_rows.append({
    "work_order": f"WO-{wo_counter}",
    "equipment_number": "GC-002",
    "order_type": "PM03",
    "order_type_desc": "Condition-Based Maintenance",
    "activity_type": "CBM",
    "priority": "2-Urgent",
    "status": "REL",  # Released, not yet completed
    "short_text": "CBM: Bearing temperature trending high - Booster Compressor A",
    "created_date": cbm_date.strftime("%Y-%m-%d"),
    "scheduled_start": (cbm_date + timedelta(days=2)).strftime("%Y-%m-%d"),
    "actual_start": "",
    "actual_finish": "",
    "downtime_hours": 0,
    "total_cost_usd": 0,
    "functional_location": "OG-FIELD-COMPRESSION",
    "planner_group": "MNT-01",
    "work_center": "MECH-01",
})

# CP-004: Emergency corrective WO on day 22 (seal failure)
wo_counter += 1
fail_date = START_DATE + timedelta(days=22)
wo_rows.append({
    "work_order": f"WO-{wo_counter}",
    "equipment_number": "CP-004",
    "order_type": "PM01",
    "order_type_desc": "Corrective Maintenance",
    "activity_type": "Breakdown",
    "priority": "1-Emergency",
    "status": "TECO",
    "short_text": "EMERGENCY: Mechanical seal failure - Seawater Lift Pump",
    "created_date": fail_date.strftime("%Y-%m-%d"),
    "scheduled_start": fail_date.strftime("%Y-%m-%d"),
    "actual_start": fail_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "actual_finish": (fail_date + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "downtime_hours": 72,
    "total_cost_usd": 48500.00,
    "functional_location": "OG-FIELD-UTILITIES",
    "planner_group": "MNT-01",
    "work_center": "MECH-01",
})

# GT-001: Inspection WO raised on day 28 due to exhaust temp anomaly
wo_counter += 1
gt_date = START_DATE + timedelta(days=28)
wo_rows.append({
    "work_order": f"WO-{wo_counter}",
    "equipment_number": "GT-001",
    "order_type": "PM03",
    "order_type_desc": "Condition-Based Maintenance",
    "activity_type": "CBM",
    "priority": "2-Urgent",
    "status": "CRTD",  # Created, not yet released
    "short_text": "CBM: Exhaust temperature anomaly - Power Gen Turbine A",
    "created_date": gt_date.strftime("%Y-%m-%d"),
    "scheduled_start": (gt_date + timedelta(days=3)).strftime("%Y-%m-%d"),
    "actual_start": "",
    "actual_finish": "",
    "downtime_hours": 0,
    "total_cost_usd": 0,
    "functional_location": "OG-FIELD-POWER-GEN",
    "planner_group": "MNT-01",
    "work_center": "MECH-01",
})

df_wo = pd.DataFrame(wo_rows)
df_wo = df_wo.sort_values("created_date").reset_index(drop=True)
wo_path = os.path.join(OUTPUT_DIR, "maintenance_work_orders.csv")
df_wo.to_csv(wo_path, index=False)
print(f"  Saved: {wo_path}")
print(f"  Total work orders: {len(df_wo)}")

# ============================================================
# SUMMARY STATS
# ============================================================
print("\n" + "=" * 60)
print("DATA GENERATION COMPLETE")
print("=" * 60)
print(f"\n  Files created in: {OUTPUT_DIR}/")
print(f"  ├── pi_sensor_readings.csv      ({len(df_pi):>10,} rows, {os.path.getsize(pi_path)/1024/1024:.1f} MB)")
print(f"  ├── equipment_master.csv         ({len(df_eq):>10,} rows)")
print(f"  └── maintenance_work_orders.csv  ({len(df_wo):>10,} rows)")
print(f"\n  Date range: {START_DATE.date()} → {END_DATE.date()}")
print(f"  Assets: {len(ASSETS)}")
print(f"  Unique Pi tags: {total_tags}")
print(f"  Reading interval: {INTERVAL_MIN} min")
print(f"\n  ANOMALIES EMBEDDED:")
print(f"    ⚠  GC-002  Bearing temp degradation (day 15→30, +1.8°C/day)")
print(f"    ⚠  GT-001  Exhaust temp rise (day 20→30, +3.5°C/day)")
print(f"    🔴 CP-004  Seal failure on day 22, 3-day outage")
print(f"\n  These anomalies are the stories your AI layer should catch.")
