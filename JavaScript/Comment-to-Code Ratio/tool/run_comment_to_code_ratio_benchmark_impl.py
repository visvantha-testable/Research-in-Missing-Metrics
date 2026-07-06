"""ESLint Comment-to-Code Ratio benchmark execution helpers."""
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
FINDINGS_COLUMNS = ["file", "line", "column", "severity", "rule_id", "message"]
COMMENT_METRICS_COLUMNS = [
    "file",
    "total_lines",
    "comment_lines",
    "block_comment_lines",
    "single_comment_lines",
    "code_lines",
    "blank_lines",
]
DOCUMENTATION_RULES = {"spaced-comment", "multiline-comment-style", "capitalized-comments"}
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
    "env": {"node": True, "es2022": True},
    "extends": ["eslint:recommended"],
    "parserOptions": {"ecmaVersion": "latest"},
    "rules": {
        "spaced-comment": "warn",
        "multiline-comment-style": ["warn", "starred-block"],
        "capitalized-comments": "off",
        "complexity": ["warn", 10],
        "max-depth": ["warn", 4],
        "max-lines": ["warn", 300],
        "max-lines-per-function": ["warn", 50],
        "max-params": ["warn", 5],
        "max-statements": ["warn", 20],
        "max-nested-callbacks": ["warn", 3],
    },
}
ESLINT_SUCCESS_CODES = {0, 1}


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
        "    files: ['**/cases/**/*.{js,mjs,cjs}'],\n"
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
                    "rule_id": message.get("ruleId", ""),
                    "message": message.get("message", ""),
                }
            )
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def _strip_strings_and_template_literals(line: str) -> str:
    result: list[str] = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "`":
            i += 1
            while i < len(line):
                if line[i] == "\\":
                    i += 2
                    continue
                if line[i] == "`":
                    i += 1
                    break
                i += 1
            result.append("``")
            continue
        if ch in "\"'":
            quote = ch
            i += 1
            while i < len(line):
                if line[i] == "\\":
                    i += 2
                    continue
                if line[i] == quote:
                    i += 1
                    break
                i += 1
            result.append(f"{quote}{quote}")
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def analyze_javascript_file_metrics(file_path: Path) -> dict[str, int]:
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {
            "total_lines": 0,
            "comment_lines": 0,
            "block_comment_lines": 0,
            "single_comment_lines": 0,
            "code_lines": 0,
            "blank_lines": 0,
        }

    lines = text.splitlines()
    total_lines = len(lines)
    blank_lines = 0
    block_comment_lines = 0
    single_comment_lines = 0
    code_lines = 0

    in_block = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            blank_lines += 1
            continue

        if in_block:
            block_comment_lines += 1
            if "*/" in stripped:
                in_block = False
            continue

        if stripped.startswith("/*"):
            in_block = True
            block_comment_lines += 1
            if stripped.count("*/") >= 1 and not stripped.startswith("/**/"):
                in_block = False
            continue

        without_strings = _strip_strings_and_template_literals(line)
        code_part = without_strings.split("//", 1)[0].strip()
        if "//" in without_strings:
            single_comment_lines += 1

        if code_part:
            code_lines += 1

    comment_lines = block_comment_lines + single_comment_lines
    return {
        "total_lines": total_lines,
        "comment_lines": comment_lines,
        "block_comment_lines": block_comment_lines,
        "single_comment_lines": single_comment_lines,
        "code_lines": code_lines,
        "blank_lines": blank_lines,
    }


def build_comment_code_metrics(js_files: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in js_files:
        metrics = analyze_javascript_file_metrics(path)
        rows.append({"file": str(path), **metrics})
    return pd.DataFrame(rows, columns=COMMENT_METRICS_COLUMNS)


def compute_comment_ratio(metrics_df: pd.DataFrame) -> dict[str, float]:
    comment = pd.to_numeric(metrics_df["comment_lines"], errors="coerce").fillna(0)
    block = pd.to_numeric(metrics_df["block_comment_lines"], errors="coerce").fillna(0)
    single = pd.to_numeric(metrics_df["single_comment_lines"], errors="coerce").fillna(0)
    code = pd.to_numeric(metrics_df["code_lines"], errors="coerce").fillna(0)

    total_comment_lines = float((block + single).sum())
    if total_comment_lines == 0:
        total_comment_lines = float(comment.sum())
    total_code_lines = float(code.sum())
    ratio = round(total_comment_lines / total_code_lines, 4) if total_code_lines > 0 else 0.0
    percentage = round(ratio * 100, 2)
    return {
        "total_comment_lines": total_comment_lines,
        "total_code_lines": total_code_lines,
        "comment_to_code_ratio": ratio,
        "comment_to_code_percentage": percentage,
    }


def build_maintainability_summary(findings_df: pd.DataFrame) -> pd.DataFrame:
    total_findings = len(findings_df)
    doc_violations = 0
    maint_violations = 0
    if not findings_df.empty:
        doc_violations = int(findings_df["rule_id"].isin(DOCUMENTATION_RULES).sum())
        maint_violations = int(findings_df["rule_id"].isin(MAINTAINABILITY_RULES).sum())
    return pd.DataFrame(
        [
            {"metric_name": "Total_Documentation_Violations", "metric_value": doc_violations},
            {"metric_name": "Total_Maintainability_Violations", "metric_value": maint_violations},
            {"metric_name": "Total_Code_Smells", "metric_value": total_findings},
        ]
    )


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

    comment_metrics_df = build_comment_code_metrics(js_files)
    comment_metrics_df.to_csv(output / "comment_code_metrics.csv", index=False)

    comment_ratio = compute_comment_ratio(comment_metrics_df)
    pd.DataFrame(
        [{"metric_name": "Comment_to_Code_Ratio", "metric_value": comment_ratio["comment_to_code_ratio"]}]
    ).to_csv(output / "comment_to_code_ratio_summary.csv", index=False)
    pd.DataFrame(
        [{"metric_name": "Comment_to_Code_Percentage", "metric_value": comment_ratio["comment_to_code_percentage"]}]
    ).to_csv(output / "comment_percentage_summary.csv", index=False)

    maintainability_df = build_maintainability_summary(findings_df)
    maintainability_df.to_csv(output / "maintainability_summary.csv", index=False)

    write_error_log(errors, output / "error_log.txt")

    doc_violations = int(
        maintainability_df.loc[
            maintainability_df["metric_name"] == "Total_Documentation_Violations", "metric_value"
        ].iloc[0]
    )
    maint_violations = int(
        maintainability_df.loc[
            maintainability_df["metric_name"] == "Total_Maintainability_Violations", "metric_value"
        ].iloc[0]
    )

    return {
        "benchmark_ready": len(js_files) > 0 and comment_ratio["total_code_lines"] > 0,
        "javascript_files": len(js_files),
        "total_comment_lines": int(comment_ratio["total_comment_lines"]),
        "total_code_lines": int(comment_ratio["total_code_lines"]),
        "comment_to_code_ratio": comment_ratio["comment_to_code_ratio"],
        "comment_to_code_percentage": comment_ratio["comment_to_code_percentage"],
        "total_findings": len(findings_df),
        "documentation_violations": doc_violations,
        "maintainability_violations": maint_violations,
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
