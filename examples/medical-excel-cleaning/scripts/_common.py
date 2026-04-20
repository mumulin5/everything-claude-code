"""Common helpers for the medical Excel cleaning skeleton.

All cleaning scripts share these utilities:
- load_excel: read Excel as strings and snake_case the columns
- load_dict:  read a 2-column CSV mapping (raw -> std)
- map_with_dict: exact or fuzzy mapping with RapidFuzz
- save_clean / save_log: write output + an audit log
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import janitor  # noqa: F401  registers .clean_names() on DataFrame
from rapidfuzz import process, fuzz

# Project-relative paths so scripts work regardless of CWD.
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
CLEAN = ROOT / "data" / "clean"
DICT = ROOT / "dict"


def load_excel(path: Path | str, sheet=0) -> pd.DataFrame:
    """Read Excel as strings (avoids id/codes being coerced to float)."""
    df = pd.read_excel(path, sheet_name=sheet, dtype=str)
    return df.clean_names()


def load_dict(name: str, key: str = "raw", value: str = "std") -> dict:
    """Load a 2-column mapping CSV from the dict/ folder."""
    path = DICT / name
    if not path.exists():
        return {}
    d = pd.read_csv(path, dtype=str).fillna("")
    return dict(zip(d[key].str.strip(), d[value].str.strip()))


def map_with_dict(series: pd.Series, mapping: dict, fuzzy: bool = False,
                  cutoff: int = 85) -> pd.Series:
    """Map values using a dict, optionally with fuzzy matching."""
    if not mapping:
        return series
    if not fuzzy:
        return series.map(lambda x: mapping.get(str(x).strip(), x) if pd.notna(x) else x)

    keys = list(mapping.keys())

    def _match(x):
        if pd.isna(x) or str(x).strip() == "":
            return x
        result = process.extractOne(str(x).strip(), keys, scorer=fuzz.WRatio)
        if result is None:
            return x
        match, score, _ = result
        return mapping[match] if score >= cutoff else x

    return series.map(_match)


def save_clean(df: pd.DataFrame, name: str) -> Path:
    CLEAN.mkdir(parents=True, exist_ok=True)
    out = CLEAN / name
    df.to_excel(out, index=False)
    return out


def save_log(df: pd.DataFrame, name: str) -> Path:
    CLEAN.mkdir(parents=True, exist_ok=True)
    out = CLEAN / name
    df.to_csv(out, index=False)
    return out
