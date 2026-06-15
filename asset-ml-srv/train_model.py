"""
train_model.py
==============
Extracts features from HANA, trains an XGBoost model for asset failure
prediction, and saves the model + metadata to model.pkl.

Run once locally before deploying the Flask service:
  cd "C:\\Asset Managment\\asset-ml-srv"
  pip install -r requirements.txt
  python train_model.py

The saved model.pkl is then deployed with the Flask app (cf push).
"""
import os, sys, pickle
from pathlib import Path
from datetime import date

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from xgboost import XGBClassifier, XGBRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import cross_val_score, StratifiedKFold

try:
    from hdbcli import dbapi
except ImportError:
    sys.exit("hdbcli not installed. Run: pip install hdbcli")

# ── HANA connection ────────────────────────────────────────────────────────────

load_dotenv(Path(__file__).parent.parent /
            "phase2-20260523T232528Z-3-001" / "phase2" / "loader" / ".env")

def connect():
    return dbapi.connect(
        address=os.environ["HANA_HOST"],
        port=int(os.environ.get("HANA_PORT", 443)),
        user=os.environ["HANA_USER"],
        password=os.environ["HANA_PASSWORD"],
        encrypt=True,
        sslValidateCertificate=True,
    )

def query(conn, sql, params=None):
    cur = conn.cursor()
    cur.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    cur.close()
    return pd.DataFrame(rows, columns=cols)

# ── Feature extraction ────────────────────────────────────────────────────────

def extract_features(conn):
    print("  Extracting assets …")
    assets = query(conn, 'SELECT "ASSET_ID","ASSET_TYPE","INSTALL_DATE","EXPECTED_LIFE_YEARS" FROM "ASSET_MASTER"."ASSETS"')

    print("  Extracting health scores …")
    health = query(conn, """
        SELECT "ASSET_ID","HEALTH_SCORE","SENSOR_SCORE","MAINT_SCORE",
               "FAILURE_SCORE","AGE_SCORE",
               COALESCE("ANOMALY_SCORE",0) AS "ANOMALY_SCORE",
               COALESCE("ANOMALY_STATUS",'Nominal') AS "ANOMALY_STATUS"
        FROM "ASSET_MASTER"."ASSET_HEALTH_SCORES"
    """)

    print("  Extracting sensor stats …")
    sensor_stats = query(conn, """
        SELECT "ASSET_ID",
               AVG("TAG_VALUE") AS SENSOR_AVG,
               STDDEV("TAG_VALUE") AS SENSOR_STD,
               MAX("TAG_VALUE") AS SENSOR_MAX,
               MIN("TAG_VALUE") AS SENSOR_MIN,
               COUNT(*) AS SENSOR_COUNT
        FROM "IOT_SENSOR"."SENSOR_READINGS"
        GROUP BY "ASSET_ID"
    """)

    print("  Extracting work order stats …")
    wo_stats = query(conn, """
        SELECT "ASSET_ID",
               COUNT(*) AS WO_TOTAL,
               COUNT(CASE WHEN "PRIORITY" <= 2 THEN 1 END) AS WO_CRITICAL,
               AVG(COALESCE(CAST("LABOR_HOURS" AS DOUBLE), 8)) AS WO_AVG_HOURS
        FROM "EAM_PM"."WORK_ORDERS"
        GROUP BY "ASSET_ID"
    """)

    print("  Extracting failure history …")
    failures = query(conn, """
        SELECT "ASSET_ID", COUNT(*) AS FAILURE_COUNT,
               MAX("FAILURE_DATE") AS LAST_FAILURE
        FROM "EAM_PM"."FAILURE_HISTORY"
        GROUP BY "ASSET_ID"
    """)

    print("  Extracting KPI snapshots …")
    kpis = query(conn, """
        SELECT "ASSET_ID",
               AVG("OEE") AS AVG_OEE,
               AVG("MTBF_HOURS") AS AVG_MTBF,
               AVG("MTTR_HOURS") AS AVG_MTTR,
               AVG("AVAILABILITY") AS AVG_AVAIL
        FROM "ASSET_MASTER"."ASSET_KPI_SNAPSHOTS"
        GROUP BY "ASSET_ID"
    """)

    print("  Extracting financials …")
    fin = query(conn, """
        SELECT "ASSET_ID",
               COALESCE("PRODUCTION_CONTRIBUTION_BBLDAY",0) AS PROD_CONTRIB,
               COALESCE("DOWNTIME_COST_PER_DAY",0) AS DOWNTIME_COST
        FROM "ASSET_MASTER"."ASSET_FINANCIALS"
    """)

    # ── Merge everything on ASSET_ID ─────────────────────────────────────────
    df = (assets
          .merge(health,      on="ASSET_ID", how="left")
          .merge(sensor_stats,on="ASSET_ID", how="left")
          .merge(wo_stats,    on="ASSET_ID", how="left")
          .merge(failures,    on="ASSET_ID", how="left")
          .merge(kpis,        on="ASSET_ID", how="left")
          .merge(fin,         on="ASSET_ID", how="left"))

    # ── Coerce all numeric columns to float (HANA returns them as object) ───
    numeric_cols = [
        "HEALTH_SCORE","SENSOR_SCORE","MAINT_SCORE","FAILURE_SCORE","AGE_SCORE",
        "ANOMALY_SCORE","SENSOR_AVG","SENSOR_STD","SENSOR_MAX","SENSOR_MIN","SENSOR_COUNT",
        "WO_TOTAL","WO_CRITICAL","WO_AVG_HOURS","FAILURE_COUNT",
        "AVG_OEE","AVG_MTBF","AVG_MTTR","AVG_AVAIL",
        "PROD_CONTRIB","DOWNTIME_COST","EXPECTED_LIFE_YEARS",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # ── Derived features ──────────────────────────────────────────────────────
    today = date.today()
    df["ASSET_AGE_YEARS"] = df["INSTALL_DATE"].apply(
        lambda d: (today - (d if isinstance(d, date) else
                            date.fromisoformat(str(d)[:10]))).days / 365.25
        if pd.notna(d) else 10.0
    )
    df["LIFE_CONSUMED_PCT"] = (df["ASSET_AGE_YEARS"] /
                                df["EXPECTED_LIFE_YEARS"].replace(0, 20) * 100).clip(0, 100)
    df["FAILURE_COUNT"] = df["FAILURE_COUNT"].fillna(0)
    df["WO_TOTAL"]       = df["WO_TOTAL"].fillna(0)
    df["WO_CRITICAL"]    = df["WO_CRITICAL"].fillna(0)

    # ── Encode ASSET_TYPE ─────────────────────────────────────────────────────
    le = LabelEncoder()
    df["ASSET_TYPE_ENC"] = le.fit_transform(df["ASSET_TYPE"].fillna("Unknown"))

    # ── Labels ────────────────────────────────────────────────────────────────
    df["AT_RISK"] = (
        (df["HEALTH_SCORE"] < 55) |
        (df["ANOMALY_STATUS"] == "Alert") |
        (df["FAILURE_SCORE"] < 40) |
        (df["SENSOR_SCORE"]  < 40) |
        (df["ANOMALY_SCORE"] > 50) |
        (df["FAILURE_COUNT"] > 1)
    ).astype(int)

    # days-to-failure proxy: health score → urgency window (100→365 days, 0→7 days)
    df["DAYS_TO_FAILURE"] = (df["HEALTH_SCORE"].fillna(50) / 100 * 358 + 7).round()

    return df, le

# ── Feature columns ───────────────────────────────────────────────────────────

FEATURE_COLS = [
    "HEALTH_SCORE", "SENSOR_SCORE", "MAINT_SCORE", "FAILURE_SCORE",
    "AGE_SCORE", "ANOMALY_SCORE", "ASSET_TYPE_ENC",
    "SENSOR_AVG", "SENSOR_STD", "SENSOR_MAX",
    "WO_TOTAL", "WO_CRITICAL", "WO_AVG_HOURS",
    "FAILURE_COUNT", "AVG_OEE", "AVG_MTBF", "AVG_MTTR",
    "ASSET_AGE_YEARS", "LIFE_CONSUMED_PCT",
    "PROD_CONTRIB", "DOWNTIME_COST",
]

FEATURE_LABELS = {
    "HEALTH_SCORE":       "Overall health score",
    "SENSOR_SCORE":       "Sensor readings",
    "MAINT_SCORE":        "Maintenance compliance",
    "FAILURE_SCORE":      "Failure history score",
    "AGE_SCORE":          "Asset age vs design life",
    "ANOMALY_SCORE":      "Anomaly detection score",
    "ASSET_TYPE_ENC":     "Asset type",
    "SENSOR_AVG":         "Average sensor readings",
    "SENSOR_STD":         "Sensor reading variability",
    "SENSOR_MAX":         "Peak sensor readings",
    "WO_TOTAL":           "Total work orders raised",
    "WO_CRITICAL":        "Critical work orders",
    "WO_AVG_HOURS":       "Average repair hours",
    "FAILURE_COUNT":      "Number of past failures",
    "AVG_OEE":            "Overall Equipment Effectiveness",
    "AVG_MTBF":           "Mean Time Between Failures",
    "AVG_MTTR":           "Mean Time To Repair",
    "ASSET_AGE_YEARS":    "Asset age (years)",
    "LIFE_CONSUMED_PCT":  "Design life consumed (%)",
    "PROD_CONTRIB":       "Production contribution",
    "DOWNTIME_COST":      "Downtime cost per day",
}

ACTION_MAP = {
    "SENSOR_SCORE": [
        "Inspect and clean all sensors; recalibrate if readings are drifting",
        "Check process parameters against design specs; look for cavitation or fouling",
        "Review sensor wiring and transmitter health",
    ],
    "MAINT_SCORE": [
        "Schedule immediate preventive maintenance; review PM frequency",
        "Inspect lubrication levels, seals, and gaskets",
        "Update maintenance plan based on current operating hours",
    ],
    "FAILURE_SCORE": [
        "Conduct root cause analysis on recent failures",
        "Inspect components with highest historical failure rate for this asset type",
        "Consider increasing inspection frequency to monthly",
    ],
    "AGE_SCORE": [
        "Commission remaining useful life (RUL) assessment",
        "Initiate capital planning for equipment replacement or major overhaul",
        "Identify and stock critical long-lead spare parts",
    ],
    "ANOMALY_SCORE": [
        "Investigate the anomalous sensor tag immediately",
        "Correlate anomaly with recent process changes or load variations",
        "Deploy vibration/thermal specialist for on-site inspection",
    ],
    "GENERAL": [
        "Review asset against current process requirements",
        "Ensure spare parts inventory is adequate",
        "Update risk register entry for this asset",
    ],
}

# ── Train (XGBoost) ───────────────────────────────────────────────────────────

def train(df):
    X_raw = df[FEATURE_COLS].apply(pd.to_numeric, errors="coerce")
    X = X_raw.fillna(X_raw.median()).astype("float64")
    y_cls = df["AT_RISK"].astype(int)
    y_reg = df["DAYS_TO_FAILURE"].astype(float)

    # Handle class imbalance via scale_pos_weight
    n_neg = int((y_cls == 0).sum())
    n_pos = int((y_cls == 1).sum())
    spw = n_neg / max(n_pos, 1)

    clf = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=spw,
        eval_metric="logloss",
        random_state=42,
        verbosity=0,
    )
    reg = XGBRegressor(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=0,
    )

    clf.fit(X, y_cls)
    reg.fit(X, y_reg)

    try:
        cv = StratifiedKFold(n_splits=min(5, n_pos + 1), shuffle=True, random_state=42)
        cv_scores = cross_val_score(clf, X, y_cls, cv=cv, scoring="f1_macro")
        print(f"\n  XGBoost Classifier CV F1 (macro): {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
    except Exception as e:
        print(f"\n  CV skipped: {e}")

    importances = dict(zip(FEATURE_COLS, clf.feature_importances_))
    top_features = sorted(importances, key=importances.get, reverse=True)[:5]
    print(f"  Top 5 features: {top_features}")
    print(f"  At-risk assets: {n_pos}/{len(df)}  |  scale_pos_weight={spw:.2f}")

    return clf, reg, importances

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Connecting to HANA …")
    conn = connect()

    print("Extracting features …")
    df, le = extract_features(conn)
    conn.close()

    print(f"\n  Dataset: {len(df)} assets  |  At-risk: {df['AT_RISK'].sum()}")

    print("\nTraining XGBoost models …")
    clf, reg, importances = train(df)

    payload = {
        "classifier":      clf,
        "regressor":       reg,
        "label_encoder":   le,
        "feature_cols":    FEATURE_COLS,
        "feature_labels":  FEATURE_LABELS,
        "action_map":      ACTION_MAP,
        "feature_medians": df[FEATURE_COLS].apply(pd.to_numeric, errors="coerce").median().to_dict(),
        "importances":     importances,
        "model_type":      "XGBoost",
        "asset_features":  df.set_index("ASSET_ID")[FEATURE_COLS + ["AT_RISK", "DAYS_TO_FAILURE"]].to_dict("index"),
    }

    out = Path(__file__).parent / "model.pkl"
    with open(out, "wb") as f:
        pickle.dump(payload, f)
    print(f"\nModel saved to {out}  ({out.stat().st_size / 1024:.0f} KB)")
    print("Done. Now run: python train_autoencoder.py")
    print("Then deploy:   cf push asset-ml-srv")

if __name__ == "__main__":
    main()
