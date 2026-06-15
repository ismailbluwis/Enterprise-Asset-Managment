# BluWis Asset Health Intelligence Platform — Complete Data Map

> **Version:** 1.0 · **Date:** 2026-05-28 · **Project:** Asset Intelligence Phase 2  
> **Author:** Generated via Claude Code analysis of `C:\Asset Managment\index.html`  
> **Purpose:** Architecture reference — every UI component, the data it needs, its source, its calculation, and gaps.

---

## Table of Contents

1. [Asset Master Data Object](#1-asset-master-data-object)
2. [Calculation Engine](#2-calculation-engine)
3. [Fleet Overview Tab](#3-fleet-overview-tab)
4. [Asset Detail Tab](#4-asset-detail-tab)
5. [Risk & Compliance Tab](#5-risk--compliance-tab)
6. [Financial Impact Tab](#6-financial-impact-tab)
7. [KPI Dashboard Tab](#7-kpi-dashboard-tab)
8. [Action Centre Tab](#8-action-centre-tab)
9. [AI Insights Engine](#9-ai-insights-engine)
10. [SAP Integration Layer](#10-sap-integration-layer)
11. [HANA Database Reference](#11-hana-database-reference)
12. [Gaps & Missing Data](#12-gaps--missing-data)
13. [Calculation Accuracy Issues](#13-calculation-accuracy-issues)

---

## 1. Asset Master Data Object

Every UI component derives from a single asset object. This is the canonical shape.

### 1.1 Identity & Classification

| Field | Type | Source | HANA Column | Status |
|---|---|---|---|---|
| `id` | string | `ASSET_MASTER.ASSETS` | `ASSET_ID` | ✅ |
| `name` | string | same | `ASSET_NAME` | ✅ |
| `shortName` | string | same as `ASSET_ID` | `ASSET_ID` | ✅ |
| `type` | string | same | `ASSET_TYPE` | ✅ |
| `category` | string | derived via `typeMap(ASSET_TYPE)` | — | ✅ computed |
| `icon` | emoji | derived via `typeMap(ASSET_TYPE)` | — | ✅ computed |
| `location` | string | same | `LOCATION` | ✅ |
| `plant` | string | **hardcoded `'1100'`** | ❌ no `PLANT_CODE` column in HANA | ⚠️ missing |
| `floc` | string | **derived as `FL-{ASSET_ID}`** | ❌ no `FUNCTIONAL_LOCATION` column | ⚠️ missing |
| `manufacturer` | string | same | `MANUFACTURER` | ✅ |
| `model` | string | same | `MODEL` | ✅ |

### 1.2 Age & Lifecycle

| Field | Type | Formula | HANA Source | Status |
|---|---|---|---|---|
| `commissionDate` | date string | raw | `ASSETS.INSTALL_DATE` | ✅ |
| `ageYears` | number | `(today − INSTALL_DATE) / 365.25` | `ASSETS.INSTALL_DATE` | ✅ |
| `designLifeYears` | number | priority: `ASSET_FINANCIALS.DESIGN_LIFE_YRS` → `ASSETS.EXPECTED_LIFE_YEARS` | both | ✅ |
| `operatingHours` | number | raw | `ASSETS.OPERATING_HOURS` | ✅ |
| `lifecycleStage` | 0–5 | priority: `ASSET_FINANCIALS.LIFECYCLE_STAGE` → derived from `ageYears/designLife` ratio | `ASSET_FINANCIALS` | ✅ |
| `pmFreqDays` | number | `ASSET_FINANCIALS.PM_FREQ_DAYS` | `ASSET_FINANCIALS` | ✅ |
| `daysSinceLastPM` | number | `today − max(WORK_ORDERS.CREATED_DATE WHERE TYPE=PM AND STATUS=Completed)` | `EAM_PM.WORK_ORDERS` | ✅ |

**Lifecycle stage mapping:**

| Stage | Label | Trigger |
|---|---|---|
| 0 | Design | — |
| 1 | Procurement | — |
| 2 | Installation | age < 10% of design life |
| 3 | Operational | 10–70% of design life |
| 4 | Degrading | 70–90% of design life |
| 5 | End of Life | > 90% of design life |

### 1.3 Financial Parameters

| Field | Type | HANA Source | Status |
|---|---|---|---|
| `replacementCost` | $ number | `ASSET_FINANCIALS.REPLACEMENT_COST` | ✅ |
| `downtimeCostPerDay` | $ number | `ASSET_FINANCIALS.DOWNTIME_COST_PER_DAY` | ✅ |
| `annualPMCost` | $ number | `ASSET_FINANCIALS.ANNUAL_PM_COST` | ✅ |
| `consequence` | 1–5 | `ASSET_FINANCIALS.CONSEQUENCE` | ✅ |

### 1.4 Sensor Thresholds

Per-asset, per-sensor limits. Used for color coding, chart threshold lines, and health scoring.

```
thresholds: {
  temperature: { unit: '°C',   safe: [min, max], warn: [min, max], crit: value }
  vibration:   { unit: 'mm/s', safe: [min, max], warn: [min, max], crit: value }
  pressure:    { unit: 'bar',  safe: [min, max], warn: [min, max], crit: value }
}
```

| Source | Status |
|---|---|
| `ASSET_MASTER.ASSET_THRESHOLDS` — columns: `TAG_NAME, SAFE_LO, SAFE_HI, WARN_LO, WARN_HI, CRIT, UNIT` | ✅ table exists, ✅ now fetched via `buildThresholds()` |
| Fallback: `defaultThresholds(ASSET_TYPE)` — hardcoded per type | ✅ fallback active |

### 1.5 Sensor History (Sparklines & Trend Charts)

10 data points per sensor, used in sparklines and trend charts.

```
sensorHistory: {
  temperature: float[10],
  vibration:   float[10],
  pressure:    float[10],
  dates:       string[10]   // 'YYYY-MM-DD' — real calendar dates
}
```

| Source | Status |
|---|---|
| `SCADA_OSIPI.PROCESS_TRENDS` — `AVG_VALUE` grouped by `(ASSET_ID, PARAMETER)`, last 30 days downsampled to 10 points | ✅ |
| Last entry overridden with `ASSET_HEALTH_SCORES.LATEST_TEMP/VIB/PRES` | ✅ |
| `dates[]` from `PROCESS_TRENDS.TREND_DATE` | ✅ |
| Fallback when no trend data: synthetic ramp from `LATEST_*` values | ✅ |

### 1.6 Computed Health Component Scores

Four sub-scores stored in HANA, displayed in the Health Score Breakdown panel.

| Field | Weight | Formula | HANA Source |
|---|---|---|---|
| `sensorScore` | 30% | `max(0, min(100, 100 − vib×10))` | `ASSET_HEALTH_SCORES.SENSOR_SCORE` |
| `maintScore` | 25% | `max(0, 100 − wo_count×10)` | `ASSET_HEALTH_SCORES.MAINT_SCORE` |
| `failureScore` | 25% | `max(0, 100 − fail_count×25)` | `ASSET_HEALTH_SCORES.FAILURE_SCORE` |
| `ageScore` | 20% | `max(0, 100 × (1 − age/designLife))` | `ASSET_HEALTH_SCORES.AGE_SCORE` |

> **Populated by:** `compute_health_scores.py` — run manually or schedule.

### 1.7 Work Orders

```
workOrders: [{ id, type, desc, date, hrs, cost, status }]
```

| HANA Column | UI Field | Status |
|---|---|---|
| `WO_ID` | `id` | ✅ |
| `WO_TYPE` (PM/CM/EM/INS) | `type` | ✅ |
| `DESCRIPTION` | `desc` | ✅ |
| `CREATED_DATE` | `date` | ✅ |
| `LABOR_HOURS` | `hrs` | ✅ |
| `COST` | `cost` | ✅ |
| `STATUS` | `status` | ✅ |
| `DUE_DATE` | — | ❌ not shown in UI |

**Table:** `EAM_PM.WORK_ORDERS`  
**Write:** `POST /asset/WorkOrders` → inserts into HANA ✅

### 1.8 Failure History

```
failures: [{ date, cause, downtime, cost }]
```

| HANA Column | UI Field | Status |
|---|---|---|
| `FAILURE_DATE` | `date` | ✅ |
| `ROOT_CAUSE` | `cause` | ✅ |
| `DOWNTIME_HOURS` | `downtime` | ✅ |
| `REPAIR_COST` | `cost` | ✅ |
| `FAILURE_MODE` | — | ❌ not shown in UI |
| `RESOLUTION_NOTES` | — | ❌ not shown in UI (used in AI context) |

**Table:** `EAM_PM.FAILURE_HISTORY`

### 1.9 Compliance Status

```
compliance: {
  ISO55000:  { status: 'Compliant'|'Due Soon'|'Overdue', lastAudit: 'YYYY-MM-DD', nextDue: 'YYYY-MM-DD' }
  API580:    { ... }
  OSHA_PSM:  { ... }
  IEC61511:  { ... }
}
```

| Source | Status |
|---|---|
| Derived by `deriveCompliance(inspections)` from `COMPLIANCE_QM.INSPECTIONS` | ⚠️ **Approximation** — inspection dates are mapped to standards by position (first inspection = ISO55000, second = API580…), not by actual standard reference |
| No `COMPLIANCE_STATUS` table exists with per-standard records | ❌ missing proper table |

### 1.10 KPI History (Sparklines)

```
kpiHistory: {
  oee:  number[6],   // 6-day trend
  mtbf: number[6],
  mttr: number[6]
}
```

| Source | Status |
|---|---|
| `ASSET_MASTER.ASSET_KPI_SNAPSHOTS` — populated by `snapshot_kpis.py` | ✅ table created, 6-day backfill done |
| Fallback when < 3 snapshots: synthetic array derived from health score | ✅ |

---

## 2. Calculation Engine

### 2.1 `calcSensorScore(asset, sensorOverrides)`

**Purpose:** Score sensor readings against per-asset thresholds.

**Inputs:** Latest temp, vib, pres (from `sensorHistory[-1]` or `sensorOverrides`) + `thresholds`  
**Output:** `ss` — sensor score 0–100

```
ss = 100
if temp ≥ crit:      ss -= 40
elif temp ≥ warn:    ss -= 20 × ((temp - warn) / (crit - warn))

if vib ≥ crit:       ss -= 35
elif vib ≥ warn:     ss -= 18 × ((vib - warn) / (crit - warn))

if pres ≥ crit:      ss -= 25
elif pres ≥ warn:    ss -= 12 × ((pres - warn) / (crit - warn))

return max(0, ss)
```

---

### 2.2 `calcHealthScore(asset, sensorOverrides)`

**Purpose:** Weighted composite health score 0–100.

**Inputs:** All 4 component scores (computed inline)  
**Output:** Integer 0–100

```
ss  = calcSensorScore(asset, sensorOverrides)                        × 0.40
ms  = max(0, 100 − (daysSinceLastPM / pmFreqDays) × 100)            × 0.25
fs  = max(0, 100 − failures.length×15 − min(35, totalDowntime/8))   × 0.20
as  = max(0, (1 − ageYears/designLifeYears) × 100)                  × 0.15

healthScore = round(min(100, max(0, ss + ms + fs + as)))
```

> **Note:** UI calculates this on-the-fly. HANA stores the pre-computed version in `ASSET_HEALTH_SCORES.HEALTH_SCORE` (via `compute_health_scores.py`). Formulas differ slightly — see [Section 13](#13-calculation-accuracy-issues).

---

### 2.3 `calcRUL(asset, score)`

**Purpose:** Remaining useful life in days.

```
remainDays = (designLifeYears − ageYears) × 365
RUL = max(0, round(remainDays × (score / 100)))
```

---

### 2.4 `calcFailureProbability(asset, score)`

**Purpose:** Probability of failure 0.01–0.99.

```
ageFactor  = ageYears / designLifeYears
pmOverdue  = daysSinceLastPM > pmFreqDays ? 1.3 : 1.0
failFreq   = failures.length
baseProb   = (1 − score/100)^1.4 × pmOverdue × (1 + failFreq×0.06) × (1 + ageFactor×0.25)
return min(0.99, round(baseProb × 1000) / 1000)
```

---

### 2.5 `calcKPIs(asset)`

**Purpose:** Operational KPIs from historical data.

**Input:** `operatingHours` (actual) or `ageYears × 8760` (fallback) + `failures` + `workOrders`

```
totalHrs = asset.operatingHours || (ageYears × 8760)
totalDown = sum(failures[].downtime)

availability  = (totalHrs − totalDown) / totalHrs × 100
mtbf          = failures.length > 0 ? round((totalHrs − totalDown) / failures.length) : totalHrs
mttr          = failures.length > 0 ? round(totalDown / failures.length) : 0
oee           = (availability/100) × 0.95 × 0.98 × 100
pmComp        = completedPMs.length / totalPMs.length × 100  (100 if no PMs)
```

---

### 2.6 `calcFinancials(asset, score)`

**Purpose:** Financial exposure and maintenance ROI.

```
prob               = calcFailureProbability(asset, score)
costAtRisk         = round(prob × replacementCost)
annualDowntimeRisk = round(prob × downtimeCostPerDay × (mttr/24) × 3.5)
avgAnnualFailCost  = sum(failures[].cost) / ageYears
maintenanceROI     = round(((annualDowntimeRisk × 0.65 − annualPMCost) / annualPMCost) × 100)
projectedLoss1yr   = round(annualDowntimeRisk + avgAnnualFailCost)
projectedLoss3yr   = round(projectedLoss1yr × 3.4)   ⚠️ hardcoded multiplier
projectedLoss5yr   = round(projectedLoss1yr × 6.2)   ⚠️ hardcoded multiplier
```

---

### 2.7 `getNextBestAction(score)`

**Purpose:** Recommend the next maintenance action.

| Score Range | Action | Priority | SAP Action |
|---|---|---|---|
| ≥ 80 | Monitor | Low | Condition monitoring — no action |
| 65–79 | Schedule PM | Medium | Create PM Work Order — Priority: Medium |
| 50–64 | Inspect Now | High | Corrective WO — Priority: High. Trigger FICO check |
| 35–49 | Urgent Repair | Very High | Emergency WO — Priority: Very High. FICO reallocation |
| < 35 | Replace Asset | Critical | MM Purchase Requisition. Lifecycle replacement initiated |

---

### 2.8 `scoreStatus(score)`

| Score | Label | Color |
|---|---|---|
| ≥ 80 | Healthy | Green `#107E3E` |
| 65–79 | Monitored | Purple `#6A5ACD` |
| 45–64 | At Risk | Amber `#E9730C` |
| < 45 | Critical | Red `#BB0000` |

---

### 2.9 `probLevel(score)`

Maps health score to risk probability level for the 5×5 Risk Matrix Y-axis.

| Score | Level |
|---|---|
| ≥ 80 | 1 — Rare |
| 65–79 | 2 — Unlikely |
| 50–64 | 3 — Possible |
| 35–49 | 4 — Likely |
| < 35 | 5 — Almost Certain |

---

## 3. Fleet Overview Tab

### 3.1 Fleet Summary Bar

| Display | Formula | Data Required | HANA Source | Status |
|---|---|---|---|---|
| Healthy count | `filter(score ≥ 80).length` | health scores | `ASSET_HEALTH_SCORES.HEALTH_SCORE` | ✅ |
| Monitored count | `filter(65 ≤ score < 80).length` | same | same | ✅ |
| At Risk count | `filter(45 ≤ score < 65).length` | same | same | ✅ |
| Critical count | `filter(score < 45).length` | same | same | ✅ |
| Fleet Avg Score | `avg(all scores)` | same | same | ✅ |
| Total Cost at Risk | `sum(failureProb × replacementCost)` | `FAILURE_PROB`, `REPLACEMENT_COST` | `ASSET_HEALTH_SCORES` + `ASSET_FINANCIALS` | ✅ |
| Asset count subtitle | `assets.length` | asset count | `count(ASSETS)` | ✅ |

### 3.2 Asset Card (per asset)

| Display | Calculation | Data Required | HANA Source | Status |
|---|---|---|---|---|
| Type + ID + location | raw | `ASSET_TYPE`, `ASSET_ID`, `LOCATION` | `ASSETS` | ✅ |
| Health badge | `scoreStatus(score)` | health score | `ASSET_HEALTH_SCORES` | ✅ |
| Circular gauge 0–100 | renders score | same | same | ✅ |
| Remaining Useful Life (days) | `calcRUL(asset, score)` | designLife, age, score | `ASSET_FINANCIALS`, `ASSETS`, `ASSET_HEALTH_SCORES` | ✅ |
| EOL date | `today + RUL` | RUL | calculated | ✅ |
| % life remaining | `RUL / (designLife × 365) × 100` | same | same | ✅ |
| Failure probability bar | `calcFailureProbability()` | age, PM recency, failures, score | multiple tables | ✅ |
| Temperature reading | `sensorHistory.temperature[-1]` | latest temp | `ASSET_HEALTH_SCORES.LATEST_TEMP` | ✅ |
| Vibration reading | `sensorHistory.vibration[-1]` | latest vib | `ASSET_HEALTH_SCORES.LATEST_VIB` | ✅ |
| Pressure reading | `sensorHistory.pressure[-1]` | latest pres | `ASSET_HEALTH_SCORES.LATEST_PRES` | ✅ |
| Sensor color (red/amber) | compare to `thresholds.warn/crit` | per-asset thresholds | `ASSET_THRESHOLDS` | ✅ real thresholds now fetched |
| Next Best Action label | `getNextBestAction(score)` | score | calculated | ✅ |
| Age / Design Life | raw fields | `INSTALL_DATE`, `DESIGN_LIFE_YRS` | `ASSETS`, `ASSET_FINANCIALS` | ✅ |

---

## 4. Asset Detail Tab

### 4.1 Header Banner

| Display | Data Required | HANA Source | Status |
|---|---|---|---|
| Asset ID, Type | `ASSET_ID`, `ASSET_TYPE` | `ASSETS` | ✅ |
| Plant, Floc | hardcoded `1100`, `FL-{ID}` | ❌ no PLANT/FLOC in HANA | ⚠️ |
| Asset name | `ASSET_NAME` | `ASSETS` | ✅ |
| Location · Manufacturer · Model | `LOCATION`, `MANUFACTURER`, `MODEL` | `ASSETS` | ✅ |
| Commissioned date | `INSTALL_DATE` | `ASSETS` | ✅ |
| Age / Design Life (yrs) | derived | `INSTALL_DATE`, `DESIGN_LIFE_YRS` | ✅ |
| Failures (total) | `failures.length` | `FAILURE_HISTORY` | ✅ |
| Downtime cost/day | `DOWNTIME_COST_PER_DAY` | `ASSET_FINANCIALS` | ✅ |
| Health gauge (large) | health score | `ASSET_HEALTH_SCORES` | ✅ |

### 4.2 Next Best Action Card

| Display | Calculation | Status |
|---|---|---|
| Action name + icon | `getNextBestAction(score)` | ✅ |
| Priority badge | score bucket | ✅ |
| SAP action text | score bucket | ✅ |
| Create Notification button | `POST /asset/WorkOrders` (TYPE=INS) → `EAM_PM.WORK_ORDERS` | ✅ writes to HANA |
| Create Work Order button | `POST /asset/WorkOrders` (TYPE=CM/EM) → same | ✅ writes to HANA |
| Initiate Replacement button | `POST /asset/WorkOrders` (TYPE=PM priority=1) — shows when `lifecycleStage ≥ 4` | ✅ |

### 4.3 Asset KPIs Card

| Display | Formula | Data Required | HANA Source | Status |
|---|---|---|---|---|
| OEE % | `avail/100 × 0.95 × 0.98 × 100` | availability | `ASSETS.OPERATING_HOURS` + `FAILURE_HISTORY` | ✅ |
| OEE sparkline | `kpiHistory.oee[6]` | 6-day KPI history | `ASSET_KPI_SNAPSHOTS.OEE` | ✅ |
| Availability % | `(totalHrs − totalDown) / totalHrs × 100` | operating hours + downtime | same | ✅ |
| MTBF | `(totalHrs − totalDown) / failCount` | same | same | ✅ |
| MTBF sparkline | `kpiHistory.mtbf[6]` | 6-day history | `ASSET_KPI_SNAPSHOTS.MTBF_HOURS` | ✅ |
| MTTR | `totalDown / failCount` | `FAILURE_HISTORY.DOWNTIME_HOURS` | same | ✅ |
| MTTR sparkline | `kpiHistory.mttr[6]` | 6-day history | `ASSET_KPI_SNAPSHOTS.MTTR_HOURS` | ✅ |
| PM Compliance % | `completedPMs / totalPMs × 100` | `WORK_ORDERS` filter PM+Completed | `EAM_PM.WORK_ORDERS` | ✅ |
| Failure Probability % | `calcFailureProbability()` | age, PM recency, failures, score | multiple | ✅ |

### 4.4 AI Insights Panel

| Display | Data Sent to AI Core | Status |
|---|---|---|
| Question text box | user input | ✅ |
| AI response (5 sections) | See [Section 9](#9-ai-insights-engine) for full context sent | ✅ enriched (pending deploy) |

### 4.5 Health Score Breakdown Panel

| Display | Data Required | HANA Source | Status |
|---|---|---|---|
| Sensor Score bar (30% weight) | `sensorScore` | `ASSET_HEALTH_SCORES.SENSOR_SCORE` | ✅ |
| Maintenance Score bar (25%) | `maintScore` | `ASSET_HEALTH_SCORES.MAINT_SCORE` | ✅ |
| Failure History Score bar (25%) | `failureScore` | `ASSET_HEALTH_SCORES.FAILURE_SCORE` | ✅ |
| Age Score bar (20%) | `ageScore` | `ASSET_HEALTH_SCORES.AGE_SCORE` | ✅ |
| Formula display | all 4 values | same | ✅ |
| Weighted total | health score | `ASSET_HEALTH_SCORES.HEALTH_SCORE` | ✅ |

### 4.6 Asset Lifecycle Stage

| Display | Data Required | HANA Source | Status |
|---|---|---|---|
| Current stage (0–5) | `lifecycleStage` | `ASSET_FINANCIALS.LIFECYCLE_STAGE` | ✅ |
| Stage stepper | static labels | config | ✅ |
| Degrading warning | `stage ≥ 4` | same | ✅ |
| Replacement planning button | `stage ≥ 4` + `replacementCost` | same + `ASSET_FINANCIALS` | ✅ |

### 4.7 Sensor Trend Charts

| Display | Data Required | HANA Source | Status |
|---|---|---|---|
| Temperature trend (10 points) | `sensorHistory.temperature[10]` | `PROCESS_TRENDS` downsampled | ✅ |
| Vibration trend | `sensorHistory.vibration[10]` | same | ✅ |
| Pressure trend | `sensorHistory.pressure[10]` | same | ✅ |
| X-axis labels | `sensorHistory.dates[10]` (real calendar dates) | `PROCESS_TRENDS.TREND_DATE` | ✅ |
| Warning threshold line | `thresholds.*.warn[0]` | `ASSET_THRESHOLDS` | ✅ real thresholds |
| Critical threshold line | `thresholds.*.crit` | `ASSET_THRESHOLDS` | ✅ real thresholds |
| Live data overlay | `liveData[assetId]` | browser simulation | ✅ simulation only |

### 4.8 Trend-to-Failure Simulation

| Display | Data Required | HANA Source | Status |
|---|---|---|---|
| 4-step forecast | `FORECAST_STEPS` config | static config | ⚠️ hardcoded for oil temperature — not asset-type specific |
| Score at each step | `score + stepΔ` | health score | ✅ |
| RUL at each step | `calcRUL(asset, simScore)` | same | ✅ |
| SAP actions (simulated) | mock `sapApi` calls | WO creation → HANA | ✅ |

### 4.9 SAP Work Order History Table

| Display | Data Required | HANA Source | Status |
|---|---|---|---|
| WO ID, Type, Description | `WO_ID`, `WO_TYPE`, `DESCRIPTION` | `EAM_PM.WORK_ORDERS` | ✅ |
| Date, Hours, Cost, Status | `CREATED_DATE`, `LABOR_HOURS`, `COST`, `STATUS` | same | ✅ |
| Invoice button | shows if `STATUS = Completed` | same | ✅ |
| Invoice line items | `LABOR_HOURS × $120 + 40% parts + 15% overhead` | **mocked** — no HANA invoices table | ❌ |

### 4.10 Failure History Table

| Display | Data Required | HANA Source | Status |
|---|---|---|---|
| Date | `FAILURE_DATE` | `EAM_PM.FAILURE_HISTORY` | ✅ |
| Root Cause | `ROOT_CAUSE` | same | ✅ |
| Downtime (hrs) | `DOWNTIME_HOURS` | same | ✅ |
| Cost | `REPAIR_COST` | same | ✅ |
| Total downtime + cost | `sum()` | calculated | ✅ |

---

## 5. Risk & Compliance Tab

### 5.1 Risk Matrix (5×5)

| Display | Formula | Data Required | HANA Source | Status |
|---|---|---|---|---|
| Asset dot X position | `asset.consequence` (1–5) | `ASSET_FINANCIALS.CONSEQUENCE` | ✅ |
| Asset dot Y position | `probLevel(score)` (1–5) | health score | `ASSET_HEALTH_SCORES` | ✅ |
| Dot color | `scoreStatus(score).color` | health score | same | ✅ |
| Risk zone colors | static 5×5 matrix (green/yellow/orange/red) | config | ✅ |

**Zone definitions:**

| Zone | Consequence × Probability | Color |
|---|---|---|
| Tolerable | low × low | Green |
| ALARP | medium | Yellow |
| Undesirable | high × medium or medium × high | Orange |
| Intolerable | high × high | Red |

### 5.2 Asset Risk Summary Table

| Display | Calculation | Status |
|---|---|---|
| Risk Zone label | `score < 40` → Intolerable · `< 55` → Undesirable · `< 70` → ALARP · `≥ 70` → Tolerable | ✅ |
| Consequence label | `consequence` 1–5 → text | ✅ |
| Failure probability | `calcFailureProbability()` | ✅ |
| Next Best Action | `getNextBestAction(score)` | ✅ |

### 5.3 Compliance Tables (Overdue / Due Soon / Compliant)

| Display | Data Required | HANA Source | Status |
|---|---|---|---|
| Standard name | `COMPLIANCE_DEFS` config | static | ✅ |
| Status badge | `deriveCompliance(inspections)` | `COMPLIANCE_QM.INSPECTIONS.NEXT_INSPECTION_DATE` | ⚠️ approximation — mapped by position not standard |
| Last Audit date | `INSPECTIONS.INSPECTION_DATE` | `COMPLIANCE_QM.INSPECTIONS` | ✅ |
| Next Due date | `INSPECTIONS.NEXT_INSPECTION_DATE` | same | ✅ |
| Schedule Audit button | `sapApi.scheduleAudit()` | **not persisted** — mock only | ❌ |

**Standards tracked:**

| Standard | Description |
|---|---|
| ISO 55000 | Asset Management System |
| API 580 | Risk-Based Inspection |
| OSHA PSM | Process Safety Management |
| IEC 61511 | Safety Instrumented Systems |
| API 653 | Aboveground Storage Tanks |
| ASME VIII | Pressure Vessel Code |

---

## 6. Financial Impact Tab

### 6.1 Fleet Summary KPI Cards

| Display | Formula | Data Required | HANA Source | Status |
|---|---|---|---|---|
| Total Cost at Risk | `sum(prob × replacementCost)` | `FAILURE_PROB`, `REPLACEMENT_COST` | `ASSET_HEALTH_SCORES` + `ASSET_FINANCIALS` | ✅ |
| Annual Downtime Risk | `sum(prob × downtimeCost/day × mttr/24 × 3.5)` | failure prob, downtime cost, MTTR | multiple | ✅ |
| Total PM Investment | `sum(annualPMCost)` | `ANNUAL_PM_COST` | `ASSET_FINANCIALS` | ✅ |
| Fleet Replacement Value | `sum(replacementCost)` | `REPLACEMENT_COST` | `ASSET_FINANCIALS` | ✅ |

### 6.2 Asset-Level Financial Table

| Display | Formula | Status |
|---|---|---|
| Cost at Risk | `prob × replacementCost` | ✅ |
| Downtime Risk | `prob × downtimeCost/day × mttr/24 × 3.5` | ✅ |
| PM Investment | `annualPMCost` | ✅ |
| Maintenance ROI | `(annualDowntimeRisk × 0.65 − annualPMCost) / annualPMCost × 100` | ⚠️ 65% savings ratio hardcoded |
| Projected Loss 1yr | `annualDowntimeRisk + avgAnnualFailCost` | ✅ |
| Projected Loss 3yr | `1yr × 3.4` | ⚠️ hardcoded multiplier |
| Projected Loss 5yr | `1yr × 6.2` | ⚠️ hardcoded multiplier |

---

## 7. KPI Dashboard Tab

### 7.1 Fleet Summary Cards

| Display | Formula | Status |
|---|---|---|
| Fleet OEE % | `avg(OEE per asset)` | ✅ |
| Fleet Availability % | `avg(avail per asset)` | ✅ |
| Fleet MTBF (days) | `avg(MTBF) / 24` | ✅ |
| Fleet MTTR (h) | `avg(MTTR per asset)` | ✅ |

### 7.2 Asset KPI Comparison Table

| Display | Formula / Data | Status |
|---|---|---|
| OEE | `calcKPIs().oee` | ✅ |
| Availability | `calcKPIs().avail` | ✅ |
| MTBF | `calcKPIs().mtbf` | ✅ |
| MTTR | `calcKPIs().mttr` | ✅ |
| PM Compliance | `calcKPIs().pmComp` | ✅ |
| OEE trend arrow ▲/▼ | `kpiHistory.oee[-1] vs [-2]` | ✅ |
| OEE sparkline | `kpiHistory.oee[6]` | ✅ from `ASSET_KPI_SNAPSHOTS` |

**Color thresholds:**

| KPI | Green | Amber | Red |
|---|---|---|---|
| OEE | ≥ 85% | 70–84% | < 70% |
| Availability | ≥ 95% | 88–94% | < 88% |
| MTTR | ≤ 20h | ≤ 50h | > 50h |
| PM Compliance | ≥ 90% | 70–89% | < 70% |

### 7.3 OEE Waterfall + MTBF vs MTTR Charts

Both use the same `calcKPIs()` per asset. No additional data required.

---

## 8. Action Centre Tab

### 8.1 Activity Log Entry Structure

```
{
  type:    'EAM' | 'FICO' | 'MM' | 'AUDIT'
  action:  string    // e.g. "Work Order Created", "Invoice Generated"
  detail:  string    // full message
  doc:     string    // document ID — WO_ID, INV_ID, etc.
  assetId: string    // asset ID or 'ALL'
  time:    string    // local time string
}
```

### 8.2 Entry Sources

| Type | Trigger | Written to HANA | Status |
|---|---|---|---|
| EAM — PM Notification | "Create Notification" button | ✅ `EAM_PM.WORK_ORDERS` | ✅ |
| EAM — Work Order | "Create Work Order" button | ✅ same | ✅ |
| EAM — Emergency WO | Live sim breach or bulk trigger | ✅ same | ✅ |
| EAM — Score Recalc | "Recalculate All Scores" button | ❌ no HANA table | in-memory only |
| FICO — Invoice | "Invoice" button on completed WO | ❌ no HANA invoices table | ❌ mocked |
| MM — Replacement PR | "Initiate Replacement" button | ❌ no HANA PR table | ❌ mocked |
| AUDIT — Schedule | "Schedule Audit" button | ❌ no HANA audit table | ❌ mocked |

### 8.3 Seeding on Load

On app startup, activity log pre-seeded from `WORK_ORDERS` sorted by `CREATED_DATE DESC`, top 20. After that, new entries are in-memory only — **lost on refresh**.

### 8.4 Bulk Emergency WO Trigger

For every asset with `score < 50`:
- `score < 35` → creates Emergency WO (type=EM, priority=Very High) → writes to HANA
- `35 ≤ score < 50` → creates Corrective WO (type=CM, priority=High) → writes to HANA

---

## 9. AI Insights Engine

### 9.1 Call Flow

```
User clicks "✨ Ask AI Core"
    ↓
POST /asset/askAI  {assetId, question}
    ↓
Backend fetches 8 data sources in parallel from HANA
    ↓
Builds structured system prompt (~1,500 tokens)
    ↓
OAuth token → AI Core token endpoint
    ↓
Discover running orchestration deployment (configId: d976e136-...)
    ↓
POST /v2/inference/deployments/{id}/completion
    ↓
GPT-4o (max_tokens: 800)
    ↓
Returns 5-section response
    ↓
Rendered in Asset Detail AI Insights panel
```

### 9.2 Context Sent to GPT-4o (after enrichment)

| Section | Data | HANA Source | Status |
|---|---|---|---|
| Asset master | name, type, manufacturer, install date, criticality, operating hours | `ASSETS` | ✅ |
| Health metrics | overall score + 4 component scores + failure prob + RUL + latest sensor readings | `ASSET_HEALTH_SCORES` | ✅ |
| Sensor thresholds | warn/crit per tag | `ASSET_THRESHOLDS` | ✅ |
| Failure history (last 3) | date, failure mode, root cause, downtime, repair cost, resolution notes | `EAM_PM.FAILURE_HISTORY` | ✅ |
| Work orders (last 5) | WO ID, type, status, description, date, cost | `EAM_PM.WORK_ORDERS` | ✅ |
| Inspections (last 3) | type, inspector, result, findings, next due | `COMPLIANCE_QM.INSPECTIONS` | ✅ |
| Financial context | replacement cost, downtime cost/day, annual PM cost, PM frequency, cost at risk | `ASSET_FINANCIALS` | ✅ |
| Fleet context | all 25 assets ranked by score (worst first) + fleet avg + rank of target asset | `ASSET_HEALTH_SCORES` | ✅ |
| Compliance docs | `COMPLIANCE_DOCS.CONTENT` (NCLOB — rich regulatory text) | `COMPLIANCE_QM.COMPLIANCE_DOCS` | ❌ not yet sent (RAG opportunity) |

### 9.3 Response Format (5 Required Sections)

```
**HEALTH SCORE**:    Score interpretation + component breakdown + primary degradation driver
**HEALTH STATUS**:   Operational risk level + most likely failure mode based on history
**CORRECTIVE ACTIONS**: 2-4 immediate actions (0-14 days) referencing specific WO IDs
**PREVENTIVE ACTIONS**: 2-3 scheduled actions (15-90 days) with PM frequency reference
**FINANCIAL SUMMARY**: Quantified cost at risk, repair vs replace ROI
```

### 9.4 AI Core Deployment Details

| Deployment | Config ID | Purpose |
|---|---|---|
| ail-auto-orchestration | `d976e136-c14f-4be9-bdbe-80b381f9c357` | GPT-4o orchestration — used by AI Insights |
| Asset Intelligence Embeddings 3 | `770c68d6-a853-405c-9c05-7866db039d5c` | Text embedding — not yet wired to UI |
| Asset Intelligence Scenario | `7ca3fcc5-0e5a-4ef9-82d4-48a0ab837038` | Scenario model — not yet wired to UI |

---

## 10. SAP Integration Layer

### 10.1 Backend Endpoints

| Endpoint | Method | Function | Writes to HANA | Status |
|---|---|---|---|---|
| `/asset/Assets` | GET | 25 asset master records | — | ✅ |
| `/asset/HealthScores` | GET | Pre-computed health scores | — | ✅ |
| `/asset/Financials` | GET | Financial parameters | — | ✅ |
| `/asset/WorkOrders` | GET | All work orders | — | ✅ |
| `/asset/WorkOrders` | POST | Create new work order | ✅ `EAM_PM.WORK_ORDERS` | ✅ |
| `/asset/FailureHistory` | GET | Failure records | — | ✅ |
| `/asset/ProcessTrends` | GET | Daily sensor aggregates | — | ✅ |
| `/asset/Inspections` | GET | Inspection records | — | ✅ |
| `/asset/Thresholds` | GET | Per-asset sensor thresholds | — | ✅ |
| `/asset/Financials` | GET | Financial data | — | ✅ |
| `/asset/askAI` | POST | AI Core GPT-4o analysis | — | ✅ |
| `/api/kpi-snapshots` | GET | 6-day KPI history | — | ✅ (pending deploy) |

### 10.2 Work Order Create Payload

```json
POST /asset/WorkOrders
{
  "ASSET_ID":    "P-101",
  "WO_TYPE":     "CM" | "PM" | "EM" | "INS",
  "PRIORITY":    1 | 2 | 3 | 4  (or "Very High"|"High"|"Medium"|"Low"),
  "DESCRIPTION": "string",
  "TECHNICIAN":  "string" (optional, defaults to 'System')
}
```

Response: `{ WO_ID: "WO-XXXXXXXX", STATUS: "Open", ... }`

---

## 11. HANA Database Reference

### 11.1 Tables Summary

| Schema | Table | Rows | Description |
|---|---|---|---|
| `ASSET_MASTER` | `ASSETS` | 25 | Equipment master data |
| `ASSET_MASTER` | `ASSET_HEALTH_SCORES` | 25 | Computed scores — refreshed by `compute_health_scores.py` |
| `ASSET_MASTER` | `ASSET_FINANCIALS` | 25 | Cost parameters |
| `ASSET_MASTER` | `ASSET_THRESHOLDS` | ~100 | Per-asset per-tag warn/crit limits |
| `ASSET_MASTER` | `ASSET_KPI_SNAPSHOTS` | 150+ | Daily KPI snapshots — refreshed by `snapshot_kpis.py` |
| `IOT_SENSOR` | `SENSOR_READINGS` | 68,400 | Hourly raw sensor values (30 days) |
| `EAM_PM` | `WORK_ORDERS` | 50+ | Maintenance work orders (grows as UI creates new ones) |
| `EAM_PM` | `FAILURE_HISTORY` | 10 | Equipment failure records |
| `SCADA_OSIPI` | `PROCESS_TRENDS` | 2,844 | Daily aggregated SCADA trends |
| `COMPLIANCE_QM` | `COMPLIANCE_DOCS` | 10 | Regulatory documents (NCLOB content) |
| `COMPLIANCE_QM` | `INSPECTIONS` | 73 | Inspection records |

### 11.2 Maintenance Scripts

| Script | Purpose | When to Run |
|---|---|---|
| `compute_health_scores.py` | Recomputes `ASSET_HEALTH_SCORES` from raw sensor averages | After sensor data updates / before demo |
| `snapshot_kpis.py` | Inserts today's KPI snapshot into `ASSET_KPI_SNAPSHOTS` | Daily (schedule via Task Scheduler) |
| `override_asset.py --list` | Show all 25 assets with current scores | Any time |
| `override_asset.py --asset X --score Y` | Manually override any asset's health values | Demo / testing |
| `override_asset.py --reset X` | Reset asset back to formula-computed values | After demo |

---

## 12. Gaps & Missing Data

### 12.1 Missing HANA Tables

| Missing Table | Impact | Suggested Schema |
|---|---|---|
| `COMPLIANCE_STATUS` | Compliance is inferred from inspection dates, not mapped to actual regulatory standards | `(ASSET_ID, STANDARD, STATUS, LAST_AUDIT, NEXT_DUE, AUDITOR)` |
| `EAM_INVOICES` | Invoice generation is fully mocked — no persistence | `(INV_ID, WO_ID, ASSET_ID, AMOUNT, LINE_ITEMS_JSON, POSTED_DATE)` |
| `AUDIT_SCHEDULE` | Scheduled audits lost on page refresh | `(AUDIT_ID, ASSET_ID, STANDARD, SCHEDULED_DATE, AUDITOR, STATUS)` |
| `AUDIT_LOG` | Action Centre resets every refresh — no persistent audit trail | `(LOG_ID, ASSET_ID, ACTION_TYPE, DOC_ID, DETAIL, CREATED_BY, CREATED_AT)` |

### 12.2 Missing Columns in Existing Tables

| Table | Missing Column | Impact |
|---|---|---|
| `ASSET_MASTER.ASSETS` | `PLANT_CODE` | Asset Detail shows hardcoded `1100` |
| `ASSET_MASTER.ASSETS` | `FUNCTIONAL_LOCATION` | Asset Detail shows `FL-{ASSET_ID}` |
| `EAM_PM.WORK_ORDERS` | `DUE_DATE` shown in UI | WO table doesn't show due dates |

### 12.3 Data Present in HANA but Not Yet Used in UI

| Data | HANA Location | Opportunity |
|---|---|---|
| `COMPLIANCE_DOCS.CONTENT` (NCLOB) | `COMPLIANCE_QM.COMPLIANCE_DOCS` | RAG — send relevant doc content to AI Core for regulation-aware responses |
| `FAILURE_HISTORY.FAILURE_MODE` | `EAM_PM.FAILURE_HISTORY` | Show in Failure History table as separate column |
| `FAILURE_HISTORY.RESOLUTION_NOTES` | same | Expandable row detail in Failure History table |
| `WORK_ORDERS.DUE_DATE` | `EAM_PM.WORK_ORDERS` | Add to Work Order History table |
| `INSPECTIONS.RESULT` + `FINDINGS` | `COMPLIANCE_QM.INSPECTIONS` | Show in Compliance table detail |
| Embeddings deployment | AI Core — config `770c68d6-...` | Semantic search over compliance docs |
| Scenario deployment | AI Core — config `7ca3fcc5-...` | Custom scenario model — not yet integrated |

---

## 13. Calculation Accuracy Issues

| Calculation | Current Logic | Problem | Suggested Fix |
|---|---|---|---|
| **MTBF / MTTR** | `ageYears × 8760` as total operating hours | Inflates MTBF for assets with downtime or variable shifts | ✅ Fixed — now uses `ASSETS.OPERATING_HOURS` |
| **Health score (UI vs HANA)** | UI formula: sensor 40%, maint 25%, failure 20%, age 15%. HANA formula: sensor 30%, maint 25%, failure 25%, age 20% | Two formulas produce different scores | Standardise on one formula and remove the UI calculation entirely — always use HANA pre-computed score |
| **Projected 3yr/5yr losses** | `1yr × 3.4` and `× 6.2` (hardcoded) | No degradation curve — assumes linear | Use asset-specific degradation rate: `Σ(annualLoss × (1 + ageFactor × 0.08)^n)` |
| **Maintenance ROI** | `PM savings = 65% of downtime risk` (hardcoded) | Not based on actual PM effectiveness history | Derive savings ratio from `sum(downtime before PM) vs sum(downtime after PM)` from work order + failure history |
| **Sensor score** | Uses only the last single sensor reading | One bad reading = big score swing | Use rolling average of last 7 days from `IOT_SENSOR.SENSOR_READINGS` |
| **PM Compliance** | `completedPMs / totalPMs` from work order list | Doesn't account for PMs that were due but never created | Also factor: `daysSinceLastPM > pmFreqDays` as an additional overdue penalty |
| **Failure probability** | Formula-based with fixed exponent (`^1.4`) | Not calibrated to actual failure data | Train a simple logistic regression on `FAILURE_HISTORY` data or use AI Core embeddings for anomaly detection |
| **Lifecycle stage** | Age-ratio buckets | Doesn't use actual HANA value | ✅ Fixed — `ASSET_FINANCIALS.LIFECYCLE_STAGE` takes priority |

---

## Appendix: Data Flow Diagram

```
SAP HANA Cloud (HANA Cloud, us-east-1 AWS)
│
├── ASSET_MASTER schema
│   ├── ASSETS                  → identity, age, operating hours
│   ├── ASSET_HEALTH_SCORES     → scores, sensor latest, failure prob, RUL
│   ├── ASSET_FINANCIALS        → costs, lifecycle stage, PM frequency
│   ├── ASSET_THRESHOLDS        → warn/crit limits per tag
│   └── ASSET_KPI_SNAPSHOTS     → 6-day OEE/MTBF/MTTR history
│
├── IOT_SENSOR schema
│   └── SENSOR_READINGS         → 68,400 hourly raw sensor values
│
├── SCADA_OSIPI schema
│   └── PROCESS_TRENDS          → daily aggregates used for sparklines
│
├── EAM_PM schema
│   ├── WORK_ORDERS             → maintenance history + write target
│   └── FAILURE_HISTORY         → failure events + root causes
│
└── COMPLIANCE_QM schema
    ├── COMPLIANCE_DOCS         → NCLOB regulatory documents
    └── INSPECTIONS             → inspection results + next due dates
         │
         ▼
asset-intel-srv (SAP Cloud Foundry, Node.js, CAP)
│   https://asset-intel-srv-smart-eland-qh.cfapps.us10-001.hana.ondemand.com
│
├── OData: /asset/Assets, /asset/HealthScores, /asset/WorkOrders (R/W), ...
├── Custom: /api/kpi-snapshots
└── Action: /asset/askAI → SAP AI Core (GPT-4o, ail-auto-orchestration)
         │
         ▼
index.html (React, Babel, file://)
│
├── loadAssetsFromHANA()   → 9 parallel fetches → maps to asset objects
├── calcHealthScore()      → weighted score from 4 components
├── calcKPIs()             → OEE, availability, MTBF, MTTR, PM compliance
├── calcFinancials()       → cost at risk, downtime risk, ROI, projections
├── calcFailureProbability() → probability 0–0.99
├── calcRUL()              → remaining useful life in days
└── getNextBestAction()    → NBA recommendation + SAP action text
```

---

*Document generated 2026-05-28. Re-run the analysis after schema changes or new table additions.*
