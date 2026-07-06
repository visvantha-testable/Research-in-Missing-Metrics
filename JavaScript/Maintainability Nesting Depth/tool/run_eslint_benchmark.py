"""Run ESLint benchmark pipeline on js_nesting_benchmark."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

os.environ.pop("PYTHONPATH", None)

TOOL_ROOT = Path(__file__).resolve().parent
METRIC_ROOT = TOOL_ROOT.parent
PROJECT_ROOT = METRIC_ROOT.parent.parent
RUNTIMES_ROOT = PROJECT_ROOT / "runtimes"
BENCHMARK = METRIC_ROOT / "workspace" / "js_nesting_benchmark"
OUTPUT = METRIC_ROOT / "outputs"
MAX_ALLOWED_DEPTH = 5
ESLINT_RULE = "max-depth"
MAX_DEPTH_PATTERN = re.compile(
    r"Blocks are nested too deeply \((?P<actual>\d+)\)\. Maximum allowed is (?P<threshold>\d+)\."
)


def discover_js(repo: Path) -> list[Path]:
    excluded = {".git", "node_modules", "dist", "build", "coverage", "out", "vendor", "docs"}
    files = []
    for path in repo.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".js", ".jsx", ".mjs", ".cjs"}:
            continue
        if any(part in excluded for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def resolve_eslint_executable(root: Path | None = None) -> list[str]:
    search_roots = [root or RUNTIMES_ROOT, RUNTIMES_ROOT, METRIC_ROOT, TOOL_ROOT]
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


def eslint_cmd(repo: Path, fmt: str | None = None) -> list[str]:
    base = resolve_eslint_executable() + [str(repo), "--rule", f'max-depth:["warn",{MAX_ALLOWED_DEPTH}]']
    if fmt:
        base.extend(["-f", fmt])
    return base


def run(cmd: list[str]) -> tuple[str, str, int]:
    completed = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return completed.stdout, completed.stderr, completed.returncode


def ensure_config(repo: Path) -> None:
    eslintrc = repo / ".eslintrc.json"
    if not eslintrc.exists():
        eslintrc.write_text(
            json.dumps(
                {
                    "env": {"browser": True, "node": True, "es2022": True},
                    "parserOptions": {"ecmaVersion": "latest", "sourceType": "module"},
                    "rules": {"max-depth": ["warn", MAX_ALLOWED_DEPTH]},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    flat = repo / "eslint.config.js"
    if not flat.exists():
        flat.write_text(
            "export default [\n"
            "  {\n"
            "    files: ['**/*.{js,jsx,mjs,cjs}'],\n"
            "    languageOptions: { ecmaVersion: 'latest', sourceType: 'module' },\n"
            f"    rules: {{ 'max-depth': ['warn', {MAX_ALLOWED_DEPTH}] }},\n"
            "  },\n"
            "];\n",
            encoding="utf-8",
        )


def parse_findings(records: list[dict]) -> pd.DataFrame:
    rows = []
    for record in records:
        for message in record.get("messages", []):
            if message.get("ruleId") != ESLINT_RULE:
                continue
            text = message.get("message", "")
            match = MAX_DEPTH_PATTERN.search(text)
            rows.append(
                {
                    "file": record.get("filePath", ""),
                    "line": message.get("line", ""),
                    "rule": message.get("ruleId", ""),
                    "actual_depth": int(match.group("actual")) if match else None,
                    "threshold": int(match.group("threshold")) if match else MAX_ALLOWED_DEPTH,
                    "status": "reported" if match else "unparsed",
                }
            )
    return pd.DataFrame(rows)


def results_dataframe(records: list[dict]) -> pd.DataFrame:
    rows = []
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
    return pd.DataFrame(rows)


def run_pipeline(repo: Path, output: Path) -> dict:
    repo = repo.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    ensure_config(repo)
    js_files = discover_js(repo)
    pd.DataFrame([
        {"absolute_path": str(p), "relative_path": str(p.relative_to(repo)), "extension": p.suffix.lower()}
        for p in js_files
    ]).to_csv(output / "javascript_files.csv", index=False)

    raw_out, raw_err, _ = run(eslint_cmd(repo))
    json_out, _, _ = run(eslint_cmd(repo, "json"))
    raw = raw_out + (("\n" + raw_err) if raw_err else "")

    (output / "eslint_raw_output.txt").write_text(raw, encoding="utf-8")
    records = json.loads(json_out) if json_out.strip() else []
    (output / "eslint_output.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    results_dataframe(records).to_csv(output / "eslint_results.csv", index=False)

    findings = parse_findings(records)
    findings.to_csv(output / "nesting_depth_findings.csv", index=False)

    if findings.empty:
        summary = pd.DataFrame([
            {"metric_name": "Maintainability_Nesting_Depth", "metric_value": 0},
            {"metric_name": "Average_Nesting_Depth", "metric_value": 0},
        ])
    else:
        valid = findings[findings["actual_depth"].notna()]
        summary = pd.DataFrame([
            {"metric_name": "Maintainability_Nesting_Depth", "metric_value": int(valid["actual_depth"].max())},
            {"metric_name": "Average_Nesting_Depth", "metric_value": round(float(valid["actual_depth"].mean()), 4)},
        ])
    summary.to_csv(output / "maintainability_nesting_depth_summary.csv", index=False)
    (output / "error_log.txt").write_text("", encoding="utf-8")

    return {
        "benchmark_ready": len(js_files) > 0 and len(findings) > 0,
        "javascript_files": len(js_files),
        "nesting_findings": len(findings),
        "max_nesting_depth": int(findings["actual_depth"].max()) if not findings.empty else 0,
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    result = run_pipeline(BENCHMARK, OUTPUT)
    print(json.dumps(result, indent=2))
    if not result.get("benchmark_ready"):
        sys.exit(1)
