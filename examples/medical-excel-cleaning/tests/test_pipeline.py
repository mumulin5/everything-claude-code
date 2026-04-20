"""End-to-end pipeline tests for the medical-excel-cleaning skeleton.

The strategy mirrors the plan's P2 item #10:

    synthetic dirty data in -> run pipeline -> assert on output

We reuse ``make_demo_data`` for input so the tests cover the same code
path users run with ``cli.py demo``.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    """Generate demo data, run the full pipeline once, return paths."""
    raw = ROOT / "data" / "raw"
    clean = ROOT / "data" / "clean"
    interim = ROOT / "data" / "interim"
    marts = ROOT / "data" / "marts"

    backup = tmp_path_factory.mktemp("backup")
    for d in (raw, clean, interim, marts):
        d.mkdir(parents=True, exist_ok=True)
        if any(c for c in d.iterdir() if c.name != ".gitkeep"):
            shutil.copytree(d, backup / d.name, dirs_exist_ok=True)
        for child in d.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    import make_demo_data
    import clean_lab
    import clean_emr
    import clean_followup
    make_demo_data.main()
    clean_lab.main()
    clean_emr.main()
    clean_followup.main()

    yield {"raw": raw, "clean": clean, "interim": interim, "marts": marts}

    # Restore original contents.
    for d in (raw, clean, interim, marts):
        for child in d.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        src = backup / d.name
        if src.exists():
            for child in src.iterdir():
                dest = d / child.name
                if child.is_dir():
                    shutil.copytree(child, dest)
                else:
                    shutil.copy2(child, dest)


def test_cleaning_outputs_exist(pipeline):
    assert (pipeline["clean"] / "lab_clean.xlsx").exists()
    assert (pipeline["clean"] / "emr_clean.xlsx").exists()
    assert (pipeline["clean"] / "followup_long.xlsx").exists()


def test_lab_value_flag_distribution(pipeline):
    df = pd.read_excel(pipeline["clean"] / "lab_clean.xlsx")
    flags = df["value_flag"].fillna("").value_counts()
    assert "invalid" in flags.index, "expected some invalid value_flag rows"
    assert (flags.get("<", 0) + flags.get(">", 0)) > 0
    numeric_rows = df[df["value_flag"].fillna("") == ""]
    assert pd.api.types.is_numeric_dtype(numeric_rows["value_num"])


def test_followup_miss_type_counts(pipeline):
    df = pd.read_excel(pipeline["clean"] / "followup_long.xlsx")
    counts = df["miss_type"].value_counts()
    assert {"ok"}.issubset(counts.index), "no 'ok' rows produced"
    assert (counts.get("lost", 0) + counts.get("not_due", 0)) > 0
    assert not df.duplicated(subset=["patient_id", "indicator", "month"]).any()


_DIGIT_18_RE = re.compile(r"\b\d{17}[\dXx]\b")


def test_emr_no_pii_columns(pipeline):
    df = pd.read_excel(pipeline["clean"] / "emr_clean.xlsx")
    for forbidden in ("name", "id_card"):
        assert forbidden not in df.columns, f"{forbidden} should be dropped"
    assert "name_hash" in df.columns
    flat = df.fillna("").astype(str).apply(lambda c: c.str.cat(sep=" ")).str.cat(sep=" ")
    assert _DIGIT_18_RE.search(flat) is None, "18-digit ID-card pattern leaked"


def test_layered_artifacts_written(pipeline):
    """raw -> interim -> clean -> marts (parquet or csv fallback)."""
    interim_files = list(pipeline["interim"].glob("lab.*"))
    marts_files = list(pipeline["marts"].glob("followup_wide.*"))
    assert any(f.name != ".gitkeep" for f in interim_files), "no interim layer for lab"
    assert any(f.name != ".gitkeep" for f in marts_files), "no marts layer for followup"


def test_fingerprint_clustering():
    from _common import fingerprint
    assert fingerprint("血 糖 ") == fingerprint("血糖")
    assert fingerprint("Type 2 diabetes") == fingerprint("diabetes Type 2")
    assert fingerprint("") == ""
    assert fingerprint(None) == ""


def test_suggest_dict_runs(pipeline, tmp_path):
    import suggest_dict
    suggest_dict.main(out_dir=tmp_path)
    files = sorted(p.name for p in tmp_path.iterdir())
    assert "lab_item_suggestions.csv" in files
    assert "diagnosis_suggestions.csv" in files
