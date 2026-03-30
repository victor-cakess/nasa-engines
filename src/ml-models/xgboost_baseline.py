import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sklearn.model_selection import GroupKFold
from sklearn.metrics import root_mean_squared_error
from xgboost import XGBRegressor

DB_URL = "postgresql://turbofan:turbofan@localhost:5432/turbofan"
SENSORS = ["s2", "s3", "s4", "s7", "s8", "s9", "s11", "s12", "s13", "s14", "s15", "s17", "s20", "s21"]
WINDOW = 30

engine = create_engine(DB_URL)


def compute_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["unit", "cycle"]).copy()
    for s in SENSORS:
        df[f"{s}_mean"] = (
            df.groupby("unit")[s]
            .transform(lambda x: x.rolling(WINDOW, min_periods=1).mean())
        )
        df[f"{s}_std"] = (
            df.groupby("unit")[s]
            .transform(lambda x: x.rolling(WINDOW, min_periods=1).std().fillna(0))
        )
    return df


# ── Training ──────────────────────────────────────────────────────────────────

print("Loading training features from analytics.fct_training_features ...")
train_df = pd.read_sql("SELECT * FROM analytics.fct_training_features", engine)

feature_cols = [c for c in train_df.columns if c not in ("unit", "cycle", "rul", "rul_capped")]
X = train_df[feature_cols].values
y = train_df["rul_capped"].values
groups = train_df["unit"].values

model_params = dict(
    n_estimators=200,
    max_depth=5,
    learning_rate=0.1,
    random_state=42,
    n_jobs=-1,
)

print("\nCross-validation (GroupKFold, 5 splits, grouped by unit) ...")
gkf = GroupKFold(n_splits=5)
fold_rmses = []

for fold, (train_idx, val_idx) in enumerate(gkf.split(X, y, groups), start=1):
    model = XGBRegressor(**model_params)
    model.fit(X[train_idx], y[train_idx], verbose=False)
    preds = model.predict(X[val_idx])
    rmse = root_mean_squared_error(y[val_idx], preds)
    fold_rmses.append(rmse)
    print(f"  Fold {fold}: RMSE = {rmse:.4f}")

print(f"\nMean CV RMSE: {np.mean(fold_rmses):.4f} ± {np.std(fold_rmses):.4f}")

# ── Final model on all training data ─────────────────────────────────────────

print("\nTraining final model on all training data ...")
final_model = XGBRegressor(**model_params)
final_model.fit(X, y, verbose=False)

# ── Test set evaluation ───────────────────────────────────────────────────────

print("\nLoading test data from analytics.stg_test_readings ...")
test_df = pd.read_sql("SELECT * FROM analytics.stg_test_readings", engine)
test_df = compute_rolling_features(test_df)

# Keep only the last observed cycle per engine
last_cycles = test_df.sort_values("cycle").groupby("unit").last().reset_index()

X_test = last_cycles[feature_cols].values

print("Loading true RUL labels from analytics.stg_rul_labels ...")
rul_labels = pd.read_sql("SELECT * FROM analytics.stg_rul_labels", engine)
last_cycles = last_cycles.merge(rul_labels, on="unit", how="left")

preds_test = final_model.predict(X_test)
test_rmse = root_mean_squared_error(last_cycles["rul"].values, preds_test)

print(f"\nTest RMSE: {test_rmse:.4f}")
