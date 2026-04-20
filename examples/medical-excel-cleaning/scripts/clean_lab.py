"""Clean lab-result Excel files.

Input  : data/raw/lab.xlsx
Columns expected (any case, will be snake_cased):
    item, value, unit, ref_range  [+ patient_id, sample_date ...]

Output : data/clean/lab_clean.xlsx, data/clean/lab_log.csv
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import pandera as pa
from pandera import Check, Column

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, load_dict, load_excel, map_with_dict, save_clean, save_log


VALUE_RE = re.compile(r"^\s*([<>]=?)?\s*(-?\d+(?:\.\d+)?)\s*$")


def parse_value(v):
    """Return (numeric_value, flag). Flag is '<', '>', '' or 'invalid'."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None, ""
    m = VALUE_RE.match(str(v))
    if not m:
        return None, "invalid"
    op, num = m.group(1) or "", m.group(2)
    return float(num), op


def main() -> None:
    src = RAW / "lab.xlsx"
    if not src.exists():
        print(f"[skip] {src} not found. Place your raw lab Excel there and rerun.")
        return

    df = load_excel(src)

    item_dict = load_dict("lab_item.csv")
    unit_dict = load_dict("unit.csv")

    df["item_std"] = map_with_dict(df["item"], item_dict, fuzzy=True, cutoff=80)
    df["unit_std"] = map_with_dict(df["unit"], unit_dict)

    df[["value_num", "value_flag"]] = df["value"].apply(
        lambda x: pd.Series(parse_value(x))
    )

    # Schema validation: numeric values must be non-negative.
    schema = pa.DataFrameSchema(
        {
            "item_std": Column(str, nullable=True),
            "unit_std": Column(str, nullable=True),
            "value_num": Column(float, Check.ge(0), nullable=True),
            "value_flag": Column(str, Check.isin(["", "<", ">", "<=", ">=", "invalid"])),
        },
        strict=False,
    )
    try:
        schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as err:
        save_log(err.failure_cases, "lab_schema_errors.csv")
        print(f"[warn] schema errors written to data/clean/lab_schema_errors.csv "
              f"({len(err.failure_cases)} rows)")

    # Audit log: rows whose item/unit changed or whose value was unparseable.
    log = df.assign(
        item_changed=df["item"].astype(str).str.strip() != df["item_std"].astype(str),
        unit_changed=df["unit"].astype(str).str.strip() != df["unit_std"].astype(str),
    )
    log = log[(log["item_changed"]) | (log["unit_changed"]) | (log["value_flag"] == "invalid")]
    save_log(log, "lab_log.csv")

    out = save_clean(df, "lab_clean.xlsx")
    print(f"[ok] wrote {out} ({len(df)} rows)")


if __name__ == "__main__":
    main()
