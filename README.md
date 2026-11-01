# Clover

**Clover** (Follow-the-Green Leaders) is an intelligent, carbon-aware leader-placement optimization engine and observability dashboard for distributed multi-region databases, specifically designed for [YugabyteDB](https://www.yugabyte.com/) and integrating a modular persistent memory layer powered by [Meko](https://meko.ai/) and Gemini AI.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Problem Statement](#problem-statement)
3. [Architecture](#architecture)
4. [Key Features](#key-features)
5. [The Optimization Decision Process](#the-optimization-decision-process)
6. [Carbon Calculation Engine & Assumptions](#carbon-calculation-engine--assumptions)
7. [Simulation vs. Live Database Operations](#simulation-vs-live-database-operations)
8. [Meko Memory Integration](#meko-memory-integration)
9. [Prerequisites & Environment Setup](#prerequisites--environment-setup)
10. [Running the Application (PowerShell on Windows)](#running-the-application-powershell-on-windows)
11. [Running with Docker Compose](#running-with-docker-compose)
12. [Executing Automated Tests](#executing-automated-tests)
13. [Configuration & Environment Variables](#configuration--environment-variables)
14. [YugabyteDB Live Cluster Configuration](#yugabytedb-live-cluster-configuration)
15. [External Carbon Data Configuration](#external-carbon-data-configuration)
16. [Known Limitations](#known-limitations)
17. [Future Enhancements](#future-enhancements)

---

## Project Overview

Modern globally distributed SQL databases run across geographically disparate regions (e.g., India, Europe, North America). While multi-region deployments ensure high availability and survivability, electricity grids in different regions exhibit drastically different carbon intensities throughout the day due to varying solar generation, wind curtailment, and fossil fuel peaking.

**Clover** dynamically evaluates regional grid conditions, application latency budgets, and historical performance outcomes to recommend optimal database leader placements. By migrating leader leases to regions powered by renewable energy during clean-grid windows, organizations can reduce their database's operational carbon footprint by up to 60% without violating strict latency Service Level Agreements (SLAs).

---

## Problem Statement

Distributed databases traditionally optimize leader placement statically or solely for geographic proximity to users. However:
- **Carbon Intensity Fluctuates:** A region can vary from 150 gCO₂/kWh (solar peak at noon) to 650 gCO₂/kWh (coal/gas peak in evening).
- **Latency Constraints Are Real:** Migrating database leaders to the cleanest region blindly can degrade cross-region commit latency, causing transaction timeouts.
- **Flapping Causes Overhead:** Rapid back-and-forth leader movements introduce consensus churn and network re-routing penalties.
- **Operator Oversight is Mandatory:** Production database leaders must never be migrated autonomously without human operator verification and dry-run safety checks.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        React + Vite + TypeScript                       │
│      Overview  •  Topology  •  Analytics  •  Decision Center  •  Audit  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / REST (/api/*)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Backend Core                          │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Meko Context Tool (Intelligence & Aggregation Layer)             │  │
│  │  • Regional Peak Traffic Windows (IST, CET, EST & Surge Factors) │  │
│  │  • Real-Time Diurnal Carbon Emissions at That Specific Time      │  │
│  │  • Persistent Historical Regression & Latency Precedents         │  │
│  │  • Synthesizes Multi-Dimensional Context Dossier for Gemini      │  │
│  └──────────────────────────────────┬───────────────────────────────┘  │
│                                     │ Context Dossier                  │
│                                     ▼                                  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Gemini AI Decision Maker                                         │  │
│  │  • Multi-Constraint Reasoning (SLA > Peaks > Carbon > Cooldown)   │  │
│  │  • Structured Analytical Chain-of-Thought (Step-by-Step)         │  │
│  │  • Confidence Meter & Peak Hour Demand Impact Assessment         │  │
│  │  • Instant Operational Rollback Plan (SQL Tablespace Statement)  │  │
│  └──────────────────────────────────┬───────────────────────────────┘  │
│                                     │                                  │
│  ┌───────────────────────┐          ▼                                  │
│  │ Carbon Calculator     │   ┌──────────────────────────────────────┐  │
│  │  • Baseline Emissions │   │ Optimization Engine Policy Enforcer  │  │
│  │  • Energy Model       │   │  • Strict SLA Latency Budget Check   │  │
│  │  • Per 1K Tx Impact   │   │  • Anti-flapping Cooldown            │  │
│  └───────────────────────┘   └──────────────────┬───────────────────┘  │
│                                                 │                      │
│  ┌──────────────────────────────────────────────┴───────────────────┐  │
│  │ Persistent Memory Service (SQLite / Meko Schema)                 │  │
│  │  • Stores AI Model, Confidence, Chain-of-Thought & Rollback Plans│  │
│  │  • Audit Trail of Operator Approvals, Rejections & Actual Latency│  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                    │                                   │
│  ┌─────────────────────────────────┴────────────────────────────────┐  │
│  │ Modular Adapters & Telemetry Providers                           │  │
│  │  • YugabyteDB Adapter (yb_servers(), Tablespaces, Dry-Run)       │  │
│  │  • Carbon Provider (Demo Diurnal Curves / Electricity Maps API)  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```


---

## Key Features

1. **Deterministic Multi-Constraint Optimization:** Evaluates carbon intensity, latency SLAs, region health, cooldown timers, cost, and historical outcomes.
2. **Interactive Green-Tech Dashboard:** Built with Tailwind CSS, Lucide icons, and Recharts, presenting real infrastructure observability metrics.
3. **Dual Workload Profiles:**
   - **`CHECKOUT`:** Latency-critical (strict 40ms SLA); rejects migrations that jeopardize transaction response times.
   - **`BACKGROUND_ANALYTICS`:** Carbon-flexible (80ms SLA); tolerates slight latency increases to maximize clean-energy utilization.
4. **Meko-Compatible Memory Engine:** Tracks decisions, operator approvals, rejections, and post-migration latencies in SQLite. Detects prior performance regressions and surfaces contextual risk warnings.
5. **Zero-Credentials Local Simulation:** Fully functional out of the box with Mumbai, Frankfurt, and Virginia regional nodes.
6. **Safety & Operator Control:** Every recommendation requires explicit operator approval before applying placement changes, with support for dry-run simulation mode.

---

## The Optimization Decision Process

The optimization engine executes an explainable, deterministic 11-step evaluation:

1. **Resolve Workload & Thresholds:** Extracts active workload SLA (e.g. 40ms for Checkout) and operator thresholds.
2. **Current Placement & Baseline:** Identifies current leader region and calculates baseline energy/emissions.
3. **Anti-Flapping & Cooldown Verification:** Validates that `cooldown_seconds` has elapsed since the last leader migration.
4. **Identify Candidate Regions:** Discovers all alternate nodes in the cluster topology.
5. **Health Invariant Filter:** Discards any nodes marked unhealthy or unreachable.
6. **Strict Latency Budget Check:** Discards candidates whose p99 write latency exceeds the workload SLA or maximum allowed increase.
7. **Calculate Carbon Reduction:** Evaluates emissions savings using the modeled energy per transaction.
8. **Electricity Cost Analysis:** Evaluates price differential when electricity cost data is available.
9. **Historical Memory Audit:** Scans stored memory for prior recorded regressions for this workload/region pair.
10. **Rank and Threshold Gate:** Selects the highest-saving candidate and validates it satisfies `min_carbon_reduction_pct`.
11. **Explainable Recommendation:** Formulates clear, plain-language audit justification.

---

## Carbon Calculation Engine & Assumptions

The carbon calculation module (`app/services/carbon_calculator.py`) implements transparent, unit-consistent formulas:

### Formulations
$$\text{Workload Energy (kWh)} = \text{Transactions} \times \text{Assumed Energy per Transaction (kWh)}$$
$$\text{Estimated Emissions } (\text{gCO}_2) = \text{Energy (kWh)} \times \text{Carbon Intensity } (\text{gCO}_2/\text{kWh})$$
$$\text{Absolute Savings } (\text{gCO}_2) = \text{Baseline Emissions} - \text{Candidate Emissions}$$
$$\text{Reduction Percentage } (\%) = \left(\frac{\text{Absolute Savings}}{\text{Baseline Emissions}}\right) \times 100$$
$$\text{Emissions per 1,000 Transactions } (\text{gCO}_2) = 1000 \times \text{Assumed kWh/Tx} \times \text{Carbon Intensity}$$

### Energy-Accounting Assumptions
- **Baseline Assumption:** 8 mWh ($0.000008\text{ kWh}$) per transactional operation based on standard multi-core cloud database instances under active load.
- **Scope Boundary:** Models database server compute and storage energy. External WAN network transit emissions are excluded.
- **Estimation Label:** All calculated values are explicitly labeled as modeled estimates, not hardware-calibrated physical meter readings.
- **Consistent Baselines:** Migrations change the emission factor per unit of energy; they do not assume an automatic reduction in total computation.

---

## Simulation vs. Live Database Operations

| Aspect | Simulation Mode (Default) | Live Database Mode |
|---|---|---|
| **Cluster Requirement** | None (100% offline local) | YugabyteDB 2.14+ (YSQL port 5433) |
| **Topology** | Mumbai, Frankfurt, Virginia | Discovered via `SELECT * FROM yb_servers()` |
| **Leader Movement** | In-memory simulated lease update | `ALTER TABLESPACE ts_<region> SET (replica_placement=...)` |
| **Approval** | Persists simulated state in SQLite | Requires operator confirmation + SQL execution |
| **Grid Telemetry** | 24h diurnal simulated curves | Electricity Maps API or Demo fallback |
| **Data Labeling** | Clearly labeled "SIMULATION MODE" | Labeled "LIVE DATABASE MODE" |

---

## Meko Memory Integration

The memory architecture utilizes an adapter pattern:
- **`BaseMemoryAdapter`:** Abstract interface defining decision storage, outcome recording, and similarity queries.
- **`LocalMemoryAdapter`:** Built-in implementation backed by SQLite (`follow_the_green.db`), requiring zero cloud credentials.
- **`MekoMemoryAdapter`:** Cloud integration proxy that forwards audit records to Meko when `MEKO_ENABLED=true` and API credentials are provided.

### Realistic Historical Heuristics
When an operator rejects a placement or marks a migration as having degraded latency, the system records it in `decision_history`. On subsequent evaluation runs, the engine queries this memory and displays a warning:
> *"Warning: 1 previous historical placement attempt(s) for 'CHECKOUT' targeting 'eu-central-1' were rejected or degraded latency. The decision engine has adjusted its risk assessment accordingly."*

Warnings appear **only** when supported by verified rows in the persistent database.

---

## Prerequisites & Environment Setup

### Required Runtimes
- **Python:** 3.11, 3.12, or 3.13 (Installed with `pip`)
- **Node.js:** v18.0.0+ (Node v24 tested) and `npm`

---

## Running the Application (PowerShell on Windows)

Open two PowerShell terminals to run the backend and frontend concurrently:

### Terminal 1: Backend (FastAPI)

```powershell
# Navigate to the backend directory
cd C:\Users\KANAK\.gemini\antigravity\scratch\follow-the-green-leaders\backend

# Install Python dependencies
& "C:\Users\KANAK\AppData\Local\Programs\Python\Python313\python.exe" -m pip install -r requirements.txt

# Start the FastAPI server (runs on port 8000)
& "C:\Users\KANAK\AppData\Local\Programs\Python\Python313\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The backend is now accessible at:
- API Root: `http://localhost:8000/`
- Interactive Swagger Documentation: `http://localhost:8000/docs`
- Health Endpoint: `http://localhost:8000/api/health`

### Terminal 2: Frontend (React + Vite)

```powershell
# Navigate to the frontend directory
cd C:\Users\KANAK\.gemini\antigravity\scratch\follow-the-green-leaders\frontend

# Install npm dependencies (if not already installed)
npm install

# Start the Vite development server
npm run dev
```

Open your browser to: **`http://localhost:5173`**

---

## Running with Docker Compose

You can spin up both the frontend and backend with a single command:

```powershell
cd C:\Users\KANAK\.gemini\antigravity\scratch\follow-the-green-leaders

# Build and start services in background
docker compose up -d --build

# View container logs
docker compose logs -f
```

- Web Dashboard: `http://localhost:3000`
- Backend API: `http://localhost:8000/docs`

---

## Executing Automated Tests

The test suite validates carbon calculations, optimization rules, SLA boundaries, anti-flapping guards, and API status codes:

```powershell
cd C:\Users\KANAK\.gemini\antigravity\scratch\follow-the-green-leaders\backend

# Run pytest with full verbosity
& "C:\Users\KANAK\AppData\Local\Programs\Python\Python313\python.exe" -m pytest -v
```

### Frontend Typecheck & Build Verification

```powershell
cd C:\Users\KANAK\.gemini\antigravity\scratch\follow-the-green-leaders\frontend

# Run TypeScript compilation and production bundle build
npm run build
```

---

## Configuration & Environment Variables

Create a `.env` file in the project root or configure system environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `OPERATING_MODE` | `SIMULATION` | `SIMULATION` or `LIVE` |
| `YUGABYTEDB_HOST` | `localhost` | Hostname of YugabyteDB node |
| `YUGABYTEDB_PORT` | `5433` | YSQL client port |
| `YUGABYTEDB_DATABASE` | `yugabyte` | Database name |
| `YUGABYTEDB_USER` | `yugabyte` | Database username |
| `YUGABYTEDB_PASSWORD` | `""` | Database password |
| `CARBON_PROVIDER` | `DEMO` | `DEMO` (offline) or `EXTERNAL` |
| `CARBON_API_KEY` | `""` | Electricity Maps API authentication key |
| `MEKO_ENABLED` | `false` | Enable remote Meko cloud memory sync |
| `MEKO_API_ENDPOINT` | `""` | Meko agent endpoint URL |
| `COOLDOWN_SECONDS` | `120` | Anti-flapping minimum seconds between migrations |
| `MIN_CARBON_REDUCTION_PCT` | `10.0` | Minimum percentage carbon improvement to qualify |
| `MAX_LATENCY_INCREASE_MS` | `20.0` | Maximum acceptable latency increase |

---

## YugabyteDB Live Cluster Configuration

To connect a live YugabyteDB multi-region cluster:

1. Update `.env`:
   ```bash
   OPERATING_MODE=LIVE
   YUGABYTEDB_HOST=yb-tserver-mumbai.internal
   YUGABYTEDB_PORT=5433
   YUGABYTEDB_DATABASE=yugabyte
   YUGABYTEDB_USER=yugabyte
   YUGABYTEDB_PASSWORD=your_secure_password
   ```
2. In Live mode:
   - The backend checks TCP reachability and executes `yb_servers()` to map node distributions.
   - Recommended leader placements generate tablespace preference policies:
     ```sql
     ALTER TABLESPACE ts_eu_central_1 
     SET (replica_placement='{"leader_preference_region":"eu-central-1"}');
     ```
   - Placement is never executed automatically; operator confirmation (`operator_confirmed=true`) is enforced.

---

## External Carbon Data Configuration

To sync live grid carbon intensity:
1. Obtain an API token from [Electricity Maps](https://www.electricitymaps.com/).
2. Set in `.env`:
   ```bash
   CARBON_PROVIDER=EXTERNAL
   CARBON_API_KEY=your_electricity_maps_api_token
   ```
3. If the external provider experiences network failure or rate limiting, the provider returns an explicit warning rather than masking errors.

---

## Known Limitations

- **Simulated Latencies:** In simulation mode, write latencies (Mumbai: 25ms, Frankfurt: 55ms, Virginia: 35ms) and 24-hour diurnal carbon curves are modeled mathematical heuristics.
- **Physical Server Power Calibration:** The 8 mWh per transaction energy constant represents an average transactional database profile; bare-metal power meters are not interfaced.
- **WAN Transit Footprint:** Cross-regional network transit energy is omitted from the carbon boundary.

---

## Future Enhancements

- **Machine Learning Predictor:** Train an autoregressive model to forecast grid curtailment 4 to 8 hours in advance for predictive leader pre-placement.
- **Per-Table Tablespace Granularity:** Support fine-grained leader placement per individual SQL table rather than cluster-wide.
- **Real-Time PUE Telemetry:** Ingest datacenter Power Usage Effectiveness (PUE) metrics from cloud provider APIs to calibrate total power consumption.
