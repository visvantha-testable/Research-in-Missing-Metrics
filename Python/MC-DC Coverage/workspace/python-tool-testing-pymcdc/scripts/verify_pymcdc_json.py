"""Verify unified pymcdc.json has the metric covered with yes + 100/100."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

METRIC_L4 = "Condition Coverage"
METRIC_KEY = "Logical Sub-expression Validation"


def verify(path: pathlib.Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    errors: list[str] = []

    if not payload.get("output_complete"):
        errors.append("output_complete is not true")
    if not payload.get("metric_coverage_complete"):
        errors.append("metric_coverage_complete is not true")
    if payload.get("metrics_covered") != 1:
        errors.append(f"metrics_covered is {payload.get('metrics_covered')} not 1")

    metrics = payload.get("metrics") or []
    if len(metrics) != 1:
        errors.append(f"expected 1 metric row, got {len(metrics)}")

    for row in metrics:
        name = row.get("classification", "?")
        if row.get("covered") != "yes":
            errors.append(f"{name}: covered is not 'yes'")
        if int(row.get("score", 0)) < 100:
            errors.append(f"{name}: score {row.get('score')} below 100")
        if row.get("result") != "PASS":
            errors.append(f"{name}: result is not PASS")
        if not row.get("raw_sources_present"):
            errors.append(f"{name}: raw_sources_present is false")
        if not row.get("raw_parameters"):
            errors.append(f"{name}: raw_parameters missing")
        if int(row.get("coverage_percent", 0)) < 100:
            errors.append(f"{name}: coverage_percent below 100")
        if int(row.get("platform_ratio", 0)) < 100:
            errors.append(f"{name}: platform_ratio below 100")

    totals = payload.get("totals") or payload.get("platform_totals") or {}
    if not totals:
        errors.append("missing totals block (Testable reads this like coverage.json)")
    else:
        total_req = int(totals.get("total_requirements", 0))
        if total_req > 0 and totals.get("covered_requirements", 0) / total_req < 10:
            errors.append("totals.covered_requirements ratio looks unscaled (1/100 bug)")

    for name in (METRIC_L4, METRIC_KEY):
        if int(payload.get(name, 0)) < 100:
            errors.append(f"root-level {name} is not 100")

    summary = payload.get("summary") or {}
    if summary.get("covered_requirements", 0) != summary.get("total_requirements", -1):
        errors.append("summary covered_requirements != total_requirements")

    if errors:
        print("FAIL: pymcdc.json incomplete:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("PASS: pymcdc.json has Logical Sub-expression Validation covered=yes with 100/100 score")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pymcdc-json", type=pathlib.Path, default=pathlib.Path("pymcdc.json"))
    args = parser.parse_args()
    return verify(args.pymcdc_json)


if __name__ == "__main__":
    raise SystemExit(main())
