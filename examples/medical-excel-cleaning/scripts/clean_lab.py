"""Clean lab-result Excel files.

Input  : data/raw/lab.xlsx
Columns expected (any case, will be snake_cased):
    item, value, unit, ref_range  [+ patient_id, sample_date ...]

Outputs:
    data/interim/lab.parquet     - column/type standardized only
    data/clean/lab_clean.xlsx    - business-cleaned Excel (back-compat)
    data/clean/lab.parquet       - business-cleaned parquet
    data/clean/lab_log.csv       - audit log
    data/clean/lab_schema_errors.csv  (only on schema failure)

P2 features:
    * Real unit conversion via pint (mg/dL -> mmol/L for glucose,
      mg/dL -> umol/L for creatinine). Falls back to the dict-based
      string mapping when pint is unavailable or the conversion isn't
      defined for that lab item.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import pandera as pa

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    RAW, cfg_get, load_dict, load_excel, map_with_dict,
    save_clean, save_interim, save_log,
)
from schemas import LabSchema  # noqa: E402


VALUE_RE = re.compile(r"^\s*([<>]=?)?\s*(-?\d+(?:\.\d+)?)\s*$")

# Canonical unit per lab item (used by pint conversion).
CANONICAL_UNITS = {
    "GLU": "mmol/L",
    "CREA": "umol/L",
    "BUN": "mmol/L",
    "HGB": "g/L",
    "WBC": "10^9/L",
}


def parse_value(v):
    """Return (numeric_value, flag). Flag is '<', '>', '' or 'invalid'."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None, ""
    m = VALUE_RE.match(str(v))
    if not m:
        return None, "invalid"
    op, num = m.group(1) or "", m.group(2)
    return float(num), op


def _normalize_unit_for_pint(u: str) -> str:
    """pint expects ``mg/dL`` not ``mg / dL`` and uses ``micromolar`` etc."""
    if not u:
        return ""
    s = str(u).replace(" ", "").replace("μ", "u").replace("µ", "u")
    # pint understands these directly:
    s = s.replace("10^9/L", "1e9/L").replace("x10^9/L", "1e9/L")
    return s


def convert_units(df: pd.DataFrame) -> pd.DataFrame:
    """Convert ``value_num`` into the canonical unit per ``item_std``.

    Uses pint when available; silently no-ops on items without a known
    canonical unit, on unparseable units, or when pint isn't installed.
    Adds a ``unit_converted`` boolean column for traceability.
    """
    df["unit_converted"] = False
    try:
        import pint  # type: ignore
    except ImportError:
        return df

    ureg = pint.UnitRegistry()
    # Substance-specific conversions (mass <-> mol) need molar masses.
    molar_mass = {
        "GLU": 180.156,   # g/mol
        "CREA": 113.12,
        "BUN": 28.014,    # urea nitrogen reported as N; BUN mg/dL -> mmol/L /2.8
    }

    def _convert(row):
        item = row.get("item_std")
        unit_raw = row.get("unit_std") or row.get("unit")
        val = row.get("value_num")
        if pd.isna(val) or not item or item not in CANONICAL_UNITS:
            return pd.Series([val, unit_raw, False])
        target = CANONICAL_UNITS[item]
        src = _normalize_unit_for_pint(unit_raw)
        if not src or src == target:
            return pd.Series([val, target, False])
        try:
            q = val * ureg(src)
            try:
                converted = q.to(target)
            except pint.DimensionalityError:
                # Mass <-> molarity needs the molar mass as context.
                if item in molar_mass:
                    mw = molar_mass[item] * ureg("g/mol")
                    if "mol" in str(q.dimensionality):
                        converted = (q * mw).to(target)
                    else:
                        converted = (q / mw).to(target)
                else:
                    return pd.Series([val, unit_raw, False])
            return pd.Series([float(converted.magnitude), target, True])
        except Exception:
            return pd.Series([val, unit_raw, False])

    out = df.apply(_convert, axis=1)
    out.columns = ["value_num", "unit_std", "unit_converted"]
    df[["value_num", "unit_std", "unit_converted"]] = out
    return df


def main() -> None:
    src = RAW / cfg_get("files", "lab", "input", default="lab.xlsx")
    if not src.exists():
        print(f"[skip] {src} not found. Place your raw lab Excel there and rerun.")
        return

    df = load_excel(src)

    # --- Layer 2: interim (column/type standardization only) -----------------
    interim = df.copy()
    if "value" in interim.columns:
        interim["value_num_raw"] = pd.to_numeric(interim["value"], errors="coerce")
    save_interim(interim, "lab")

    # --- Layer 3: clean (business cleaning) ----------------------------------
    item_dict = load_dict(cfg_get("dicts", "lab_item", default="lab_item.csv"))
    unit_dict = load_dict(cfg_get("dicts", "unit", default="unit.csv"))
    item_cutoff = int(cfg_get("fuzzy", "lab_item_cutoff", default=80))

    df["item_std"] = map_with_dict(df["item"], item_dict, fuzzy=True, cutoff=item_cutoff)
    df["unit_std"] = map_with_dict(df["unit"], unit_dict)

    df[["value_num", "value_flag"]] = df["value"].apply(
        lambda x: pd.Series(parse_value(x))
    )

    # P2: real unit conversion (mg/dL -> mmol/L for glucose, etc.)
    df = convert_units(df)

    # Schema validation via DataFrameModel (P1).
    try:
        LabSchema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as err:
        save_log(err.failure_cases, cfg_get(
            "files", "lab", "schema_errors", default="lab_schema_errors.csv"))
        print(f"[warn] schema errors written ({len(err.failure_cases)} rows)")

    # Audit log.
    log = df.assign(
        item_changed=df["item"].astype(str).str.strip() != df["item_std"].astype(str),
        unit_changed=df["unit"].astype(str).str.strip() != df["unit_std"].astype(str),
    )
    log = log[(log["item_changed"]) | (log["unit_changed"]) | (log["value_flag"] == "invalid")]
    save_log(log, cfg_get("files", "lab", "log", default="lab_log.csv"))

    out = save_clean(df, cfg_get("files", "lab", "clean", default="lab_clean.xlsx"))
    # Also persist clean parquet for downstream analytics.
    from _common import _save_parquet, CLEAN
    _save_parquet(df, CLEAN, "lab")
    print(f"[ok] wrote {out} ({len(df)} rows)")


if __name__ == "__main__":
    main()
