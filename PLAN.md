# Turbofan engine RUL prediction

## Problem statement

Predictive maintenance is a core industrial ML application. The goal is to predict the Remaining Useful Life (RUL) of turbofan engines using sensor data, enabling maintenance teams to schedule interventions at the right time, not too early (wasting operational hours) and not too late (catastrophic failure).

This project uses NASA's C-MAPSS dataset (FD001 subset): 100 engines, 21 sensors, single operating condition, single fault mode (HPC degradation).

## Business justification

Unplanned engine failures cost airlines a lot per event in delays, replacements, and safety risk. Current maintenance approaches are either time-based (wasteful, cause they replace healthy components on schedule) or reactive (dangerous, cause is waiting for failure indicators). A predictive model that estimates RUL within ~10 cycles enables condition-based maintenance: service engines precisely when needed.

This project compares two approaches to delivering that prediction, a hand-built ML pipeline (Track B) and a managed platform approach (Track A), to answer a practical engineering question: when does the added complexity of a custom solution justify itself over managed tooling?

## Architecture overview

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
                    ┌─────▼─────┐            ┌──────▼──────┐
                    │  PyTorch  │            │ Snowflake ML│
                    │  (LSTM)   │            │  (Cortex)   │
                    └─────┬─────┘            └──────┬──────┘
                          │                         │
                    ┌─────▼─────┐                   │
                    │  FastAPI  │                   │
                    │ (serving) │                   │
                    └─────┬─────┘                   │
                          │                         │
                    ┌─────▼──────┐                  │
                    │ Prometheus │                   │
                    │ + Grafana  │                   │
                    │(monitoring)│                   │
                    └────────────┘                   │
                          │                         │
                          └────────────┬────────────┘
                                       │
                              ┌────────▼────────┐
                              │   Comparison    │
                              │  (same metrics, │
                              │   same test set)│
                              └─────────────────┘
```

---

## Track B: Python/PyTorch (custom pipeline)

This is the learning track. Full control, full understanding.

### Phase 1: data infrastructure

**Objective:** load raw data into Postgres, define schema, make it queryable.

**Stack:** PostgreSQL, Python (psycopg2 or SQLAlchemy)

**Steps:**
1. Design schema: `raw.sensor_readings` table (unit, cycle, 21 sensors, 3 op settings)
2. Load train_FD001.txt, test_FD001.txt, RUL_FD001.txt into Postgres
3. Validate row counts match the CSVs

**Deliverable:** populated Postgres database with raw data.

### Phase 2: feature engineering with dbt

**Objective:** transform raw sensor data into ML-ready features using SQL, version-controlled and testable.

**Stack:** dbt-postgres

**Models:**
1. `stg_sensor_readings`: clean raw data, drop flat sensors (s1, s5, s6, s10, s16, s18, s19) and constant op settings, cast types
2. `int_rul_target`: compute RUL per engine/cycle, apply piecewise linear cap at 125
3. `int_rolling_features`: compute rolling mean, std, and slope (via window functions) over 30-cycle windows per sensor per engine
4. `fct_training_features`: final joined table ready for model consumption

**Tests:**
- RUL is never negative
- RUL capped never exceeds 125
- No null values in feature columns
- Row count matches raw data

**Deliverable:** dbt project with documented models, tests passing, feature table materialized in Postgres.

### Phase 3: baseline model (XGBoost)

**Objective:** establish a performance benchmark using classical ML.

**Stack:** python, scikit-learn, XGBoost

**Steps:**
1. Query feature table from Postgres
2. Train XGBoost with GroupKFold (split by engine)
3. Evaluate on test set
4. Document baseline RMSE (current benchmark: 15.02 from the notebook ad-hoc session)

**Deliverable:** trained XGBoost model, test RMSE, feature importance analysis.

### Phase 4: deep learning model (LSTM)

**Objective:** beat the XGBoost baseline using a sequence model that learns temporal patterns directly.

**Stack:** python, PyTorch

**Steps:**
1. Build a PyTorch Dataset that creates sliding windows of 30 cycles from raw sensor data (no manual feature engineering — the LSTM learns its own)
2. Normalize sensors using min-max scaling fitted on training data only
3. Architecture: LSTM (2 layers, 64 hidden units) → dropout → linear → RUL prediction
4. Train with MSE loss, Adam optimizer, early stopping on validation loss
5. Evaluate on test set using same metrics as XGBoost
6. Compare: did the LSTM beat 15.02 RMSE?

**Deliverable:** trained LSTM model, test RMSE, comparison analysis.

### Phase 5: model serving

**Objective:** deploy the best model behind an API endpoint.

**Stack:** FastAPI, Python

**Steps:**
1. Save trained model artifact (torch.save)
2. Build FastAPI endpoint: POST /predict accepts a JSON array of sensor readings (last 30 cycles), returns predicted RUL
3. Input validation (correct number of sensors, correct window size)
4. Load model once at startup, not per request

**Deliverable:** Running API that accepts sensor data and returns RUL predictions.

### Phase 6: monitoring

**Objective:** track model health in production.

**Stack:** Prometheus, Grafana

**Metrics to track:**
- Prediction distribution (histogram of predicted RUL values over time)
- Prediction latency (p50, p95, p99)
- Input feature drift (are incoming sensor distributions shifting from training data?)
- Error rates (malformed requests, model failures)

**Deliverable:** Grafana dashboard showing model health.

---

## Track A: Snowflake ML (managed pipeline)

This is the comparison track. Same data, same problem, managed tooling.

### Phase 1: data loading

**Objective:** load raw C-MAPSS data into Snowflake.

**Stack:** Snowflake, SnowSQL or Python connector

**Steps:**
1. Create database, schema, and raw table
2. Load CSVs via PUT/COPY or Python
3. Validate row counts

### Phase 2: feature engineering with dbt

**Objective:** same transformations as Track B, running on Snowflake compute, trying to keep as replicable as possible.

**Stack:** dbt-snowflake

**Models:** same SQL models as Track B. Same logic, different warehouse. The dbt project uses profiles to target either Postgres or Snowflake.

### Phase 3: model training

**Objective:** train a model using Snowflake's built-in ML capabilities.

**Stack:** Snowflake Cortex ML or Snowpark ML

**Steps:**
1. Use Snowflake's ML functions on the same feature table
2. Document what's configurable and what's a black box
3. Evaluate on same test set with same metrics

### Phase 4: evaluation

**Objective:** Compare against Track B results.

**Comparison dimensions:**
- RMSE on same test set
- Training time
- Iteration speed (how fast can you try a new idea?)
- Flexibility (can you change the architecture? the loss function?)
- Cost (compute time, Snowflake credits vs. local GPU/CPU)
- Observability (can you monitor predictions in production?)

---

## Comparison framework

| Dimension               | Track B (PyTorch) | Track A (Snowflake ML) |
|--------------------------|-------------------|------------------------|
| Test RMSE                | TBD               | TBD                    |
| Training time            | TBD               | TBD                    |
| Feature engineering time | TBD               | TBD                    |
| Lines of code            | TBD               | TBD                    |
| Flexibility              | Full control      | Limited to platform    |
| Production readiness     | Custom serving     | Platform-dependent     |
| Monitoring               | Prometheus/Grafana | Snowflake-native?      |
| Cost                     | TBD               | TBD                    |

---

## Success criteria

1. LSTM beats XGBoost baseline (RMSE < 15.02)
2. End-to-end pipeline works: data in Postgres → dbt → model → API → prediction
3. Honest comparison with quantified tradeoffs between tracks
4. Monitoring dashboard showing model health
5. Medium article documenting the comparison with real numbers

## Deliverables

- GitHub repository with clean, documented code
- EDA notebook (done)
- XGBoost baseline notebook (done)
- LSTM training notebook
- FastAPI serving code
- dbt project (dual-target: Postgres + Snowflake)
- Grafana dashboard
- Medium article: "Custom ML pipeline vs Snowflake ML: a predictive maintenance comparison"

## Future endeavors

- Kubernetes deployment
- Complex orchestration (Airflow, Dagster)
- Automated retraining pipeline
- Multi-dataset support (FD002, FD004)