"""Generate dirty demo Excel files so the skeleton runs out of the box.

Inspired by Faker + the OpenRefine philosophy of "show users what messy
data looks like." Produces three files in ``data/raw/``:

* ``lab.xlsx``       -- lab results with mixed unit/item spellings,
                        ``<0.01`` / ``>1000`` strings, and a few
                        unparseable values.
* ``emr.xlsx``       -- patient records with names + ID cards (PII),
                        Chinese / English diagnoses, swapped admit /
                        discharge dates, and free-text history.
* ``followup.xlsx``  -- wide table ``patient_id, bp_m3, hba1c_m6, ...``
                        with realistic missingness, plus
                        ``followup_status.xlsx`` (last_visit_month, lost).

Run::

    python scripts/make_demo_data.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW  # noqa: E402
from _config import load_config  # noqa: E402

try:
    from faker import Faker
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "Faker is required for demo data generation. "
        "Install with: pip install faker"
    ) from exc


# Variants intentionally chosen to exercise dict + fuzzy mapping.
LAB_ITEMS = [
    "血糖", "Glucose", "GLU", "空腹血糖", " 血 糖 ",
    "肌酐", "Creatinine", "血肌酐", "肌酐 ",
    "尿素氮", "BUN",
    "血红蛋白", "Hemoglobin", "HGB",
    "白细胞", "WBC",
]
UNITS = ["mmol/L", "mmol / L", "mg/dL", "umol/L", "μmol/L", "g/L", "10^9/L", "x10^9/L"]
SEX_RAW = ["男", "女", "M", "F", "male", "Female", "1", "2", "未知", ""]
DX_RAW = [
    "2型糖尿病", "T2DM", "Type 2 diabetes", "糖尿病2型",
    "高血压", "Hypertension", "HTN", "原发性高血压",
    "冠心病", "CHD", "Coronary heart disease",
    "慢性肾病3期", "CKD stage 3",
]
HISTORY_SNIPPETS = [
    "患者吸烟20年，每日1包。",
    "饮酒史30年，已戒酒5年。",
    "no smoking, occasional drinking.",
    "无吸烟饮酒史。",
    "smoker, denies alcohol.",
    "",
]


def _dirty_value(scale: float) -> str:
    """Return a value string that may include <, >, or be unparseable."""
    r = random.random()
    if r < 0.05:
        return "ND"           # unparseable
    if r < 0.10:
        return f"<{round(scale * 0.01, 2)}"
    if r < 0.15:
        return f">{round(scale * 100, 1)}"
    if r < 0.20:
        return ""             # missing
    return str(round(random.uniform(scale * 0.5, scale * 2), 2))


def make_lab(fake: Faker, patient_ids: list[str], n_rows: int) -> pd.DataFrame:
    rows = []
    for _ in range(n_rows):
        item = random.choice(LAB_ITEMS)
        # Pick a plausible numeric scale per item.
        scale = {
            "血糖": 5, "Glucose": 5, "GLU": 5, "空腹血糖": 5, " 血 糖 ": 5,
            "肌酐": 80, "Creatinine": 80, "血肌酐": 80, "肌酐 ": 80,
            "尿素氮": 5, "BUN": 5,
            "血红蛋白": 130, "Hemoglobin": 130, "HGB": 130,
            "白细胞": 6, "WBC": 6,
        }.get(item, 10)
        rows.append({
            "patient_id": random.choice(patient_ids),
            "sample_date": fake.date_between(start_date="-2y", end_date="today"),
            "item": item,
            "value": _dirty_value(scale),
            "unit": random.choice(UNITS),
            "ref_range": "0-10",
        })
    return pd.DataFrame(rows)


def make_emr(fake: Faker, patient_ids: list[str]) -> pd.DataFrame:
    rows = []
    for pid in patient_ids:
        admit = fake.date_between(start_date="-2y", end_date="-1y")
        discharge = fake.date_between(start_date=admit, end_date="today")
        # 5% have swapped dates for the sanity-check log to flag.
        if random.random() < 0.05:
            admit, discharge = discharge, admit
        rows.append({
            "patient_id": pid,
            "name": fake.name(),
            "id_card": fake.ssn(),
            "sex": random.choice(SEX_RAW),
            "birth_date": fake.date_of_birth(minimum_age=20, maximum_age=85),
            "admit_date": admit,
            "discharge_date": discharge,
            "diagnosis": random.choice(DX_RAW),
            "history_text": random.choice(HISTORY_SNIPPETS),
        })
    return pd.DataFrame(rows)


def make_followup(patient_ids: list[str], months: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    indicators = ["bp", "hba1c"]
    cols = {f"{ind}_m{m}": [] for ind in indicators for m in months}
    status_rows = []
    for pid in patient_ids:
        # Some patients are lost to follow-up.
        lost = random.random() < 0.20
        last_visit = random.choice(months) if lost else max(months)
        status_rows.append({
            "patient_id": pid,
            "last_visit_month": last_visit,
            "lost": int(lost),
        })
        for ind in indicators:
            base = 130 if ind == "bp" else 7.0
            for m in months:
                if m > last_visit:
                    cols[f"{ind}_m{m}"].append(None)            # not_due / lost
                elif random.random() < 0.10:
                    cols[f"{ind}_m{m}"].append(None)            # missing visit
                else:
                    cols[f"{ind}_m{m}"].append(round(base + random.uniform(-10, 10), 1))
    wide = pd.DataFrame({"patient_id": patient_ids, **cols})
    status = pd.DataFrame(status_rows)
    return wide, status


def main() -> None:
    cfg = load_config()
    demo = cfg.get("demo", {})
    seed = int(demo.get("seed", 42))
    n_patients = int(demo.get("n_patients", 50))
    lab_rows = int(demo.get("lab_rows", 300))
    months = list(demo.get("followup_months", [3, 6, 12, 24]))
    locale = demo.get("locale", "zh_CN")

    random.seed(seed)
    Faker.seed(seed)
    fake = Faker(locale)

    RAW.mkdir(parents=True, exist_ok=True)
    patient_ids = [f"P{1000 + i}" for i in range(n_patients)]

    lab = make_lab(fake, patient_ids, lab_rows)
    emr = make_emr(fake, patient_ids)
    fu_wide, fu_status = make_followup(patient_ids, months)

    files = cfg.get("files", {})
    lab_path = RAW / files.get("lab", {}).get("input", "lab.xlsx")
    emr_path = RAW / files.get("emr", {}).get("input", "emr.xlsx")
    fu_path = RAW / files.get("followup", {}).get("input", "followup.xlsx")
    fu_status_path = RAW / files.get("followup", {}).get("status", "followup_status.xlsx")

    lab.to_excel(lab_path, index=False)
    emr.to_excel(emr_path, index=False)
    fu_wide.to_excel(fu_path, index=False)
    fu_status.to_excel(fu_status_path, index=False)

    print(f"[ok] wrote {lab_path}        ({len(lab)} rows)")
    print(f"[ok] wrote {emr_path}        ({len(emr)} rows)")
    print(f"[ok] wrote {fu_path}   ({len(fu_wide)} rows)")
    print(f"[ok] wrote {fu_status_path} ({len(fu_status)} rows)")


if __name__ == "__main__":
    main()
