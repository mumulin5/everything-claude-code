"""Tiny helper to load ``config.yaml`` from the project root.

Kept separate from ``_common.py`` to avoid forcing PyYAML on users who
only run the original cleaning scripts.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    """Load and return the YAML config as a dict.

    Returns an empty dict if the file is missing so callers can fall back
    to defaults gracefully.
    """
    p = Path(path) if path else CONFIG_PATH
    if not p.exists():
        return {}
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover - import guard
        raise SystemExit(
            "PyYAML is required to read config.yaml. "
            "Install with: pip install pyyaml"
        ) from exc
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"{p} must contain a YAML mapping at the top level")
    return data
