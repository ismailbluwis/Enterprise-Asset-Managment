"""
app.py — BluWis Asset ML Prediction Service
============================================
Serves Random Forest predictions for asset failure risk and corrective actions.
Loaded model.pkl is built by train_model.py before deployment.

Endpoints:
  GET  /health                   → liveness check
  POST /predict  { assetId }     → failure probability + risk factors + actions
  GET  /predict?assetId=P-101    → same, GET variant for browser testing
"""
import os, pickle, traceback
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np

app = Flask(__name__)
CORS(app)

# ── Load models once at startup ───────────────────────────────────────────────

MODEL_PATH = Path(__file__).parent / "model.pkl"
MODEL = None

AE_PATH = Path(__file__).parent / "autoencoders.pkl"
AUTOENCODERS = {}

def load_autoencoders():
    global AUTOENCODERS
    if AUTOENCODERS:
        return AUTOENCODERS
    if not AE_PATH.exists():
        return {}
    with open(AE_PATH, "rb") as f:
        AUTOENCODERS = pickle.load(f)
    print(f"[ML] Autoencoders loaded — types: {list(AUTOENCODERS.keys())}")
    return AUTOENCODERS

def load_model():
    global MODEL
    if MODEL is not None:
        return MODEL
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            "model.pkl not found. Run train_model.py first, then redeploy.")
    with open(MODEL_PATH, "rb") as f:
        MODEL = pickle.load(f)
    print(f"[ML] Model loaded — {len(MODEL['asset_features'])} assets in baseline")
    return MODEL

try:
    load_model()
except Exception as e:
    print(f"[ML] WARNING: model not loaded at startup: {e}")

try:
    load_autoencoders()
except Exception as e:
    print(f"[ML] WARNING: autoencoders not loaded at startup: {e}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def to_float(v):
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0

def get_feature_vector(model, asset_id, overrides=None):
    """
    Build a feature vector for the given asset.
    Uses the baseline stored in model.pkl (snapshot from training time).
    `overrides` dict can supply live values (e.g. from a fresh HANA query).
    """
    baseline = model["asset_features"].get(asset_id)
    medians  = model["feature_medians"]
    cols     = model["feature_cols"]

    if baseline:
        row = {c: to_float(baseline.get(c, medians.get(c, 0))) for c in cols}
    else:
        row = {c: to_float(medians.get(c, 0)) for c in cols}

    if overrides:
        row.update({k: to_float(v) for k, v in overrides.items()})

    return np.array([[row[c] for c in cols]], dtype=np.float64)


def top_risk_factors(model, asset_id, n=3):
    """Return the n features with highest importance × deviation from median."""
    baseline = model["asset_features"].get(asset_id, {})
    medians  = model["feature_medians"]
    imp      = model["importances"]
    labels   = model["feature_labels"]
    cols     = model["feature_cols"]

    scored = []
    for c in cols:
        val = to_float(baseline.get(c, medians.get(c, 0)))
        med = to_float(medians.get(c, 1)) or 1
        # For scores (HEALTH_SCORE, SENSOR_SCORE etc) low = bad
        deviation = (med - val) / med if med != 0 else 0
        # For failure/wo counts high = bad
        if c in ("FAILURE_COUNT", "WO_CRITICAL", "WO_TOTAL", "ANOMALY_SCORE",
                 "LIFE_CONSUMED_PCT", "ASSET_AGE_YEARS"):
            deviation = (val - med) / (med or 1)
        scored.append({
            "feature": c,
            "label":   labels.get(c, c),
            "value":   round(float(val), 2),
            "score":   float(imp.get(c, 0)) * max(deviation, 0),
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return [s for s in scored[:n] if s["score"] > 0]


def recommend_actions(model, asset_id, risk_factors):
    """Map top risk features to corrective actions."""
    action_map  = model["action_map"]
    baseline    = model["asset_features"].get(asset_id, {})
    actions     = []

    # Find the lowest-scoring component
    component_scores = {
        "SENSOR_SCORE":  to_float(baseline.get("SENSOR_SCORE",  100)),
        "MAINT_SCORE":   to_float(baseline.get("MAINT_SCORE",   100)),
        "FAILURE_SCORE": to_float(baseline.get("FAILURE_SCORE", 100)),
        "AGE_SCORE":     to_float(baseline.get("AGE_SCORE",     100)),
        "ANOMALY_SCORE": to_float(baseline.get("ANOMALY_SCORE", 0)),
    }
    # Invert anomaly (high = bad)
    component_scores["ANOMALY_SCORE"] = 100 - component_scores["ANOMALY_SCORE"]

    # Worst component drives primary recommendation
    worst = min(component_scores, key=component_scores.get)
    if worst in action_map:
        actions.extend(action_map[worst][:2])

    # Secondary actions from risk factors
    for rf in risk_factors[:2]:
        feat = rf["feature"]
        if feat in action_map and action_map[feat][0] not in actions:
            actions.append(action_map[feat][0])

    if not actions:
        actions = action_map["GENERAL"]

    return list(dict.fromkeys(actions))[:4]  # dedupe, max 4


def urgency_label(prob, days):
    if prob >= 0.75 or days <= 14:
        return "Critical"
    if prob >= 0.50 or days <= 45:
        return "High"
    if prob >= 0.25 or days <= 90:
        return "Medium"
    return "Low"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    loaded = MODEL is not None
    return jsonify({"status": "ok" if loaded else "model_not_loaded",
                    "model_ready": loaded}), 200


@app.route("/predict", methods=["GET", "POST"])
def predict():
    try:
        model = load_model()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 503

    # Accept assetId from JSON body or query string
    if request.method == "POST":
        body     = request.get_json(silent=True) or {}
        asset_id = body.get("assetId") or request.args.get("assetId", "")
        overrides = body.get("features")  # optional live feature overrides
    else:
        asset_id  = request.args.get("assetId", "")
        overrides = None

    if not asset_id:
        return jsonify({"error": "assetId is required"}), 400

    try:
        clf = model["classifier"]
        reg = model["regressor"]

        X = get_feature_vector(model, asset_id, overrides)

        failure_prob   = float(clf.predict_proba(X)[0][1])
        days_to_fail   = float(reg.predict(X)[0])
        at_risk        = bool(clf.predict(X)[0] == 1)
        risk_factors   = top_risk_factors(model, asset_id)
        actions        = recommend_actions(model, asset_id, risk_factors)
        urgency        = urgency_label(failure_prob, days_to_fail)

        # Format risk factors for UI display
        rf_display = [
            {
                "label":   rf["label"],
                "value":   rf["value"],
                "concern": f"{'Low' if 'Score' in rf['label'] and rf['value'] < 50 else 'Elevated'} — contributing {rf['score']*100:.0f}% to risk",
            }
            for rf in risk_factors
        ]

        return jsonify({
            "assetId":            asset_id,
            "failureProbability": round(failure_prob * 100, 1),
            "atRisk":             at_risk,
            "urgency":            urgency,
            "daysToFailure":      round(days_to_fail),
            "riskFactors":        rf_display,
            "correctiveActions":  actions,
            "modelNote":          "XGBoost — trained on HANA asset health, sensor, maintenance and failure data",
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ── TimeGPT / Statistical Forecast ───────────────────────────────────────────

@app.route("/timegpt/forecast", methods=["POST"])
def timegpt_forecast():
    """
    POST { assetId, tagName, readings:[{ts,value}], h, thresholdWarn, thresholdCrit }
    Returns 24-hour forecast + anomaly score + trend + hours-to-threshold.
    Uses TimeGPT (Nixtla) if NIXTLA_API_KEY is set, else EWM statistical fallback.
    """
    import pandas as pd
    import numpy as np

    body             = request.get_json(silent=True) or {}
    readings_raw     = body.get("readings", [])
    h                = int(body.get("h", 24))
    threshold_warn   = body.get("thresholdWarn")
    threshold_crit   = body.get("thresholdCrit")
    asset_id         = body.get("assetId", "unknown")
    tag_name         = body.get("tagName", "unknown")

    if len(readings_raw) < 10:
        return jsonify({"error": f"Need ≥10 readings, got {len(readings_raw)}"}), 400

    df = pd.DataFrame(readings_raw)
    # ts is sent as "YYYY-MM-DD HH24:MI:SS" ISO string from HANA TO_VARCHAR
    df["ds"] = pd.to_datetime(df["ts"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    df["y"]  = pd.to_numeric(df["value"], errors="coerce").fillna(0)
    df = df.dropna(subset=["ds"]).sort_values("ds").reset_index(drop=True)
    if len(df) < 10:
        return jsonify({"error": f"After timestamp parsing, only {len(df)} valid rows remain (need ≥10)"}), 400

    api_key      = os.environ.get("NIXTLA_API_KEY", "").strip()
    forecast_list = []
    anomaly_pts  = []
    anomaly_score = 0.0
    model_used   = ""

    if api_key:
        try:
            from nixtla import NixtlaClient
            client = NixtlaClient(api_key=api_key)

            tdf = df[["ds", "y"]].copy()
            tdf.insert(0, "unique_id", f"{asset_id}_{tag_name}")

            fcast = client.forecast(tdf, h=h, freq="h", level=[80, 95])
            for _, row in fcast.iterrows():
                forecast_list.append({
                    "ds":    str(row["ds"])[:16],
                    "value": round(to_float(row.get("TimeGPT", 0)), 4),
                    "lo80":  round(to_float(row.get("TimeGPT-lo-80", 0)), 4),
                    "hi80":  round(to_float(row.get("TimeGPT-hi-80", 0)), 4),
                    "hi95":  round(to_float(row.get("TimeGPT-hi-95", 0)), 4),
                })

            hist = tdf.tail(min(len(tdf), 168)).copy()
            try:
                anom = client.detect_anomalies(hist, freq="h", level=99)
                bad  = anom[anom["anomaly"] == True]
                anomaly_pts   = [{"ds": str(r["ds"])[:16], "value": to_float(r["y"])}
                                 for _, r in bad.iterrows()][:20]
                anomaly_score = min(100.0, len(anomaly_pts) / max(len(hist), 1) * 500)
            except Exception:
                pass

            model_used = "TimeGPT (Nixtla Foundation Model)"
        except Exception:
            traceback.print_exc()
            api_key = ""   # fall through to statistical

    if not api_key:
        values   = df["y"].values.astype(float)
        alpha    = 0.2
        ewm_val  = float(values[-1])
        for v in reversed(values[:-1]):
            ewm_val = alpha * float(v) + (1 - alpha) * ewm_val

        recent  = values[-min(len(values), 72):]
        std_val = float(np.std(recent)) if len(recent) > 1 else 1.0
        slope   = float((recent[-1] - recent[0]) / max(len(recent) - 1, 1)) if len(recent) > 1 else 0.0

        last_ts = df["ds"].iloc[-1]
        for i in range(1, h + 1):
            pred = ewm_val + slope * i
            ts   = last_ts + pd.Timedelta(hours=i)
            forecast_list.append({
                "ds":    str(ts)[:16],
                "value": round(pred, 4),
                "lo80":  round(pred - 1.28 * std_val, 4),
                "hi80":  round(pred + 1.28 * std_val, 4),
                "hi95":  round(pred + 1.96 * std_val, 4),
            })

        recent24  = values[-min(len(values), 24):]
        mu, sig   = float(np.mean(recent24)), float(np.std(recent24)) or 1.0
        zs        = [abs(float(v) - mu) / sig for v in recent24]
        anomaly_score = min(100.0, max(zs) / 3.0 * 100.0) if zs else 0.0
        model_used    = "Statistical (EWM + linear trend)"

    # Trend direction vs last actual
    last_val     = to_float(df["y"].iloc[-1])
    avg_fcast    = sum(r["value"] for r in forecast_list) / max(len(forecast_list), 1)
    std_ref      = to_float(df["y"].std()) or 1.0
    if avg_fcast > last_val + 0.5 * std_ref:
        trend = "degrading"
    elif avg_fcast < last_val - 0.5 * std_ref:
        trend = "improving"
    else:
        trend = "stable"

    # Hours until forecast (or hi80) crosses critical threshold
    hours_to_threshold = None
    thr = to_float(threshold_crit) if threshold_crit is not None else None
    if thr and thr > 0:
        for i, row in enumerate(forecast_list):
            if row["value"] >= thr or row["hi80"] >= thr:
                hours_to_threshold = i + 1
                break

    return jsonify({
        "assetId":           asset_id,
        "tagName":           tag_name,
        "forecast":          forecast_list,
        "anomalyPoints":     anomaly_pts,
        "anomalyScore":      round(anomaly_score, 1),
        "trend":             trend,
        "hoursToThreshold":  hours_to_threshold,
        "modelUsed":         model_used,
        "historicalCount":   len(readings_raw),
    })


# ── Autoencoder Anomaly Detection ─────────────────────────────────────────────

@app.route("/autoencoder/detect", methods=["POST"])
def autoencoder_detect():
    """
    POST { assetId, assetType, readings: {TAG_NAME: value, ...} }
    Returns per-tag reconstruction error scores and overall anomaly score.
    """
    body       = request.get_json(silent=True) or {}
    asset_id   = body.get("assetId", "unknown")
    asset_type = body.get("assetType", "")
    readings   = body.get("readings", {})

    aes = load_autoencoders()
    if not aes:
        return jsonify({"error": "Autoencoders not loaded — run train_autoencoder.py and redeploy"}), 503

    ae = aes.get(asset_type)
    if not ae:
        available = list(aes.keys())
        return jsonify({
            "error": f"No autoencoder for asset type '{asset_type}'",
            "availableTypes": available,
        }), 404

    tags    = ae["tags"]
    scaler  = ae["scaler"]
    model   = ae["model"]
    thresh  = ae["threshold"]
    medians = ae["medians"]

    # Build input vector — use median for any missing tag
    x_raw = np.array([[to_float(readings.get(t, medians.get(t, 0))) for t in tags]])

    try:
        x_scaled = scaler.transform(x_raw)
        x_rec    = model.predict(x_scaled)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Autoencoder inference failed: {str(e)}"}), 500

    # Per-tag squared errors in scaled space
    tag_sq_errors = (x_scaled[0] - x_rec[0]) ** 2
    overall_mse   = float(np.mean(tag_sq_errors))

    # Normalize to 0–100 anomaly score  (threshold MSE → score 50; 3× threshold → 100)
    def mse_to_score(mse):
        return min(100.0, mse / max(thresh, 1e-9) * 50.0)

    tag_scores = {tags[i]: round(mse_to_score(float(tag_sq_errors[i])), 1)
                  for i in range(len(tags))}

    overall_score = round(mse_to_score(overall_mse), 1)
    most_anomalous = max(tag_scores, key=tag_scores.get) if tag_scores else None

    # Identify tags that individually breach the per-tag 95th-pct scaled threshold
    # (using 2× average tag-level threshold as a heuristic)
    per_tag_thresh = thresh / max(len(tags), 1)
    anomalous_tags = [t for t, sq in zip(tags, tag_sq_errors) if sq > per_tag_thresh * 2]

    return jsonify({
        "assetId":           asset_id,
        "assetType":         asset_type,
        "overallAnomalyScore": overall_score,
        "isAnomaly":         overall_mse > thresh,
        "reconstructionError": round(overall_mse, 6),
        "threshold":         round(thresh, 6),
        "tagScores":         tag_scores,
        "mostAnomalousTag":  most_anomalous,
        "anomalousTags":     anomalous_tags,
        "tagsMonitored":     tags,
        "model":             f"MLP-Autoencoder-{asset_type}",
        "trainRows":         ae.get("train_rows", 0),
    })


@app.route("/autoencoder/types", methods=["GET"])
def autoencoder_types():
    """List which asset types have trained autoencoders."""
    aes = load_autoencoders()
    return jsonify({
        "types": [
            {"assetType": k, "tags": v["tags"], "trainRows": v.get("train_rows", 0)}
            for k, v in aes.items()
        ]
    })


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
