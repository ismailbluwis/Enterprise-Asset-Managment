"""
train_autoencoder.py
====================
Trains one MLP Autoencoder per asset type using multivariate sensor data from
HANA. The autoencoder learns normal operating patterns; high reconstruction
error at inference time indicates anomalous multi-sensor correlation.

Architecture per asset type:
  n_tags → 2*n_tags → bottleneck(max 4) → 2*n_tags → n_tags (reconstruct X from X)

Run after train_model.py:
  cd "C:\\Asset Managment\\asset-ml-srv"
  python train_autoencoder.py

Outputs autoencoders.pkl alongside model.pkl for deployment with cf push.
"""
import os, sys, pickle, warnings
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

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

# ── Build per-asset-type sensor matrices ──────────────────────────────────────

MIN_TAG_READINGS = 200    # ignore tags with too few readings
MIN_TAGS_PER_TYPE = 3     # need at least 3 tags to build an autoencoder
MIN_ROWS_TO_TRAIN = 50    # minimum pivot rows after dropping NaN-heavy rows

def build_pivot(conn, asset_ids, tags):
    """
    Returns a [timestamps × tags] DataFrame for the given asset IDs and tag list.
    Rows where more than 40% of tags are NaN are dropped.
    Remaining NaN filled with column median.
    """
    if not asset_ids or not tags:
        return pd.DataFrame()

    id_placeholders = ",".join(["?" for _ in asset_ids])
    tag_placeholders = ",".join(["?" for _ in tags])

    rows = query(conn, f"""
        SELECT TO_VARCHAR("READING_TS", 'YYYY-MM-DD HH24:MI:SS') AS "TS",
               "TAG_NAME",
               CAST("TAG_VALUE" AS DOUBLE) AS "VALUE"
        FROM "IOT_SENSOR"."SENSOR_READINGS"
        WHERE "ASSET_ID" IN ({id_placeholders})
          AND "TAG_NAME" IN ({tag_placeholders})
          AND "QUALITY" = 'Good'
        ORDER BY "TS"
    """, asset_ids + tags)

    if rows.empty:
        return pd.DataFrame()

    # Pivot: one row per timestamp, one column per tag, average across assets
    pivot = (rows.groupby(["TS", "TAG_NAME"])["VALUE"]
             .mean()
             .unstack("TAG_NAME")
             .reset_index(drop=True))

    # Keep only the requested tags that actually appear
    pivot = pivot[[t for t in tags if t in pivot.columns]]

    # Drop rows missing > 40% of tags
    threshold = int(len(pivot.columns) * 0.6)
    pivot = pivot.dropna(thresh=threshold).reset_index(drop=True)

    # Fill remaining NaN with column median
    pivot = pivot.fillna(pivot.median())

    return pivot


def discover_tags(conn, asset_ids):
    """Return tags with ≥ MIN_TAG_READINGS Good readings for these assets."""
    if not asset_ids:
        return []
    placeholders = ",".join(["?" for _ in asset_ids])
    df = query(conn, f"""
        SELECT "TAG_NAME", COUNT(*) AS CNT
        FROM "IOT_SENSOR"."SENSOR_READINGS"
        WHERE "ASSET_ID" IN ({placeholders}) AND "QUALITY"='Good'
        GROUP BY "TAG_NAME"
        HAVING COUNT(*) >= {MIN_TAG_READINGS}
        ORDER BY "TAG_NAME"
    """, asset_ids)
    return df["TAG_NAME"].tolist() if not df.empty else []


# ── Train one autoencoder ─────────────────────────────────────────────────────

def train_autoencoder(X_scaled, n_tags):
    """
    MLP autoencoder: input/output = n_tags, bottleneck = max(3, n_tags//2).
    Trained with X → X reconstruction.
    """
    bottleneck = max(3, n_tags // 2)
    hidden = (n_tags * 2, bottleneck, n_tags * 2)

    model = MLPRegressor(
        hidden_layer_sizes=hidden,
        activation="relu",
        solver="adam",
        learning_rate_init=0.001,
        max_iter=600,
        tol=1e-5,
        random_state=42,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=20,
    )
    model.fit(X_scaled, X_scaled)
    return model


def compute_threshold(model, X_scaled, percentile=95):
    """Reconstruction MSE at given percentile of training data → anomaly threshold."""
    X_rec = model.predict(X_scaled)
    mse_per_row = np.mean((X_scaled - X_rec) ** 2, axis=1)
    return float(np.percentile(mse_per_row, percentile))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Connecting to HANA …")
    conn = connect()

    print("Loading asset types …")
    assets_df = query(conn, 'SELECT "ASSET_ID","ASSET_TYPE" FROM "ASSET_MASTER"."ASSETS"')
    if assets_df.empty:
        print("ERROR: No assets found in HANA")
        conn.close()
        return

    type_to_assets = assets_df.groupby("ASSET_TYPE")["ASSET_ID"].apply(list).to_dict()
    print(f"  Found {len(type_to_assets)} asset types: {list(type_to_assets.keys())}")

    autoencoders = {}

    for asset_type, asset_ids in type_to_assets.items():
        print(f"\n── {asset_type} ({len(asset_ids)} assets) ──")

        tags = discover_tags(conn, asset_ids)
        print(f"  Tags with sufficient data: {tags}")

        if len(tags) < MIN_TAGS_PER_TYPE:
            print(f"  SKIP — need ≥{MIN_TAGS_PER_TYPE} tags, found {len(tags)}")
            continue

        print(f"  Building pivot matrix …")
        pivot = build_pivot(conn, asset_ids, tags)
        print(f"  Pivot shape: {pivot.shape}")

        if len(pivot) < MIN_ROWS_TO_TRAIN:
            print(f"  SKIP — need ≥{MIN_ROWS_TO_TRAIN} training rows, got {len(pivot)}")
            continue

        X = pivot.values.astype(float)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        print(f"  Training MLP autoencoder [{len(tags)} → {len(tags)*2} → {max(3,len(tags)//2)} → {len(tags)*2} → {len(tags)}] …")
        model = train_autoencoder(X_scaled, len(tags))

        threshold = compute_threshold(model, X_scaled, percentile=95)
        print(f"  95th-percentile MSE threshold: {threshold:.6f}")

        train_rec = model.predict(X_scaled)
        train_mse = float(np.mean((X_scaled - train_rec) ** 2))
        print(f"  Mean training MSE: {train_mse:.6f}")

        autoencoders[asset_type] = {
            "model":      model,
            "scaler":     scaler,
            "tags":       tags,
            "threshold":  threshold,
            "medians":    pivot.median().to_dict(),
            "asset_ids":  asset_ids,
            "train_rows": len(pivot),
        }
        print(f"  ✓ Autoencoder ready for {asset_type}")

    conn.close()

    if not autoencoders:
        print("\nERROR: No autoencoders trained. Check HANA connectivity and data.")
        return

    out = Path(__file__).parent / "autoencoders.pkl"
    with open(out, "wb") as f:
        pickle.dump(autoencoders, f)

    size_kb = out.stat().st_size / 1024
    print(f"\n{'='*50}")
    print(f"Saved {len(autoencoders)} autoencoders to {out} ({size_kb:.0f} KB)")
    print(f"Types trained: {list(autoencoders.keys())}")
    print("Deploy with:  cf push asset-ml-srv")

if __name__ == "__main__":
    main()
