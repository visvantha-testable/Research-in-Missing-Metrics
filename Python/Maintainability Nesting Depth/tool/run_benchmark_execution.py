"""Run Pylint on nesting_depth_benchmark and validate 100% expected outcomes."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

TOOL_ROOT = Path(__file__).resolve().parent
METRIC_ROOT = TOOL_ROOT.parent
PROJECT_ROOT = METRIC_ROOT.parent.parent
BENCHMARK_REPO = METRIC_ROOT / "workspace" / "nesting_depth_benchmark"
OUTPUT_PATH = METRIC_ROOT / "outputs"
EXPECTED_PATH = BENCHMARK_REPO / "expected_outcomes.json"
PY = sys.executable

NESTING_DEPTH_PATTERN = re.compile(
    r"Too many nested blocks\s*\((\d+)\s*/\s*(\d+)\)",
    re.IGNORECASE,
)


def run_pylint(repo_path: Path, output_format: str | None = None) -> tuple[str, str, int]:
    command = [
        PY,
        "-m",
        "pylint",
        str(repo_path),
        "--ignore=venv,.venv,env,build,dist,.tox,node_modules",
    ]
    if output_format:
        command.extend(["--output-format", output_format])
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.stdout, completed.stderr, completed.returncode


def combine_raw(stdout: str, stderr: str) -> str:
    raw = stdout
    if stderr:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += stderr
    return raw


def extract_depth(message: str) -> int | None:
    match = NESTING_DEPTH_PATTERN.search(message)
    return int(match.group(1)) if match else None


def normalize_path(path: str) -> str:
    return Path(path.replace("\\", "/")).as_posix()


def discover_python_files(repo_path: Path) -> list[Path]:
    excluded = {".git", "venv", ".venv", "env", "__pycache__", "build", "dist", "node_modules", ".tox", "migrations"}
    files = []
    for file_path in repo_path.rglob("*.py"):
        if any(part in excluded for part in file_path.parts):
            continue
        files.append(file_path.resolve())
    return sorted(files)


def validate_against_expected(records: list[dict], raw_text: str, expected: dict) -> dict:
    nesting_records = [r for r in records if r.get("message-id") == "R1702"]
    expected_findings = expected["expected_nesting_findings"]

    actual_rows = []
    for record in nesting_records:
        path = normalize_path(record.get("path") or record.get("module", ""))
        actual_rows.append(
            {
                "file_suffix": path.split("nesting_depth_benchmark/")[-1],
                "line": record.get("line"),
                "function": record.get("obj"),
                "message": record.get("message"),
                "detected_nesting_depth": extract_depth(str(record.get("message", ""))),
            }
        )

    checks = []
    for exp in expected_findings:
        match = next(
            (
                row
                for row in actual_rows
                if row["file_suffix"] == exp["file_suffix"]
                and row["line"] == exp["line"]
                and row["detected_nesting_depth"] == exp["detected_nesting_depth"]
            ),
            None,
        )
        checks.append(
            {
                "expected": exp,
                "matched": match is not None,
                "actual": match,
            }
        )

    clean_checks = []
    for rel in expected["expected_files_with_no_nesting_violation"]:
        hits = [row for row in actual_rows if row["file_suffix"] == rel]
        clean_checks.append({"file_suffix": rel, "no_violation": len(hits) == 0})

    raw_message_checks = [
        {
            "message": exp["message"],
            "present_in_raw_output": exp["message"] in raw_text,
        }
        for exp in expected_findings
    ]

    all_expected_matched = all(item["matched"] for item in checks)
    all_clean = all(item["no_violation"] for item in clean_checks)
    all_raw_present = all(item["present_in_raw_output"] for item in raw_message_checks)
    count_ok = len(nesting_records) == expected["expected_nesting_findings_count"]

    return {
        "benchmark_passed": all(
            [all_expected_matched, all_clean, all_raw_present, count_ok]
        ),
        "expected_nesting_findings_count": expected["expected_nesting_findings_count"],
        "actual_nesting_findings_count": len(nesting_records),
        "count_match": count_ok,
        "finding_checks": checks,
        "clean_file_checks": clean_checks,
        "raw_output_message_checks": raw_message_checks,
        "all_expected_findings_matched": all_expected_matched,
        "all_clean_files_clean": all_clean,
        "all_messages_in_raw_output": all_raw_present,
    }


def main() -> None:
    if not BENCHMARK_REPO.exists():
        raise FileNotFoundError(f"Benchmark repo not found: {BENCHMARK_REPO}")

    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    python_files = discover_python_files(BENCHMARK_REPO)
    pd.DataFrame(
        [
            {
                "absolute_path": str(path),
                "relative_path": str(path.relative_to(BENCHMARK_REPO)),
            }
            for path in python_files
        ]
    ).to_csv(OUTPUT_PATH / "python_files.csv", index=False)

    raw_stdout, raw_stderr, _ = run_pylint(BENCHMARK_REPO)
    raw_text = combine_raw(raw_stdout, raw_stderr)
    (OUTPUT_PATH / "pylint_raw_output.txt").write_text(raw_text, encoding="utf-8")

    json_stdout, _, _ = run_pylint(BENCHMARK_REPO, output_format="json")
    records = json.loads(json_stdout) if json_stdout.strip() else []
    (OUTPUT_PATH / "pylint_output.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    results_df = pd.DataFrame(
        [
            {
                "file": r.get("path") or r.get("module", ""),
                "line": r.get("line", ""),
                "column": r.get("column", ""),
                "type": r.get("type", ""),
                "symbol": r.get("symbol", ""),
                "message": r.get("message", ""),
                "message-id": r.get("message-id", ""),
                "confidence": r.get("confidence", ""),
            }
            for r in records
        ]
    )
    results_df.to_csv(OUTPUT_PATH / "pylint_results.csv", index=False)

    nesting_df = pd.DataFrame(
        [
            {
                "file": r.get("path") or r.get("module", ""),
                "line": r.get("line", ""),
                "warning": r.get("symbol", ""),
                "message": r.get("message", ""),
                "detected_nesting_depth": extract_depth(str(r.get("message", ""))),
            }
            for r in records
            if r.get("message-id") == "R1702"
        ]
    )
    nesting_df.to_csv(OUTPUT_PATH / "nesting_depth_findings.csv", index=False)

    validation = validate_against_expected(records, raw_text, expected)
    validation["benchmark_repo"] = str(BENCHMARK_REPO)
    now = datetime.now(timezone.utc).isoformat()
    validation["generated_at_utc"] = now
    (OUTPUT_PATH / "benchmark_validation.json").write_text(
        json.dumps(validation, indent=2),
        encoding="utf-8",
    )

    manifest = {
        "prepared_at_utc": now,
        "repo_path": str(BENCHMARK_REPO.resolve()),
        "benchmark_name": expected["benchmark_name"],
        "python_file_count": len(python_files),
        "expected_nesting_findings_count": expected["expected_nesting_findings_count"],
        "actual_nesting_findings_count": validation["actual_nesting_findings_count"],
        "benchmark_passed": validation["benchmark_passed"],
        "ready_for_metric_evaluation": validation["benchmark_passed"],
    }
    (OUTPUT_PATH / "repo_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    (OUTPUT_PATH / "error_log.txt").write_text("", encoding="utf-8")

    print(f"Benchmark repo: {BENCHMARK_REPO}")
    print(f"Python files: {len(python_files)}")
    print(f"Nesting findings: {validation['actual_nesting_findings_count']}")
    print(f"Benchmark passed: {validation['benchmark_passed']}")
    print(f"Outputs: {OUTPUT_PATH}")
    if not validation["benchmark_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
