"""ESLint code smells benchmark execution helpers."""
from __future__ import annotations

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

JS_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs"}
EXCLUDED = {".git", "node_modules", "dist", "build", "coverage", "out", "vendor", "docs"}
CODE_SMELL_RULES = {
    "complexity",
    "max-depth",
    "max-lines-per-function",
    "max-params",
    "max-statements",
    "no-duplicate-imports",
    "no-unused-vars",
    "no-unreachable",
    "no-shadow",
}
ESLINT_CONFIG = {
    "env": {"browser": True, "node": True, "es2022": True},
    "parserOptions": {"ecmaVersion": "latest", "sourceType": "module"},
    "extends": ["eslint:recommended"],
    "rules": {
        "complexity": ["warn", 10],
        "max-depth": ["warn", 4],
        "max-lines-per-function": ["warn", 50],
        "max-params": ["warn", 5],
        "max-statements": ["warn", 20],
        "no-duplicate-imports": "warn",
        "no-unused-vars": "warn",
        "no-unreachable": "warn",
        "no-shadow": "warn",
    },
}
FLAT_CONFIG_RULES = ESLINT_CONFIG["rules"]
RESULTS_COLUMNS = ["file", "line", "column", "severity", "ruleId", "message", "nodeType"]
SMELLS_COLUMNS = ["file", "line", "rule_id", "severity", "message"]
ESLINT_SUCCESS_CODES = {0, 1}


def discover_javascript_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in JS_EXTENSIONS:
            continue
        if any(part in EXCLUDED for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


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


def ensure_eslint_config(repo: Path) -> tuple[Path, Path | None]:
    eslintrc = repo / ".eslintrc.json"
    if not eslintrc.exists():
        eslintrc.write_text(json.dumps(ESLINT_CONFIG, indent=2), encoding="utf-8")

    flat_config = repo / "eslint.config.js"
    if not flat_config.exists():
        rules_json = json.dumps(FLAT_CONFIG_RULES, indent=6).replace("\n", "\n      ")
        flat_config.write_text(
            "export default [\n"
            "  {\n"
            "    files: ['**/*.{js,jsx,mjs,cjs}'],\n"
            "    languageOptions: { ecmaVersion: 'latest', sourceType: 'module' },\n"
            f"    rules: {rules_json},\n"
            "  },\n"
            "];\n",
            encoding="utf-8",
        )
        return eslintrc, flat_config
    return eslintrc, None


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


def records_to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in records:
        for message in record.get("messages", []):
            rows.append(
                {
                    "file": record.get("filePath", ""),
                    "line": message.get("line", ""),
                    "column": message.get("column", ""),
                    "severity": message.get("severity", ""),
                    "ruleId": message.get("ruleId", ""),
                    "message": message.get("message", ""),
                    "nodeType": message.get("nodeType", ""),
                }
            )
    return pd.DataFrame(rows, columns=RESULTS_COLUMNS)


def is_code_smell(rule_id: str) -> bool:
    return rule_id in CODE_SMELL_RULES


def extract_code_smells(results_df: pd.DataFrame) -> pd.DataFrame:
    if results_df.empty:
        return pd.DataFrame(columns=SMELLS_COLUMNS)
    smells = results_df[results_df["ruleId"].map(lambda value: is_code_smell(str(value)))].copy()
    smells = smells.rename(columns={"ruleId": "rule_id"})
    return smells[SMELLS_COLUMNS].reset_index(drop=True)


def count_failed_files(records: list[dict[str, Any]], javascript_files: list[Path]) -> int:
    failed: set[str] = set()
    for record in records:
        for message in record.get("messages", []):
            if message.get("fatal"):
                failed.add(str(record.get("filePath", "")))
    analyzed = {
        str(record.get("filePath", ""))
        for record in records
        if not any(message.get("fatal") for message in record.get("messages", []))
    }
    return max(len(javascript_files) - len(analyzed), len(failed))


def run_pipeline(repo: Path, output: Path, runtimes_root: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    repo = repo.resolve()
    error_lines: list[str] = []

    ensure_eslint_config(repo)
    javascript_files = discover_javascript_files(repo)
    pd.DataFrame(
        [
            {
                "absolute_path": str(path),
                "relative_path": str(path.relative_to(repo)),
                "extension": path.suffix.lower(),
            }
            for path in javascript_files
        ]
    ).to_csv(output / "javascript_files.csv", index=False)

    eslint_executable = resolve_eslint_executable(runtimes_root)
    text_cmd = build_eslint_command(eslint_executable, repo)
    json_cmd = build_eslint_command(eslint_executable, repo, "json")

    raw_out, raw_err, raw_code = run_command(text_cmd)
    json_out, json_err, json_code = run_command(json_cmd)
    raw_text = combine_raw(raw_out, raw_err)

    (output / "eslint_raw_output.txt").write_text(raw_text, encoding="utf-8")

    records = parse_eslint_json(json_out)
    (output / "eslint_output.json").write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    if raw_code not in ESLINT_SUCCESS_CODES and not records:
        error_lines.append(f"ESLint text run exited with code {raw_code}")
    if json_code not in ESLINT_SUCCESS_CODES and not records:
        error_lines.append(f"ESLint JSON run exited with code {json_code}")
    if json_err.strip():
        error_lines.append(f"ESLint JSON stderr: {json_err.strip()}")

    results_df = records_to_dataframe(records)
    results_df.to_csv(output / "eslint_results.csv", index=False)

    smells_df = extract_code_smells(results_df)
    smells_df.to_csv(output / "code_smells_findings.csv", index=False)

    summary_df = pd.DataFrame([{"metric_name": "Code_Smells_Count", "metric_value": len(smells_df)}])
    summary_df.to_csv(output / "code_smells_summary.csv", index=False)
    (output / "error_log.txt").write_text("\n".join(error_lines), encoding="utf-8")

    files_failed = count_failed_files(records, javascript_files)
    files_success = max(len(javascript_files) - files_failed, 0)

    return {
        "benchmark_ready": len(javascript_files) > 0 and len(smells_df) >= 5,
        "javascript_files": len(javascript_files),
        "files_success": files_success,
        "files_failed": files_failed,
        "total_findings": len(results_df),
        "code_smells_count": len(smells_df),
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
