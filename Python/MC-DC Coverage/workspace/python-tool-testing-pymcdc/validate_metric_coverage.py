"""Validate that the Logical Sub-expression Validation metric is fully covered."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from pymcdc_metrics import compute_metrics, compute_normalized_scores  # noqa: E402


def load_config(config_path: pathlib.Path) -> list[dict]:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return data["metrics"]


def validate(
    *,
    config_path: pathlib.Path,
    artifacts_dir: pathlib.Path,
    metrics_json: pathlib.Path | None = None,
) -> tuple[bool, list[str]]:
    entries = load_config(config_path)
    errors: list[str] = []

    mdc = artifacts_dir / "logic.py.mdc"
    report = artifacts_dir / "pymcdc_report.json"

    if metrics_json and metrics_json.exists():
        payload = json.loads(metrics_json.read_text(encoding="utf-8"))
        metrics_dict = payload
        scores = payload.get("normalized_scores") or {}
    else:
        computed = compute_metrics(mdc)
        metrics_dict = computed.__dict__
        scores = compute_normalized_scores(computed)

    for entry in entries:
        name = entry["normalized_score_key"]
        field = entry["score_field"]

        for artifact in entry.get("required_artifacts", []):
            path = ROOT / artifact
            if not path.exists():
                errors.append(f"{name}: missing artifact {artifact}")
            elif path.stat().st_size == 0:
                errors.append(f"{name}: empty artifact {artifact}")

        if field not in metrics_dict:
            errors.append(f"{name}: missing score field {field}")
            continue

        for param in entry.get("raw_parameters", []):
            if param not in metrics_dict:
                errors.append(f"{name}: missing raw parameter {param}")

        if name not in scores:
            errors.append(f"{name}: missing normalized score")
            continue

        if float(scores[name]) < 100.0:
            errors.append(f"{name}: score {scores[name]} is below 100/100")

    if not report.exists():
        errors.append("missing pymcdc_report.json")

    return len(errors) == 0, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=pathlib.Path, default=ROOT / "config" / "metric_coverage.json")
    parser.add_argument("--artifacts-dir", type=pathlib.Path, default=ROOT / "artifacts" / "training")
    parser.add_argument("--metrics-json", type=pathlib.Path, default=None)
    args = parser.parse_args()

    ok, errors = validate(
        config_path=args.config,
        artifacts_dir=args.artifacts_dir,
        metrics_json=args.metrics_json,
    )
    if ok:
        print("All 1 pymcdc Condition Coverage metrics are covered with 100/100 scores.")
        return 0

    print("Metric coverage validation failed:", file=sys.stderr)
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
