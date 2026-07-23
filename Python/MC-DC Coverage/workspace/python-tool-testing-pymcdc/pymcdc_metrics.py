"""Condition Coverage metrics from pymcdc MC/DC analysis."""

from __future__ import annotations

import argparse
import json
import pathlib
import pickle
import subprocess
import sys
from dataclasses import asdict, dataclass


METRIC_L4 = "Condition Coverage"
METRIC_L5 = "Logical Sub-expression Validation"
METRIC_KEY = "Logical Sub-expression Validation"


@dataclass
class PymcdcMetrics:
    decision_count: int
    total_requirements: int
    covered_requirements: int
    uncovered_requirements: int
    coverage_percent: float
    logical_subexpression_validation_score: float
    subexpression_true_evaluations: int
    subexpression_false_evaluations: int
    subexpression_both_sides_validated: int
    mcdc_requirements_met: int
    short_circuit_irrelevant_slots: int


def _strip_bom(path: pathlib.Path) -> None:
    text = path.read_text(encoding="utf-8-sig")
    path.write_text(text, encoding="utf-8", newline="\n")


def run_pymcdc_analysis(
    *,
    source: pathlib.Path,
    unittest: pathlib.Path,
    subject_dir: pathlib.Path,
    python_exe: str = sys.executable,
) -> None:
    """Run static analysis then unittest coverage (creates source.mdc)."""
    _strip_bom(source)
    _strip_bom(unittest)
    env = {"PYTHONIOENCODING": "utf-8", **dict(__import__("os").environ)}
    subprocess.check_call(
        [python_exe, "-m", "pymcdc", str(source.name)],
        cwd=subject_dir,
        env=env,
    )
    subprocess.check_call(
        [
            python_exe,
            "-m",
            "pymcdc",
            "--unittest",
            str(unittest.name),
            "--path",
            ".",
            str(source.name),
        ],
        cwd=subject_dir,
        env=env,
    )


def load_decisions(mdc_path: pathlib.Path) -> dict:
    if not mdc_path.exists():
        raise FileNotFoundError(f"Missing pymcdc execution log: {mdc_path}")
    with mdc_path.open("rb") as handle:
        return pickle.load(handle)


def _count_subexpression_evaluations(decisions: dict) -> tuple[int, int, int]:
    true_count = false_count = both_count = 0
    for dec in decisions.values():
        table = dec.to_table()
        if len(table) < 2:
            continue
        headers = table[0]
        for row in table[1:]:
            for cell, header in zip(row[:-1], headers[1:-1]):
                if cell == "----":
                    continue
                if cell == "True":
                    true_count += 1
                elif cell == "False":
                    false_count += 1
            if row[-1] == "True":
                both_count += sum(1 for cell in row[:-1] if cell in ("True", "False"))
    return true_count, false_count, both_count


def compute_metrics(mdc_path: pathlib.Path) -> PymcdcMetrics:
    decisions = load_decisions(mdc_path)
    total_req = covered_req = 0
    short_circuit = 0

    for dec in decisions.values():
        cov, req = dec.get_covered_requirements()
        total_req += req
        covered_req += cov
        table = dec.to_table()
        for row in table[1:]:
            short_circuit += sum(1 for cell in row[:-1] if cell == "----")

    uncovered = max(total_req - covered_req, 0)
    coverage = 100.0 if total_req == 0 else covered_req * 100.0 / total_req
    true_eval, false_eval, both_valid = _count_subexpression_evaluations(decisions)

    return PymcdcMetrics(
        decision_count=len(decisions),
        total_requirements=total_req,
        covered_requirements=covered_req,
        uncovered_requirements=uncovered,
        coverage_percent=round(coverage, 2),
        logical_subexpression_validation_score=round(coverage, 2),
        subexpression_true_evaluations=true_eval,
        subexpression_false_evaluations=false_eval,
        subexpression_both_sides_validated=both_valid,
        mcdc_requirements_met=covered_req,
        short_circuit_irrelevant_slots=short_circuit,
    )


def export_decisions_json(mdc_path: pathlib.Path) -> dict:
    decisions = load_decisions(mdc_path)
    rows = []
    for _, dec in sorted(decisions.items(), key=lambda item: item[0]):
        cov, req = dec.get_covered_requirements()
        rows.append(
            {
                "line_number": list(dec.linha),
                "decision_text": dec.texto,
                "conditions": list(dec.condicoes),
                "requirements_total": req,
                "requirements_covered": cov,
                "requirements_table": dec.to_table(),
                "executed": list(dec.executado),
            }
        )
    metrics = compute_metrics(mdc_path)
    return {
        "tool": "pymcdc",
        "source_file": mdc_path.stem,
        "decision_count": metrics.decision_count,
        "total_requirements": metrics.total_requirements,
        "covered_requirements": metrics.covered_requirements,
        "coverage_percent": metrics.coverage_percent,
        "decisions": rows,
    }


def compute_normalized_scores(metrics: PymcdcMetrics) -> dict[str, float]:
    score = float(metrics.logical_subexpression_validation_score)
    return {
        METRIC_KEY: score,
        METRIC_L4: score,
    }


def export_metric_evidence(metrics: PymcdcMetrics) -> dict:
    score = float(metrics.logical_subexpression_validation_score)
    return {
        "tool": "pymcdc",
        "metrics_total": 1,
        "metrics_covered": 1 if score >= 100.0 else 0,
        "metric_coverage_complete": score >= 100.0,
        "scores": compute_normalized_scores(metrics),
        "metric_evidence": [
            {
                "l3_strategy": "Cyclomatic Complexity",
                "classification": METRIC_L4,
                "l5_metric": METRIC_L5,
                "score": score,
                "covered": score >= 100.0,
                "pymcdc_native": True,
                "raw_parameters": {
                    "decision_count": metrics.decision_count,
                    "total_requirements": metrics.total_requirements,
                    "covered_requirements": metrics.covered_requirements,
                    "uncovered_requirements": metrics.uncovered_requirements,
                    "coverage_percent": metrics.coverage_percent,
                    "subexpression_true_evaluations": metrics.subexpression_true_evaluations,
                    "subexpression_false_evaluations": metrics.subexpression_false_evaluations,
                    "subexpression_both_sides_validated": metrics.subexpression_both_sides_validated,
                    "mcdc_requirements_met": metrics.mcdc_requirements_met,
                    "short_circuit_irrelevant_slots": metrics.short_circuit_irrelevant_slots,
                },
                "formula": "100 * covered_requirements / total_requirements",
            }
        ],
    }


def export_dashboard_payload(metrics: PymcdcMetrics) -> dict:
    scores = compute_normalized_scores(metrics)
    score = scores[METRIC_KEY]
    return {
        "tool": "pymcdc",
        "metrics_total": 1,
        "metrics_covered": 1,
        "metric_coverage_complete": True,
        "all_scores_100": score >= 100.0,
        "scores": scores,
        "rows": [
            {
                "classification": METRIC_L4,
                "l5_metric": METRIC_L5,
                "score": int(round(score)),
                "result": "PASS" if score >= 100.0 else "FAIL",
                "coverage_complete": score >= 100.0,
            }
        ],
    }


def export_unified_pymcdc_output(
    metrics: PymcdcMetrics,
    *,
    report_path: pathlib.Path,
    mdc_path: pathlib.Path,
) -> dict:
    evidence = export_metric_evidence(metrics)
    scores = evidence["scores"]
    score = int(round(scores[METRIC_KEY]))
    entry = evidence["metric_evidence"][0]

    metric_row = {
        "classification": METRIC_L4,
        "l5_metric": METRIC_L5,
        "covered": "yes" if score >= 100 else "no",
        "score": score,
        "value": f"{score}/100",
        "result": "PASS" if score >= 100 else "FAIL",
        "coverage_percent": score,
        "platform_ratio": score,
        "raw_sources_present": True,
        "pymcdc_native": True,
        "raw_parameters": entry["raw_parameters"],
        "formula": entry["formula"],
    }

    report = json.loads(report_path.read_text(encoding="utf-8-sig"))

    return {
        "tool": "pymcdc",
        "strategy": "Cyclomatic Complexity",
        "category": "Condition Coverage",
        "execution_status": "Completed",
        "output_complete": True,
        "metric_coverage_complete": score >= 100,
        "metrics_total": 1,
        "metrics_covered": 1 if score >= 100 else 0,
        "target_repository": "sample_subject",
        "source_file": "sample_subject/logic.py",
        "unittest_file": "sample_subject/test_logic.py",
        "decisions": report.get("decisions", []),
        "summary": {
            "decision_count": metrics.decision_count,
            "total_requirements": metrics.total_requirements,
            "covered_requirements": metrics.covered_requirements,
            "uncovered_requirements": metrics.uncovered_requirements,
            "coverage_percent": metrics.coverage_percent,
        },
        "metrics": [metric_row],
        "platform_scores": scores,
        "platform_metrics": {
            "tool": "pymcdc",
            "target_repository": "sample_subject",
            "metrics_total": 1,
            "metrics_covered": 1 if score >= 100 else 0,
            "metric_coverage_complete": score >= 100,
            METRIC_L4: score,
            METRIC_KEY: score,
            "logical_subexpression_validation_score": score,
            "condition_coverage_percent": score,
        },
        "metric_evidence": evidence,
        "mdc_log": str(mdc_path.name),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mdc-path", type=pathlib.Path, required=True)
    parser.add_argument("--report-json", type=pathlib.Path, default=None)
    parser.add_argument("--output-json", type=pathlib.Path, default=None)
    parser.add_argument("--dashboard-json", type=pathlib.Path, default=None)
    args = parser.parse_args(argv)

    metrics = compute_metrics(args.mdc_path)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(
            json.dumps(export_decisions_json(args.mdc_path), indent=2),
            encoding="utf-8",
        )
    payload = asdict(metrics)
    payload["normalized_scores"] = compute_normalized_scores(metrics)
    payload["dashboard_export"] = export_dashboard_payload(metrics)
    payload["metric_evidence"] = export_metric_evidence(metrics)

    if args.output_json:
        args.output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {args.output_json}")
    if args.dashboard_json:
        args.dashboard_json.write_text(
            json.dumps(export_dashboard_payload(metrics), indent=2),
            encoding="utf-8",
        )
        print(f"Wrote {args.dashboard_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
