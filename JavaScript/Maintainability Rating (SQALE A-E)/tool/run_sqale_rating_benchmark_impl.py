"""ESLint maintainability rating benchmark execution helpers."""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

os.environ.pop("PYTHONPATH", None)

JS_EXTENSIONS = {".js", ".mjs", ".cjs"}
EXCLUDED = {".git", "node_modules", "dist", "build", "coverage", "vendor", "docs", "test", "tests"}
MAINTAINABILITY_RULES = {
    "complexity",
    "max-depth",
    "max-lines",
    "max-lines-per-function",
    "max-params",
    "max-statements",
    "max-nested-callbacks",
}
ESLINT_CONFIG = {
    "env": {"es2022": True, "node": True},
    "extends": ["eslint:recommended"],
    "parserOptions": {"ecmaVersion": "latest"},
    "rules": {
        "complexity": ["warn", 10],
        "max-depth": ["warn", 4],
        "max-lines": ["warn", 300],
        "max-lines-per-function": ["warn", 50],
        "max-params": ["warn", 5],
        "max-statements": ["warn", 20],
        "max-nested-callbacks": ["warn", 3],
    },
}
FINDINGS_COLUMNS = ["file", "line", "column", "severity", "rule_id", "message"]
ESLINT_SUCCESS_CODES = {0, 1}
MAX_DEPTH_PATTERN = re.compile(
    r"Blocks are nested too deeply \((?P<actual>\d+)\)\. Maximum allowed is (?P<threshold>\d+)\."
)


def discover_javascript_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in JS_EXTENSIONS:
            continue
        if any(part in EXCLUDED for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def save_javascript_inventory(js_files: list[Path], output: Path) -> None:
    rows = [
        {"file_path": str(path), "file_name": path.name, "directory": str(path.parent)}
        for path in js_files
    ]
    pd.DataFrame(rows, columns=["file_path", "file_name", "directory"]).to_csv(output, index=False)


def resolve_eslint_executable(runtimes_root: Path) -> list[str]:
    search_roots = [runtimes_root, runtimes_root.parent]
    for base in search_roots:
        local = base / "node_modules" / ".bin" / "eslint"
        for candidate in (local.with_suffix(".cmd"), local):
            if candidate.exists():
                return [str(candidate.resolve())]
    for name in ("eslint", "npx"):
        resolved = shutil.which(name)
        if resolved:
            if name == "npx":
                return [resolved, "eslint"]
            return [resolved]
    raise FileNotFoundError("ESLint not found. Install with: npm install -g eslint")


def ensure_eslint_config(repo: Path) -> Path:
    eslintrc = repo / ".eslintrc.json"
    eslintrc.write_text(json.dumps(ESLINT_CONFIG, indent=2), encoding="utf-8")

    flat_config = repo / "eslint.config.js"
    rules_json = json.dumps(ESLINT_CONFIG["rules"], indent=6).replace("\n", "\n      ")
    flat_config.write_text(
        "export default [\n"
        "  {\n"
        "    files: ['**/*.{js,mjs,cjs}'],\n"
        "    languageOptions: { ecmaVersion: 'latest', sourceType: 'module' },\n"
        f"    rules: {rules_json},\n"
        "  },\n"
        "];\n",
        encoding="utf-8",
    )
    return eslintrc


def build_eslint_command(eslint_executable: list[str], repo: Path, output_format: str | None = None) -> list[str]:
    command = [*eslint_executable, str(repo), "--ext", ".js,.mjs,.cjs"]
    if output_format:
        command.extend(["-f", output_format])
    return command


def run_command(command: list[str]) -> tuple[str, str, int]:
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


def parse_eslint_json(json_text: str) -> list[dict[str, Any]]:
    if not json_text.strip():
        return []
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def records_to_findings(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in records:
        for message in record.get("messages", []):
            rows.append(
                {
                    "file": record.get("filePath", ""),
                    "line": message.get("line", ""),
                    "column": message.get("column", ""),
                    "severity": message.get("severity", ""),
                    "rule_id": message.get("ruleId", ""),
                    "message": message.get("message", ""),
                }
            )
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def is_maintainability_violation(rule_id: str) -> bool:
    return str(rule_id) in MAINTAINABILITY_RULES


def extract_maintainability_findings(findings_df: pd.DataFrame) -> pd.DataFrame:
    if findings_df.empty:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    filtered = findings_df[findings_df["rule_id"].map(is_maintainability_violation)].copy()
    return filtered.reset_index(drop=True)


def extract_max_nesting_depth(findings_df: pd.DataFrame) -> int:
    depth_rows = findings_df[findings_df["rule_id"] == "max-depth"]
    depths: list[int] = []
    for message in depth_rows["message"].astype(str):
        match = MAX_DEPTH_PATTERN.search(message)
        if match:
            depths.append(int(match.group("actual")))
    return max(depths) if depths else 0


def compute_maintainability_score(violation_count: int, file_count: int) -> float:
    if file_count <= 0:
        return 0.0
    score = 100 - ((violation_count / file_count) * 5)
    return round(max(score, 0.0), 4)


def score_to_sqale_rating(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "E"


def append_error(errors: list[dict[str, str]], file: str, message: str) -> None:
    errors.append(
        {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "file": file,
            "error_message": message,
        }
    )


def write_error_log(errors: list[dict[str, str]], output: Path) -> None:
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "file", "error_message"])
        writer.writeheader()
        writer.writerows(errors)


def run_pipeline(repo: Path, output: Path, runtimes_root: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    errors: list[dict[str, str]] = []
    repo = repo.resolve()

    ensure_eslint_config(repo)
    js_files = discover_javascript_files(repo)
    save_javascript_inventory(js_files, output / "javascript_files_inventory.csv")

    try:
        eslint_executable = resolve_eslint_executable(runtimes_root)
    except FileNotFoundError as exc:
        append_error(errors, "eslint", str(exc))
        write_error_log(errors, output / "error_log.txt")
        return {"benchmark_ready": False, "error": str(exc), "javascript_files": len(js_files)}

    text_cmd = build_eslint_command(eslint_executable, repo)
    json_cmd = build_eslint_command(eslint_executable, repo, "json")

    raw_out, raw_err, raw_code = run_command(text_cmd)
    json_out, json_err, json_code = run_command(json_cmd)

    console_chunks = [
        "===== eslint (text) =====\n" + combine_raw(raw_out, raw_err),
        "===== eslint (json) =====\n" + combine_raw(json_out, json_err),
    ]
    (output / "eslint_raw_console_output.txt").write_text("\n".join(console_chunks), encoding="utf-8")
    (output / "eslint_output.json").write_text(json_out, encoding="utf-8")

    if raw_code not in ESLINT_SUCCESS_CODES and not json_out.strip():
        append_error(errors, "eslint_text", f"ESLint text run exited with code {raw_code}")
    if json_code not in ESLINT_SUCCESS_CODES and not json_out.strip():
        append_error(errors, "eslint_json", f"ESLint JSON run exited with code {json_code}")

    records = parse_eslint_json(json_out)
    findings_df = records_to_findings(records)
    findings_df.to_csv(output / "eslint_findings.csv", index=False)

    maintainability_df = extract_maintainability_findings(findings_df)
    violation_count = len(maintainability_df)
    code_smells_count = violation_count

    pd.DataFrame([{"metric_name": "Code_Smells_Count", "metric_value": code_smells_count}]).to_csv(
        output / "code_smells_summary.csv", index=False
    )

    max_nesting = extract_max_nesting_depth(findings_df)
    pd.DataFrame([{"metric_name": "Maximum_Nesting_Depth", "metric_value": max_nesting}]).to_csv(
        output / "nesting_depth_summary.csv", index=False
    )

    maintainability_score = compute_maintainability_score(violation_count, len(js_files))
    pd.DataFrame([{"metric_name": "Maintainability_Score", "metric_value": maintainability_score}]).to_csv(
        output / "maintainability_score_summary.csv", index=False
    )

    rating = score_to_sqale_rating(maintainability_score)
    pd.DataFrame([{"metric_name": "Maintainability_Rating", "metric_value": rating}]).to_csv(
        output / "maintainability_rating_summary.csv", index=False
    )

    write_error_log(errors, output / "error_log.txt")

    return {
        "benchmark_ready": len(js_files) > 0,
        "javascript_files": len(js_files),
        "total_findings": len(findings_df),
        "code_smells_count": code_smells_count,
        "maintainability_violations": violation_count,
        "maximum_nesting_depth": max_nesting,
        "maintainability_score": maintainability_score,
        "maintainability_rating": rating,
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
