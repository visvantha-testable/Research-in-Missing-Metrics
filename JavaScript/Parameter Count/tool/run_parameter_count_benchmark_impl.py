"""ESLint Parameter Count benchmark execution helpers (JavaScript)."""
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
FINDINGS_COLUMNS = ["file", "line", "column", "severity", "rule", "message"]
PARAM_SUMMARY_COLUMNS = ["file", "function", "parameter_count", "allowed_limit"]
LONG_PARAMETER_LIST_COLUMNS = ["file", "function", "parameter_count", "status"]
MAX_PARAMS_RULE = "max-params"
LONG_PARAMETER_THRESHOLD = 5
ESLINT_CONFIG = {
    "env": {"node": True, "es2022": True},
    "extends": ["eslint:recommended"],
    "rules": {
        "max-params": ["error", LONG_PARAMETER_THRESHOLD],
    },
}
ESLINT_SUCCESS_CODES = {0, 1}
MAX_PARAMS_MESSAGE = re.compile(
    r"Function\s+'(?P<function>[^']+)'\s+has too many parameters\s+\((?P<count>\d+)\)\.\s+Maximum allowed is\s+(?P<limit>\d+)\.",
    re.IGNORECASE,
)


def resolve_project_root(metric_root: Path) -> Path:
    current = metric_root.resolve()
    for _ in range(8):
        runtimes = current / "runtimes"
        if runtimes.is_dir() and (runtimes / "node_modules").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return metric_root.resolve().parent.parent


def discover_javascript_files(repo: Path) -> list[Path]:
    skip_names = {".eslintrc.json", "eslint.config.js", "eslint.config.mjs", "eslint.config.cjs"}
    files: list[Path] = []
    for path in repo.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in JS_EXTENSIONS:
            continue
        if path.name in skip_names:
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
    for config_name in ("eslint.config.js", "eslint.config.mjs", "eslint.config.cjs"):
        config_path = repo / config_name
        if config_path.exists():
            config_path.unlink()

    eslintrc = repo / ".eslintrc.json"
    eslintrc.write_text(json.dumps(ESLINT_CONFIG, indent=2), encoding="utf-8")

    rules_json = json.dumps(ESLINT_CONFIG["rules"], indent=6).replace("\n", "\n      ")
    flat_config = repo / "eslint.config.cjs"
    flat_config.write_text(
        "module.exports = [\n"
        "  {\n"
        "    files: ['**/*.{js,mjs,cjs}'],\n"
        "    ignores: ['**/eslint.config.cjs', '**/.eslintrc.json'],\n"
        "    languageOptions: { ecmaVersion: 'latest', sourceType: 'commonjs' },\n"
        f"    rules: {rules_json},\n"
        "  },\n"
        "];\n",
        encoding="utf-8",
    )
    return eslintrc


def build_eslint_command(eslint_executable: list[str], repo: Path, output_format: str | None = None) -> list[str]:
    command = [*eslint_executable, str(repo)]
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
                    "rule": message.get("ruleId", ""),
                    "message": message.get("message", ""),
                }
            )
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def parse_max_params_violation(message: str) -> dict[str, Any] | None:
    match = MAX_PARAMS_MESSAGE.search(message)
    if not match:
        return None
    return {
        "function": match.group("function"),
        "parameter_count": int(match.group("count")),
        "allowed_limit": int(match.group("limit")),
    }


def build_parameter_count_summary(findings_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if findings_df.empty:
        return pd.DataFrame(columns=PARAM_SUMMARY_COLUMNS)

    max_params = findings_df[findings_df["rule"] == MAX_PARAMS_RULE]
    for _, record in max_params.iterrows():
        parsed = parse_max_params_violation(str(record.get("message", "")))
        if not parsed:
            continue
        rows.append(
            {
                "file": record.get("file", ""),
                "function": parsed["function"],
                "parameter_count": parsed["parameter_count"],
                "allowed_limit": parsed["allowed_limit"],
            }
        )
    return pd.DataFrame(rows, columns=PARAM_SUMMARY_COLUMNS)


def build_long_parameter_list(param_summary_df: pd.DataFrame) -> pd.DataFrame:
    if param_summary_df.empty:
        return pd.DataFrame(columns=LONG_PARAMETER_LIST_COLUMNS)
    rows: list[dict[str, Any]] = []
    for _, record in param_summary_df.iterrows():
        param_count = int(record.get("parameter_count", 0) or 0)
        status = "Long Parameter List" if param_count > LONG_PARAMETER_THRESHOLD else "OK"
        rows.append(
            {
                "file": record.get("file", ""),
                "function": record.get("function", ""),
                "parameter_count": param_count,
                "status": status,
            }
        )
    return pd.DataFrame(rows, columns=LONG_PARAMETER_LIST_COLUMNS)


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

    param_summary_df = build_parameter_count_summary(findings_df)
    param_summary_df.to_csv(output / "parameter_count_summary.csv", index=False)

    long_param_df = build_long_parameter_list(param_summary_df)
    long_param_df.to_csv(output / "long_parameter_list.csv", index=False)

    write_error_log(errors, output / "error_log.txt")

    param_values = pd.to_numeric(param_summary_df["parameter_count"], errors="coerce").dropna()
    max_param = int(param_values.max()) if not param_values.empty else 0
    avg_param = round(float(param_values.mean()), 4) if not param_values.empty else 0.0
    violation_count = len(param_summary_df)
    long_param_count = int((long_param_df["status"] == "Long Parameter List").sum())

    return {
        "benchmark_ready": len(js_files) > 0 and violation_count >= 1 and max_param >= 8,
        "javascript_files": len(js_files),
        "functions_with_parameter_violations": violation_count,
        "maximum_parameter_count": max_param,
        "average_parameter_count_violating": avg_param,
        "long_parameter_list_violations": long_param_count,
        "total_findings": len(findings_df),
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
