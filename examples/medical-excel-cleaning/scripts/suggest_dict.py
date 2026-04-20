"""Suggest new dictionary entries by clustering unmapped raw values.

Borrowing from OpenRefine's *key collision* clustering: every raw value
is reduced to a fingerprint (lowercase, NFKC-normalize, strip
punctuation, sort tokens) and rows with the same fingerprint are
considered the same canonical concept.

For each cluster that is **not already** in the corresponding dict CSV,
we emit a one-row suggestion: which raw spellings appeared, how often,
and a placeholder ``std`` column for a human to fill in.

Outputs (written to the project root by default):
    suggestions/lab_item_suggestions.csv
    suggestions/diagnosis_suggestions.csv

Run::

    python scripts/suggest_dict.py
    python cli.py suggest-dict
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DICT, RAW, ROOT, cfg_get, fingerprint, load_dict, load_excel,
)


def _cluster(values: pd.Series) -> dict[str, list[tuple[str, int]]]:
    """Group raw values by fingerprint -> list of (variant, count)."""
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for v in values.dropna():
        s = str(v).strip()
        if not s:
            continue
        counts[fingerprint(s)][s] += 1
    return {fp: sorted(d.items(), key=lambda kv: kv[1], reverse=True)
            for fp, d in counts.items()}


def _known_fingerprints(dict_name: str, key: str = "raw") -> set[str]:
    """Fingerprints for everything already in a dict CSV."""
    path = DICT / dict_name
    if not path.exists():
        return set()
    d = pd.read_csv(path, dtype=str).fillna("")
    if key not in d.columns:
        return set()
    return {fingerprint(s) for s in d[key].astype(str)}


def _suggest(clusters: dict[str, list[tuple[str, int]]],
             known: set[str]) -> pd.DataFrame:
    rows = []
    for fp, variants in clusters.items():
        if not fp or fp in known:
            continue
        total = sum(c for _, c in variants)
        rows.append({
            "fingerprint": fp,
            "variants": " | ".join(f"{v}({c})" for v, c in variants),
            "total_count": total,
            "std": "",   # human fills this in
        })
    df = pd.DataFrame(rows, columns=["fingerprint", "variants", "total_count", "std"])
    if df.empty:
        return df
    return df.sort_values("total_count", ascending=False)


def _scan_excels(filename: str, column: str) -> pd.Series:
    src = RAW / filename
    if not src.exists():
        return pd.Series(dtype=str)
    df = load_excel(src)
    return df[column] if column in df.columns else pd.Series(dtype=str)


def main(out_dir: Path | str | None = None) -> None:
    out = Path(out_dir) if out_dir else ROOT / "suggestions"
    out.mkdir(parents=True, exist_ok=True)

    targets = [
        # (raw file, column, dict csv, output filename, dict-key-column)
        (cfg_get("files", "lab", "input", default="lab.xlsx"),
         "item",
         cfg_get("dicts", "lab_item", default="lab_item.csv"),
         "lab_item_suggestions.csv",
         "raw"),
        (cfg_get("files", "emr", "input", default="emr.xlsx"),
         "diagnosis",
         cfg_get("dicts", "diagnosis_icd10", default="diagnosis_icd10.csv"),
         "diagnosis_suggestions.csv",
         "raw"),
    ]

    any_written = False
    for raw_file, column, dict_csv, out_name, key in targets:
        values = _scan_excels(raw_file, column)
        if values.empty:
            print(f"[skip] {raw_file}::{column} not found, skipping {out_name}")
            continue
        clusters = _cluster(values)
        known = _known_fingerprints(dict_csv, key=key)
        suggestions = _suggest(clusters, known)
        out_path = out / out_name
        suggestions.to_csv(out_path, index=False)
        any_written = True
        print(f"[ok] wrote {out_path} ({len(suggestions)} suggestions; "
              f"scanned {len(values)} rows from {raw_file})")

    if not any_written:
        print("[skip] no raw inputs to scan; run `cli.py demo` first.")


if __name__ == "__main__":
    main()
