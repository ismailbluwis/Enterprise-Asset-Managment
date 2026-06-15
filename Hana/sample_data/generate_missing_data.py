"""
DATA HIGHWAY — Missing Data Sources Generator
================================================
Generates the data sources missing from the architecture diagram:

  1. failure_history.csv         — Dedicated failure/breakdown log with root cause analysis
  2. compliance_inspections.csv  — Regulatory inspection logs & audit findings
  3. compliance_certificates.csv — Equipment certifications & regulatory compliance records
  4. oem_maintenance_specs.csv   — OEM recommended maintenance intervals & specs
  5. warranty_records.csv        — Warranty coverage, claims, and status
  6. oem_bulletins.csv           — Manufacturer service bulletins & advisories
  7. spare_parts_catalog.csv     — Critical spare parts inventory per asset
  8. pi_load_readings.csv        — Supplemental LOAD sensor data (missing from original Pi gen)

All data is correlated with the 20 Oil & Gas assets from the original generation.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

np.random.seed(99)

START_DATE = datetime(2026, 3, 16, 0, 0, 0)
END_DATE   = datetime(2026, 4, 15, 0, 0, 0)
OUTPUT_DIR = "/home/claude/sample_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Asset registry (same 20 assets)
ASSETS = [
    {"asset_id": "CP-001", "name": "Crude Transfer Pump A",        "type": "Centrifugal Pump",      "area": "Production",     "criticality": "High",   "age_years": 8},
    {"asset_id": "CP-002", "name": "Crude Transfer Pump B",        "type": "Centrifugal Pump",      "area": "Production",     "criticality": "High",   "age_years": 8},
    {"asset_id": "CP-003", "name": "Water Injection Pump",         "type": "Centrifugal Pump",      "area": "Injection",      "criticality": "Medium", "age_years": 5},
    {"asset_id": "CP-004", "name": "Seawater Lift Pump",           "type": "Centrifugal Pump",      "area": "Utilities",      "criticality": "Medium", "age_years": 12},
    {"asset_id": "GC-001", "name": "Export Gas Compressor",        "type": "Gas Compressor",        "area": "Compression",    "criticality": "High",   "age_years": 6},
    {"asset_id": "GC-002", "name": "Booster Compressor A",         "type": "Gas Compressor",        "area": "Compression",    "criticality": "High",   "age_years": 10},
    {"asset_id": "GC-003", "name": "Vapor Recovery Compressor",    "type": "Gas Compressor",        "area": "Compression",    "criticality": "Medium", "age_years": 3},
    {"asset_id": "HX-001", "name": "Crude-Crude Heat Exchanger",   "type": "Heat Exchanger",        "area": "Processing",     "criticality": "Medium", "age_years": 9},
    {"asset_id": "HX-002", "name": "Gas Cooler",                   "type": "Heat Exchanger",        "area": "Compression",    "criticality": "High",   "age_years": 6},
    {"asset_id": "HX-003", "name": "Produced Water Cooler",        "type": "Heat Exchanger",        "area": "Utilities",      "criticality": "Low",    "age_years": 4},
    {"asset_id": "SP-001", "name": "1st Stage Separator",          "type": "Three-Phase Separator", "area": "Processing",     "criticality": "High",   "age_years": 9},
    {"asset_id": "SP-002", "name": "2nd Stage Separator",          "type": "Three-Phase Separator", "area": "Processing",     "criticality": "High",   "age_years": 9},
    {"asset_id": "SP-003", "name": "Test Separator",               "type": "Three-Phase Separator", "area": "Well Testing",   "criticality": "Medium", "age_years": 7},
    {"asset_id": "GT-001", "name": "Power Gen Turbine A",          "type": "Gas Turbine",           "area": "Power Gen",      "criticality": "High",   "age_years": 11},
    {"asset_id": "GT-002", "name": "Power Gen Turbine B",          "type": "Gas Turbine",           "area": "Power Gen",      "criticality": "High",   "age_years": 7},
    {"asset_id": "EM-001", "name": "Pump Drive Motor A",           "type": "Electric Motor",        "area": "Production",     "criticality": "High",   "age_years": 8},
    {"asset_id": "EM-002", "name": "Compressor Drive Motor",       "type": "Electric Motor",        "area": "Compression",    "criticality": "High",   "age_years": 10},
    {"asset_id": "CV-001", "name": "Separator Level Control Valve","type": "Control Valve",         "area": "Processing",     "criticality": "Medium", "age_years": 5},
    {"asset_id": "CV-002", "name": "Compressor Anti-Surge Valve",  "type": "Control Valve",         "area": "Compression",    "criticality": "High",   "age_years": 6},
    {"asset_id": "FP-001", "name": "Fire Water Pump",              "type": "Fire Water Pump",       "area": "Safety Systems", "criticality": "High",   "age_years": 14},
]

# ============================================================
# 1. FAILURE HISTORY — Root cause analysis log
# Goes back 3 years to give AI historical patterns to learn from
# ============================================================
print("[1/8] Generating Failure History (3-year lookback)...")

FAILURE_MODES = {
    "Centrifugal Pump": [
        ("Mechanical Seal Failure",    "Seal",        "Worn seal faces due to abrasive particles in fluid",         "Replace seal assembly, install strainer upstream"),
        ("Bearing Failure",            "Bearing",     "Lubrication starvation from blocked oil line",               "Replace bearing, flush lube oil system"),
        ("Impeller Erosion",           "Impeller",    "Cavitation damage from low NPSH conditions",                 "Replace impeller, adjust suction piping"),
        ("Coupling Misalignment",      "Coupling",    "Thermal growth exceeded alignment tolerance",                "Re-align coupling, install expansion compensation"),
        ("Motor Overload Trip",        "Motor",       "Downstream valve partially closed increasing head",          "Clear valve blockage, recalibrate protection relay"),
    ],
    "Gas Compressor": [
        ("Valve Plate Failure",        "Valve",       "Fatigue cracking from pulsation-induced stress",             "Replace valve plates, install pulsation dampener"),
        ("Bearing Degradation",        "Bearing",     "Contaminated lube oil caused accelerated wear",              "Replace bearing, upgrade oil filtration"),
        ("Piston Ring Wear",           "Piston",      "Normal wear exceeding clearance limits after extended run",   "Replace piston rings, verify cylinder liner condition"),
        ("Intercooler Fouling",        "Cooler",      "Hydrocarbon condensate buildup in cooling passages",         "Clean intercooler, install knockout drum"),
        ("Seal Gas System Failure",    "Seal System", "Instrument air supply pressure drop below minimum",          "Repair air compressor, add backup supply"),
    ],
    "Heat Exchanger": [
        ("Tube Leak",                  "Tubes",       "Galvanic corrosion between dissimilar metals",               "Plug leaking tubes, plan tube bundle replacement"),
        ("Fouling - Shell Side",       "Shell",       "Scale buildup from untreated seawater",                      "Chemical cleaning, improve water treatment"),
        ("Gasket Failure",             "Gasket",      "Thermal cycling exceeded gasket material limits",            "Replace gaskets with spiral wound type"),
    ],
    "Three-Phase Separator": [
        ("Level Control Failure",      "Instruments", "Level transmitter drift from emulsion buildup on sensor",    "Clean/replace transmitter, add chemical injection"),
        ("Pressure Relief Valve Lift", "PRV",         "Downstream restriction caused overpressure condition",       "Clear restriction, recertify PRV"),
        ("Weir Plate Corrosion",       "Internals",   "H2S corrosion on carbon steel weir plates",                 "Replace with duplex stainless steel weir plates"),
    ],
    "Gas Turbine": [
        ("Combustion Liner Crack",     "Combustor",   "Thermal fatigue from frequent start/stop cycles",           "Replace liner segments, reduce start/stop frequency"),
        ("Turbine Blade Fouling",      "Blades",      "Salt deposits from ambient air ingestion",                  "Online wash + offline compressor wash"),
        ("Fuel Nozzle Blockage",       "Fuel System", "Particulate contamination in fuel gas supply",              "Clean nozzles, upgrade fuel gas filtration"),
        ("Exhaust Temp Spread High",   "Combustor",   "Uneven fuel distribution across combustion cans",           "Balance fuel nozzle flow, replace worn nozzles"),
    ],
    "Electric Motor": [
        ("Winding Insulation Failure", "Stator",      "Moisture ingress degraded insulation resistance",           "Rewind stator, improve enclosure sealing"),
        ("Bearing Failure",            "Bearing",     "Grease over-lubrication caused overheating",                "Replace bearing, retrain lubrication personnel"),
        ("VFD Fault",                  "VFD",         "Power supply harmonic distortion exceeded VFD tolerance",   "Install line reactor, upgrade VFD firmware"),
    ],
    "Control Valve": [
        ("Actuator Diaphragm Failure", "Actuator",    "Diaphragm material degraded from chemical exposure",       "Replace diaphragm, upgrade to chemical-resistant material"),
        ("Trim Erosion",               "Trim",        "High-velocity flow with entrained sand particles",          "Replace trim with tungsten carbide, add desander"),
        ("Positioner Calibration Drift","Positioner",  "Electronic positioner board component aging",              "Recalibrate positioner, schedule replacement"),
    ],
    "Fire Water Pump": [
        ("Diesel Engine Start Failure","Engine",      "Battery bank degradation below starting threshold",         "Replace battery bank, add trickle charger monitoring"),
        ("Impeller Corrosion",         "Impeller",    "Seawater corrosion on cast iron impeller",                  "Replace with bronze impeller, add cathodic protection"),
        ("Jockey Pump Failure",        "Jockey Pump", "Mechanical seal failure on jockey pump from dry running",   "Replace jockey pump seal, install low-flow alarm"),
    ],
}

SEVERITY_LEVELS = ["Minor", "Moderate", "Major", "Critical"]
DETECTION_METHODS = ["Operator Round", "Control Room Alarm", "Vibration Monitoring", "Visual Inspection",
                     "Thermography", "Oil Analysis", "Performance Deviation", "Scheduled Inspection"]

fail_rows = []
fail_counter = 5000
lookback_start = datetime(2023, 3, 16)  # 3-year lookback

for asset in ASSETS:
    aid = asset["asset_id"]
    atype = asset["type"]
    modes = FAILURE_MODES[atype]
    
    # Number of failures over 3 years: more for older/critical assets
    base_failures = 3
    age_factor = max(0, (asset["age_years"] - 5)) // 2
    crit_factor = 2 if asset["criticality"] == "High" else (1 if asset["criticality"] == "Medium" else 0)
    n_failures = base_failures + age_factor + crit_factor + np.random.randint(0, 3)
    
    for _ in range(n_failures):
        fail_counter += 1
        mode = modes[np.random.randint(0, len(modes))]
        fail_date = lookback_start + timedelta(days=int(np.random.randint(0, 1095)))  # random across 3 years
        detection_lag_hrs = np.random.choice([0, 0, 0, 2, 4, 8, 24, 48], p=[0.3, 0.15, 0.15, 0.1, 0.1, 0.08, 0.07, 0.05])
        repair_hrs = np.random.choice([4, 8, 12, 16, 24, 48, 72, 168], p=[0.15, 0.25, 0.2, 0.15, 0.1, 0.08, 0.05, 0.02])
        severity = np.random.choice(SEVERITY_LEVELS, p=[0.25, 0.35, 0.25, 0.15])
        
        production_loss = 0
        if severity in ["Major", "Critical"]:
            production_loss = round(np.random.uniform(50, 500) * (repair_hrs / 24), 2)  # barrels lost
        
        fail_rows.append({
            "failure_id": f"FL-{fail_counter}",
            "equipment_number": aid,
            "equipment_name": asset["name"],
            "equipment_type": atype,
            "failure_date": fail_date.strftime("%Y-%m-%d"),
            "failure_mode": mode[0],
            "failed_component": mode[1],
            "root_cause": mode[2],
            "corrective_action": mode[3],
            "severity": severity,
            "detection_method": np.random.choice(DETECTION_METHODS),
            "detection_to_failure_hrs": detection_lag_hrs,
            "time_to_repair_hrs": repair_hrs,
            "total_downtime_hrs": detection_lag_hrs + repair_hrs,
            "production_loss_bbl": production_loss,
            "repair_cost_usd": round(np.random.uniform(1500, 85000) * (1 if severity != "Critical" else 2.5), 2),
            "was_predictable": np.random.choice(["Yes", "No", "Partially"], p=[0.3, 0.4, 0.3]),
            "linked_work_order": f"WO-{np.random.randint(3000000, 4000000)}",
        })

# Add specific failures for our anomaly assets
fail_counter += 1
fail_rows.append({
    "failure_id": f"FL-{fail_counter}",
    "equipment_number": "CP-004",
    "equipment_name": "Seawater Lift Pump",
    "equipment_type": "Centrifugal Pump",
    "failure_date": "2026-04-07",
    "failure_mode": "Mechanical Seal Failure",
    "failed_component": "Seal",
    "root_cause": "Worn seal faces due to abrasive particles in seawater — no upstream strainer installed",
    "corrective_action": "Emergency seal replacement, installed 50-micron strainer upstream, ordered duplex SS seal upgrade",
    "severity": "Critical",
    "detection_method": "Control Room Alarm",
    "detection_to_failure_hrs": 0,
    "time_to_repair_hrs": 72,
    "total_downtime_hrs": 72,
    "production_loss_bbl": 4500.0,
    "repair_cost_usd": 48500.00,
    "was_predictable": "Yes",
    "linked_work_order": "WO-4000148",
})

df_fail = pd.DataFrame(fail_rows).sort_values("failure_date").reset_index(drop=True)
path = os.path.join(OUTPUT_DIR, "failure_history.csv")
df_fail.to_csv(path, index=False)
print(f"  Saved: {path} — {len(df_fail)} records (3-year lookback)")


# ============================================================
# 2. COMPLIANCE INSPECTIONS — Regulatory inspection logs
# ============================================================
print("\n[2/8] Generating Compliance Inspection Logs...")

INSPECTION_TYPES = [
    ("API 510",        "Pressure Vessel Inspection",     ["Three-Phase Separator", "Heat Exchanger"]),
    ("API 570",        "Piping Inspection",               ["Centrifugal Pump", "Gas Compressor", "Heat Exchanger"]),
    ("API 612",        "Special Purpose Steam Turbine",   ["Gas Turbine"]),
    ("API 617",        "Axial & Centrifugal Compressor",  ["Gas Compressor"]),
    ("NFPA 20",        "Fire Pump Inspection",            ["Fire Water Pump"]),
    ("OSHA PSM",       "Process Safety Management Audit", ["Three-Phase Separator", "Gas Compressor", "Gas Turbine"]),
    ("EPA LDAR",       "Leak Detection & Repair",         ["Gas Compressor", "Control Valve", "Three-Phase Separator"]),
    ("ISA 84 / IEC 61511", "SIF/SIL Verification",       ["Control Valve", "Three-Phase Separator"]),
    ("API 580/581",    "Risk-Based Inspection (RBI)",     ["Centrifugal Pump", "Gas Compressor", "Heat Exchanger", "Three-Phase Separator"]),
    ("Vibration ISO 10816", "Vibration Analysis Survey",  ["Centrifugal Pump", "Gas Compressor", "Electric Motor", "Gas Turbine"]),
]

FINDINGS = [
    "No defects found — equipment in good condition",
    "No defects found — equipment in good condition",
    "No defects found — equipment in good condition",
    "Minor surface corrosion on external casing — monitor at next inspection",
    "Wall thickness reading below nominal but above minimum — increase monitoring frequency",
    "Gasket seepage noted at flange joint — schedule replacement at next turnaround",
    "Missing nameplate/identification tag — order replacement",
    "Insulation damage exposing bare metal — repair before next wet season",
    "Vibration levels elevated but within alarm threshold — add to watchlist",
    "Grounding strap disconnected — reconnect and verify",
    "Pressure gauge out of calibration — replaced on site",
    "Emergency shutdown tested — 2-second delay exceeds 1-second target — investigate",
    "Corrosion under insulation (CUI) detected at elbow — requires NDE follow-up",
    "Safety valve set pressure drifted +3% — recertified on site",
    "Leak detected at valve packing — repacked and torqued to spec",
]

RESULTS = ["Pass", "Pass", "Pass", "Pass", "Conditional Pass", "Conditional Pass", "Fail", "N/A — Advisory"]
INSPECTORS = ["J. Martinez (Bureau Veritas)", "R. Campbell (TÜV)", "A. Patel (Intertek)", 
              "S. Kim (Lloyd's Register)", "M. Hassan (DNV)", "T. Rodriguez (ABS Group)"]

insp_rows = []
insp_counter = 7000

for asset in ASSETS:
    applicable = [(code, desc) for code, desc, types in INSPECTION_TYPES if asset["type"] in types]
    
    for reg_code, reg_desc in applicable:
        # 2-4 inspections per applicable standard over past 3 years
        n_insp = np.random.randint(2, 5)
        for i in range(n_insp):
            insp_counter += 1
            insp_date = lookback_start + timedelta(days=int(np.random.randint(0, 1095)))
            next_due = insp_date + timedelta(days=int(np.random.choice([180, 365, 730])))
            result = np.random.choice(RESULTS, p=[0.4, 0.15, 0.15, 0.1, 0.1, 0.05, 0.03, 0.02])
            finding = np.random.choice(FINDINGS)
            if result == "Fail":
                finding = np.random.choice(FINDINGS[11:])  # pick a real finding
            
            insp_rows.append({
                "inspection_id": f"INSP-{insp_counter}",
                "equipment_number": asset["asset_id"],
                "equipment_name": asset["name"],
                "regulatory_standard": reg_code,
                "inspection_type": reg_desc,
                "inspection_date": insp_date.strftime("%Y-%m-%d"),
                "next_due_date": next_due.strftime("%Y-%m-%d"),
                "inspector": np.random.choice(INSPECTORS),
                "inspection_company": np.random.choice(INSPECTORS).split("(")[1].replace(")", ""),
                "result": result,
                "finding": finding,
                "corrective_action_required": "Yes" if result in ["Fail", "Conditional Pass"] else "No",
                "corrective_action_due_date": (insp_date + timedelta(days=int(np.random.randint(30, 90)))).strftime("%Y-%m-%d") if result in ["Fail", "Conditional Pass"] else "",
                "corrective_action_status": np.random.choice(["Open", "Closed", "Overdue"]) if result in ["Fail", "Conditional Pass"] else "N/A",
                "risk_ranking": np.random.choice(["Low", "Medium", "High"], p=[0.5, 0.35, 0.15]),
                "functional_location": f"OG-FIELD-{asset['area'].upper().replace(' ', '-')}",
            })

df_insp = pd.DataFrame(insp_rows).sort_values("inspection_date").reset_index(drop=True)
path = os.path.join(OUTPUT_DIR, "compliance_inspections.csv")
df_insp.to_csv(path, index=False)
print(f"  Saved: {path} — {len(df_insp)} records")


# ============================================================
# 3. COMPLIANCE CERTIFICATES — Equipment certifications
# ============================================================
print("\n[3/8] Generating Compliance Certificates...")

CERT_TYPES = {
    "Centrifugal Pump":      [("ASME B73.1", "Pump Design Certification"), ("API 610", "Centrifugal Pump Compliance"), ("ATEX/IECEx", "Hazardous Area Certification")],
    "Gas Compressor":        [("API 618", "Reciprocating Compressor Cert"), ("PED 2014/68/EU", "Pressure Equipment Directive"), ("ATEX/IECEx", "Hazardous Area Certification")],
    "Heat Exchanger":        [("ASME VIII Div 1", "Pressure Vessel Code Stamp"), ("TEMA", "Heat Exchanger Standards Cert"), ("API 660", "Shell & Tube HX Certification")],
    "Three-Phase Separator": [("ASME VIII Div 1", "Pressure Vessel Code Stamp"), ("API 12J", "Oil & Gas Separator Cert"), ("PED 2014/68/EU", "Pressure Equipment Directive")],
    "Gas Turbine":           [("ISO 3977", "Gas Turbine Procurement Cert"), ("API 616", "Gas Turbine for Refinery Service"), ("NEMA MG-1", "Motor/Generator Standards")],
    "Electric Motor":        [("NEMA MG-1", "Motor Standards Certification"), ("IEEE 841", "Severe Duty Motor Cert"), ("ATEX/IECEx", "Hazardous Area Certification")],
    "Control Valve":         [("ISA/IEC 61511", "Safety Instrumented System"), ("API 6D", "Pipeline Valve Certification"), ("SIL 2/SIL 3", "Safety Integrity Level Cert")],
    "Fire Water Pump":       [("NFPA 20", "Fire Pump Certification"), ("UL/FM", "Fire Protection Equipment Listing"), ("API 610", "Centrifugal Pump Compliance")],
}

cert_rows = []
cert_counter = 9000

for asset in ASSETS:
    certs = CERT_TYPES.get(asset["type"], [])
    install_year = 2026 - asset["age_years"]
    
    for cert_code, cert_desc in certs:
        cert_counter += 1
        issue_date = datetime(install_year, np.random.randint(1, 7), np.random.randint(1, 28))
        validity_years = np.random.choice([3, 5, 5, 10])
        expiry = issue_date + timedelta(days=int(365 * validity_years))
        
        # Renew if expired
        while expiry < datetime(2026, 4, 15):
            issue_date = expiry - timedelta(days=int(np.random.randint(0, 30)))
            expiry = issue_date + timedelta(days=int(365 * validity_years))
        
        days_to_expiry = (expiry - datetime(2026, 4, 15)).days
        
        cert_rows.append({
            "certificate_id": f"CERT-{cert_counter}",
            "equipment_number": asset["asset_id"],
            "equipment_name": asset["name"],
            "certification_standard": cert_code,
            "certificate_description": cert_desc,
            "issuing_body": np.random.choice(["Bureau Veritas", "TÜV Rheinland", "Lloyd's Register", "DNV GL", "ABS Group", "Intertek"]),
            "certificate_number": f"{cert_code.replace(' ', '').replace('/', '-')}-{np.random.randint(100000, 999999)}",
            "issue_date": issue_date.strftime("%Y-%m-%d"),
            "expiry_date": expiry.strftime("%Y-%m-%d"),
            "days_to_expiry": days_to_expiry,
            "status": "Valid" if days_to_expiry > 90 else ("Expiring Soon" if days_to_expiry > 0 else "EXPIRED"),
            "renewal_required": "Yes" if days_to_expiry <= 180 else "No",
            "document_ref": f"DOC-{np.random.randint(10000, 99999)}.pdf",
        })

df_cert = pd.DataFrame(cert_rows).sort_values(["equipment_number", "certification_standard"]).reset_index(drop=True)
path = os.path.join(OUTPUT_DIR, "compliance_certificates.csv")
df_cert.to_csv(path, index=False)
print(f"  Saved: {path} — {len(df_cert)} records")


# ============================================================
# 4. OEM MAINTENANCE SPECIFICATIONS — Manufacturer recommended intervals
# ============================================================
print("\n[4/8] Generating OEM Maintenance Specifications...")

OEM_SPECS = {
    "Centrifugal Pump": {
        "manufacturer": "Sulzer/Flowserve",
        "tasks": [
            ("Bearing lubrication",           "Weekly",    7,    0.5, "Grease bearings per OEM spec — do not over-lubricate"),
            ("Vibration check",               "Weekly",    7,    0.25, "Record DE and NDE vibration. Alert if >7.1 mm/s"),
            ("Mechanical seal inspection",    "Monthly",   30,   1.0, "Check for visible leakage, record leakage rate"),
            ("Coupling alignment check",      "Quarterly", 90,   2.0, "Laser alignment — thermal growth compensation required"),
            ("Impeller clearance check",      "Annual",    365,  4.0, "Measure back-pullout clearance per OEM manual"),
            ("Full pump overhaul",            "5-Year",    1825, 40.0, "Complete teardown, inspect all wetted parts, replace seals/bearings"),
        ],
    },
    "Gas Compressor": {
        "manufacturer": "Atlas Copco/Siemens/Ariel",
        "tasks": [
            ("Lube oil sample & analysis",    "Weekly",    7,    0.5, "Send to lab — flag if particle count >18/16/13 per ISO 4406"),
            ("Vibration monitoring",          "Weekly",    7,    0.25, "Record all measurement points. Alert if >8.0 mm/s"),
            ("Valve inspection",              "Quarterly", 90,   8.0, "Remove and inspect suction/discharge valve plates"),
            ("Piston ring wear check",        "6-Month",   180,  6.0, "Measure ring gap and cylinder bore — compare to limits"),
            ("Intercooler cleaning",          "Annual",    365,  16.0, "Chemical clean, pressure test, verify thermal performance"),
            ("Major overhaul",               "3-Year",    1095, 120.0, "Full teardown — replace all wear parts per OEM schedule"),
        ],
    },
    "Heat Exchanger": {
        "manufacturer": "Alfa Laval/Kelvion",
        "tasks": [
            ("Pressure drop monitoring",      "Daily",     1,    0.1, "Record DP across exchanger — trend for fouling indication"),
            ("Visual external inspection",    "Monthly",   30,   0.5, "Check for leaks, corrosion, insulation damage"),
            ("Tube bundle cleaning",          "Annual",    365,  24.0, "Hydro-blast shell and tube side per OEM procedure"),
            ("Wall thickness survey (NDE)",   "2-Year",    730,  8.0, "UT thickness survey on tubes and shell — compare to nominal"),
        ],
    },
    "Three-Phase Separator": {
        "manufacturer": "Exterran/HC Petroleum",
        "tasks": [
            ("Level instrument calibration",  "Monthly",   30,   1.0, "Calibrate all level transmitters — 3-point check"),
            ("PRV function test",             "Quarterly", 90,   2.0, "Pop test or in-situ test per API 576"),
            ("Internal inspection",           "2-Year",    730,  40.0, "Man-entry inspection of internals, weir plates, demisters"),
            ("Corrosion coupon review",       "Quarterly", 90,   0.5, "Pull and weigh corrosion coupons — calculate mpy rate"),
        ],
    },
    "Gas Turbine": {
        "manufacturer": "GE/Siemens",
        "tasks": [
            ("Online water wash",             "Weekly",    7,    1.0, "Automated online wash — verify differential pressure recovery"),
            ("Borescope inspection",          "Quarterly", 90,   8.0, "Inspect combustion liners, transition pieces, first-stage blades"),
            ("Combustion inspection (CI)",    "8000-hrs",  333,  80.0, "Replace combustion liners, fuel nozzles, transition pieces"),
            ("Hot gas path inspection (HGPI)","24000-hrs", 1000, 200.0, "Full hot section — blades, vanes, seals, bearings"),
            ("Major overhaul",               "48000-hrs", 2000, 500.0, "Complete teardown — rotor, stator, compressor, turbine sections"),
        ],
    },
    "Electric Motor": {
        "manufacturer": "ABB/Siemens",
        "tasks": [
            ("Insulation resistance test",    "Quarterly", 90,   1.0, "Megger test — alert if PI ratio <2.0"),
            ("Bearing lubrication",           "Monthly",   30,   0.5, "Grease per OEM calculated quantity — do NOT over-grease"),
            ("Thermography scan",             "Quarterly", 90,   0.5, "IR scan of junction box, bearings, cooling fins"),
            ("Motor current signature analysis","Annual",  365,  2.0, "MCSA to detect rotor bar/stator faults"),
            ("Full motor overhaul",           "5-Year",    1825, 60.0, "Rewind stator, replace bearings, check rotor balance"),
        ],
    },
    "Control Valve": {
        "manufacturer": "Emerson",
        "tasks": [
            ("Stroke test",                   "Monthly",   30,   0.5, "Full stroke — verify travel, dead band, hysteresis"),
            ("Positioner calibration",        "Quarterly", 90,   1.0, "5-point calibration check and adjust"),
            ("Packing adjustment/replacement","Annual",    365,  2.0, "Check packing leakage, tighten or replace as needed"),
            ("Full valve overhaul",           "3-Year",    1095, 16.0, "Replace trim, actuator diaphragm, positioner if required"),
        ],
    },
    "Fire Water Pump": {
        "manufacturer": "Ruhrpumpen",
        "tasks": [
            ("Weekly run test",               "Weekly",    7,    0.5, "Start and run for 30 min — record suction/discharge pressure, flow"),
            ("Battery bank check",            "Monthly",   30,   0.5, "Check voltage, electrolyte level, tighten connections"),
            ("Annual fire pump performance test","Annual",  365,  4.0, "Full flow test per NFPA 25 — compare to original acceptance curve"),
            ("Diesel engine service",         "Annual",    365,  8.0, "Oil change, filters, belts, injector check per engine OEM"),
        ],
    },
}

oem_rows = []
oem_counter = 0

for asset in ASSETS:
    specs = OEM_SPECS.get(asset["type"])
    if not specs:
        continue
    
    for task_name, frequency, interval_days, duration_hrs, notes in specs["tasks"]:
        oem_counter += 1
        # Calculate next due based on a realistic last-done date
        last_done = END_DATE - timedelta(days=int(np.random.randint(1, max(2, interval_days))))
        next_due = last_done + timedelta(days=interval_days)
        overdue = (next_due < END_DATE)
        
        oem_rows.append({
            "spec_id": f"OEM-{oem_counter:04d}",
            "equipment_number": asset["asset_id"],
            "equipment_name": asset["name"],
            "equipment_type": asset["type"],
            "manufacturer": specs["manufacturer"].split("/")[0] if asset["asset_id"] not in ["CP-003", "CP-004", "HX-003"] else specs["manufacturer"].split("/")[-1],
            "task_name": task_name,
            "frequency": frequency,
            "interval_days": interval_days,
            "estimated_duration_hrs": duration_hrs,
            "last_performed_date": last_done.strftime("%Y-%m-%d"),
            "next_due_date": next_due.strftime("%Y-%m-%d"),
            "overdue": "Yes" if overdue else "No",
            "oem_notes": notes,
            "skill_required": np.random.choice(["Mechanical", "Electrical", "Instrumentation", "Multi-discipline"]),
            "requires_shutdown": "Yes" if duration_hrs >= 8 else "No",
            "oem_manual_ref": f"MAN-{asset['type'][:3].upper()}-{np.random.randint(100, 999)}-{np.random.randint(1, 15):02d}",
        })

df_oem = pd.DataFrame(oem_rows)
path = os.path.join(OUTPUT_DIR, "oem_maintenance_specs.csv")
df_oem.to_csv(path, index=False)
print(f"  Saved: {path} — {len(df_oem)} records")


# ============================================================
# 5. WARRANTY RECORDS
# ============================================================
print("\n[5/8] Generating Warranty Records...")

warr_rows = []
warr_counter = 0

for asset in ASSETS:
    install_year = 2026 - asset["age_years"]
    install_date = datetime(install_year, 1, 15)
    
    # Standard warranty: 2 years from install
    std_start = install_date
    std_end = install_date + timedelta(days=730)
    
    # Extended warranty: some assets purchased extended coverage
    has_extended = np.random.choice([True, False], p=[0.4, 0.6])
    ext_end = std_end + timedelta(days=int(np.random.choice([365, 730, 1095]))) if has_extended else None
    
    active_end = ext_end if ext_end else std_end
    is_active = active_end > datetime(2026, 4, 15)
    
    warr_counter += 1
    warr_rows.append({
        "warranty_id": f"WARR-{warr_counter:04d}",
        "equipment_number": asset["asset_id"],
        "equipment_name": asset["name"],
        "equipment_type": asset["type"],
        "manufacturer": next(v["manufacturer"].split("/")[0] for k, v in OEM_SPECS.items() if k == asset["type"]),
        "purchase_date": (install_date - timedelta(days=int(np.random.randint(60, 180)))).strftime("%Y-%m-%d"),
        "installation_date": install_date.strftime("%Y-%m-%d"),
        "standard_warranty_start": std_start.strftime("%Y-%m-%d"),
        "standard_warranty_end": std_end.strftime("%Y-%m-%d"),
        "extended_warranty": "Yes" if has_extended else "No",
        "extended_warranty_end": ext_end.strftime("%Y-%m-%d") if ext_end else "",
        "warranty_status": "Active" if is_active else "Expired",
        "coverage_type": "Parts & Labor" if is_active else "Expired",
        "exclusions": "Normal wear parts (seals, gaskets, filters), consumables, damage from misoperation",
        "warranty_provider": np.random.choice(["Manufacturer Direct", "Third-Party (Allianz Engineering)", "Third-Party (HSB)"]),
        "total_claims_filed": np.random.randint(0, 4) if not is_active else np.random.randint(0, 2),
        "total_claims_value_usd": round(np.random.uniform(0, 45000), 2),
        "contract_ref": f"PO-{np.random.randint(400000, 499999)}",
    })

df_warr = pd.DataFrame(warr_rows)
path = os.path.join(OUTPUT_DIR, "warranty_records.csv")
df_warr.to_csv(path, index=False)
print(f"  Saved: {path} — {len(df_warr)} records")


# ============================================================
# 6. OEM BULLETINS — Manufacturer service bulletins & advisories
# ============================================================
print("\n[6/8] Generating OEM Service Bulletins...")

BULLETINS = [
    {"bulletin_id": "SB-2024-001", "manufacturer": "Sulzer",       "title": "Impeller Upgrade Advisory for CPT Series Pumps",
     "severity": "Advisory", "affected_types": ["Centrifugal Pump"],
     "summary": "Sulzer recommends upgrading to duplex stainless impellers on CPT series pumps handling >2% sand cut fluids to prevent premature erosion.",
     "action_required": "Evaluate sand cut levels. If >2%, schedule impeller replacement at next turnaround.",
     "issue_date": "2024-06-15", "compliance_deadline": "2025-06-15"},
    
    {"bulletin_id": "SB-2024-007", "manufacturer": "Atlas Copco",  "title": "Valve Plate Material Recall — ZR Series Compressors",
     "severity": "Mandatory", "affected_types": ["Gas Compressor"],
     "summary": "Batch defect identified in valve plate material (lot 2023-Q3). Plates may fatigue prematurely under normal pulsation loads.",
     "action_required": "Check serial numbers against affected lot list. Replace affected plates within 90 days. Replacement parts provided at no cost.",
     "issue_date": "2024-09-01", "compliance_deadline": "2024-12-01"},
    
    {"bulletin_id": "SB-2025-003", "manufacturer": "GE",           "title": "Fuel Nozzle Inspection Interval Reduction — LM2500",
     "severity": "Mandatory", "affected_types": ["Gas Turbine"],
     "summary": "Field reports of accelerated fuel nozzle coking on units operating with >5ppm H2S fuel gas. Inspection interval reduced from 8000 to 4000 equivalent operating hours.",
     "action_required": "Analyze fuel gas composition. If H2S >5ppm, revise PM schedule to 4000 EOH nozzle inspection.",
     "issue_date": "2025-02-20", "compliance_deadline": "2025-08-20"},
    
    {"bulletin_id": "SB-2025-008", "manufacturer": "Emerson",      "title": "Positioner Firmware Update — DVC6200 Series",
     "severity": "Recommended", "affected_types": ["Control Valve"],
     "summary": "Firmware v12.4 resolves intermittent positioner calibration drift observed in high-vibration installations. Free download from Emerson support portal.",
     "action_required": "Update firmware during next scheduled outage. No process shutdown required if bypass available.",
     "issue_date": "2025-05-10", "compliance_deadline": ""},
    
    {"bulletin_id": "SB-2025-011", "manufacturer": "ABB",          "title": "Bearing Grease Compatibility Warning — M3BP Series Motors",
     "severity": "Mandatory", "affected_types": ["Electric Motor"],
     "summary": "Polyurea-based greases (e.g., Mobil SHC 100) found incompatible with factory-installed lithium complex grease. Mixing causes grease hardening and bearing failure.",
     "action_required": "Verify grease type in use. If polyurea, flush bearings completely and repack with OEM-specified lithium complex grease.",
     "issue_date": "2025-07-01", "compliance_deadline": "2025-10-01"},
    
    {"bulletin_id": "SB-2025-015", "manufacturer": "Alfa Laval",   "title": "Gasket Material Upgrade for Sour Service Heat Exchangers",
     "severity": "Advisory", "affected_types": ["Heat Exchanger"],
     "summary": "PTFE-lined spiral wound gaskets recommended over standard graphite for H2S service to prevent hydrogen blistering at flange joints.",
     "action_required": "At next gasket replacement, upgrade to PTFE-lined spiral wound type. No immediate action required if current gaskets show no leakage.",
     "issue_date": "2025-09-12", "compliance_deadline": ""},
    
    {"bulletin_id": "SB-2026-002", "manufacturer": "Ruhrpumpen",   "title": "Battery Charger Module Recall — DFP Series Fire Pumps",
     "severity": "Mandatory", "affected_types": ["Fire Water Pump"],
     "summary": "Charger module PCB revision A through C may fail to detect low battery condition, risking engine start failure during emergency.",
     "action_required": "Inspect charger module PCB revision. If Rev A-C, replace with Rev D module (warranty replacement, contact distributor).",
     "issue_date": "2026-01-18", "compliance_deadline": "2026-04-18"},

    {"bulletin_id": "SB-2026-004", "manufacturer": "Exterran",     "title": "Internal Coating Inspection Requirement — HP Separators",
     "severity": "Advisory", "affected_types": ["Three-Phase Separator"],
     "summary": "Units >7 years in sour service should undergo internal coating integrity inspection. Epoxy phenolic coatings may degrade under sustained H2S exposure.",
     "action_required": "Schedule internal inspection at next planned entry. If coating degradation >30%, plan recoating at next turnaround.",
     "issue_date": "2026-03-05", "compliance_deadline": ""},
]

bull_rows = []
for bull in BULLETINS:
    affected_assets = [a for a in ASSETS if a["type"] in bull["affected_types"]]
    for asset in affected_assets:
        bull_rows.append({
            "bulletin_id": bull["bulletin_id"],
            "equipment_number": asset["asset_id"],
            "equipment_name": asset["name"],
            "manufacturer": bull["manufacturer"],
            "title": bull["title"],
            "severity": bull["severity"],
            "summary": bull["summary"],
            "action_required": bull["action_required"],
            "issue_date": bull["issue_date"],
            "compliance_deadline": bull["compliance_deadline"],
            "compliance_status": np.random.choice(["Complied", "In Progress", "Not Started", "Overdue"],
                                                   p=[0.4, 0.25, 0.2, 0.15]) if bull["severity"] == "Mandatory"
                                 else np.random.choice(["Acknowledged", "Planned", "Not Reviewed"], p=[0.4, 0.35, 0.25]),
        })

df_bull = pd.DataFrame(bull_rows)
path = os.path.join(OUTPUT_DIR, "oem_bulletins.csv")
df_bull.to_csv(path, index=False)
print(f"  Saved: {path} — {len(df_bull)} records")


# ============================================================
# 7. SPARE PARTS CATALOG — Critical spares per asset
# ============================================================
print("\n[7/8] Generating Spare Parts Catalog...")

SPARES = {
    "Centrifugal Pump": [
        ("Mechanical Seal Assembly",   "SPR-SEAL",  4500,   2, 16, "Replace every 2 years or on failure"),
        ("Bearing Set (DE + NDE)",     "SPR-BRG",   1200,   2, 8,  "SKF 6316 or equivalent"),
        ("Impeller",                   "SPR-IMP",   8500,   1, 26, "Match to pump curve revision"),
        ("Coupling Element",          "SPR-CPL",   2200,   1, 12, "Flexible disc coupling insert"),
        ("Wear Ring Set",             "SPR-WR",    900,    2, 10, "Front and back wear rings"),
    ],
    "Gas Compressor": [
        ("Valve Plate Set (S+D)",      "SPR-VLV",   6200,   4, 14, "Keep 2x sets minimum for multi-stage"),
        ("Piston Ring Set",            "SPR-PR",    3800,   2, 12, "Per cylinder — match material to gas composition"),
        ("Main Bearing Set",          "SPR-MBR",   4500,   1, 20, "White metal or tilting pad per OEM"),
        ("Intercooler Gasket Set",    "SPR-ICG",   800,    2, 6,  "Full set for both stages"),
        ("Seal Gas Filter Elements",  "SPR-SGF",   350,    6, 4,  "Coalescing type, 0.3 micron"),
    ],
    "Heat Exchanger": [
        ("Gasket Set (Full)",          "SPR-GSK",   3200,   2, 8,  "Spiral wound + O-rings for entire unit"),
        ("Tube Bundle",               "SPR-TB",    45000,  0, 52, "Long lead item — order well in advance"),
        ("Zinc Anodes",               "SPR-ZA",    600,    4, 2,  "Cathodic protection — seawater side"),
    ],
    "Three-Phase Separator": [
        ("Level Transmitter",          "SPR-LT",    2800,   2, 12, "Guided wave radar type"),
        ("Pressure Relief Valve",     "SPR-PRV",   5500,   1, 16, "Must match set pressure and orifice size"),
        ("Demister Pad",              "SPR-DMP",   1800,   1, 20, "Knitted mesh — match metallurgy to service"),
    ],
    "Gas Turbine": [
        ("Combustion Liner Set",       "SPR-CL",    85000,  1, 40, "GE/Siemens OEM only — no aftermarket"),
        ("Fuel Nozzle Set",           "SPR-FN",    32000,  1, 36, "12x nozzles per turbine"),
        ("Turbine Blade Set (1st Stage)","SPR-TB1", 120000, 0, 52, "Critical long-lead — maintain blanket PO"),
        ("Thermocouple Set (Exhaust)", "SPR-TC",   3500,   2, 4,  "12x T/C per turbine, Type K"),
    ],
    "Electric Motor": [
        ("Bearing Set",               "SPR-BRG",   1800,   2, 8,  "Match to OEM bearing schedule"),
        ("Space Heater Element",      "SPR-SH",    400,    2, 4,  "Anti-condensation heater"),
        ("Terminal Box Gasket",       "SPR-TBG",   150,    4, 2,  "Replace at every opening"),
    ],
    "Control Valve": [
        ("Trim Kit",                   "SPR-TRM",   4200,   2, 14, "Plug + seat + cage — match to Cv"),
        ("Actuator Diaphragm",        "SPR-DPH",   1500,   2, 8,  "Nitrile or EPDM per service"),
        ("Packing Set",               "SPR-PCK",   600,    4, 4,  "PTFE/graphite combination"),
        ("Positioner Module",         "SPR-POS",   3800,   1, 16, "DVC6200 or equivalent"),
    ],
    "Fire Water Pump": [
        ("Starter Battery Bank",       "SPR-BAT",   2200,   1, 4,  "24V DC lead-acid bank"),
        ("Impeller (Bronze)",         "SPR-IMP",   6500,   1, 20, "Bronze alloy for seawater service"),
        ("Fuel Injector Set",         "SPR-FI",    1800,   1, 8,  "Diesel engine — 6 cylinder set"),
        ("Mechanical Seal",           "SPR-SEAL",  3200,   1, 12, "Tungsten carbide for abrasive service"),
    ],
}

spare_rows = []
spare_counter = 0

for asset in ASSETS:
    parts = SPARES.get(asset["type"], [])
    for part_name, part_code, unit_cost, qty_on_hand, lead_weeks, notes in parts:
        spare_counter += 1
        min_qty = max(1, qty_on_hand)
        reorder = qty_on_hand <= 1
        
        spare_rows.append({
            "spare_id": f"SP-{spare_counter:05d}",
            "equipment_number": asset["asset_id"],
            "equipment_name": asset["name"],
            "part_name": part_name,
            "part_number": f"{part_code}-{asset['asset_id']}",
            "manufacturer_part_number": f"{asset['type'][:3].upper()}-{np.random.randint(10000, 99999)}",
            "unit_cost_usd": unit_cost,
            "quantity_on_hand": qty_on_hand,
            "minimum_stock_qty": min_qty,
            "reorder_required": "Yes" if reorder else "No",
            "lead_time_weeks": lead_weeks,
            "storage_location": f"WH-{np.random.choice(['A', 'B', 'C'])}{np.random.randint(1, 20):02d}",
            "last_used_date": (END_DATE - timedelta(days=int(np.random.randint(30, 365)))).strftime("%Y-%m-%d"),
            "criticality": "Critical" if lead_weeks >= 20 else ("Important" if lead_weeks >= 10 else "Standard"),
            "notes": notes,
        })

df_spare = pd.DataFrame(spare_rows)
path = os.path.join(OUTPUT_DIR, "spare_parts_catalog.csv")
df_spare.to_csv(path, index=False)
print(f"  Saved: {path} — {len(df_spare)} records")


# ============================================================
# 8. SUPPLEMENTAL LOAD SENSOR DATA — Missing from original Pi gen
# ============================================================
print("\n[8/8] Generating Supplemental Load Sensor Readings...")

timestamps = pd.date_range(start=START_DATE, end=END_DATE, freq="15min")
n_steps = len(timestamps)

LOAD_PROFILES = {
    "Centrifugal Pump":      ("LOAD_PCT",  "%",   72.0,  5.0,  "Pump load as % of rated capacity"),
    "Gas Compressor":        ("LOAD_PCT",  "%",   78.0,  6.0,  "Compressor load as % of rated capacity"),
    "Gas Turbine":           ("LOAD_PCT",  "%",   85.0,  4.0,  "Turbine load as % of rated output"),
    "Electric Motor":        ("LOAD_PCT",  "%",   68.0,  5.0,  "Motor load as % of rated power"),
    "Fire Water Pump":       ("LOAD_PCT",  "%",   15.0,  3.0,  "Standby load — spikes during weekly test"),
}

load_rows = []
for asset in ASSETS:
    if asset["type"] not in LOAD_PROFILES:
        continue
    
    tag_suffix, unit, base, noise, desc = LOAD_PROFILES[asset["type"]]
    tag_name = f"{asset['asset_id']}.{tag_suffix}"
    
    values = base + np.random.normal(0, noise, n_steps)
    
    # Diurnal: higher load during day shift
    hours = np.array([t.hour + t.minute / 60 for t in timestamps])
    diurnal = base * 0.05 * np.sin(2 * np.pi * (hours - 6) / 24)
    values += diurnal
    
    # Weekend dip
    weekdays = np.array([t.weekday() for t in timestamps])
    values += np.where(weekdays >= 5, -base * 0.08, 0)
    
    # Fire water pump: spike during weekly test (Wednesday 10:00-10:30)
    if asset["type"] == "Fire Water Pump":
        is_test = (weekdays == 2) & (hours >= 10) & (hours < 10.5)
        values[is_test] = 95.0 + np.random.normal(0, 2, is_test.sum())
    
    # CP-004 failure: load drops to 0 during downtime
    if asset["asset_id"] == "CP-004":
        days_elapsed = np.array([(t - START_DATE).total_seconds() / 86400 for t in timestamps])
        offline = (days_elapsed >= 22.01) & (days_elapsed < 25)
        values[offline] = 0.0
    
    values = np.clip(np.round(values, 1), 0, 100)
    
    for i in range(n_steps):
        load_rows.append({
            "timestamp": timestamps[i].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tag_name": tag_name,
            "asset_id": asset["asset_id"],
            "value": values[i],
            "unit": unit,
            "quality": "Good",
        })

df_load = pd.DataFrame(load_rows)
path = os.path.join(OUTPUT_DIR, "pi_load_readings.csv")
df_load.to_csv(path, index=False)
print(f"  Saved: {path} — {len(df_load):,} rows ({os.path.getsize(path)/1024/1024:.1f} MB)")


# ============================================================
# FINAL SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("ALL MISSING DATA SOURCES GENERATED")
print("=" * 60)

files = [
    ("failure_history.csv",          len(df_fail),  "3-year failure log with root cause analysis"),
    ("compliance_inspections.csv",   len(df_insp),  "Regulatory inspection logs (API, OSHA, EPA, NFPA)"),
    ("compliance_certificates.csv",  len(df_cert),  "Equipment certifications & expiry tracking"),
    ("oem_maintenance_specs.csv",    len(df_oem),   "OEM recommended maintenance intervals"),
    ("warranty_records.csv",         len(df_warr),   "Warranty coverage, claims, status"),
    ("oem_bulletins.csv",            len(df_bull),   "Manufacturer service bulletins & advisories"),
    ("spare_parts_catalog.csv",      len(df_spare),  "Critical spare parts inventory"),
    ("pi_load_readings.csv",         len(df_load),   "Supplemental LOAD sensor data"),
]

print(f"\n  Files created in: {OUTPUT_DIR}/\n")
for fname, count, desc in files:
    fpath = os.path.join(OUTPUT_DIR, fname)
    size = os.path.getsize(fpath)
    size_str = f"{size/1024:.0f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB"
    print(f"  ├── {fname:<36s} {count:>6,} rows  ({size_str:>8s})  {desc}")

print(f"\n  ARCHITECTURE COVERAGE:")
print(f"    ✓ IoT Sensors       → pi_sensor_readings.csv + pi_load_readings.csv")
print(f"    ✓ SAP EAM / PM      → maintenance_work_orders.csv + failure_history.csv")
print(f"    ✓ Asset Master       → equipment_master.csv")
print(f"    ✓ SCADA / OSI Pi     → pi_sensor_readings.csv (30-day trending + process data)")
print(f"    ✓ Compliance DB      → compliance_inspections.csv + compliance_certificates.csv")
print(f"    ✓ External / OEM     → oem_maintenance_specs.csv + warranty_records.csv + oem_bulletins.csv + spare_parts_catalog.csv")
print(f"\n  ALL 6 DATA SOURCES FROM ARCHITECTURE DIAGRAM: COVERED ✓")
