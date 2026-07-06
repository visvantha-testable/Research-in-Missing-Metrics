"""Run Pylint code smells benchmark pipeline."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

os.environ.pop("PYTHONPATH", None)

TOOL_ROOT = Path(__file__).resolve().parent
METRIC_ROOT = TOOL_ROOT.parent
BENCHMARK = METRIC_ROOT / "workspace" / "code_smells_benchmark"
OUTPUT = METRIC_ROOT / "outputs"
PY = sys.executable

EXCLUDED = {".git", "venv", ".venv", "env", "__pycache__", "build", "dist", "node_modules", ".tox"}

CODE_SMELL_SYMBOLS = {
    "duplicate-code",
    "too-many-branches",
    "too-many-arguments",
    "too-many-instance-attributes",
    "too-many-locals",
    "too-many-public-methods",
    "too-many-return-statements",
    "too-many-statements",
    "too-many-nested-blocks",
    "too-many-boolean-expressions",
    "too-many-ancestors",
}

CODE_SMELL_MESSAGE_IDS = {
    "R0801",
    "R0912",
    "R0913",
    "R0902",
    "R0914",
    "R0904",
    "R0911",
    "R0915",
    "R1702",
    "R0916",
    "R0901",
}

SEVERITY_MAP = {
    "convention": "convention",
    "refactor": "refactor",
    "warning": "warning",
    "error": "error",
    "fatal": "fatal",
}


def discover_python_files(repo: Path) -> list[Path]:
    files = []
    for path in repo.rglob("*.py"):
        if any(part in EXCLUDED for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def build_pylint_command(targets: Path | list[Path], output_format: str | None = None) -> list[str]:
    target_list = [targets] if isinstance(targets, Path) else list(targets)
    command = [PY, "-m", "pylint", *[str(t) for t in target_list]]
    command.extend(["--ignore=venv,.venv,env,build,dist,.tox,node_modules"])
    if output_format:
        command.extend(["--output-format", output_format])
    return command


def run_command(command: list[str]) -> tuple[str, str, int]:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=os.environ.copy(),
    )
    return completed.stdout, completed.stderr, completed.returncode


def combine_raw(stdout: str, stderr: str) -> str:
    raw = stdout
    if stderr:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += stderr
    return raw


def parse_json_chunks(json_text: str) -> list[dict]:
    records: list[dict] = []
    for chunk in json_text.split("\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            parsed = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            records.extend(parsed)
    if not records and json_text.strip():
        try:
            parsed = json.loads(json_text)
            if isinstance(parsed, list):
                records = parsed
        except json.JSONDecodeError:
            pass
    return records


def records_to_dataframe(records: list[dict]) -> pd.DataFrame:
    rows = []
    for record in records:
        rows.append(
            {
                "file": record.get("path") or record.get("module", ""),
                "line": record.get("line", ""),
                "column": record.get("column", ""),
                "type": record.get("type", ""),
                "symbol": record.get("symbol", ""),
                "message": record.get("message", ""),
                "message-id": record.get("message-id", ""),
                "confidence": record.get("confidence", ""),
            }
        )
    columns = ["file", "line", "column", "type", "symbol", "message", "message-id", "confidence"]
    return pd.DataFrame(rows, columns=columns)


def is_code_smell(record: dict) -> bool:
    symbol = str(record.get("symbol", "")).lower()
    message_id = str(record.get("message-id", "")).upper()
    return symbol in CODE_SMELL_SYMBOLS or message_id in CODE_SMELL_MESSAGE_IDS


def extract_code_smells(records: list[dict]) -> pd.DataFrame:
    rows = []
    for record in records:
        if not is_code_smell(record):
            continue
        record_type = str(record.get("type", "")).lower()
        rows.append(
            {
                "file": record.get("path") or record.get("module", ""),
                "line": record.get("line", ""),
                "message_id": record.get("message-id", ""),
                "symbol": record.get("symbol", ""),
                "message": record.get("message", ""),
                "severity": SEVERITY_MAP.get(record_type, record_type or "unknown"),
            }
        )
    return pd.DataFrame(rows, columns=["file", "line", "message_id", "symbol", "message", "severity"])


def run_per_file(python_files: list[Path]) -> tuple[str, list[dict], int, int]:
    raw_chunks: list[str] = []
    all_records: list[dict] = []
    success_count = 0
    failure_count = 0

    for index, file_path in enumerate(python_files, start=1):
        raw_out, raw_err, raw_code = run_command(build_pylint_command(file_path))
        json_out, json_err, json_code = run_command(build_pylint_command(file_path, "json"))
        raw_chunks.append(combine_raw(raw_out, raw_err))
        all_records.extend(parse_json_chunks(json_out))
        if raw_code in (0, 1, 2, 4, 8, 16, 32) or json_code in (0, 1, 2, 4, 8, 16, 32):
            success_count += 1
        else:
            failure_count += 1

    return "".join(raw_chunks), all_records, success_count, failure_count


def run_repo(repo: Path) -> tuple[str, list[dict], int, int]:
    raw_out, raw_err, raw_code = run_command(build_pylint_command(repo))
    json_out, json_err, json_code = run_command(build_pylint_command(repo, "json"))
    raw_text = combine_raw(raw_out, raw_err)
    records = parse_json_chunks(json_out)
    success = raw_code in (0, 1, 2, 4, 8, 16, 32) or json_code in (0, 1, 2, 4, 8, 16, 32)
    file_count = len(discover_python_files(repo))
    return raw_text, records, file_count if success else 0, 0 if success else file_count


def merge_duplicate_code(repo: Path, records: list[dict], raw_chunks: list[str]) -> tuple[list[dict], list[str]]:
    repo_raw, repo_records, _, _ = run_repo(repo)
    existing = {(r.get("message-id"), r.get("path"), r.get("line")) for r in records}
    for record in repo_records:
        key = (record.get("message-id"), record.get("path"), record.get("line"))
        if key not in existing:
            records.append(record)
            existing.add(key)
    raw_chunks.append(repo_raw)
    return records, raw_chunks


def run_pipeline(repo: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    python_files = discover_python_files(repo)
    pd.DataFrame(
        [{"absolute_path": str(p), "relative_path": str(p.relative_to(repo))} for p in python_files]
    ).to_csv(output / "python_files.csv", index=False)

    raw_text, records, success_count, failure_count = run_per_file(python_files)
    raw_chunks = [raw_text]
    records, raw_chunks = merge_duplicate_code(repo, records, raw_chunks)
    raw_text = "".join(raw_chunks)

    (output / "pylint_raw_output.txt").write_text(raw_text, encoding="utf-8")
    (output / "pylint_output.json").write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    results_df = records_to_dataframe(records)
    results_df.to_csv(output / "pylint_results.csv", index=False)

    smells_df = extract_code_smells(records)
    smells_df.to_csv(output / "code_smells_findings.csv", index=False)

    summary_df = pd.DataFrame([{"metric_name": "Code_Smells_Count", "metric_value": len(smells_df)}])
    summary_df.to_csv(output / "code_smells_summary.csv", index=False)
    (output / "error_log.txt").write_text("", encoding="utf-8")

    return {
        "benchmark_ready": len(python_files) > 0 and len(smells_df) >= 10,
        "python_files": len(python_files),
        "files_success": success_count,
        "files_failed": failure_count,
        "total_findings": len(results_df),
        "code_smells_count": len(smells_df),
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    result = run_pipeline(BENCHMARK, OUTPUT)
    print(json.dumps(result, indent=2))
    if not result.get("benchmark_ready"):
        sys.exit(1)
