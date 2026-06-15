"""
Asset Value Override Tool
─────────────────────────
Modify HANA values for any asset and see the UI react.

Usage:
  python override_asset.py               # interactive menu
  python override_asset.py --list        # show all assets + current scores
  python override_asset.py --asset P-101 --score 25 --temp 89 --vib 9.2 --pres 72
  python override_asset.py --reset P-101 # recalculate from raw sensor data
"""

import sys
import argparse
from hdbcli import dbapi
from datetime import datetime

conn = dbapi.connect(
    address="48e539b6-6ba6-4891-9538-727dd496988b.hna1.prod-us10.hanacloud.ondemand.com",
    port=443, user="DBADMIN", password="Admin123",
    encrypt=True, sslValidateCertificate=True
)
cur = conn.cursor()

STATUS_MAP = [(80, "Healthy"), (65, "Monitored"), (45, "At Risk"), (0, "Critical")]
def score_to_status(s):
    for threshold, label in STATUS_MAP:
        if s >= threshold:
            return label
    return "Critical"

def list_assets():
    cur.execute('''
        SELECT a.ASSET_ID, a.ASSET_NAME, a.ASSET_TYPE, a.STATUS,
               h.HEALTH_SCORE, h.STATUS as HEALTH_STATUS,
               h.LATEST_TEMP, h.LATEST_VIB, h.LATEST_PRES, h.FAILURE_PROB
        FROM "ASSET_MASTER"."ASSETS" a
        LEFT JOIN "ASSET_MASTER"."ASSET_HEALTH_SCORES" h ON a.ASSET_ID = h.ASSET_ID
        ORDER BY h.HEALTH_SCORE ASC
    ''')
    rows = cur.fetchall()
    print(f"\n{'ID':<8} {'Name':<35} {'Score':>5} {'Status':<12} {'Temp':>7} {'Vib':>7} {'Pres':>7} {'FailProb':>9}")
    print("─" * 100)
    for r in rows:
        score = r[4] or 0
        bar = "█" * (score // 10) + "░" * (10 - score // 10)
        print(f"{r[0]:<8} {str(r[1])[:34]:<35} {score:>5} {str(r[5]):<12} "
              f"{str(r[6] or '?'):>7} {str(r[7] or '?'):>7} {str(r[8] or '?'):>7} "
              f"{float(r[9] or 0)*100:>8.1f}%  {bar}")
    print()

def show_asset(asset_id):
    cur.execute('SELECT * FROM "ASSET_MASTER"."ASSET_HEALTH_SCORES" WHERE ASSET_ID=?', [asset_id])
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    if not row:
        print(f"Asset {asset_id} not found in ASSET_HEALTH_SCORES")
        return None
    return dict(zip(cols, row))

def override(asset_id, health_score=None, temp=None, vib=None, pres=None, failure_prob=None, rul=None):
    cur.execute('SELECT * FROM "ASSET_MASTER"."ASSET_HEALTH_SCORES" WHERE ASSET_ID=?', [asset_id])
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    if not row:
        print(f"ERROR: Asset {asset_id} not found.")
        return

    current = dict(zip(cols, row))
    print(f"\nCurrent values for {asset_id}:")
    print(f"  HEALTH_SCORE: {current['HEALTH_SCORE']}  STATUS: {current['STATUS']}")
    print(f"  LATEST_TEMP:  {current['LATEST_TEMP']}  LATEST_VIB: {current['LATEST_VIB']}  LATEST_PRES: {current['LATEST_PRES']}")
    print(f"  FAILURE_PROB: {current['FAILURE_PROB']}  RUL_DAYS: {current['RUL_DAYS']}")

    new_score = int(health_score) if health_score is not None else current['HEALTH_SCORE']
    new_temp  = float(temp)        if temp         is not None else current['LATEST_TEMP']
    new_vib   = float(vib)         if vib          is not None else current['LATEST_VIB']
    new_pres  = float(pres)        if pres         is not None else current['LATEST_PRES']
    new_fprob = float(failure_prob) if failure_prob is not None else round(max(0.01, min(0.99, 1 - new_score/100)), 4)
    new_rul   = int(rul)           if rul          is not None else current['RUL_DAYS']
    new_status = score_to_status(new_score)

    cur.execute('''
        UPDATE "ASSET_MASTER"."ASSET_HEALTH_SCORES"
        SET HEALTH_SCORE=?, STATUS=?, FAILURE_PROB=?, RUL_DAYS=?,
            LATEST_TEMP=?, LATEST_VIB=?, LATEST_PRES=?,
            SCORE_ENGINE=?, COMPUTED_AT=CURRENT_TIMESTAMP
        WHERE ASSET_ID=?
    ''', [new_score, new_status, new_fprob, new_rul,
          new_temp, new_vib, new_pres, "MANUAL", asset_id])
    conn.commit()

    print(f"\n✅ Updated {asset_id}:")
    print(f"  HEALTH_SCORE: {current['HEALTH_SCORE']} → {new_score}  ({current['STATUS']} → {new_status})")
    if temp  is not None: print(f"  LATEST_TEMP:  {current['LATEST_TEMP']} → {new_temp}")
    if vib   is not None: print(f"  LATEST_VIB:   {current['LATEST_VIB']} → {new_vib}")
    if pres  is not None: print(f"  LATEST_PRES:  {current['LATEST_PRES']} → {new_pres}")
    print(f"\n  → Refresh index.html to see changes in the UI.")

def reset_from_sensors(asset_id):
    """Re-run the health score formula from raw sensor averages."""
    import pandas as pd
    cur.execute('SELECT ASSET_ID, INSTALL_DATE, EXPECTED_LIFE_YEARS FROM "ASSET_MASTER"."ASSETS" WHERE ASSET_ID=?', [asset_id])
    a = cur.fetchone()
    if not a: print("Asset not found"); return

    cur.execute('''SELECT TAG_NAME, AVG(TAG_VALUE) as AVG_VAL
                   FROM "IOT_SENSOR"."SENSOR_READINGS"
                   WHERE ASSET_ID=? GROUP BY TAG_NAME''', [asset_id])
    sensors = {r[0]: r[1] for r in cur.fetchall()}

    cur.execute('SELECT COUNT(*) FROM "EAM_PM"."WORK_ORDERS" WHERE ASSET_ID=?', [asset_id])
    wo_count = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM "EAM_PM"."FAILURE_HISTORY" WHERE ASSET_ID=?', [asset_id])
    fail_count = cur.fetchone()[0]

    today = datetime.today()
    install = datetime.strptime(str(a[1])[:10], "%Y-%m-%d")
    life = float(a[2]) if a[2] else 20
    age_years = (today - install).days / 365
    age_score = max(0, round(100 * (1 - age_years / life), 2))
    rul_days  = max(0, int((life - age_years) * 365))

    temp = next((v for k,v in sensors.items() if "TEMP" in k.upper() and v), 50.0)
    vib  = next((v for k,v in sensors.items() if "VIB"  in k.upper() and v), 1.0)
    pres = next((v for k,v in sensors.items() if "PRES" in k.upper() and v), 80.0)
    temp, vib, pres = round(float(temp),2), round(float(vib),4), round(float(pres),2)

    sensor_score = round(max(0, min(100, 100 - vib * 10)), 2)
    maint_score  = round(max(0, 100 - wo_count * 10), 2)
    fail_score   = round(max(0, 100 - fail_count * 25), 2)
    health_score = int(round(0.3*sensor_score + 0.25*maint_score + 0.25*fail_score + 0.2*age_score))
    failure_prob = round(max(0.01, min(0.99, 1 - health_score/100)), 4)
    status = score_to_status(health_score)

    cur.execute('''
        UPDATE "ASSET_MASTER"."ASSET_HEALTH_SCORES"
        SET HEALTH_SCORE=?, STATUS=?, SENSOR_SCORE=?, MAINT_SCORE=?, FAILURE_SCORE=?,
            AGE_SCORE=?, FAILURE_PROB=?, RUL_DAYS=?,
            LATEST_TEMP=?, LATEST_VIB=?, LATEST_PRES=?,
            SCORE_ENGINE=?, COMPUTED_AT=CURRENT_TIMESTAMP
        WHERE ASSET_ID=?
    ''', [health_score, status, sensor_score, maint_score, fail_score,
          age_score, failure_prob, rul_days, temp, vib, pres, "FORMULA", asset_id])
    conn.commit()
    print(f"\n✅ Reset {asset_id} from sensor data:")
    print(f"  HEALTH_SCORE: {health_score}  STATUS: {status}")
    print(f"  TEMP: {temp}  VIB: {vib}  PRES: {pres}  FAILURE_PROB: {failure_prob}")

def interactive():
    print("\n╔══════════════════════════════════════════════════╗")
    print("║  Asset Value Override Tool — SAP HANA Cloud     ║")
    print("╚══════════════════════════════════════════════════╝")
    list_assets()
    asset_id = input("Asset ID to modify (e.g. P-101, C-201): ").strip().upper()
    if not asset_id: return

    current = show_asset(asset_id)
    if not current: return

    print(f"\nWhat to change? (press Enter to keep current value)")
    score = input(f"  HEALTH_SCORE [{current['HEALTH_SCORE']}] (0-100): ").strip() or None
    temp  = input(f"  LATEST_TEMP  [{current['LATEST_TEMP']}] (°C): ").strip() or None
    vib   = input(f"  LATEST_VIB   [{current['LATEST_VIB']}] (mm/s): ").strip() or None
    pres  = input(f"  LATEST_PRES  [{current['LATEST_PRES']}] (bar): ").strip() or None
    rul   = input(f"  RUL_DAYS     [{current['RUL_DAYS']}] (days): ").strip() or None

    if any([score, temp, vib, pres, rul]):
        override(asset_id, score, temp, vib, pres, rul=rul)
    else:
        print("No changes made.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Override HANA asset values")
    parser.add_argument("--list",   action="store_true", help="List all assets with scores")
    parser.add_argument("--asset",  help="Asset ID (e.g. P-101)")
    parser.add_argument("--score",  help="Health score 0-100")
    parser.add_argument("--temp",   help="Temperature °C")
    parser.add_argument("--vib",    help="Vibration mm/s")
    parser.add_argument("--pres",   help="Pressure bar")
    parser.add_argument("--rul",    help="Remaining useful life days")
    parser.add_argument("--reset",  help="Reset asset from raw sensors (e.g. --reset P-101)")
    args = parser.parse_args()

    if args.list:
        list_assets()
    elif args.reset:
        reset_from_sensors(args.reset.upper())
    elif args.asset:
        override(args.asset.upper(), args.score, args.temp, args.vib, args.pres, rul=args.rul)
    else:
        interactive()

    cur.close()
    conn.close()
