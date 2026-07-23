"""Vitest Exception Path Analysis notebook helpers."""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from git import Repo
from git.exc import GitCommandError

os.environ.pop("PYTHONPATH", None)

REPO_URL = "https://github.com/visvantha-testable/typescript-tool-testing-knip.git"
PROGRAMMING_LANGUAGE = "TypeScript"
PRIMARY_TOOL = "Vitest"
COVERAGE_TOOL = "@vitest/coverage-v8"
WHITEBOX_STRATEGY = "Control Flow Testing"
CLASSIFICATION = "Path Coverage"
METRIC_NAME = "Exception Path Handling"
METRIC_DESCRIPTION = (
    "Measure the application's ability to gracefully handle unexpected errors and exception paths, "
    "ensuring the system does not crash when execution reaches failure states such as thrown exceptions, "
    "try-catch-finally blocks, rejected promises, runtime errors, or other exceptional control flows."
)
VITEST_PACKAGES = ("vitest", "@vitest/coverage-v8")
VITEST_CONFIG_NAMES = (
    "vitest.config.ts",
    "vitest.config.js",
    "vitest.config.mjs",
    "vitest.config.cjs",
    "vite.config.ts",
    "vite.config.js",
)
EVIDENCE_PATTERNS: list[tuple[str, str]] = [
    ("throw statements", r"\bthrow\b"),
    ("catch blocks", r"\bcatch\b"),
    ("finally blocks", r"\bfinally\b"),
    ("runtime exceptions", r"\b(exception|Exception)\b"),
    ("handled exceptions", r"\b(handled|Handled)\b"),
    ("uncaught exceptions", r"\b(Uncaught|uncaught|unhandled)\b"),
    ("rejected promises", r"\b(reject|rejected|Rejected)\b"),
    ("assertion failures", r"\b(FAIL|AssertionError|assertion failed)\b"),
    ("stack traces", r"\b(at .+|stack trace|Stack:)\b"),
    ("error messages", r"\b(error|Error|ERROR)\b"),
    ("branch execution through exceptional paths", r"\b(branches?\.(covered|total|pct)|errorflow|errorFlow)\b"),
]
METRIC_MAPPING_ROWS = [
    ("Control Flow Testing (Strategy)", "Vitest test execution output"),
    ("Path Coverage (Classification)", "coverage-summary.json total.branches.*"),
    ("Exception Path Handling (Metric)", "Exception-path evidence in raw Vitest/coverage output"),
    ("Statements Coverage", "coverage-summary.json total.statements.*"),
    ("Branches Coverage", "coverage-summary.json total.branches.*"),
    ("Functions Coverage", "coverage-summary.json total.functions.*"),
    ("Lines Coverage", "coverage-summary.json total.lines.*"),
]


def resolve_metric_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__).resolve().parent).resolve()
    for _ in range(8):
        if (current / "tool" / "_vitest_exception_path_analysis_utils.py").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return Path(__file__).resolve().parent.parent


def ensure_dirs(metric_root: Path) -> dict[str, Path]:
    paths = {
        "root": metric_root,
        "artifacts": metric_root / "artifacts",
        "workspace": metric_root / "workspace",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def clone_repository(repo_url: str, workspace: Path, reuse: bool = True) -> tuple[Path, dict[str, Any]]:
    repo_name = repo_url.rstrip("/").removesuffix(".git").split("/")[-1]
    clone_path = workspace / repo_name
    status = {"cloned": False, "reused": False, "error": ""}
    try:
        if clone_path.exists() and reuse:
            status["reused"] = True
            return clone_path.resolve(), status
        if clone_path.exists():
            shutil.rmtree(clone_path)
        Repo.clone_from(repo_url, clone_path, depth=1)
        status["cloned"] = True
        return clone_path.resolve(), status
    except GitCommandError as exc:
        status["error"] = str(exc)
        return clone_path.resolve(), status


def collect_environment(repo_path: Path) -> dict[str, str]:
    node = shutil.which("node") or shutil.which("node.exe")
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    node_version = "unknown"
    npm_version = "unknown"
    if node:
        proc = subprocess.run([node, "--version"], capture_output=True, text=True, check=False)
        node_version = (proc.stdout or proc.stderr).strip() if proc.returncode == 0 else "unknown"
    if npm:
        proc = subprocess.run([npm, "--version"], capture_output=True, text=True, check=False)
        npm_version = (proc.stdout or proc.stderr).strip() if proc.returncode == 0 else "unknown"
    return {
        "node_version": node_version,
        "npm_version": npm_version,
        "operating_system": platform.platform(),
        "python_version": sys.version.split()[0],
        "current_working_directory": str(repo_path.resolve()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def resolve_executable(*names: str) -> str | None:
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return None


def build_shell_command(command: str | list[str]) -> tuple[list[str], bool]:
    if isinstance(command, str):
        return [command], True
    if not command:
        return [], False
    executable = command[0]
    if executable == "npm":
        resolved = resolve_executable("npm", "npm.cmd")
        if resolved:
            return [resolved, *command[1:]], False
    if executable == "npx":
        resolved = resolve_executable("npx", "npx.cmd")
        if resolved:
            return [resolved, *command[1:]], False
    return command, False


def run_command(
    command: list[str] | str,
    cwd: Path,
    label: str = "",
) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    resolved_command, use_shell = build_shell_command(command)
    try:
        completed = subprocess.run(
            resolved_command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            shell=use_shell,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        terminal = stdout
        if stderr:
            terminal = f"{stdout}\n----- STDERR -----\n{stderr}" if stdout else stderr
        return {
            "label": label,
            "command": resolved_command if isinstance(resolved_command, str) else " ".join(resolved_command),
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "terminal_output": terminal,
            "success": completed.returncode == 0,
            "started_at": started.isoformat(),
            "error": "",
        }
    except Exception as exc:
        return {
            "label": label,
            "command": resolved_command if isinstance(resolved_command, str) else " ".join(resolved_command),
            "returncode": -1,
            "stdout": "",
            "stderr": "",
            "terminal_output": str(exc),
            "success": False,
            "started_at": started.isoformat(),
            "error": str(exc),
        }


def npm_install(repo_path: Path) -> dict[str, Any]:
    npm = resolve_executable("npm", "npm.cmd")
    if not npm:
        return run_command("npm install", repo_path, "npm install")
    return run_command([npm, "install"], repo_path, "npm install")


def package_installed(repo_path: Path, package_name: str) -> bool:
    return (repo_path / "node_modules" / package_name / "package.json").exists()


def read_package_version(repo_path: Path, package_name: str) -> str:
    package_json = repo_path / "node_modules" / package_name / "package.json"
    if not package_json.exists():
        return "NOT INSTALLED"
    try:
        return str(json.loads(package_json.read_text(encoding="utf-8")).get("version", "unknown"))
    except json.JSONDecodeError:
        return "unknown"


def ensure_vitest_packages(repo_path: Path) -> pd.DataFrame:
    npm = resolve_executable("npm", "npm.cmd") or "npm"
    rows: list[dict[str, str]] = []
    for package in VITEST_PACKAGES:
        version = read_package_version(repo_path, package)
        if version != "NOT INSTALLED":
            rows.append({"package": package, "version": version, "action": "already present", "status": "OK"})
            continue
        result = run_command([npm, "install", "--no-save", package], repo_path, f"install {package}")
        version = read_package_version(repo_path, package)
        status = "OK" if result["success"] and version != "NOT INSTALLED" else "FAIL"
        rows.append(
            {
                "package": package,
                "version": version,
                "action": "installed with --no-save",
                "status": status,
            }
        )
    return pd.DataFrame(rows)


def detect_test_configuration(repo_path: Path) -> dict[str, Any]:
    config: dict[str, Any] = {
        "package_json_path": str(repo_path / "package.json"),
        "scripts": {},
        "vitest_config_files": [],
        "test_command": "npx vitest run",
        "coverage_command": "npx vitest run --coverage",
    }
    package_json = repo_path / "package.json"
    if package_json.exists():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
            scripts = payload.get("scripts") or {}
            config["scripts"] = scripts
            if "test" in scripts:
                config["test_command"] = "npm test"
            if "coverage" in scripts:
                config["coverage_command"] = "npm run coverage"
        except json.JSONDecodeError:
            config["parse_error"] = "Invalid package.json"
    for name in VITEST_CONFIG_NAMES:
        candidate = repo_path / name
        if candidate.is_file():
            config["vitest_config_files"].append(str(candidate.resolve()))
    return config


def _parse_reports_directory(config_text: str) -> str | None:
    match = re.search(r"reportsDirectory\s*:\s*['\"]([^'\"]+)['\"]", config_text)
    return match.group(1) if match else None


def locate_coverage_dir(repo_path: Path, config_files: list[str]) -> Path | None:
    candidates: list[Path] = []
    for config_file in config_files:
        path = Path(config_file)
        if not path.exists():
            continue
        reports_dir = _parse_reports_directory(path.read_text(encoding="utf-8", errors="replace"))
        if reports_dir:
            configured = Path(reports_dir)
            candidates.append(configured if configured.is_absolute() else (repo_path / configured).resolve())
    candidates.extend(
        [
            repo_path / "artifacts" / "training" / "coverage",
            repo_path / "coverage",
        ]
    )
    for candidate in candidates:
        if (candidate / "coverage-summary.json").exists():
            return candidate.resolve()
    for summary in repo_path.rglob("coverage-summary.json"):
        if "node_modules" not in summary.parts:
            return summary.parent.resolve()
    return None


def copy_if_exists(source: Path, destination: Path) -> bool:
    if not source.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True


def collect_coverage_artifacts(coverage_dir: Path | None, artifacts_dir: Path) -> dict[str, Any]:
    names = ["coverage-final.json", "coverage-summary.json", "lcov.info", "index.html", "taxonomy_metrics.json"]
    found: dict[str, Any] = {"coverage_directory": str(coverage_dir) if coverage_dir else "", "files": {}, "missing": []}
    if coverage_dir is None:
        found["missing"] = names
        return found
    for name in names:
        source = coverage_dir / name
        target = artifacts_dir / name
        if copy_if_exists(source, target):
            found["files"][name] = str(target.resolve())
        else:
            found["missing"].append(name)
    coverage_tree = artifacts_dir / "coverage"
    if coverage_dir.exists():
        for path in coverage_dir.rglob("*"):
            if path.is_file():
                rel = path.relative_to(coverage_dir)
                target = coverage_tree / rel
                copy_if_exists(path, target)
    return found


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def extract_matching_lines(source_name: str, text: str, evidence_type: str, pattern: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not text:
        return rows
    compiled = re.compile(pattern, re.IGNORECASE)
    for line in text.splitlines():
        if compiled.search(line):
            rows.append({"Source": source_name, "Evidence Type": evidence_type, "Raw Output": line})
    return rows


def build_exception_evidence_dataframe(sources: dict[str, str]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for source_name, text in sources.items():
        for evidence_type, pattern in EVIDENCE_PATTERNS:
            rows.extend(extract_matching_lines(source_name, text, evidence_type, pattern))
    if not rows:
        return pd.DataFrame(columns=["Source", "Evidence Type", "Raw Output"])
    return pd.DataFrame(rows)


def extract_coverage_metrics(summary_path: Path) -> pd.DataFrame:
    if not summary_path.exists():
        return pd.DataFrame(columns=["Metric", "JSON Field", "Value"])
    summary = json.loads(read_text(summary_path))
    total = summary.get("total") or {}
    rows: list[dict[str, Any]] = []
    for metric in ("statements", "branches", "functions", "lines"):
        section = total.get(metric) or {}
        for key in ("covered", "total", "pct"):
            if key in section:
                rows.append(
                    {
                        "Metric": metric.capitalize(),
                        "JSON Field": f"total.{metric}.{key}",
                        "Value": section[key],
                    }
                )
    return pd.DataFrame(rows)


def load_taxonomy_metrics(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError:
        return None


def build_metric_mapping(
    evidence_df: pd.DataFrame,
    coverage_metrics_df: pd.DataFrame,
    test_result: dict[str, Any],
    coverage_result: dict[str, Any],
    artifact_info: dict[str, Any],
    taxonomy_metrics: dict[str, Any] | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    def taxonomy_entry(level: str) -> tuple[str, str] | None:
        if not taxonomy_metrics:
            return None
        section = taxonomy_metrics.get("taxonomy_coverage") or {}
        entry = section.get(level)
        if isinstance(entry, dict):
            covered = str(entry.get("covered", "No"))
            evidence = str(entry.get("evidence", ""))
            present = "Yes" if covered.lower() == "yes" else "Partial" if covered.lower() == "partial" else "No"
            return present, evidence
        return None

    def present_from_evidence(keywords: list[str]) -> tuple[str, str]:
        if taxonomy_metrics:
            metric_entry = taxonomy_entry("Exception Path Handling")
            if metric_entry:
                return metric_entry
        if evidence_df.empty:
            return "No", "No Exception Path Handling evidence found in the raw tool output."
        mask = evidence_df["Evidence Type"].str.lower().apply(
            lambda value: any(keyword.lower() in value for keyword in keywords)
        )
        matched = evidence_df[mask]
        if matched.empty:
            return "No", "No Exception Path Handling evidence found in the raw tool output."
        sample = matched.iloc[0]["Raw Output"]
        return "Yes", sample

    strategy_entry = taxonomy_entry("Control Flow Testing")
    if strategy_entry:
        strategy_present, strategy_evidence = strategy_entry
    else:
        strategy_present = "Yes" if test_result.get("success") else "No"
        strategy_evidence = test_result.get("terminal_output", "")[:200] or "Test execution did not succeed."

    classification_entry = taxonomy_entry("Path Coverage")
    branch_rows = coverage_metrics_df[coverage_metrics_df["Metric"] == "Branches"]
    if classification_entry:
        branch_present, branch_evidence = classification_entry
    elif not branch_rows.empty:
        branch_present = "Yes"
        branch_evidence = "; ".join(f"{row['JSON Field']}={row['Value']}" for _, row in branch_rows.iterrows())
    else:
        branch_present = "No"
        branch_evidence = "No branch coverage reported."

    exception_present, exception_evidence = present_from_evidence(["exception", "throw", "catch", "branch execution"])

    kpi_entry = taxonomy_entry("Error Flow Verification")
    if kpi_entry:
        kpi_present, kpi_evidence = kpi_entry
    elif taxonomy_metrics and taxonomy_metrics.get("Error Flow Verification") == 100:
        kpi_present = "Yes"
        kpi_evidence = f"taxonomy_metrics.json Error Flow Verification={taxonomy_metrics.get('Error Flow Verification')}"
    else:
        kpi_present = "No"
        kpi_evidence = "No Error Flow Verification field in raw tool output."

    mapping = [
        ("Control Flow Testing (Strategy)", strategy_evidence, strategy_present),
        ("Path Coverage (Classification)", branch_evidence, branch_present),
        ("Exception Path Handling (Metric)", exception_evidence, exception_present),
        ("Error Flow Verification (KPI)", kpi_evidence, kpi_present),
    ]

    for metric in ("Statements", "Branches", "Functions", "Lines"):
        section = coverage_metrics_df[coverage_metrics_df["Metric"] == metric]
        if section.empty:
            mapping.append((f"{metric} Coverage", "Not reported in coverage-summary.json", "No"))
        else:
            evidence = "; ".join(f"{row['JSON Field']}={row['Value']}" for _, row in section.iterrows())
            mapping.append((f"{metric} Coverage", evidence, "Yes"))

    return pd.DataFrame(
        [{"Metric": metric, "Tool Evidence": evidence, "Present (Yes/No)": present} for metric, evidence, present in mapping]
    )


def build_execution_summary(
    repo_url: str,
    test_result: dict[str, Any],
    coverage_result: dict[str, Any],
    artifact_info: dict[str, Any],
    evidence_df: pd.DataFrame,
    saved_files: list[str],
    notebook_status: str,
    taxonomy_metrics: dict[str, Any] | None = None,
) -> pd.DataFrame:
    branch_available = "Yes" if "coverage-summary.json" in artifact_info.get("files", {}) else "No"
    if taxonomy_metrics:
        taxonomy = taxonomy_metrics.get("taxonomy_coverage") or {}
        exception_entry = taxonomy.get("Exception Path Handling") or {}
        kpi_entry = taxonomy.get("Error Flow Verification") or {}
        if exception_entry.get("covered") == "Yes" and kpi_entry.get("covered") == "Yes":
            evidence_found = "Yes"
        elif exception_entry.get("covered") == "Partial" or kpi_entry.get("covered") == "Partial":
            evidence_found = "Partial"
        else:
            evidence_found = "No Exception Path Handling evidence found in the raw tool output."
    else:
        evidence_found = "Yes" if not evidence_df.empty else "No Exception Path Handling evidence found in the raw tool output."
    return pd.DataFrame(
        [
            {"Field": "Repository URL", "Value": repo_url},
            {"Field": "Tool Name", "Value": f"{PRIMARY_TOOL} + {COVERAGE_TOOL}"},
            {"Field": "Language", "Value": PROGRAMMING_LANGUAGE},
            {"Field": "White-box Strategy", "Value": WHITEBOX_STRATEGY},
            {"Field": "Classification", "Value": CLASSIFICATION},
            {"Field": "Metric", "Value": METRIC_NAME},
            {"Field": "Test Execution Status", "Value": "SUCCESS" if test_result.get("success") else "FAILED"},
            {"Field": "Coverage Execution Status", "Value": "SUCCESS" if coverage_result.get("success") else "FAILED"},
            {
                "Field": "Coverage Files Generated",
                "Value": ", ".join(artifact_info.get("files", {}).keys()) or "None",
            },
            {"Field": "Exception Path Evidence Found", "Value": evidence_found},
            {"Field": "Branch Coverage Available", "Value": branch_available},
            {"Field": "Output Files Saved", "Value": ", ".join(saved_files)},
            {"Field": "Notebook Execution Status", "Value": notebook_status},
        ]
    )
