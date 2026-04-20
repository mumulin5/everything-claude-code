"""Generate one HTML data-quality report per Excel in ``data/raw/``.

Inspired by ydata-profiling (formerly pandas-profiling) and the
OpenRefine "Facet" idea: before cleaning, look at what's actually in the
data -- missing rates, unique values, distributions, duplicate rows.

Output goes to ``reports/<stem>.html``.

Run::

    python scripts/profile.py
    python scripts/profile.py data/raw/lab.xlsx   # one specific file
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, ROOT  # noqa: E402
from _config import load_config  # noqa: E402


def _profile_one(src: Path, out_dir: Path) -> Path:
    try:
        from ydata_profiling import ProfileReport  # type: ignore
    except ImportError as exc:  # pragma: no cover - import guard
        raise SystemExit(
            "ydata-profiling is required for profile.py. "
            "Install with: pip install ydata-profiling"
        ) from exc

    df = pd.read_excel(src, dtype=str)
    report = ProfileReport(
        df,
        title=f"Data profile: {src.name}",
        minimal=True,          # fast + safe on wide medical tables
        explorative=False,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{src.stem}.html"
    report.to_file(out)
    return out


def main(argv: list[str] | None = None) -> None:
    cfg = load_config()
    reports_dir = ROOT / cfg.get("paths", {}).get("reports", "reports")

    args = argv if argv is not None else sys.argv[1:]
    if args:
        targets = [Path(a) for a in args]
    else:
        targets = sorted(RAW.glob("*.xlsx"))

    if not targets:
        print(f"[skip] no Excel files in {RAW}. Run make_demo_data.py first.")
        return

    for src in targets:
        if not src.exists():
            print(f"[skip] {src} not found")
            continue
        out = _profile_one(src, reports_dir)
        print(f"[ok] wrote {out}")


if __name__ == "__main__":
    main()
