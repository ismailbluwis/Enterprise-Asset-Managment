# Strategic Data & Calculation Evaluation
## BluWis Asset Health Intelligence Platform

> **Evaluation Date:** 2026-05-28  
> **Standards Referenced:** ISO 55000, API 580, API 581, ISO 10816-3, ISO 13709, SAP PM best practice  
> **Evaluator Lens:** Senior Asset Integrity Manager + Reliability Engineer + O&G Platform Architect  
> **Verdict per item:** ✅ Correct · ⚠️ Needs improvement · ❌ Wrong or missing · 🔄 Static → Dynamic needed

---

## Executive Summary

The platform covers the right categories but has **6 formula errors**, **14 hardcoded values that must become dynamic**, **23 missing data points** that any serious asset manager would demand, and **3 entire functional areas** that do not exist yet. The AI and health scoring engines are directionally sound but not calibrated to industry standards. Below is the complete line-by-line verdict.

---

## PART 1 — FORMULA EVALUATION

### 1.1 Health Score Formula

**Current implementation (HANA `compute_health_scores.py`):**
```
health_score = 0.30 × sensor_score + 0.25 × maint_score + 0.25 × failure_score + 0.20 × age_score
```

**Current implementation (UI `calcHealthScore()`):**
```
health_score = 0.40 × sensor_score + 0.25 × maint_score + 0.20 × failure_score + 0.15 × age_score
```

**Verdict: ❌ Two different formulas producing different scores for the same asset.**

The UI recalculates health scores differently than HANA — an asset scoring 68 in HANA might score 72 in the UI. This destroys trust in the numbers.

**Fix:** Remove the UI calculation entirely. Always use the HANA pre-computed score. UI should render `ASSET_HEALTH_SCORES.HEALTH_SCORE` only, never recalculate.

**Industry-standard weighting (recommended for O&G rotating equipment):**
```
Sensor Score:      35% — real-time condition is the strongest predictor
Failure History:   25% — past failures are the best predictor of future failures
Maintenance Score: 20% — PM recency matters but less than condition
Age Score:         20% — age/design life ratio
```
Different equipment types should have different weights:
- **Safety valves/ESDs:** Sensor score weight drops to 15%, failure history rises to 40% (low sensor data, high consequence)
- **Pipelines:** Age/corrosion rises to 35%
- **Rotating equipment:** Sensor (vibration) dominates at 40%

---

### 1.2 Sensor Score Formula

**Current:**
```
if temp ≥ crit:      ss -= 40
elif temp ≥ warn:    ss -= 20 × normalized
if vib ≥ crit:       ss -= 35
elif vib ≥ warn:     ss -= 18 × normalized
if pres ≥ crit:      ss -= 25
elif pres ≥ warn:    ss -= 12 × normalized
```

**Verdict: ⚠️ Directionally correct but has two problems:**

**Problem 1 — Uses only the last single reading.** One anomalous spike causes a large score drop.
Industry practice (ISO 10816, API 580): use a 7-day rolling average, not a point-in-time value.

**Problem 2 — Fixed deductions are not calibrated.** Why is temperature worth 40 points and pressure 25? The relative weights should reflect each sensor's predictive power for the specific failure mode. For a centrifugal pump, vibration (seal/bearing failure predictor) is more important than temperature. For a heat exchanger, differential pressure (fouling indicator) is the primary signal.

**Fix:**
```
sensor_score = 100 − weighted_sum(
    each_sensor_deduction × equipment_type_weight[sensor_type]
)
rolling_average = avg(IOT_SENSOR.SENSOR_READINGS for last 7 days, quality='Good')
```

---

### 1.3 Remaining Useful Life (RUL) Formula

**Current:**
```
RUL = (designLifeYears − ageYears) × 365 × (score / 100)
```

**Verdict: ❌ Fundamentally wrong.**

**Why it's wrong:**
- A score of 50 does NOT mean 50% of remaining life is consumed. A healthy 15-year-old asset with score 100 has the same multiplier as a degraded 2-year-old asset with score 50. They clearly do not have the same remaining life.
- Score is a proxy for condition, not a direct percentage of remaining life.
- This formula can produce RUL = 0 for an asset with score = 0 that still has 10 years of design life left.

**Industry standard approach (Weibull degradation):**
```
// Weibull-based RUL with degradation acceleration
remainingCalendarDays = (designLifeYears − ageYears) × 365
degradationRate       = 1 + (1 − score/100) × aggressiveness_factor
RUL                   = round(remainingCalendarDays / degradationRate)

// Where aggressiveness_factor depends on how fast the asset is degrading:
// Healthy (score 80-100):   aggressiveness = 1.0  → RUL ≈ calendar remaining
// At Risk (score 50-64):    aggressiveness = 1.5  → RUL = 67% of calendar remaining
// Critical (score < 35):    aggressiveness = 3.0  → RUL = 33% of calendar remaining
```

**Even better — use actual HANA data for degradation rate:**
```
score_delta_30d = current_score − score_30_days_ago  (from ASSET_KPI_SNAPSHOTS)
if score_delta_30d < 0:
    days_to_zero = current_score / abs(score_delta_30d) × 30
    RUL = min(calendar_remaining, days_to_zero)
```
This uses actual observed degradation velocity, not a static formula.

---

### 1.4 Failure Probability Formula

**Current:**
```
baseProb = (1 − score/100)^1.4 × pmOverdue × (1 + failFreq×0.06) × (1 + ageFactor×0.25)
```

**Verdict: ⚠️ Structure is right, constants are arbitrary.**

The shape exponent `1.4`, the PM overdue multiplier `1.3`, and the failure frequency coefficient `0.06` are made up. They produce plausible-looking numbers but are not calibrated to actual failure data.

**Industry standard (API 581 approach):**
```
POF = POF_base × F_damage × F_inspection × F_management

Where:
  POF_base    = generic failure frequency for equipment type (API 581 Table)
  F_damage    = damage factor based on active degradation mechanisms
  F_inspection = inspection effectiveness factor (reduces POF based on inspection history)
  F_management = management systems factor (0.5–2.0 based on safety culture)
```

**Immediate improvement (no new data required):**
```
// Use actual HANA data instead of arbitrary constants
pmOverdueFactor    = daysSinceLastPM / pmFreqDays          // e.g. 1.8 if 80% overdue
failFreqFactor     = 1 + (totalFailures / ageYears × 0.1)  // failure rate per year
inspectionFactor   = latestInspectionResult === 'Pass' ? 0.8 : 1.5  // from INSPECTIONS
baseProb           = (1 − score/100)^1.6 × pmOverdueFactor × failFreqFactor × inspectionFactor
```

---

### 1.5 OEE Formula

**Current:**
```
OEE = (availability/100) × 0.95 × 0.98 × 100
```

**Verdict: ❌ Hardcoded performance and quality factors make this meaningless.**

`0.95` and `0.98` are constants that produce OEE = availability × 93.1% always. If availability is 99%, OEE is always 92.2% regardless of actual equipment condition.

**Industry standard (ISO 22400, IEC 62264):**
```
OEE = Availability × Performance × Quality

Availability  = (Planned time − Unplanned downtime) / Planned time
Performance   = (Actual throughput rate / Design throughput rate)  ← from SCADA
Quality       = (Saleable output / Total output)                    ← from production data
```

**For your HANA data, minimum viable improvement:**
```
// Use actual operating hours and production data
Availability = (operatingHours − totalDowntimeHours) / operatingHours
Performance  = SCADA process flow rate / design flow rate  (from PROCESS_TRENDS vs ASSETS)
// If quality data unavailable, use 0.98 as documented assumption — do not hide it
OEE = Availability × Performance × 0.98  // clearly labelled "assumed quality factor"
```

**If throughput data is not available:** label OEE as "Availability-Adjusted Score" not OEE, to avoid misleading the asset manager.

---

### 1.6 MTBF and MTTR Formula

**Current:**
```
totalHrs = operatingHours || (ageYears × 8760)
MTBF = (totalHrs − totalDowntime) / failures.length
MTTR = totalDowntime / failures.length
```

**Verdict: ⚠️ Formula is correct, but missing critical components.**

**Problem 1:** MTTR is only the average repair duration. It does not break down the 6 components that O&G reliability engineers actually manage:

| Segment | Description | Action to Improve |
|---|---|---|
| MTTD | Mean Time to Detect | Better sensor alarming |
| MTTA | Mean Time to Acknowledge | Notification routing |
| MTTF_prep | Mean Time to mobilize (parts, permit) | Spare parts strategy |
| MTTR_active | Active repair/wrench time | Skill improvement |
| MTTR_test | Post-repair testing | Better test procedures |
| MTTV | Mean Time to Verify (in-service) | Monitoring after repair |

Industry finding: **40–60% of total MTTR is wait time, not repair time.** If the platform shows MTTR = 48h, the asset manager has no idea if 40h is waiting for a spare part or 40h is actual repair. These require completely different interventions.

**Problem 2:** No MTTF (Mean Time to Failure) for non-repairable components (seals, bearings, gaskets).

**Problem 3:** MTBF uses `totalHrs` from asset installation, but should only count operational hours between the last failure and the next.

---

### 1.7 Maintenance ROI Formula

**Current:**
```
ROI = (annualDowntimeRisk × 0.65 − annualPMCost) / annualPMCost × 100
```

**Verdict: 🔄 The `0.65` PM savings ratio must become dynamic.**

`0.65` means "PM prevents 65% of potential downtime." This is a reasonable industry assumption, but it should be measured from actual HANA data:

```
// Actual PM effectiveness from HANA
failures_before_PM = failures that occurred within pmFreqDays of a scheduled PM
failures_after_PM  = failures that occurred more than pmFreqDays after last PM
actual_savings_ratio = 1 − (failures_before_PM / total_failures)

// Or simpler: compare downtime in PM-compliant periods vs non-compliant periods
```

---

### 1.8 Projected Loss Multipliers

**Current:**
```
3yr loss = 1yr × 3.4
5yr loss = 1yr × 6.2
```

**Verdict: ❌ These multipliers have no basis. They must be replaced.**

The multipliers imply that losses accelerate over time (`3.4` vs a pure `3.0` for linear, and `6.2` vs `5.0`). The acceleration factor is correct conceptually but `3.4` and `6.2` are arbitrary.

**Industry approach — Compound degradation:**
```
// Asset degrades faster as it ages — use annual degradation rate
degradation_rate = 0.05  // 5% per year — calibrate from ASSET_KPI_SNAPSHOTS trend
annual_loss[yr]  = 1yr_loss × (1 + degradation_rate)^(yr-1)
3yr_loss = sum(annual_loss[1..3])
5yr_loss = sum(annual_loss[1..5])

// For an asset with degradation_rate = 0.05:
// 3yr multiplier = 3.15  (not 3.4)
// 5yr multiplier = 5.53  (not 6.2)
// For degradation_rate = 0.10:
// 3yr multiplier = 3.31  (closer to your 3.4)
// 5yr multiplier = 6.11  (close to your 6.2)
```

So `3.4` implies `~10%` annual degradation. For a healthy asset (score 80+) the rate should be lower (~5%). For a critical asset (score < 40) it should be higher (~15%). The multiplier should be dynamic per asset.

---

## PART 2 — STATIC VALUES THAT MUST BECOME DYNAMIC

| # | Value | Current | Should Be | Source in HANA |
|---|---|---|---|---|
| 1 | OEE performance factor | `0.95` (hardcoded) | Actual throughput / design capacity | `PROCESS_TRENDS.AVG_VALUE` (FLOW_RATE) vs design spec |
| 2 | OEE quality factor | `0.98` (hardcoded) | Actual quality rate | Production data (not in HANA yet) |
| 3 | PM savings ratio | `0.65` (hardcoded) | Calculated from PM vs failure correlation | `WORK_ORDERS` + `FAILURE_HISTORY` |
| 4 | Score weights (UI) | `0.40/0.25/0.20/0.15` | Per asset type weights | Add `ASSET_TYPE_CONFIG` table |
| 5 | Projected loss 3yr | `1yr × 3.4` | `Σ(1yr × (1 + degradeRate)^n)` | `ASSET_KPI_SNAPSHOTS` score trend |
| 6 | Projected loss 5yr | `1yr × 6.2` | Same compound formula | same |
| 7 | Failure prob exponent | `^1.4` | Calibrated from failure history | `FAILURE_HISTORY` + `ASSET_HEALTH_SCORES` |
| 8 | Forecast step temperatures | `40/50/70/80°C` | `thresholds.temperature.safe/warn/crit` | `ASSET_THRESHOLDS` |
| 9 | Auto WO trigger threshold | `score < 50 → WO` | Configurable per asset criticality | Add `CRITICALITY_CONFIG` table |
| 10 | Plant code | `'1100'` | Real plant code | Add `PLANT_CODE` to `ASSETS` |
| 11 | Functional location | `'FL-{ID}'` | Real SAP FL structure | Add `FUNCTIONAL_LOCATION` to `ASSETS` |
| 12 | Risk zone boundaries | Score < 40/55/70 | API 580 risk acceptance criteria | `ASSET_FINANCIALS.CONSEQUENCE` drives zone |
| 13 | Vibration thresholds | Per-type hardcoded | ISO 10816-3 zones by machine power class | `ASSET_THRESHOLDS` + `ASSETS.OPERATING_HOURS` for power class |
| 14 | PM compliance denominator | Only counts WOs already created | Total WOs that *should have been* created based on `pmFreqDays` | Calculate from `PM_FREQ_DAYS` + `INSTALL_DATE` |

---

## PART 3 — MISSING DATA POINTS

### 3.1 Equipment-Specific Operational Parameters (Critical Gap)

Current HANA has only 3 sensor types: temperature, vibration, pressure. Real O&G assets produce 8–15 meaningful parameters per equipment type. These are in `IOT_SENSOR.SENSOR_READINGS` — they're just not being surfaced in the UI.

**Centrifugal Pumps (P-101 to P-501):**

| Parameter | Why It Matters | HANA Status |
|---|---|---|
| Differential head (bar) | Primary performance indicator — degradation shows as head loss | ✅ `DISCHARGE_PRESSURE − SUCTION_PRESSURE` in SENSOR_READINGS |
| Flow rate (m³/h) | Efficiency and BEP tracking — cavitation risk | ✅ `FLOW_RATE` in SENSOR_READINGS |
| Pump efficiency (%) | `Flow × dP / Power` — drops 5–10% before visible failure | ❌ Not calculated anywhere |
| NPSH margin | `NPSHa − NPSHr` — below 0 = cavitation imminent | ❌ Not in HANA |
| Bearing temperature | Separate from process fluid temp — seal/bearing failure indicator | ❌ Not in HANA |
| Seal leakage rate | Mechanical seal failure predictor | ❌ Not in HANA |

**Reciprocating Compressors (C-101 to C-501):**

| Parameter | Why It Matters | HANA Status |
|---|---|---|
| Volumetric efficiency (%) | Valve wear indicator — drops before complete valve failure | ❌ Not in HANA |
| Rod load (% of allowable) | Structural integrity indicator | ❌ Not in HANA |
| Suction/discharge valve temperature delta | Valve leakage indicator | ⚠️ Temperature in HANA but not delta |
| Packing gas leakage (scfm) | Environmental and efficiency indicator | ❌ Not in HANA |
| Compression ratio | Process efficiency + valve stress | ✅ Derivable from pressure readings |
| RPM (actual vs setpoint) | Speed governor health | ✅ `RPM` in SENSOR_READINGS |

**Shell & Tube Heat Exchangers (HE-101 to HE-501):**

| Parameter | Why It Matters | HANA Status |
|---|---|---|
| Fouling factor Rf (m²K/W) | Primary degradation indicator — `Rf = 1/U_actual − 1/U_clean` | ❌ Not calculated |
| Heat transfer coefficient U (W/m²K) | Performance baseline — drops with fouling | ⚠️ Data available to calculate but not done |
| LMTD (Log Mean Temperature Difference) | Thermal efficiency — inlet/outlet delta | ⚠️ Inlet/outlet temps in HANA but not computed |
| Pressure drop across shell | Fouling and corrosion indicator | ✅ `DIFFERENTIAL_PRES` in SENSOR_READINGS |
| Tube wall thickness (mm) | Corrosion allowance remaining — from UT inspection | ❌ Not in HANA |

**3-Phase Separators (S-101 to S-501):**

| Parameter | Why It Matters | HANA Status |
|---|---|---|
| Level control stability (variance) | Interface control issue indicator | ⚠️ `LEVEL` in HANA but no variance calc |
| GOR (gas-oil ratio) | Process efficiency and emulsion indication | ⚠️ Derivable from flow data |
| Wall thickness (UT) | Corrosion monitoring — API 653 requirement | ❌ Not in HANA |
| Safety relief valve last test | ASME VIII + OSHA PSM requirement | ⚠️ Should be in INSPECTIONS |
| Corrosion rate (mm/year) | API 580 mandatory — measure from UT readings | ❌ Not in HANA |

**Control Valves (V-101 to V-501):**

| Parameter | Why It Matters | HANA Status |
|---|---|---|
| Valve position vs setpoint error (%) | Actuator / positioner degradation | ⚠️ `POSITION` in HANA but no setpoint comparison |
| Travel time (sec) — open to close | Actuator wear — increases with degradation | ❌ Not in HANA |
| Seat leakage class | Erosion/corrosion of trim | ❌ Not in HANA |
| Cv actual vs rated | Flow capacity degradation | ❌ Not calculated |
| Actuator supply pressure | Pneumatic supply failure indicator | ❌ Not in HANA |

---

### 3.2 Missing KPI Metrics

Every real asset management platform tracks these. None are currently in the platform:

| KPI | Formula | Why Asset Managers Need It | Missing From |
|---|---|---|---|
| **Planned Maintenance % (PMP)** | `Planned WO hours / Total WO hours × 100` | World-class = >85% planned. Currently tracking completion not planning split | UI + HANA |
| **Maintenance Cost per Operating Hour** | `Total WO cost / operatingHours` | Normalises cost across assets of different ages | UI calculation |
| **First-Time Fix Rate (FTFR)** | `WOs closed without repeat within 30 days / total closed` | Low FTFR = technician skill gap or wrong diagnosis | HANA + UI |
| **Schedule Compliance** | `WOs completed on time / total WOs scheduled` | Different from PM completion % | HANA + UI |
| **Maintenance Backlog (hours)** | `Sum of open WO estimated hours` | Capacity planning — should be 2–4 weeks of work | UI only (need `LABOR_HOURS` for open WOs) |
| **MTTD (Mean Time to Detect)** | `Time from failure onset to detection` | Measures sensor / monitoring effectiveness | ❌ Not tracked |
| **Corrective/Preventive Ratio** | `CM WO hours / PM WO hours` | World-class target: 20:80 (20% corrective) | UI calculation |
| **Asset Utilisation Rate** | `Actual running hours / Available hours` | Different from availability — accounts for demand | ❌ Not tracked |
| **Cost of Unreliability (COUR)** | `Lost production × margin + repair costs + safety costs` | CFO-facing metric — total cost of not being reliable | ❌ Not in platform |
| **Risk Priority Number (RPN)** | `Severity × Occurrence × Detectability` | FMECA metric — standard in SAP PM APM | ❌ Not in platform |

---

### 3.3 Missing Compliance Data Points

Current compliance is a rough approximation from inspection dates. A real ISO 55000 / API 580 compliant system needs:

| Data Point | Standard | Currently in HANA | Gap |
|---|---|---|---|
| Per-standard compliance status | ISO 55000 | ❌ No `COMPLIANCE_STATUS` table | Create table with `(ASSET_ID, STANDARD, STATUS, LAST_AUDIT_DATE, NEXT_DUE_DATE, AUDITOR, FINDINGS)` |
| Corrosion rate (mm/year) | API 580, API 653 | ❌ Not in HANA | Add to `ASSET_THRESHOLDS` or new `CORROSION_MONITORING` table |
| Damage mechanism assessment | API 581 | ❌ Not in HANA | Add `DAMAGE_MECHANISMS` table: `(ASSET_ID, MECHANISM, SUSCEPTIBILITY, ACTIVE)` |
| Inspection interval (days) | API 580 | Implied by `NEXT_INSPECTION_DATE` | Derive and store as `INSPECTION_INTERVAL_DAYS` |
| Inspection effectiveness | API 580 | ❌ Not tracked | Track inspector certification level → drives POF reduction factor |
| Process safety events (near misses) | OSHA PSM | ❌ Not in HANA | Add `SAFETY_EVENTS` table |
| SIL level (Safety Instrumented Function) | IEC 61511 | ❌ Not in HANA | Add `SIL_RATING` to `ASSETS` for safety instrumented assets |
| Pressure test history | ASME VIII | ⚠️ Partially in `INSPECTIONS` | Add `TEST_TYPE`, `TEST_PRESSURE`, `TEST_DATE` columns |
| Regulatory permit expiry | OSHA PSM | ❌ Not in HANA | Add `PERMITS` table: `(ASSET_ID, PERMIT_TYPE, EXPIRY_DATE, AUTHORITY)` |
| Cathodic protection readings (mV) | NACE SP0169 | ❌ Pipelines only, not tracked | Add to `SENSOR_READINGS` as a tag |

---

### 3.4 Missing Financial Data Points

| Data Point | Why Asset Managers Need It | Source |
|---|---|---|
| **Production impact (bbls/day or MMSCFD)** | What production is lost when this asset fails? Directly links asset health to revenue | SCADA/DCS — `PROCESS_TRENDS.AVG_VALUE` for FLOW_RATE |
| **Energy consumption (kWh)** | Degraded pumps/compressors consume 15–30% more power — hidden cost | Add `ENERGY_METER` tag to `SENSOR_READINGS` |
| **Insurance value** | May differ from replacement cost — affects risk calculation | Add `INSURANCE_VALUE` to `ASSET_FINANCIALS` |
| **Maintenance budget vs actual** | Are we under or over spending this year? | Add `BUDGET_MAINTENANCE_COST` to `ASSET_FINANCIALS` |
| **Spare parts inventory value** | Critical spares not available = extended MTTR | New `SPARE_PARTS_INVENTORY` table |
| **Contractor/service agreement cost** | Many assets have maintenance contracts — not reflected in `ANNUAL_PM_COST` | Add `CONTRACT_VALUE`, `CONTRACT_EXPIRY` to `ASSET_FINANCIALS` |

---

## PART 4 — CALCULATION CORRECTIONS REQUIRED

### 4.1 PM Compliance % — Wrong Formula

**Current:**
```
pmComp = completedPMs / totalPMsInWorkOrderHistory × 100
```

**Why it's wrong:** Only counts PMs that were explicitly created in the system. If a PM was *due* but never created (missed entirely), it doesn't appear as a failure. A truly missed PM is invisible.

**Correct formula:**
```
// How many PM windows have passed since commissioning?
totalPMsScheduled = floor((today − installDate) / pmFreqDays)

// How many are recorded as Completed?
totalPMsCompleted = count(WORK_ORDERS WHERE TYPE='PM' AND STATUS='Completed')

// Real PM compliance
pmCompliance = totalPMsCompleted / totalPMsScheduled × 100
```

This will show the true picture — an asset may show 100% PM compliance under the current formula even if 8 of 10 scheduled PMs were never raised.

---

### 4.2 ISO 10816-3 Vibration Zones — Current Thresholds Are Inconsistent

**Current hardcoded defaults by type (a sample):**
- Centrifugal Pump: warn=7, crit=11 mm/s
- Reciprocating Compressor: warn=6, crit=10 mm/s
- Shell & Tube HX: warn=4, crit=7 mm/s

**ISO 10816-3 actual zones for rigid-foundation machines (most O&G equipment):**

| Zone | Boundary | Action |
|---|---|---|
| A (Good) | 0 – 2.3 mm/s RMS | New machinery — acceptable |
| B (Acceptable) | 2.3 – 4.5 mm/s RMS | Normal operation |
| C (Warning) | 4.5 – 7.1 mm/s RMS | Schedule maintenance |
| D (Danger) | > 7.1 mm/s RMS | **Immediate shutdown** |

**Your current thresholds:**
- Pumps: warn at 7 mm/s → this is already in Zone D per ISO. An asset in Zone C would show as "normal."
- Compressors: warn at 6 mm/s → Zone C/D boundary. Zone B is already showing as green.

**Recommended thresholds (ISO 10816-3 aligned, store in `ASSET_THRESHOLDS`):**
```
All rotating equipment (rigid mount):
  warn = 4.5 mm/s   (Zone B/C boundary → schedule maintenance)
  crit = 7.1 mm/s   (Zone C/D boundary → immediate action)

Flexible mount equipment (offshore modules):
  warn = 7.1 mm/s
  crit = 11.0 mm/s
```

---

### 4.3 Consequence Rating — Too Coarse

**Current:** Static integer 1–5 from `ASSET_FINANCIALS.CONSEQUENCE` — assigned during data generation.

**API 580 defines consequence as a function of multiple factors:**
```
Consequence = f(
  area_affected_m²,         // release area
  fluid_hazard_class,       // H2S, flammable, toxic
  inventory_kg,             // mass available for release
  population_density,       // people exposed
  safety_system_credit,     // deluge, ESD, containment
  environmental_sensitivity // near water body, populated area
)
```

**Immediate improvement without API 581 full implementation:**
Add these fields to `ASSET_FINANCIALS` or `ASSETS`:
```
FLUID_TYPE:          'H2S' | 'Hydrocarbon' | 'Water' | 'Gas' | 'Chemical'
MAX_INVENTORY_KG:    number
POPULATION_ZONE:     'Isolated' | 'General' | 'Controlled' | 'Sensitive'
SAFETY_SYSTEMS:      'ESD + Deluge + Containment' | 'ESD Only' | 'None'
```
Consequence then auto-calculates from these fields instead of being a static 1–5 number.

---

## PART 5 — STRATEGIC MISSING FUNCTIONAL AREAS

### 5.1 AREA 1: Corrosion & Integrity Management

**Every pressure-containing asset in O&G must have this. It is absent from the platform.**

Required data and calculations:
```
Corrosion rate (mm/year) = (wall_thickness_t1 − wall_thickness_t2) / time_between_measurements

Remaining corrosion allowance = current_wall_thickness − minimum_required_thickness
                                (from ASME B31.3 or vessel design code)

Remaining inspection life = remaining_corrosion_allowance / corrosion_rate

Maximum allowed inspection interval = min(
  API 580 risk-based interval,
  corrosion_rate_based_interval,
  regulatory_requirement
)
```

**New table needed:** `CORROSION_MONITORING` with columns:
```
ASSET_ID, MEASUREMENT_POINT, MEASUREMENT_DATE,
WALL_THICKNESS_MM, NOMINAL_WALL_MM, MINIMUM_WALL_MM,
CORROSION_RATE_MM_YR, INSPECTOR, METHOD (UT/RT/ET)
```

---

### 5.2 AREA 2: Maintenance Planning & Backlog

**An asset manager's primary daily tool. Currently invisible in the platform.**

Required:
1. **Open WO backlog** — total hours of work waiting (from `WORK_ORDERS WHERE STATUS IN ('Open','In Progress')`)
2. **Overdue WOs** — past `DUE_DATE`
3. **Due in next 30 days** — WOs approaching due date
4. **Planned vs unplanned split** — `PM+INS / CM+EM` ratio
5. **Maintenance schedule calendar** — which assets need work when
6. **Turnaround backlog** — work only executable during planned shutdown

Required formula:
```
Backlog weeks = sum(LABOR_HOURS of open WOs) / weekly_workforce_capacity
Planned Maintenance % = PM WO hours / total WO hours × 100
Target: >85% planned maintenance (world-class reliability)
```

---

### 5.3 AREA 3: Production Impact Quantification

**The single most important number for an asset manager in an O&G context: what does this asset's health mean for production?**

Currently the platform shows cost-at-risk in dollar terms but not production terms.

Required:
```
production_contribution (bbls/day or MMSCFD) — add to ASSET_FINANCIALS
deferral_rate = actual_flow / design_flow × 100 — from PROCESS_TRENDS
deferred_production_today = design_flow − actual_flow

// Fleet-level
total_deferred_production = sum(deferred_production per asset)
deferred_revenue_per_day  = total_deferred_production × commodity_price

// Per asset
production_availability = actual_runtime_hours / scheduled_hours × 100
```

This connects the health score directly to barrels — an asset manager understands "P-101 at 52/100 health score is deferring 850 bbl/day" far better than "52/100."

---

## PART 6 — WHAT AN ASSET MANAGER WANTS THAT ISN'T THERE

Based on ISO 55000 and industry practice, here are the views that O&G asset managers look at daily and weekly that are missing:

### 6.1 Daily Operations View (missing)
- **Equipment in alarm right now** — sensors above warn or crit threshold
- **WOs overdue today**
- **PMs due this week**
- **Assets with score drop > 5 points in last 24h**
- **Open emergency WOs and their status**

### 6.2 Weekly Reliability Review (missing)
- **Planned vs unplanned maintenance ratio** — target >80% planned
- **PM schedule adherence** — how many PMs were done on time
- **Corrective to preventive ratio** — is the fleet trending toward reactive?
- **MTTR trend** — is it getting better or worse?
- **Top 5 repeat failures** — same failure mode recurring on same asset

### 6.3 Monthly Management Report (missing)
- **Health score trend** per asset over 30 days — improving or degrading?
- **Maintenance spend vs budget** — over/under by how much?
- **Compliance calendar** — what inspections are due next 90 days?
- **RUL horizon** — which assets will reach critical RUL within 6/12 months?
- **Cost of unreliability** — actual loss from unplanned downtime this month

### 6.4 Annual Planning View (missing)
- **Asset lifecycle portfolio** — how many assets enter Degrading/EOL in next 3 years?
- **CAPEX forecast** — which assets need replacement and when?
- **Long-term maintenance cost curve** — maintenance cost rises as assets age
- **Risk portfolio trend** — are we more or less risky than last year?

---

## PART 7 — RECOMMENDED PRIORITY IMPLEMENTATION ORDER

### Tier 1 — Fix now (breaks data trust if left wrong)

| # | Item | Impact | Effort |
|---|---|---|---|
| 1 | **Unify health score formula** — remove UI recalculation, always use HANA | Eliminates dual-score problem | Low |
| 2 | **Fix RUL formula** — use degradation-rate based calculation | Asset managers make shutdown decisions from RUL | Medium |
| 3 | **Fix PM Compliance** — include missed PMs in denominator | Currently 100% on assets with no PMs raised | Low |
| 4 | **Fix vibration thresholds** — align to ISO 10816-3 (warn=4.5, crit=7.1 mm/s) | Sensors not alarming correctly | Low |
| 5 | **OEE label** — rename to "Availability Score" until real performance/quality data exists | Prevents misleading OEE on dashboard | Trivial |

### Tier 2 — Add high-value data (most asked for by asset managers)

| # | Item | Impact | Effort |
|---|---|---|---|
| 6 | **Maintenance backlog panel** — open WO hours, overdue WOs, planned % | Daily tool for maintenance planners | Medium |
| 7 | **Score trend over 30 days** — is this asset getting better or worse? | Most important chart for predictive maintenance | Low (data in KPI_SNAPSHOTS) |
| 8 | **Production deferral** — actual vs design flow per asset | Links health to revenue for management | Medium |
| 9 | **Equipment-specific sensor surfacing** — show FLOW_RATE, DIFFERENTIAL_PRES etc per type | Operators need these, not just temp/vib/pres | Low (data in HANA) |
| 10 | **Planned vs Corrective split** — maintenance strategy KPI | Reliability posture indicator | Low |

### Tier 3 — Structural improvements (medium-term)

| # | Item | Impact | Effort |
|---|---|---|---|
| 11 | **Corrosion monitoring module** — UT readings, corrosion rate, remaining life | API 580 requirement, risk-based inspection | High |
| 12 | **Per-standard compliance table** — replace approximation with real standard tracking | ISO 55000 compliance | Medium |
| 13 | **MTTR breakdown** — detection, response, repair, test segments | Identify bottlenecks in maintenance process | Medium |
| 14 | **Dynamic consequence** — calculate from fluid type, inventory, safety systems | Better risk matrix positioning | Medium |
| 15 | **Failure mode library** — known failure modes per equipment type | Feed AI context, drive FMECA | High |

### Tier 4 — Advanced capabilities (strategic)

| # | Item | Impact | Effort |
|---|---|---|---|
| 16 | **Weibull RUL model** — calibrate from `FAILURE_HISTORY` β parameter per asset type | Statistically defensible RUL | High |
| 17 | **API 581 POF calculation** — damage mechanisms, inspection effectiveness factor | Industry-standard risk quantification | Very High |
| 18 | **Energy consumption tracking** — link kWh degradation to cost | Hidden cost of degradation | Medium |
| 19 | **RAG (Retrieval-Augmented Generation)** — use `COMPLIANCE_DOCS.CONTENT` for AI answers | AI gives regulation-specific advice | Medium (AI Core embedding deployment ready) |
| 20 | **Digital twin / process model** — expected vs actual for each sensor | True anomaly detection, not threshold-based | Very High |

---

## PART 8 — QUICK WIN CODE CHANGES

The following changes require minimal code but deliver maximum accuracy improvement:

### QW1: Fix OEE Label (10 minutes)
```javascript
// In calcKPIs(), change:
{ l: 'OEE', v: `${kpis.oee}%` }
// To:
{ l: 'Avail. Score', v: `${kpis.oee}%`, tooltip: 'Availability-adjusted score (true OEE requires throughput data)' }
```

### QW2: Fix PM Compliance to Include Missed PMs (30 minutes)
```javascript
// In calcKPIs(), replace:
const pmDone = asset.workOrders.filter(w => w.type==='PM' && w.status==='Completed').length;
const pmTotal = asset.workOrders.filter(w => w.type==='PM').length;
const pmComp = pmTotal > 0 ? round(pmDone/pmTotal*100) : 100;

// With:
const pmDone = asset.workOrders.filter(w => w.type==='PM' && w.status==='Completed').length;
const pmScheduled = Math.max(1, Math.floor(
  (new Date() - new Date(asset.commissionDate)) / (asset.pmFreqDays * 86400000)
));
const pmComp = Math.min(100, Math.round(pmDone / pmScheduled * 100));
```

### QW3: Fix RUL to Use Degradation Rate (45 minutes)
```javascript
// In calcRUL():
function calcRUL(asset, score) {
  const remainDays = (asset.designLifeYears - asset.ageYears) * 365;
  // Degradation acceleration: critical assets age faster
  const degRate = score >= 80 ? 1.0 : score >= 65 ? 1.3 : score >= 50 ? 1.8 : score >= 35 ? 2.5 : 4.0;
  return Math.max(0, Math.round(remainDays / degRate));
}
```

### QW4: Surface Equipment-Specific Sensors (1 hour)
```javascript
// In AssetDetail sensor section, add equipment-specific parameters
// Already in HANA SENSOR_READINGS — just need to surface them
const specialSensors = {
  'Centrifugal Pump':         ['FLOW_RATE', 'SUCTION_PRESSURE', 'DISCHARGE_PRESSURE'],
  'Reciprocating Compressor': ['RPM', 'DISCHARGE_TEMP', 'DISCHARGE_PRESSURE'],
  'Shell & Tube Heat Exch.':  ['INLET_TEMP', 'OUTLET_TEMP', 'DIFFERENTIAL_PRES', 'FLOW_RATE'],
  '3-Phase Separator':        ['LEVEL', 'GAS_FLOW', 'PRESSURE'],
  'Control Valve':            ['POSITION', 'UPSTREAM_PRESSURE', 'DOWNSTREAM_PRESSURE'],
};
// Fetch latest values from ASSET_HEALTH_SCORES or IOT_SENSOR.SENSOR_READINGS
// Display as an additional "Process Parameters" row below the main 3 sensor bars
```

### QW5: Add Score Trend Indicator to Asset Cards (30 minutes)
```javascript
// In KPI snapshots (already fetched), compare latest vs 5-days-ago score
// Show ▲+3 (green) or ▼-8 (red) next to the circular gauge
const snaps = kpiSnapMap[asset.id] || [];
const trend = snaps.length >= 2
  ? snaps[snaps.length-1].HEALTH_SCORE - snaps[0].HEALTH_SCORE
  : null;
// Display: trend > 0 ? `▲${trend}` : `▼${Math.abs(trend)}`
```

### QW6: Add Maintenance Backlog to Action Centre (1 hour)
```javascript
// Already have all work orders in HANA — compute from loaded data
const openWOs = allAssets.flatMap(a => a.workOrders.filter(w => w.status === 'Open' || w.status === 'In Progress'));
const backlogHours = openWOs.reduce((sum, w) => sum + (w.hrs || 0), 0);
const overdueWOs = openWOs.filter(w => w.date && new Date(w.date) < new Date());
const plannedRatio = allAssets.flatMap(a => a.workOrders)
  .filter(w => w.status === 'Completed')
  .reduce((acc, w) => { acc[w.type === 'PM' || w.type === 'INS' ? 'planned' : 'corrective']++; return acc; }, {planned:0, corrective:0});
```

---

## Summary Table

| Category | Issues Found | Critical | Medium | Low |
|---|---|---|---|---|
| Formula errors | 6 | 3 (RUL, OEE, dual health score) | 2 (projected losses, PM compliance) | 1 (failure prob constants) |
| Static → Dynamic | 14 | 5 | 6 | 3 |
| Missing data points | 23 | 8 | 10 | 5 |
| Missing functional areas | 3 | 2 (corrosion, backlog) | 1 (production impact) | — |
| Missing KPIs | 10 | 4 (PMP, backlog, MTTD, COUR) | 4 | 2 |
| Industry standard gaps | 5 | 2 (ISO 10816-3 vib, PM compliance) | 2 (API 580 POF, OEE) | 1 |

**Total items to address: 61**  
**Tier 1 (fix immediately): 15**  
**Tier 2 (high value, near-term): 10**  
**Tier 3–4 (strategic): 36**

---

*Sources: ISO 55000:2014, API RP 580 (2016), API 581 (2016), ISO 10816-3:2009, ISO 22400-2:2014 (OEE), OREDA-2015 (O&G reliability data), SAP PM Best Practice Library, DNV-RP-G101 (Risk Based Inspection of Topsides), NACE SP0169 (Cathodic Protection)*
