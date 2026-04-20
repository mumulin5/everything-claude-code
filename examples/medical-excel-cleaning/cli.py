"""Unified CLI for the medical Excel cleaning skeleton.

Inspired by dbt's single-entrypoint workflow. Wraps the existing
standalone scripts so users can run::

    python cli.py demo            # generate dirty demo Excels
    python cli.py profile         # HTML data-quality reports
    python cli.py lab             # clean only lab data
    python cli.py emr
    python cli.py followup
    python cli.py all             # lab + emr + followup

The original scripts under ``scripts/`` keep working unchanged; this
module just dispatches to their ``main()`` functions.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import typer
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "typer is required for the CLI. Install with: pip install typer"
    ) from exc


app = typer.Typer(
    add_completion=False,
    help="Clean medical Excel files: lab / emr / followup.",
    no_args_is_help=True,
)


@app.command()
def demo() -> None:
    """Generate dirty demo Excels into data/raw/ (uses Faker)."""
    import make_demo_data  # type: ignore
    make_demo_data.main()


@app.command()
def profile(
    files: list[Path] = typer.Argument(None, help="Specific Excel(s) to profile."),
) -> None:
    """Generate HTML data-quality reports for data/raw/*.xlsx."""
    import profile as _profile  # type: ignore
    _profile.main([str(f) for f in files] if files else None)


@app.command()
def lab() -> None:
    """Clean lab.xlsx -> data/clean/lab_clean.xlsx."""
    import clean_lab  # type: ignore
    clean_lab.main()


@app.command()
def emr() -> None:
    """Clean emr.xlsx -> data/clean/emr_clean.xlsx."""
    import clean_emr  # type: ignore
    clean_emr.main()


@app.command()
def followup() -> None:
    """Clean followup.xlsx -> data/clean/followup_long.xlsx."""
    import clean_followup  # type: ignore
    clean_followup.main()


@app.command(name="all")
def run_all() -> None:
    """Run lab + emr + followup in sequence."""
    lab()
    emr()
    followup()


if __name__ == "__main__":
    app()
