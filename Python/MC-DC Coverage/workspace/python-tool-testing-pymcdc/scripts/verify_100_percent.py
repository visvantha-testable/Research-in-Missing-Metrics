"""Verify dashboard and metrics JSON report 100/100."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

METRIC_KEY = "Logical Sub-expression Validation"


def verify(metrics_json: pathlib.Path, dashboard_json: pathlib.Path) -> int:
    metrics = json.loads(metrics_json.read_text(encoding="utf-8-sig"))
    dashboard = json.loads(dashboard_json.read_text(encoding="utf-8-sig"))
    errors: list[str] = []

    score = float(metrics.get("logical_subexpression_validation_score", 0))
    if score < 100.0:
        errors.append(f"logical_subexpression_validation_score is {score}, expected 100")

    normalized = metrics.get("normalized_scores") or {}
    if float(normalized.get(METRIC_KEY, 0)) < 100.0:
        errors.append(f"normalized_scores[{METRIC_KEY}] below 100")

    if not dashboard.get("metric_coverage_complete"):
        errors.append("dashboard metric_coverage_complete is false")

    rows = dashboard.get("rows") or []
    if not rows or int(rows[0].get("score", 0)) < 100:
        errors.append("dashboard row score below 100")

    if errors:
        print("FAIL:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("PASS: all metrics are 100/100")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics-json", type=pathlib.Path, default=pathlib.Path("pymcdc_metrics.json"))
    parser.add_argument("--dashboard-json", type=pathlib.Path, default=pathlib.Path("dashboard_metrics.json"))
    args = parser.parse_args()
    return verify(args.metrics_json, args.dashboard_json)


if __name__ == "__main__":
    raise SystemExit(main())
