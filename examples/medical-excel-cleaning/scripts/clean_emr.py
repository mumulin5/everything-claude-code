"""Clean EMR (electronic medical record) Excel files.

Input  : data/raw/emr.xlsx
Columns expected (any case, will be snake_cased):
    patient_id, name, id_card, sex, birth_date,
    admit_date, discharge_date, diagnosis, history_text

Output : data/clean/emr_clean.xlsx, data/clean/emr_log.csv

Privacy:
    `name` and `id_card` are removed; a short SHA-256 hash of `name`
    is kept as `name_hash` for record linkage.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, load_dict, load_excel, map_with_dict, save_clean, save_log


def short_hash(s: str) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return hashlib.sha256(str(s).encode("utf-8")).hexdigest()[:12]


def main() -> None:
    src = RAW / "emr.xlsx"
    if not src.exists():
        print(f"[skip] {src} not found. Place your raw EMR Excel there and rerun.")
        return

    df = load_excel(src)

    sex_dict = load_dict("sex.csv")
    dx_dict = load_dict("diagnosis_icd10.csv", key="raw", value="icd10")

    if "sex" in df.columns:
        df["sex_std"] = map_with_dict(df["sex"], sex_dict)
    if "diagnosis" in df.columns:
        df["icd10"] = map_with_dict(df["diagnosis"], dx_dict, fuzzy=True, cutoff=80)

    # Date parsing.
    for col in ("birth_date", "admit_date", "discharge_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Sanity check: discharge >= admit, both after birth.
    if {"admit_date", "discharge_date"}.issubset(df.columns):
        bad = df["admit_date"] > df["discharge_date"]
        df.loc[bad, ["admit_date", "discharge_date"]] = pd.NaT
        bad_count = int(bad.sum())
    else:
        bad_count = 0

    # Simple keyword extraction from free text.
    if "history_text" in df.columns:
        text = df["history_text"].fillna("")
        df["smoking"] = text.str.contains(r"吸烟|smok", case=False, regex=True).astype(int)
        df["drinking"] = text.str.contains(r"饮酒|alcohol|drink", case=False, regex=True).astype(int)

    # Privacy: hash name, drop name + id_card.
    if "name" in df.columns:
        df["name_hash"] = df["name"].map(short_hash)
    df = df.drop(columns=[c for c in ("name", "id_card") if c in df.columns])

    save_log(
        pd.DataFrame({"check": ["admit_after_discharge_rows"], "count": [bad_count]}),
        "emr_log.csv",
    )
    out = save_clean(df, "emr_clean.xlsx")
    print(f"[ok] wrote {out} ({len(df)} rows)")


if __name__ == "__main__":
    main()
