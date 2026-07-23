from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pymcdc_metrics import compute_metrics, compute_normalized_scores  # noqa: E402


def test_training_subject_scores_100():
    mdc = ROOT / "artifacts" / "training" / "logic.py.mdc"
    if not mdc.exists():
        mdc = ROOT / "sample_subject" / "logic.py.mdc"
    metrics = compute_metrics(mdc)
    scores = compute_normalized_scores(metrics)
    assert metrics.total_requirements == 11
    assert metrics.covered_requirements == 11
    assert metrics.logical_subexpression_validation_score == 100.0
    assert scores["Logical Sub-expression Validation"] == 100.0


def test_platform_json_has_root_scores():
    payload = json.loads((ROOT / "pymcdc.json").read_text(encoding="utf-8"))
    assert payload["metric_coverage_complete"] is True
    assert payload["Condition Coverage"] == 100
    assert payload["Logical Sub-expression Validation"] == 100
