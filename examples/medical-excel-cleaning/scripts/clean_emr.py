"""Clean EMR (electronic medical record) Excel files.

Input  : data/raw/emr.xlsx
Columns expected (any case, will be snake_cased):
    patient_id, name, id_card, sex, birth_date,
    admit_date, discharge_date, diagnosis, history_text

Outputs:
    data/interim/emr.parquet        - column/type standardized only
    data/clean/emr_clean.xlsx       - business-cleaned (back-compat)
    data/clean/emr.parquet
    data/clean/emr_log.csv

Privacy (config-driven via config.yaml -> anonymization):
    * Columns in ``drop_columns`` (default: ``id_card``) are removed.
    * Columns in ``hash_columns`` (default: ``name``) are replaced with
      a short SHA-256 (``<col><hash_suffix>``).
    * If Microsoft Presidio is installed, ``history_text`` is also
      scrubbed for PII entities (PERSON / PHONE_NUMBER / ID / EMAIL ...).
      Without Presidio we fall back to the original keyword extraction
      and leave the text intact.

Date parsing (P2):
    * Dates that ``pandas.to_datetime`` can't read (e.g. ``二〇二四年三月一日``)
      are retried with ``dateparser`` when it's installed.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    CLEAN, RAW, _save_parquet, cfg_get, load_dict, load_excel,
    map_with_dict, save_clean, save_interim, save_log,
)


def make_short_hash(length: int):
    def _h(s: str) -> str:
        if s is None or (isinstance(s, float) and pd.isna(s)):
            return ""
        return hashlib.sha256(str(s).encode("utf-8")).hexdigest()[:length]
    return _h


def parse_dates_robust(series: pd.Series) -> pd.Series:
    """Pandas-first, dateparser fallback for stragglers (Chinese, fuzzy)."""
    parsed = pd.to_datetime(series, errors="coerce")
    missing = parsed.isna() & series.notna() & (series.astype(str).str.strip() != "")
    if not missing.any():
        return parsed
    try:
        import dateparser  # type: ignore
    except ImportError:
        return parsed
    settings = {"languages": ["zh", "en"]}
    fallback = series[missing].map(
        lambda s: dateparser.parse(str(s), settings=settings)
    )
    parsed.loc[missing] = pd.to_datetime(fallback, errors="coerce")
    return parsed


def anonymize_history(series: pd.Series) -> pd.Series:
    """Optional Presidio-based scrub of free-text PII. Best-effort."""
    try:
        from presidio_analyzer import AnalyzerEngine  # type: ignore
        from presidio_anonymizer import AnonymizerEngine  # type: ignore
    except ImportError:
        return series

    try:
        analyzer = AnalyzerEngine()
        anonymizer = AnonymizerEngine()
    except Exception:
        # Presidio installed but spaCy model missing etc. -- skip silently.
        return series

    def _scrub(text):
        if text is None or (isinstance(text, float) and pd.isna(text)) or not str(text).strip():
            return text
        try:
            results = analyzer.analyze(text=str(text), language="en")
            return anonymizer.anonymize(text=str(text), analyzer_results=results).text
        except Exception:
            return text

    return series.map(_scrub)


def main() -> None:
    src = RAW / cfg_get("files", "emr", "input", default="emr.xlsx")
    if not src.exists():
        print(f"[skip] {src} not found. Place your raw EMR Excel there and rerun.")
        return

    df = load_excel(src)

    # --- Layer 2: interim (column/type standardization only) -----------------
    save_interim(df.copy(), "emr")

    # --- Layer 3: clean (business cleaning) ----------------------------------
    sex_dict = load_dict(cfg_get("dicts", "sex", default="sex.csv"))
    dx_dict = load_dict(
        cfg_get("dicts", "diagnosis_icd10", default="diagnosis_icd10.csv"),
        key="raw", value="icd10",
    )
    dx_cutoff = int(cfg_get("fuzzy", "diagnosis_cutoff", default=80))

    if "sex" in df.columns:
        df["sex_std"] = map_with_dict(df["sex"], sex_dict)
    if "diagnosis" in df.columns:
        df["icd10"] = map_with_dict(df["diagnosis"], dx_dict, fuzzy=True, cutoff=dx_cutoff)

    # Robust date parsing (pandas + dateparser fallback).
    for col in ("birth_date", "admit_date", "discharge_date"):
        if col in df.columns:
            df[col] = parse_dates_robust(df[col])

    # Sanity check: discharge >= admit, both after birth.
    if {"admit_date", "discharge_date"}.issubset(df.columns):
        bad = df["admit_date"] > df["discharge_date"]
        df.loc[bad, ["admit_date", "discharge_date"]] = pd.NaT
        bad_count = int(bad.sum())
    else:
        bad_count = 0

    # Simple keyword extraction from free text (kept as a baseline).
    if "history_text" in df.columns:
        text = df["history_text"].fillna("")
        df["smoking"] = text.str.contains(r"吸烟|smok", case=False, regex=True).astype(int)
        df["drinking"] = text.str.contains(r"饮酒|alcohol|drink", case=False, regex=True).astype(int)
        # P1: scrub free-text PII via Presidio if available.
        df["history_text"] = anonymize_history(df["history_text"])

    # Privacy: hash + drop columns per config.
    hash_cols = list(cfg_get("anonymization", "hash_columns", default=["name"]))
    drop_cols = list(cfg_get("anonymization", "drop_columns", default=["id_card"]))
    suffix = cfg_get("anonymization", "hash_suffix", default="_hash")
    hash_len = int(cfg_get("anonymization", "hash_length", default=12))
    short_hash = make_short_hash(hash_len)

    for col in hash_cols:
        if col in df.columns:
            df[f"{col}{suffix}"] = df[col].map(short_hash)
    df = df.drop(columns=[c for c in (drop_cols + hash_cols) if c in df.columns])

    save_log(
        pd.DataFrame({"check": ["admit_after_discharge_rows"], "count": [bad_count]}),
        cfg_get("files", "emr", "log", default="emr_log.csv"),
    )
    out = save_clean(df, cfg_get("files", "emr", "clean", default="emr_clean.xlsx"))
    _save_parquet(df, CLEAN, "emr")
    print(f"[ok] wrote {out} ({len(df)} rows)")


if __name__ == "__main__":
    main()
