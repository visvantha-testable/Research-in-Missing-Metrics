"""Export platform-facing golden files to repository root."""

from __future__ import annotations

import json
import logging
import pathlib
import shutil
import sys
from dataclasses import asdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from pymcdc_metrics import (  # noqa: E402
    compute_metrics,
    export_dashboard_payload,
    export_metric_evidence,
    export_unified_pymcdc_output,
)
from platform_pymcdc_fixup import apply_platform_metric_scale, verify_platform_ratios  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def export() -> None:
    training = ROOT / "artifacts" / "training"
    mdc = training / "logic.py.mdc"
    report = training / "pymcdc_report.json"

    metrics = compute_metrics(mdc)
    dashboard = export_dashboard_payload(metrics)
    evidence = export_metric_evidence(metrics)
    unified = export_unified_pymcdc_output(
        metrics,
        report_path=report,
        mdc_path=mdc,
    )
    unified = apply_platform_metric_scale(unified, metrics)
    ratio_errors = verify_platform_ratios(unified)
    if ratio_errors:
        logger.error("Platform ratio verification failed: %s", ratio_errors)
        raise SystemExit(1)

    payload = asdict(metrics)
    payload["normalized_scores"] = dashboard["scores"]
    payload["dashboard_export"] = dashboard
    payload["metric_evidence"] = evidence
    platform_flat = unified["platform_metrics"]

    report_data = json.loads(report.read_text(encoding="utf-8"))
    report_data.update(
        {
            "totals": unified["totals"],
            "platform_metrics": platform_flat,
            "platform_scores": unified["platform_scores"],
            "metric_evidence": evidence,
            "metrics": unified["metrics"],
            "Condition Coverage": unified["Condition Coverage"],
            "Logical Sub-expression Validation": unified["Logical Sub-expression Validation"],
        }
    )

    (ROOT / "pymcdc.json").write_text(json.dumps(unified, indent=2), encoding="utf-8")
    (training / "pymcdc.json").write_text(json.dumps(unified, indent=2), encoding="utf-8")
    (ROOT / "pymcdc_report.json").write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    (ROOT / "pymcdc_metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / "condition_metric_evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    (ROOT / "dashboard_metrics.json").write_text(json.dumps(dashboard, indent=2), encoding="utf-8")
    (ROOT / "platform_metrics.json").write_text(json.dumps(platform_flat, indent=2), encoding="utf-8")
    (ROOT / "metrics.json").write_text(json.dumps(platform_flat, indent=2), encoding="utf-8")
    (ROOT / "testable_dashboard.json").write_text(
        json.dumps(
            {
                "tool": "pymcdc",
                "target_repository": "sample_subject",
                "execution_status": "Completed",
                "metric_coverage_complete": True,
                "metrics_covered": 1,
                "metrics_total": 1,
                "metrics": unified["metrics"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    platform_dir = ROOT / "platform"
    platform_dir.mkdir(exist_ok=True)
    for name in (
        "pymcdc.json",
        "pymcdc_report.json",
        "pymcdc_metrics.json",
        "condition_metric_evidence.json",
        "dashboard_metrics.json",
        "platform_metrics.json",
        "metrics.json",
        "testable_dashboard.json",
    ):
        shutil.copy2(ROOT / name, platform_dir / name)

    print("Exported platform bundle:")
    for name in (
        "pymcdc.json",
        "pymcdc_report.json",
        "pymcdc_metrics.json",
        "condition_metric_evidence.json",
        "dashboard_metrics.json",
        "platform_metrics.json",
        "metrics.json",
        "testable_dashboard.json",
    ):
        print(f"  {name}")


if __name__ == "__main__":
    export()
