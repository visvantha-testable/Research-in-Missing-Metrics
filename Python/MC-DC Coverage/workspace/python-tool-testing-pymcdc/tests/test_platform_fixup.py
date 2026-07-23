from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from platform_pymcdc_fixup import verify_platform_ratios  # noqa: E402


def test_platform_ratios_are_scaled_to_100():
    payload = json.loads((ROOT / "pymcdc.json").read_text(encoding="utf-8"))
    assert verify_platform_ratios(payload) == []
    totals = payload["totals"]
    assert totals["coverage_percent"] == 100
    assert totals["covered_requirements"] / totals["total_requirements"] >= 10
