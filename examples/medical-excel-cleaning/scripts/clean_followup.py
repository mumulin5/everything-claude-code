"""Clean follow-up Excel files (wide -> long, classify missingness).

Inputs :
    data/raw/followup.xlsx        wide table, columns like:
        patient_id, bp_m3, bp_m6, bp_m12, hba1c_m3, ...
    data/raw/followup_status.xlsx (optional) columns:
        patient_id, last_visit_month, lost (0/1)

Output : data/clean/followup_long.xlsx
Schema : patient_id x indicator x month  (uniqueness enforced)

Missingness categories (`miss_type`):
    ok        - value present
    missing   - visit happened but value not recorded
    lost      - patient lost to follow-up before this visit
    not_due   - this visit point not yet reached
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pandera as pa
from pandera import Check, Column

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, load_excel, save_clean

# Sentinel used when last_visit_month is unknown: treat the patient as still
# under follow-up so we don't mis-classify a missing value as `not_due`.
_MAX_MONTH = 10**9


def main() -> None:
    src = RAW / "followup.xlsx"
    if not src.exists():
        print(f"[skip] {src} not found. Place your raw follow-up Excel there and rerun.")
        return

    df = load_excel(src)
    if "patient_id" not in df.columns:
        raise SystemExit("followup.xlsx must contain a 'patient_id' column")

    # Wide -> long via pyjanitor's pivot_longer.
    long = df.pivot_longer(
        index="patient_id",
        names_to=("indicator", "month"),
        names_pattern=r"(.+)_m(\d+)",
        values_to="value",
    )
    long["month"] = pd.to_numeric(long["month"], errors="coerce").astype("Int64")
    long["value"] = pd.to_numeric(long["value"], errors="coerce")

    # Optional: merge follow-up status to classify missingness.
    status_path = RAW / "followup_status.xlsx"
    if status_path.exists():
        status = load_excel(status_path)
        status["last_visit_month"] = pd.to_numeric(
            status.get("last_visit_month"), errors="coerce"
        ).astype("Int64")
        status["lost"] = pd.to_numeric(status.get("lost"), errors="coerce").fillna(0).astype(int)
        long = long.merge(status[["patient_id", "last_visit_month", "lost"]],
                          on="patient_id", how="left")
    else:
        long["last_visit_month"] = pd.NA
        long["lost"] = 0

    long["miss_type"] = "ok"
    val_na = long["value"].isna()
    visited = long["month"] <= long["last_visit_month"].fillna(_MAX_MONTH)
    long.loc[val_na & visited, "miss_type"] = "missing"
    long.loc[val_na & ~visited & (long["lost"] == 1), "miss_type"] = "lost"
    long.loc[val_na & ~visited & (long["lost"] == 0), "miss_type"] = "not_due"

    # Schema: every (patient_id, indicator, month) must be unique.
    schema = pa.DataFrameSchema(
        {
            "patient_id": Column(str),
            "indicator": Column(str),
            "month": Column("Int64", Check.ge(0), nullable=True),
            "value": Column(float, nullable=True),
            "miss_type": Column(str, Check.isin(["ok", "missing", "lost", "not_due"])),
        },
        unique=["patient_id", "indicator", "month"],
        strict=False,
    )
    schema.validate(long, lazy=True)

    out = save_clean(long, "followup_long.xlsx")
    print(f"[ok] wrote {out} ({len(long)} rows)")


if __name__ == "__main__":
    main()
