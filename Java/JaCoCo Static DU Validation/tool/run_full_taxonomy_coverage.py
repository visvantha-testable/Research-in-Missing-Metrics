"""Run all taxonomy pipelines and summarize native vs platform coverage."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JAVA_ROOT = ROOT.parent

PIPELINES = [
    {
        "name": "JaCoCo Static DU Validation",
        "cwd": ROOT,
        "command": [sys.executable, "tool/run_jacoco_static_du_validation_benchmark.py"],
        "action_plan": ROOT / "outputs" / "metric_coverage_action_plan.csv",
    },
    {
        "name": "JaCoCo Coverage",
        "cwd": JAVA_ROOT / "JaCoCo Coverage",
        "command": [sys.executable, "tool/run_jacoco_benchmark.py"],
        "action_plan": None,
    },
    {
        "name": "JPF Path Analysis",
        "cwd": JAVA_ROOT / "JPF Path Analysis",
        "command": [sys.executable, "tool/run_jpf_benchmark.py"],
        "action_plan": None,
    },
    {
        "name": "Static DU Analysis",
        "cwd": JAVA_ROOT / "Static DU Analysis",
        "command": [sys.executable, "tool/run_static_du_benchmark.py"],
        "action_plan": None,
    },
]


def run_pipeline(entry: dict) -> dict:
    cwd = entry["cwd"]
    if not cwd.exists():
        return {"name": entry["name"], "status": "skipped", "reason": f"missing folder: {cwd}"}
    try:
        completed = subprocess.run(
            entry["command"],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
        return {
            "name": entry["name"],
            "status": "ok" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "stdout_tail": "\n".join(completed.stdout.splitlines()[-8:]),
            "stderr_tail": "\n".join(completed.stderr.splitlines()[-8:]),
        }
    except Exception as exc:  # noqa: BLE001
        return {"name": entry["name"], "status": "error", "reason": str(exc)}


def main() -> None:
    results = [run_pipeline(entry) for entry in PIPELINES]
    summary_path = ROOT / "outputs" / "full_taxonomy_run_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    print(f"\nWrote {summary_path}")
    action_plan = ROOT / "outputs" / "metric_coverage_action_plan.csv"
    if action_plan.exists():
        print(f"Per-metric action plan: {action_plan}")
        print("Open metric_coverage_action_plan.csv — filter Current_Repo_Native_Coverage=No for gaps + alternatives.")


if __name__ == "__main__":
    main()
