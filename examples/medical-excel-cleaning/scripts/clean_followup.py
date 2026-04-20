"""Clean follow-up Excel files (wide -> long, classify missingness).

Inputs :
    data/raw/followup.xlsx        wide table, columns like:
        patient_id, bp_m3, bp_m6, bp_m12, hba1c_m3, ...
    data/raw/followup_status.xlsx (optional) columns:
        patient_id, last_visit_month, lost (0/1)

Outputs:
    data/interim/followup.parquet  - wide -> long, types only
    data/clean/followup_long.xlsx  - business-cleaned long table
    data/clean/followup.parquet
    data/marts/followup_wide.parquet - analysis-ready wide view

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    CLEAN, RAW, _save_parquet, cfg_get, load_excel,
    save_clean, save_interim, save_marts,
)
from schemas import FollowupLongSchema  # noqa: E402

# Sentinel used when last_visit_month is unknown: treat the patient as still
# under follow-up so we don't mis-classify a missing value as `not_due`.
_MAX_MONTH = 10**9


def main() -> None:
    src = RAW / cfg_get("files", "followup", "input", default="followup.xlsx")
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

    # --- Layer 2: interim (just shape + types, no business logic yet) -------
    save_interim(long.copy(), "followup")

    # Optional: merge follow-up status to classify missingness.
    status_path = RAW / cfg_get("files", "followup", "status", default="followup_status.xlsx")
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

    # Schema check via DataFrameModel (P1).
    FollowupLongSchema.validate(long, lazy=True)

    out = save_clean(long, cfg_get("files", "followup", "clean", default="followup_long.xlsx"))
    _save_parquet(long, CLEAN, "followup")

    # --- Layer 4: marts (analysis-ready wide table with miss_type counts) ---
    if not long.empty:
        wide_value = long.pivot_table(
            index="patient_id", columns=["indicator", "month"],
            values="value", aggfunc="first",
        )
        wide_value.columns = [f"{ind}_m{m}" for ind, m in wide_value.columns]
        miss_summary = long.groupby("patient_id")["miss_type"].value_counts().unstack(fill_value=0)
        miss_summary.columns = [f"miss_{c}" for c in miss_summary.columns]
        marts = wide_value.join(miss_summary, how="left").reset_index()
        save_marts(marts, "followup_wide")

    print(f"[ok] wrote {out} ({len(long)} rows)")


if __name__ == "__main__":
    main()
