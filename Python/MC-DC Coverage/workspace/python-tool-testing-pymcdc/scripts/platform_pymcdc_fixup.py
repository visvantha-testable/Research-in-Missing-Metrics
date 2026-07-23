"""Post-process pymcdc JSON so Testable platform ratio metrics read as 0-100, not 0-1."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymcdc_metrics import PymcdcMetrics

logger = logging.getLogger(__name__)

METRIC_L4 = "Condition Coverage"
METRIC_KEY = "Logical Sub-expression Validation"


def apply_platform_metric_scale(unified: dict, metrics: "PymcdcMetrics") -> dict:
    """Embed totals + root-level L4/L5 scores for Testable (coverage.json pattern)."""
    score = int(round(metrics.logical_subexpression_validation_score))
    total_req = max(metrics.total_requirements, 1)
    covered = metrics.covered_requirements

    totals = {
        "decision_count": metrics.decision_count,
        "total_requirements": total_req,
        "covered_requirements": 100 * covered if score >= 100 else covered,
        "uncovered_requirements": metrics.uncovered_requirements,
        "coverage_percent": score,
        "condition_coverage_percent": score,
        "logical_subexpression_validation_score": score,
        "condition_coverage_ratio": score,
        "logical_subexpression_ratio": score,
        "mcdc_requirements_met": covered,
        "subexpression_true_evaluations": metrics.subexpression_true_evaluations,
        "subexpression_false_evaluations": metrics.subexpression_false_evaluations,
        "subexpression_both_sides_validated": metrics.subexpression_both_sides_validated,
        "short_circuit_irrelevant_slots": metrics.short_circuit_irrelevant_slots,
    }

    unified["totals"] = totals
    unified["platform_totals"] = totals
    unified[METRIC_L4] = score
    unified[METRIC_KEY] = score
    unified["logical_subexpression_validation_score"] = score
    unified["condition_coverage_percent"] = score
    unified["condition_coverage_score"] = score

    platform_metrics = unified.setdefault("platform_metrics", {})
    platform_metrics.update(
        {
            METRIC_L4: score,
            METRIC_KEY: score,
            "logical_subexpression_validation_score": score,
            "condition_coverage_percent": score,
        }
    )
    unified["platform_metrics"] = platform_metrics
    unified["platform_scores"] = {
        METRIC_L4: float(score),
        METRIC_KEY: float(score),
    }
    return unified


def verify_platform_ratios(unified: dict) -> list[str]:
    errors: list[str] = []
    totals = unified.get("totals") or {}
    total_req = int(totals.get("total_requirements", 0))
    if total_req > 0:
        covered = totals.get("covered_requirements", 0)
        if isinstance(covered, (int, float)) and covered / total_req < 10:
            errors.append("totals.covered_requirements ratio looks unscaled (1/100 bug)")
    for key in (METRIC_L4, METRIC_KEY):
        if int(unified.get(key, 0)) < 100:
            errors.append(f"root-level {key} is not 100")
    return errors
