import pandas as pd
from sqlalchemy import create_engine, text
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

engine = create_engine("postgresql://turbofan:turbofan@localhost:5432/turbofan")

columns = [
    "unit", "cycle", "op1", "op2", "op3",
    "s1", "s2", "s3", "s4", "s5", "s6", "s7",
    "s8", "s9", "s10", "s11", "s12", "s13", "s14",
    "s15", "s16", "s17", "s18", "s19", "s20", "s21",
]

train = pd.read_csv(DATA_DIR / "train_FD001.txt", sep=r"\s+", header=None, names=columns)
test = pd.read_csv(DATA_DIR / "test_FD001.txt", sep=r"\s+", header=None, names=columns)
rul = pd.read_csv(DATA_DIR / "RUL_FD001.txt", header=None, names=["rul"])
rul["unit"] = range(1, len(rul) + 1)

with engine.connect() as conn:
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))
    conn.commit()

train.to_sql("train_fd001", engine, schema="raw", if_exists="replace", index=False)
test.to_sql("test_fd001", engine, schema="raw", if_exists="replace", index=False)
rul.to_sql("rul_fd001", engine, schema="raw", if_exists="replace", index=False)

print("Loaded train_fd001, test_fd001, rul_fd001 into schema raw.")
