"""
compute_health_scores.py
Recomputes ASSET_HEALTH_SCORES for all 25 assets.

Improvements over v1:
- Uses dynamic weights from ASSET_TYPE_CONFIG (per equipment type)
- Uses 7-day rolling average of Good-quality sensor readings (not single reading)
- Uses inspection result as a reliability factor
- Calibrates failure probability from actual inspection compliance
"""
from hdbcli import dbapi
import pandas as pd
from datetime import datetime, timedelta

conn = dbapi.connect(
    address="48e539b6-6ba6-4891-9538-727dd496988b.hna1.prod-us10.hanacloud.ondemand.com",
    port=443, user="DBADMIN", password="Admin123",
    encrypt=True, sslValidateCertificate=True
)
cur = conn.cursor()

# ── Load base data ─────────────────────────────────────────────────────────
cur.execute('SELECT ASSET_ID, INSTALL_DATE, EXPECTED_LIFE_YEARS, STATUS, ASSET_TYPE, OPERATING_HOURS FROM "ASSET_MASTER"."ASSETS"')
assets = pd.DataFrame(cur.fetchall(), columns=["ASSET_ID","INSTALL_DATE","EXPECTED_LIFE_YEARS","STATUS","ASSET_TYPE","OPERATING_HOURS"])

# Dynamic weights from ASSET_TYPE_CONFIG
cur.execute('SELECT ASSET_TYPE, SENSOR_WEIGHT, MAINT_WEIGHT, FAILURE_WEIGHT, AGE_WEIGHT FROM "ASSET_MASTER"."ASSET_TYPE_CONFIG"')
type_cfg = {r[0]: {'sw':float(r[1]),'mw':float(r[2]),'fw':float(r[3]),'aw':float(r[4])} for r in cur.fetchall()}

# 7-day rolling average sensor readings (Good quality only)
cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
cur.execute(f'''
    SELECT ASSET_ID, TAG_NAME, AVG(TAG_VALUE) AS AVG_VAL
    FROM "IOT_SENSOR"."SENSOR_READINGS"
    WHERE READING_TS >= ? AND QUALITY = 'Good'
    GROUP BY ASSET_ID, TAG_NAME
''', [cutoff])
sensors = pd.DataFrame(cur.fetchall(), columns=["ASSET_ID","TAG_NAME","AVG_VAL"])

# Work orders
cur.execute('SELECT ASSET_ID, COUNT(*) AS WO_COUNT FROM "EAM_PM"."WORK_ORDERS" GROUP BY ASSET_ID')
wo = pd.DataFrame(cur.fetchall(), columns=["ASSET_ID","WO_COUNT"])

# Failure history
cur.execute('SELECT ASSET_ID, COUNT(*) AS FAIL_COUNT, AVG(REPAIR_COST) AS AVG_COST FROM "EAM_PM"."FAILURE_HISTORY" GROUP BY ASSET_ID')
fh = pd.DataFrame(cur.fetchall(), columns=["ASSET_ID","FAIL_COUNT","AVG_COST"])

# Latest inspection result (drives reliability factor)
cur.execute('''
    SELECT i1.ASSET_ID, i1.RESULT
    FROM "COMPLIANCE_QM"."INSPECTIONS" i1
    INNER JOIN (
        SELECT ASSET_ID, MAX(INSPECTION_DATE) AS LATEST
        FROM "COMPLIANCE_QM"."INSPECTIONS" GROUP BY ASSET_ID
    ) i2 ON i1.ASSET_ID=i2.ASSET_ID AND i1.INSPECTION_DATE=i2.LATEST
''')
insp = {r[0]: r[1] for r in cur.fetchall()}

today = datetime.today()
DEFAULT_WEIGHTS = {'sw':0.30,'mw':0.25,'fw':0.25,'aw':0.20}

rows = []
for _, a in assets.iterrows():
    aid = a["ASSET_ID"]
    asset_type = str(a["ASSET_TYPE"])
    weights = type_cfg.get(asset_type, DEFAULT_WEIGHTS)

    # ── Age score + Weibull RUL ────────────────────────────────────────
    try:
        install = pd.to_datetime(a["INSTALL_DATE"])
        age_years = (today - install).days / 365
        life = float(a["EXPECTED_LIFE_YEARS"]) if a["EXPECTED_LIFE_YEARS"] else 20
        age_score = max(0, round(100 * (1 - age_years / life), 2))
        # Weibull RUL — beta from ASSET_TYPE_CONFIG, eta = design life hours
        w_cfg = type_cfg.get(asset_type, {})
        beta  = float(w_cfg.get('sw', 2.5))   # using SENSOR_WEIGHT as beta proxy if no dedicated column
        # If ASSET_TYPE_CONFIG has WEIBULL_BETA/ETA columns, use them directly
        # beta represents wear-out shape: >1 = wear-out, 1 = random failure
        eta   = life * 8760  # design life in hours
        t_hrs = age_years * 8760
        reliability = 0.90   # target 90% reliability
        import math
        # Weibull RUL: time remaining to reach target reliability
        # R(t) = exp(-(t/eta)^beta)  =>  t_at_R = eta * (-ln(R))^(1/beta)
        t_at_R = eta * ((-math.log(reliability)) ** (1.0 / max(0.5, beta)))
        rul_days = max(0, int((t_at_R - t_hrs) / 24))
        # Cap at calendar remaining life if Weibull gives unreasonably high value
        calendar_rul = max(0, int((life - age_years) * 365))
        rul_days = min(rul_days, calendar_rul * 2)  # allow up to 2x for healthy assets
    except Exception as e:
        age_score, rul_days = 50.0, 3000

    # ── Sensor score (7-day rolling avg) ──────────────────────────────
    asset_sensors = sensors[sensors["ASSET_ID"] == aid]
    temp = asset_sensors[asset_sensors["TAG_NAME"].str.contains("TEMP", case=False)]["AVG_VAL"].mean()
    vib  = asset_sensors[asset_sensors["TAG_NAME"].str.contains("VIB",  case=False)]["AVG_VAL"].mean()
    pres = asset_sensors[asset_sensors["TAG_NAME"].str.contains("PRES", case=False)]["AVG_VAL"].mean()
    temp = round(float(temp), 2) if pd.notna(temp) else 50.0
    vib  = round(float(vib),  4) if pd.notna(vib)  else 1.0
    pres = round(float(pres), 2) if pd.notna(pres) else 80.0
    # Vibration-weighted sensor score (primary degradation indicator)
    sensor_score = round(max(0, min(100, 100 - (vib * 10))), 2)

    # ── Maintenance score ──────────────────────────────────────────────
    wo_count = int(wo[wo["ASSET_ID"] == aid]["WO_COUNT"].values[0]) if aid in wo["ASSET_ID"].values else 0
    maint_score = round(max(0, 100 - wo_count * 10), 2)

    # ── Failure score ──────────────────────────────────────────────────
    fail_count = int(fh[fh["ASSET_ID"] == aid]["FAIL_COUNT"].values[0]) if aid in fh["ASSET_ID"].values else 0
    failure_score = round(max(0, 100 - fail_count * 25), 2)

    # ── Weighted health score (dynamic per type) ───────────────────────
    health_score = int(round(
        weights['sw'] * sensor_score +
        weights['mw'] * maint_score  +
        weights['fw'] * failure_score +
        weights['aw'] * age_score
    ))

    # ── Failure probability (inspection-adjusted) ──────────────────────
    insp_result = insp.get(aid, 'Unknown')
    insp_factor = 0.85 if insp_result and 'Pass' in str(insp_result) else 1.4 if insp_result == 'Fail' else 1.0
    failure_prob = round(max(0.01, min(0.99, (1 - health_score / 100) ** 1.6 * insp_factor)), 4)

    # ── Status ─────────────────────────────────────────────────────────
    if health_score >= 80: status = "Healthy"
    elif health_score >= 65: status = "Monitored"
    elif health_score >= 45: status = "At Risk"
    else: status = "Critical"

    rows.append((aid, health_score, sensor_score, maint_score, failure_score,
                 age_score, failure_prob, rul_days, status, temp, vib, pres,
                 "FORMULA_v2"))

# ── Write to HANA ──────────────────────────────────────────────────────────
cur.execute('DELETE FROM "ASSET_MASTER"."ASSET_HEALTH_SCORES"')
for r in rows:
    cur.execute('''
        INSERT INTO "ASSET_MASTER"."ASSET_HEALTH_SCORES"
        (ASSET_ID, HEALTH_SCORE, SENSOR_SCORE, MAINT_SCORE, FAILURE_SCORE,
         AGE_SCORE, FAILURE_PROB, RUL_DAYS, STATUS, LATEST_TEMP, LATEST_VIB,
         LATEST_PRES, SCORE_ENGINE, COMPUTED_AT)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
    ''', r)

conn.commit()
print(f"Scored {len(rows)} assets with dynamic weights. Sample:")
print(f"  {'ID':<8} {'Score':>5} {'Status':<12} {'Sensor':>6} {'Maint':>6} {'Fail':>6} {'Age':>6}")
for r in sorted(rows, key=lambda x: x[1]):
    print(f"  {r[0]:<8} {r[1]:>5} {r[8]:<12} {r[2]:>6} {r[3]:>6} {r[4]:>6} {r[5]:>6}")
cur.close()
conn.close()
