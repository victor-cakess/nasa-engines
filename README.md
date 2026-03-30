# Turbofan engine RUL prediction: project plan

## Problem statement

Predictive maintenance is a core industrial ML application. The goal is to predict the remaining useful life (RUL) of turbofan engines using sensor data, enabling maintenance teams to schedule interventions at the right time — not too early (wasting operational hours) and not too late (catastrophic failure).

This project uses NASA's C-MAPSS dataset (FD001 subset): 100 engines, 21 sensors, single operating condition, single fault mode (HPC degradation).

## Business justification

Unplanned engine failures cost airlines $1M+ per event in delays, replacements, and safety risk. Current maintenance approaches are either time-based (wasteful — replacing healthy components on schedule) or reactive (dangerous — waiting for failure indicators). A predictive model that estimates RUL within ~10 cycles enables condition-based maintenance: service engines precisely when needed.

This project is split into two phases. Phase 1 compares a hand-built ML pipeline against a managed platform to answer a practical engineering question: when does the added complexity of a custom solution justify itself? Phase 2 takes the trained model and deploys it inside a real-time streaming system, proving the full path from research to production.

---

## Phase 1 — ML comparison (batch)

The goal here is pure ML. No infrastructure, no serving, no monitoring. Train models, evaluate them rigorously, compare approaches, write it up.

### Architecture

```
                        ┌─────────────────────────────────────────┐
                        │           Raw C-MAPSS CSVs              │
                        └──────────────┬──────────────────────────┘
                                       │
                          ┌────────────┴────────────┐
                          │                         │
                    ┌─────▼─────┐            ┌──────▼──────┐
                    │ PostgreSQL │            │  Snowflake  │
                    │ (raw data) │            │ (raw data)  │
                    └─────┬─────┘            └──────┬──────┘
                          │                         │
                    ┌─────▼─────┐            ┌──────▼──────┐
                    │    dbt    │            │     dbt     │
                    │ (features)│            │ (features)  │
                    └─────┬─────┘            └──────┬──────┘
                          │                         │
                ┌─────────┴─────────┐        ┌──────▼──────┐
                │                   │        │ Snowflake ML│
          ┌─────▼─────┐     ┌──────▼──────┐ │  (Cortex)   │
          │  XGBoost  │     │   PyTorch   │ └──────┬──────┘
          │ (baseline)│     │   (LSTM)    │        │
          └─────┬─────┘     └──────┬──────┘        │
                │                  │               │
                └────────┬─────────┘               │
                         │                         │
                ┌────────▼─────────────────────────▼┐
                │         Comparison report          │
                │   (same test set, same metrics)    │
                └───────────────────────────────────┘
```

### Track B — Python/PyTorch (custom pipeline)

#### Step 1: Data infrastructure

**Goal:** Load raw data into Postgres, make it queryable.

**Stack:** PostgreSQL, Docker, Python (psycopg2 or SQLAlchemy)

**Work:**
- Postgres runs in a Docker container (docker-compose for local dev)
- Design schema: `raw.sensor_readings`, `raw.rul_labels` tables
- Load train_FD001.txt, test_FD001.txt, RUL_FD001.txt
- Validate row counts match CSVs

#### Step 2: Feature engineering with dbt

**Goal:** Transform raw sensor data into ML-ready features using version-controlled, testable SQL.

**Stack:** dbt-postgres

**dbt models:**
- `stg_sensor_readings` — drop flat sensors (s1, s5, s6, s10, s16, s18, s19) and constant op settings, cast types
- `int_rul_target` — compute RUL per engine/cycle, apply piecewise linear cap at 125
- `int_rolling_features` — rolling mean, std, and slope via SQL window functions over 30-cycle windows per sensor per engine
- `fct_training_features` — final joined table ready for model consumption

**dbt tests:**
- RUL is never negative
- Capped RUL never exceeds 125
- No nulls in feature columns
- Row count matches raw data

#### Step 3: Baseline model (XGBoost)

**Goal:** Establish performance benchmark. Already done in EDA phase.

**Stack:** Python, scikit-learn, XGBoost

**Result:** Test RMSE = 15.02. This is the number to beat.

#### Step 4: Deep learning model (LSTM)

**Goal:** Beat the XGBoost baseline using a sequence model that learns temporal patterns directly.

**Stack:** Python, PyTorch

**Work:**
- Build a PyTorch Dataset that creates sliding windows of 30 cycles from raw (normalized) sensor data — no manual feature engineering, the LSTM learns its own features
- Normalize sensors using min-max scaling fitted on training data only
- Architecture: LSTM (2 layers, 64 hidden units) → dropout → linear → RUL prediction
- Train with MSE loss, Adam optimizer, early stopping on validation loss
- Evaluate on test set using same metrics as XGBoost

### Track A — Snowflake ML (managed pipeline)

#### Step 1: Data loading

**Goal:** Same raw data into Snowflake.

**Stack:** Snowflake, SnowSQL or Python connector

#### Step 2: Feature engineering with dbt

**Goal:** Same transformations as Track B, running on Snowflake compute.

**Stack:** dbt-snowflake

Same SQL models, different dbt profile. Write once, run on both warehouses.

#### Step 3: Model training

**Goal:** Train using Snowflake's built-in ML capabilities.

**Stack:** Snowflake Cortex ML or Snowpark ML

Document what's configurable and what's a black box.

### Comparison framework

| Dimension              | Track B (PyTorch) | Track A (Snowflake ML) |
|------------------------|-------------------|------------------------|
| Test RMSE              | TBD               | TBD                    |
| Training time          | TBD               | TBD                    |
| Lines of code          | TBD               | TBD                    |
| Flexibility            | Full control      | Limited to platform    |
| Iteration speed        | TBD               | TBD                    |
| Cost                   | TBD               | TBD                    |

### Phase 1 deliverables

- GitHub repository with clean, documented code
- EDA notebook (done)
- XGBoost baseline notebook (done)
- LSTM training notebook
- dbt project (dual-target: Postgres + Snowflake)
- Medium article: "Custom ML pipeline vs Snowflake ML: a predictive maintenance comparison"

---

## Phase 2 — Real-time inference (streaming)

The goal here is production deployment. Take the trained model from Phase 1 and serve predictions in a real-time streaming system with full observability.

### Architecture

```
┌──────────────┐     ┌─────────┐     ┌───────────────────┐     ┌─────────┐
│  Fleet       │     │         │     │                   │     │         │
│  simulator   ├────►│  Kafka  ├────►│  Flink (Java)     │     │ FastAPI │
│  (Python)    │     │ (raw    │     │  - window 30      │────►│ (model  │
│              │     │  topic) │     │    cycles/engine   │     │  serve) │
└──────────────┘     └─────────┘     │  - compute        │     └────┬────┘
                                     │    features        │          │
                                     └───────────────────┘          │
                                                                    │
                                          ┌─────────────┐          │
                                          │   Kafka      │◄─────────┘
                                          │ (predictions │
                                          │    topic)    │
                                          └──────┬──────┘
                                                 │
                                          ┌──────▼──────┐
                                          │  Postgres   │
                                          │ (prediction │
                                          │    store)   │
                                          └──────┬──────┘
                                                 │
                                          ┌──────▼──────┐
                                          │  Grafana +  │
                                          │ Prometheus  │
                                          └─────────────┘
```

### Step 1: Fleet simulator

**Goal:** Replay C-MAPSS training data as a realistic real-time stream.

**Stack:** Python

**How it works:**
- Reads training data row by row per engine
- Publishes each row to a Kafka topic keyed by engine ID
- Timestamps are wall clock time (not simulated), so Grafana queries work naturally
- Time compression: 1 flight = 5 seconds (configurable). Full fleet runs ~30 minutes
- 100 engines publishing concurrently, each at its own lifecycle stage
- Cycle number preserved as a data field for domain context

**Realism:**
- One cycle = one flight in reality
- Commercial aircraft average ~4 flights/day
- At 5 seconds per flight, a 200-cycle engine life plays out in ~17 minutes
- Engines start and fail at different times, simulating a real fleet

### Step 2: Flink feature computation

**Goal:** Window and prepare sensor data for inference in real time.

**Stack:** Apache Flink (Java)

**Work:**
- Consume from raw sensor Kafka topic
- Maintain a 30-cycle sliding window per engine (keyed state)
- Compute features within the window (normalization, or pass raw window to model)
- Publish feature-ready windows to a second Kafka topic or call inference directly

**Design decision:** Flink handles windowing and feature computation only. Model inference is decoupled — same pattern as the wind turbine project (lesson learned: decouple processing from the sink).

### Step 3: Model serving

**Goal:** Serve RUL predictions via HTTP.

**Stack:** FastAPI, PyTorch

**Work:**
- Load trained LSTM model at startup
- POST /predict accepts a 30-cycle window of sensor readings, returns predicted RUL
- A separate Python consumer reads feature-ready windows from Kafka, calls the API, publishes predictions to a predictions Kafka topic

**Why FastAPI instead of embedding the model in Flink:**
- Model is in Python (PyTorch), Flink jobs are in Java
- Decoupled: update the model without redeploying Flink
- Could later swap to ONNX runtime in Java if latency matters

### Step 4: Prediction storage

**Goal:** Store predictions for Grafana querying and historical analysis.

**Stack:** PostgreSQL

**Work:**
- Consumer reads from predictions Kafka topic
- Writes to a `predictions` table: engine_id, timestamp, predicted_rul, sensor_snapshot
- Grafana queries this table

### Step 5: Monitoring and observability

**Goal:** Live dashboard showing fleet health and model behavior.

**Stack:** Prometheus, Grafana

**Grafana dashboards:**
- Fleet overview: all 100 engines, current predicted RUL, color-coded (green/yellow/red)
- Individual engine drilldown: RUL prediction over time, key sensor trends
- Alert panel: engines predicted to fail within N cycles

**Prometheus metrics:**
- Prediction latency (p50, p95, p99)
- API request rate and error rate
- Prediction distribution (histogram of current RUL predictions)
- Input feature drift (sensor value distributions vs training data baseline)

### Phase 2 deliverables

- Fleet simulator script (Python)
- Flink windowing job (Java)
- FastAPI model serving endpoint
- Kafka consumer for inference bridge
- Postgres prediction store
- Grafana dashboard
- Docker Compose for the full stack
- Medium article: "From batch ML to real-time inference: deploying predictive maintenance on a streaming pipeline"

---

## What we are NOT building

- A frontend / UI (Grafana is the interface)
- Kubernetes (Docker Compose is sufficient for portfolio)
- Complex orchestration (Airflow, Dagster)
- Automated retraining pipeline (future scope)
- Multi-dataset support (FD002-FD004 are future scope)

## Success criteria

1. LSTM beats XGBoost baseline (RMSE < 15.02)
2. Honest comparison between PyTorch and Snowflake ML with quantified tradeoffs
3. Fleet simulator produces realistic real-time data through Kafka
4. Flink windows sensor data and triggers inference correctly
5. Grafana shows live fleet health with working alerts
6. Two Medium articles documenting both phases
7. Clean GitHub repository with documentation

## Portfolio story

Phase 1 says "I understand ML fundamentals — model selection, evaluation, feature engineering, and the tradeoffs between custom and managed solutions."

Phase 2 says "I can deploy ML in a real-time streaming system with proper infrastructure — Kafka, Flink, model serving, observability."

Together they say "I can take a model from research to real-time production." That's the Staff/Principal Engineer narrative.