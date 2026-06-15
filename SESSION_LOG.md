# BluWis Asset Intelligence Platform — Full Session Log
## Complete Discussion, Decisions & Implementation Record

> **Session Date:** 2026-05-28 to 2026-05-29
> **Project:** Asset Intelligence Phase 2 — SAP HANA + AI Core + React UI Integration

---

## Table of Contents

1. [Starting Point](#1-starting-point)
2. [Strategy Discussion](#2-strategy-discussion)
3. [Implementation — Phase by Phase](#3-implementation)
4. [Data Validation — Real HANA vs Demo](#4-data-validation)
5. [Complete Data Map](#5-complete-data-map)
6. [Strategic Evaluation](#6-strategic-evaluation)
7. [Hosting Decision](#7-hosting-decision)
8. [Production Architecture Discussion](#8-production-architecture)
9. [What Was Built — File Reference](#9-what-was-built)
10. [Current Live State](#10-current-live-state)
11. [Pending Items](#11-pending-items)
12. [Quick Command Reference](#12-quick-command-reference)

---

## 1. Starting Point

### What existed before this session

| Component | State |
|---|---|
| `C:\Asset Managment\index.html` | Standalone React app, ALL data hardcoded in `ASSETS_INIT` (10 assets, IDs A-001 to A-010) |
| `asset-intel-srv` (SAP BTP CF) | CAP Node.js backend deployed, connected to HANA, serving OData |
| SAP HANA Cloud (`hcdev`) | 25 real assets loaded, 7 tables, 68,400 IoT readings |
| SAP AI Core | 3 deployments running (orchestration, embeddings, scenario) |
| `asset-intel-ui` | Separate Fiori Elements UI already deployed on CF |

### The Gap
The UI was completely disconnected from SAP. All data was hardcoded. The `sapApi` object was entirely mocked with fake `pause()` delays. AI Insights had very thin context (only health scores sent to GPT-4o).

---

## 2. Strategy Discussion

### The Question
> *"I now have everything in SAP integrated. I need to bridge the UI to my SAP integration."*

### Agreed Architecture

```
index.html (React)
    ↓ 9 parallel fetch calls on startup
asset-intel-srv (CAP, BTP CF)
    ├── /asset/Assets              → 25 assets from HANA
    ├── /asset/HealthScores        → pre-computed scores
    ├── /asset/Financials          → cost data
    ├── /asset/WorkOrders (R/W)    → work orders + write target
    ├── /asset/FailureHistory      → failure records
    ├── /asset/ProcessTrends       → sensor sparklines (real dates)
    ├── /asset/Inspections         → compliance data
    ├── /asset/Thresholds          → real per-asset warn/crit limits
    ├── /api/kpi-snapshots         → 6-day KPI history
    └── POST /asset/askAI          → SAP AI Core GPT-4o
```

### 5-Phase Implementation Plan

```
Phase 1: Data Adapter     → Replace ASSETS_INIT with live HANA data
Phase 2: Sensor Sparklines → Use ProcessTrends for real chart data + real dates
Phase 3: Real SAP Actions  → sapApi writes to EAM_PM.WORK_ORDERS
Phase 4: AI Insights Panel → Surface askAI in Asset Detail tab
Phase 5: Action Centre     → Seed activity log from HANA work orders
```

---

## 3. Implementation

### 3.1 Backend Changes

#### `gen/srv/server.js`
- Added `'null'` to CORS allowed origins (file:// local access)
- Added dashboard CF URL to CORS whitelist
- Added `/api/kpi-snapshots` custom Express route → reads `ASSET_MASTER.ASSET_KPI_SNAPSHOTS`

#### `gen/srv/srv/asset-service.js`
- Added `CREATE` handler for `WorkOrders` → inserts into `EAM_PM.WORK_ORDERS`
- Priority mapping: `'Very High'→1, 'High'→2, 'Medium'→3, 'Low'→4`
- Auto-generates `WO-{timestamp}` ID
- **askAI enrichment** (pending deploy): fetches 8 data sources in parallel for rich GPT-4o context:
  - Asset master + health component scores (all 4) + fleet ranking
  - Last 3 failures with root cause + resolution notes
  - Last 5 work orders with cost
  - Last 3 inspections with findings
  - Financial context (replacement cost, downtime cost, PM cost, cost-at-risk)
  - Sensor thresholds per tag from ASSET_THRESHOLDS
  - Increased max_tokens 500 → 800

### 3.2 index.html Changes

#### New helpers added
```javascript
const BACKEND = 'https://asset-intel-srv-smart-eland-qh.cfapps.us10-001.hana.ondemand.com'
function typeMap(assetType)            // type → {category, icon}
function defaultThresholds(type)       // per-type fallback thresholds
function buildThresholds(type, tagMap) // real HANA thresholds per asset
function deriveCompliance(inspections) // inspection dates → compliance status
```

#### `sapApi` replaced with real fetch calls
- `createPMNotification()` → `POST /asset/WorkOrders` (TYPE=INS) + fallback to mock
- `createWorkOrder()` → `POST /asset/WorkOrders` (TYPE=CM/EM) + fallback
- `initiateReplacement()` → `POST /asset/WorkOrders` (TYPE=PM) + fallback
- `scheduleAudit()`, `generateInvoice()`, `triggerScoreRecalc()` → still mocked (no HANA table)

#### `loadAssetsFromHANA()` function added
- 9 parallel fetches on startup
- Maps all 25 HANA assets (P-101, C-201, HE-301, S-101, V-101 etc.) to UI format
- Real sensor history from `PROCESS_TRENDS` (downsampled to 10 points)
- Real calendar dates in `sensorHistory.dates[]` → used as chart X-axis labels
- Real thresholds from `ASSET_THRESHOLDS` via `buildThresholds()`
- Component scores: `sensorScore`, `maintScore`, `failureScore`, `ageScore` from HANA
- Real `operatingHours` from `ASSETS.OPERATING_HOURS`
- KPI history from `ASSET_KPI_SNAPSHOTS` (falls back to synthetic if < 3 rows)

#### `AIInsightsPanel` component added
- Collapsible panel in Asset Detail (below Asset KPIs card)
- Pre-filled question for selected asset
- Calls `POST /asset/askAI` → returns 5-section GPT-4o response
- Renders: HEALTH SCORE / HEALTH STATUS / CORRECTIVE ACTIONS / PREVENTIVE ACTIONS / FINANCIAL SUMMARY

#### `HealthScoreBreakdown` component added
- Shows 4 component score bars with weights
- Sensor 30% · Maintenance 25% · Failure History 25% · Age 20%
- Shows formula: `0.30×S + 0.25×M + 0.25×F + 0.20×A = total`
- Data from `ASSET_HEALTH_SCORES.SENSOR_SCORE / MAINT_SCORE / FAILURE_SCORE / AGE_SCORE`

#### Other fixes
- `calcKPIs()` now uses `asset.operatingHours || (ageYears × 8760)`
- Loading spinner shown while HANA data fetches ("Connecting to SAP HANA Cloud…")
- Falls back to `ASSETS_INIT` 10 demo assets if backend unreachable
- Activity log pre-seeded from HANA work orders (top 20 by date)
- Sensor chart X-axis shows real `TREND_DATE` values ("05-13, 05-14 … Today")
- Live simulation reset uses `assets` state instead of hardcoded `ASSETS_INIT`
- "10 assets" hardcoded strings → `assets.length`

### 3.3 Python Scripts Created

#### `override_asset.py`
Interactive HANA value override tool for testing UI reactions.
```powershell
python override_asset.py --list                              # all 25 assets + scores
python override_asset.py --asset P-101 --score 18 --vib 12.5 --temp 94
python override_asset.py --reset P-101                      # recalculate from sensors
```

#### `show_asset.py`
Displays full HANA profile for one asset (ASSETS, HEALTH_SCORES, FINANCIALS, SENSOR_READINGS, WORK_ORDERS).

#### `snapshot_kpis.py`
- Creates `ASSET_MASTER.ASSET_KPI_SNAPSHOTS` table
- Computes and inserts OEE, Availability, MTBF, MTTR, PM Compliance per asset
- Backfills 6 days → 150 rows for 25 assets
- Run daily: `python snapshot_kpis.py --today`

### 3.4 Deploy History

| Deploy | What Changed | When |
|---|---|---|
| `cf push asset-intel-srv` | CORS fix + WorkOrders CREATE handler | 2026-05-28 |
| `cf push asset-intel-srv` | `/api/kpi-snapshots` + CORS for dashboard URL | 2026-05-29 |
| `cf push asset-intel-dashboard` | First deploy of index.html as public static site | 2026-05-29 |
| `cf push asset-intel-srv` | CORS fix — correct dashboard URL (no -smart-eland-qh suffix) | 2026-05-29 |

---

## 4. Data Validation

### Real HANA vs Demo — Key Differences

| | Demo (ASSETS_INIT) | Real HANA |
|---|---|---|
| Asset count | 10 | 25 |
| Asset IDs | A-001 to A-010 | P-101…P-501, C-101…C-501, HE-101…HE-501, S-101…S-501, V-101…V-501 |
| Worst asset | HX-3301 (score 35) | P-101 (score 18 after override) |
| Data source | Hardcoded JavaScript | SAP HANA Cloud, us-east-1 |

### Override Tool Demo Run
```powershell
# Pushed P-101 to deep Critical for UI testing
python override_asset.py --asset P-101 --score 18 --vib 12.5 --temp 20
# → Refresh browser: P-101 shows red Critical badge, 82% failure probability
# → NBA changes to "Urgent Repair / Priority: Very High"
python override_asset.py --reset P-101   # restore
```

---

## 5. Complete Data Map

Full document: `C:\Asset Managment\DATA_MAP.md`

### Scope
- Every UI component (6 tabs, 10+ Asset Detail sub-sections) mapped to its HANA source
- All 8 calculation functions documented with exact formulas
- All 11 HANA tables referenced with their role
- Missing data, approximations, and gaps called out per component
- AI context mapping (what is/isn't sent to GPT-4o)

---

## 6. Strategic Evaluation

Full document: `C:\Asset Managment\STRATEGIC_EVALUATION.md`

### 61 Issues Found Across 6 Categories

#### Formula Errors (6)

| Formula | Problem | Fix |
|---|---|---|
| Health Score | Two formulas: UI 40/25/20/15%, HANA 30/25/25/20% — same asset gets different scores | Remove UI recalculation, always use `ASSET_HEALTH_SCORES.HEALTH_SCORE` |
| RUL | `(designLife-age)×365×(score/100)` — score ≠ life percentage | Use degradation rate: `remainDays / degFactor(score)` |
| OEE | `avail × 0.95 × 0.98` — performance/quality hardcoded | Label as "Availability Score" until real throughput data exists |
| PM Compliance | Counts WOs created, not WOs due — missed PMs invisible | Denominator = `floor((today-installDate)/pmFreqDays)` |
| Projected 3yr/5yr | `×3.4` and `×6.2` multipliers are arbitrary | `Σ(1yr×(1+degradeRate)^n)` compound formula |
| Vibration thresholds | Current warn=7-11 mm/s; ISO 10816-3 says shutdown at 7.1 | Set warn=4.5, crit=7.1 for all rotating equipment |

#### 14 Static Values → Must Become Dynamic
OEE performance factor, PM savings ratio (0.65), score weights, projected loss multipliers, forecast step temperatures, plant code, auto-trigger thresholds, risk zone boundaries.

#### 23 Missing Data Points
Equipment-specific sensors (NPSH, volumetric efficiency, fouling factor), corrosion rate, wall thickness (UT), SIL level, energy consumption, production deferral volume.

#### 3 Missing Functional Areas
1. **Corrosion & Integrity Management** — mandatory for API 580
2. **Maintenance Backlog** — open WO hours, overdue WOs, planned vs corrective %
3. **Production Deferral** — actual vs design flow linked to revenue

#### 10 Missing KPIs
Planned Maintenance %, Maintenance Cost per Operating Hour, First-Time Fix Rate, Schedule Compliance, MTTD (Mean Time to Detect), Corrective/Preventive Ratio, Cost of Unreliability (COUR), Risk Priority Number (RPN).

#### Industry Standards Referenced
ISO 55000, API 580, API 581, ISO 10816-3 (vibration), ISO 22400 (OEE), OREDA-2015, SAP PM Best Practice, DNV-RP-G101.

### Priority Implementation Order

| Tier | Items | Timeframe |
|---|---|---|
| Tier 1 — Fix now | Unify score formula, fix RUL, fix PM compliance, fix vib thresholds, rename OEE | Days |
| Tier 2 — High value | Backlog panel, score trend indicator, equipment-specific sensors, XSUAA auth | Weeks |
| Tier 3 — Structural | Corrosion module, per-standard compliance, MTTR breakdown | Months |
| Tier 4 — Advanced | Weibull RUL, API 581 POF, energy tracking, RAG on compliance docs | Strategic |

---

## 7. Hosting Decision

### Options Evaluated

| Option | Complexity | Best For |
|---|---|---|
| **CF Staticfile (chosen)** | ⭐ Lowest | Now — demo, internal sharing, development |
| SAP HTML5 App Repository | Medium | When adding SSO/auth |
| SAP Build Work Zone | Higher | When integrating with SAP Launchpad |

### Decision
**CF staticfile buildpack** — uses existing infrastructure, 5-minute deploy, zero config.

### Files Created
```
C:\Asset Managment\
├── manifest.yml   → name: asset-intel-dashboard, 64M, staticfile_buildpack
├── Staticfile     → root: .
└── .cfignore      → excludes phase2/, asset-intel-push/, *.xlsx, *.py, etc.
```

### Live URL
```
https://asset-intel-dashboard.cfapps.us10-001.hana.ondemand.com
```

### CORS Fix Required
CF assigned URL without `-smart-eland-qh` suffix (different from prediction). Backend CORS whitelist updated and redeployed.

---

## 8. Production Architecture Discussion

### The Question
> *"This is a live production app. Multiple roles, accessible from everywhere. Production-grade."*

### Full Stack Recommendation

```
User → SAP IAS (SSO/MFA) → SAP Build Work Zone (Launchpad tile)
     → HTML5 App Repository (CDN-backed global hosting)
     → App Router (XSUAA JWT validation)
     → asset-intel-srv (CAP + role checks)
     → SAP HANA Cloud + SAP AI Core
```

### Role Architecture Designed

| Role | Accessible Tabs | Write Permissions |
|---|---|---|
| Asset Engineer | All | Create WOs, run AI, edit data |
| Asset Manager | All | Approve WOs only |
| Reliability Engineer | Fleet + Detail + KPI | View + AI only |
| Compliance Officer | Risk & Compliance + Action Centre | Audit scheduling |
| Operations Viewer | Fleet + Detail | Read-only |
| Finance Analyst | Financial + KPI | Read-only |
| Executive | KPI + Financial | Aggregates only |

### Migration Roadmap

```
TODAY:   CF static URL, no auth, global access → fine for demos
PHASE 1: Add XSUAA to backend (2 days) → login required, secure
PHASE 2: Proper React build + role-based tabs (2-3 weeks)
PHASE 3: Build Work Zone integration (1 week) → SAP Launchpad tile
PHASE 4: API Management, audit logging, monitoring (ongoing)
```

### Build Work Zone Decision
**Not required now.** Needed only when adding SSO login and Launchpad integration. Direct URL sufficient for current stage.

### Additional Production Services Needed

| Service | Purpose |
|---|---|
| SAP Alert Notification | Email/Teams when asset goes Critical, backend down |
| SAP Cloud ALM | Uptime monitoring, response time, error rates |
| SAP API Management | Rate limiting, security headers, analytics |
| 2 CF instances | Zero-downtime rolling deploys |
| HANA auto-backup | Point-in-time recovery, 14-day retention |

---

## 9. What Was Built — File Reference

### New Files

| File | Purpose |
|---|---|
| `C:\Asset Managment\DATA_MAP.md` | Complete data architecture — every component → HANA source |
| `C:\Asset Managment\STRATEGIC_EVALUATION.md` | 61-issue industry standards evaluation |
| `C:\Asset Managment\SESSION_LOG.md` | This file |
| `C:\Asset Managment\manifest.yml` | CF deploy config |
| `C:\Asset Managment\Staticfile` | nginx staticfile config |
| `C:\Asset Managment\.cfignore` | Excludes heavy folders from CF upload |
| `C:\Asset Managment\asset-intel-push\show_asset.py` | Query full HANA profile for any asset |
| `C:\Asset Managment\asset-intel-push\override_asset.py` | Modify asset health values in HANA |
| `C:\Asset Managment\asset-intel-push\snapshot_kpis.py` | Create + populate KPI history table |

### Modified Files

| File | What Changed |
|---|---|
| `C:\Asset Managment\index.html` | Full HANA bridge: data adapter, AI panel, health breakdown, real thresholds, real dates |
| `asset-intel-push\gen\srv\server.js` | CORS whitelist + `/api/kpi-snapshots` route |
| `asset-intel-push\gen\srv\srv\asset-service.js` | WorkOrders CREATE + enriched askAI context (pending) |
| `asset-intel-push\srv\asset-service.js` | Same changes to source copy |

### New HANA Table

| Table | Schema | Rows | Purpose |
|---|---|---|---|
| `ASSET_KPI_SNAPSHOTS` | `ASSET_MASTER` | 150 | Daily OEE/MTBF/MTTR/Availability history per asset |

---

## 10. Current Live State

### Deployed Applications

| App | URL | Status |
|---|---|---|
| Dashboard (React UI) | `https://asset-intel-dashboard.cfapps.us10-001.hana.ondemand.com` | ✅ Running |
| Backend API (CAP) | `https://asset-intel-srv-smart-eland-qh.cfapps.us10-001.hana.ondemand.com` | ✅ Running |
| Fiori UI (original) | `https://asset-intel-ui-smart-eland-qh.cfapps.us10-001.hana.ondemand.com` | ✅ Running |

### AI Core Deployments

| Name | Config ID | Status |
|---|---|---|
| ail-auto-orchestration | `d976e136-c14f-4be9-bdbe-80b381f9c357` | ✅ Running |
| Asset Intelligence Embeddings 3 | `770c68d6-a853-405c-9c05-7866db039d5c` | ✅ Running |
| Asset Intelligence Scenario | `7ca3fcc5-0e5a-4ef9-82d4-48a0ab837038` | ✅ Running |

### HANA Tables

| Table | Rows | Notes |
|---|---|---|
| `ASSET_MASTER.ASSETS` | 25 | Equipment master |
| `ASSET_MASTER.ASSET_HEALTH_SCORES` | 25 | Refreshed via `compute_health_scores.py` |
| `ASSET_MASTER.ASSET_FINANCIALS` | 25 | Cost parameters |
| `ASSET_MASTER.ASSET_THRESHOLDS` | ~100 | Real per-asset warn/crit per tag |
| `ASSET_MASTER.ASSET_KPI_SNAPSHOTS` | 150 | 6-day history, grow daily via `snapshot_kpis.py` |
| `IOT_SENSOR.SENSOR_READINGS` | 68,400 | 30-day hourly IoT data |
| `EAM_PM.WORK_ORDERS` | 50+ | Grows as UI creates new WOs |
| `EAM_PM.FAILURE_HISTORY` | 10 | Equipment failure records |
| `SCADA_OSIPI.PROCESS_TRENDS` | 2,844 | Daily sensor aggregates |
| `COMPLIANCE_QM.COMPLIANCE_DOCS` | 10 | NCLOB regulatory docs |
| `COMPLIANCE_QM.INSPECTIONS` | 73 | Inspection records |

---

## 11. Pending Items

### Blocked — Needs Approval

| Item | Status | How to Unblock |
|---|---|---|
| Enrich `askAI` handler in `asset-service.js` | Blocked by credential guard in auto mode | Allow editing `asset-intel-push/` in Claude Code settings, or manually apply the changes from `STRATEGIC_EVALUATION.md` Section 9.2 |

### Next Steps (Priority Order)

| # | Item | Effort |
|---|---|---|
| 1 | Fix health score — remove UI recalculation, use HANA score only | 1 hour |
| 2 | Fix RUL formula — degradation-rate based | 2 hours |
| 3 | Fix PM Compliance — include missed PMs in denominator | 30 min |
| 4 | Fix vibration thresholds — ISO 10816-3 (warn=4.5, crit=7.1) | 30 min |
| 5 | Add Score Trend indicator on fleet cards (▲/▼ from KPI snapshots) | 30 min |
| 6 | Maintenance Backlog panel — open WOs, overdue, planned % | 1 day |
| 7 | Equipment-specific sensors surfaced (FLOW_RATE, DIFF_PRES, etc.) | 1 day |
| 8 | Add XSUAA authentication to backend | 2 days |
| 9 | Proper React build (replace inline Babel) | 1 week |
| 10 | SAP Build Work Zone integration | 1 week |

---

## 12. Quick Command Reference

### Update live dashboard
```powershell
cd "c:\Asset Managment"
cf push asset-intel-dashboard
```

### Update backend
```powershell
cd "c:\Asset Managment\asset-intel-push\gen\srv"
cf push asset-intel-srv
```

### Refresh HANA health scores
```powershell
cd "c:\Asset Managment\asset-intel-push"
python compute_health_scores.py
```

### Add today's KPI snapshot
```powershell
cd "c:\Asset Managment\asset-intel-push"
python snapshot_kpis.py --today
```

### Test a failure scenario on any asset
```powershell
cd "c:\Asset Managment\asset-intel-push"
$env:PYTHONIOENCODING="utf-8"
python override_asset.py --asset P-101 --score 18 --vib 12.5 --temp 94
# Refresh browser → see Critical state
python override_asset.py --reset P-101
# Refresh browser → restored to calculated values
```

### Show all 25 assets with scores
```powershell
cd "c:\Asset Managment\asset-intel-push"
$env:PYTHONIOENCODING="utf-8"
python override_asset.py --list
```

### Show full HANA profile for an asset
```powershell
cd "c:\Asset Managment\asset-intel-push"
# Edit AID = "P-101" at top of show_asset.py, then:
python show_asset.py
```

### Check CF app status
```powershell
cf apps
cf logs asset-intel-srv --recent
cf logs asset-intel-dashboard --recent
```

### Restart a stopped AI Core deployment
```powershell
cd "c:\Asset Managment\phase2-20260523T232528Z-3-001\phase2\loader"
python list_deployments.py
```

---

*Session completed 2026-05-29. Platform: Claude Code (claude-sonnet-4-6) in VSCode extension.*
