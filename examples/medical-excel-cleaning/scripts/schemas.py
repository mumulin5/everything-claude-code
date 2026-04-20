"""Pandera DataFrameModel schemas (P1).

Keeps every dataset's contract in one place. Class-based schemas are
more IDE-friendly than the inline ``DataFrameSchema`` dicts that the
original cleaning scripts used.

Each model also exposes a ``.validate(df, lazy=True)`` style hook via
Pandera's standard ``DataFrameModel`` API.
"""
from __future__ import annotations

import pandera as pa
from pandera.typing import Series


class LabSchema(pa.DataFrameModel):
    """Cleaned lab-result rows.

    Numeric value can be ``NaN`` (unparseable); ``value_flag`` records the
    operator (``<``, ``>``, ``<=``, ``>=``) or ``invalid``.
    """

    item_std: Series[str] = pa.Field(nullable=True)
    unit_std: Series[str] = pa.Field(nullable=True)
    value_num: Series[float] = pa.Field(nullable=True)
    value_flag: Series[str] = pa.Field(isin=["", "<", ">", "<=", ">=", "invalid"])

    class Config:
        strict = False
        coerce = True


class FollowupLongSchema(pa.DataFrameModel):
    """Long-format follow-up rows: one row per (patient, indicator, month)."""

    patient_id: Series[str]
    indicator: Series[str]
    month: Series[pa.Int64] = pa.Field(ge=0, nullable=True)
    value: Series[float] = pa.Field(nullable=True)
    miss_type: Series[str] = pa.Field(isin=["ok", "missing", "lost", "not_due"])

    class Config:
        strict = False
        coerce = True
        unique = ["patient_id", "indicator", "month"]


class EMRSchema(pa.DataFrameModel):
    """Cleaned EMR rows. Free-text and PII columns are *not* required;
    the model simply asserts what *should* be present and well-typed."""

    patient_id: Series[str] = pa.Field(nullable=True)

    class Config:
        strict = False
        coerce = True
