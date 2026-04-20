"""Common helpers for the medical Excel cleaning skeleton.

All cleaning scripts share these utilities:
- load_excel: read Excel as strings and snake_case the columns
- load_dict:  read a 2-column CSV mapping (raw -> std)
- map_with_dict: exact or fuzzy mapping with RapidFuzz
- save_clean / save_log: write output + an audit log
- save_interim / save_marts: parquet for the dbt-style data layers
- fingerprint: OpenRefine-style key-collision string normalization
- get_config: cached config.yaml access (paths, dicts, fuzzy, anonymization)
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import pandas as pd
import janitor  # noqa: F401  registers .clean_names() on DataFrame
from rapidfuzz import process, fuzz

# Project-relative paths so scripts work regardless of CWD.
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
CLEAN = ROOT / "data" / "clean"
MARTS = ROOT / "data" / "marts"
DICT = ROOT / "dict"
REPORTS = ROOT / "reports"


@lru_cache(maxsize=1)
def get_config() -> dict:
    """Return the parsed config.yaml dict (cached). Empty dict if missing."""
    from _config import load_config  # local import to avoid hard PyYAML dep
    return load_config()


def cfg_get(*keys, default=None):
    """Nested config lookup: ``cfg_get('fuzzy', 'lab_item_cutoff', default=80)``."""
    node = get_config()
    for k in keys:
        if not isinstance(node, dict) or k not in node:
            return default
        node = node[k]
    return node if node is not None else default


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
    """Write cleaning output as Excel (back-compat with original skeleton)."""
    CLEAN.mkdir(parents=True, exist_ok=True)
    out = CLEAN / name
    df.to_excel(out, index=False)
    return out


def save_log(df: pd.DataFrame, name: str) -> Path:
    CLEAN.mkdir(parents=True, exist_ok=True)
    out = CLEAN / name
    df.to_csv(out, index=False)
    return out


def _save_parquet(df: pd.DataFrame, target_dir: Path, name: str) -> Path:
    """Best-effort parquet writer. Falls back to CSV if no engine installed."""
    target_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(name).stem
    parquet_path = target_dir / f"{stem}.parquet"
    try:
        df.to_parquet(parquet_path, index=False)
        return parquet_path
    except (ImportError, ValueError):
        # pyarrow / fastparquet missing -- degrade gracefully.
        csv_path = target_dir / f"{stem}.csv"
        df.to_csv(csv_path, index=False)
        return csv_path


def save_interim(df: pd.DataFrame, name: str) -> Path:
    """Layer 2: column / type standardized. Parquet (or CSV fallback)."""
    return _save_parquet(df, INTERIM, name)


def save_marts(df: pd.DataFrame, name: str) -> Path:
    """Layer 4: analysis-ready wide table. Parquet (or CSV fallback)."""
    return _save_parquet(df, MARTS, name)


# ---- OpenRefine-style fingerprint (used by suggest_dict.py) -----------------

_PUNCT_RE = re.compile(r"[\s\u3000\u00A0\W_]+", flags=re.UNICODE)
# Whitespace between two CJK characters is almost always a typo, not a token
# boundary. Single-pass collapse using lookbehind + lookahead so chains like
# "血 糖 测 试" reduce in one substitution.
_CJK_WS_RE = re.compile(
    r"(?<=[\u3400-\u9fff\uF900-\uFAFF])[\s\u3000\u00A0]+(?=[\u3400-\u9fff\uF900-\uFAFF])"
)


def fingerprint(s: str) -> str:
    """Key-collision fingerprint: lowercase, NFKC-normalize, collapse
    intra-CJK whitespace, strip punctuation, tokenize, dedupe, sort, rejoin.

    Maps strings like ``"血 糖 "`` and ``"血糖"`` to the same key, and
    ``"Type 2 diabetes"`` / ``"diabetes type 2"`` to the same key.
    """
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s)).strip().lower()
    if not s:
        return ""
    s = _CJK_WS_RE.sub("", s)
    tokens = [t for t in _PUNCT_RE.split(s) if t]
    return " ".join(sorted(set(tokens)))
