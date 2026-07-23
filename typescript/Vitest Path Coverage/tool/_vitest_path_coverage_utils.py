"""Vitest + @vitest/coverage-v8 Path Coverage validation helpers."""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

os.environ.pop("PYTHONPATH", None)

DEFAULT_REPO_URL = (
    "https://github.com/visvantha-testable/typescript-tool-testing-eslint-eslint-plugin-sonarjs.git"
)
PACKAGE_MANAGER = "npm"
PROGRAMMING_LANGUAGE = "TypeScript"
VITEST_PACKAGES = ("vitest", "@vitest/coverage-v8")
VITEST_CONFIG_NAMES = (
    "vitest.config.ts",
    "vitest.config.js",
    "vitest.config.mjs",
    "vitest.config.cjs",
    "vite.config.ts",
    "vite.config.js",
)
PATH_COVERAGE_FIELDS = (
    "pathCoverage",
    "path_coverage",
    "pathCoveragePercent",
    "path_coverage_percent",
    "paths",
    "total_paths",
    "covered_paths",
)
METRIC_DEFINITION = (
    "Percentage of all distinct execution paths through a function that are exercised by the test suite."
)
COVERAGE_METRIC_COLUMNS = [
    "Metric",
    "JSON Field",
    "Value",
]
FINAL_REPORT_COLUMNS = [
    "Technique",
    "Classification",
    "Metric",
    "Definition",
    "Tool Used",
    "Raw Output File",
    "Metric Available",
    "Evidence",
]


class NotebookLogger:
    def __init__(self, error_log_path: Path) -> None:
        self.error_log_path = error_log_path
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._errors: list[dict[str, str]] = []
        self.command_log: list[dict[str, Any]] = []
        if not self.error_log_path.exists():
            self.write_errors()

    def info(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"[{timestamp}] INFO: {message}")

    def error(self, message: str, file: str = "notebook") -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        line = f"[{timestamp}] ERROR: {message}\n"
        print(line, end="")
        self._errors.append({"timestamp": timestamp, "file": file, "error_message": message})
        self.write_errors()

    def log_command(self, command: list[str], stdout: str, stderr: str, returncode: int, elapsed_ms: float) -> None:
        self.command_log.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "command": " ".join(command),
                "returncode": returncode,
                "elapsed_ms": round(elapsed_ms, 2),
            }
        )

    def write_errors(self) -> None:
        with self.error_log_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timestamp", "file", "error_message"])
            writer.writeheader()
            writer.writerows(self._errors)
        if self.command_log:
            with self.error_log_path.open("a", encoding="utf-8") as handle:
                handle.write("\n===== COMMAND LOG =====\n")
                for entry in self.command_log:
                    handle.write(json.dumps(entry) + "\n")


def resolve_metric_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__).resolve().parent).resolve()
    for _ in range(8):
        if (current / "tool" / "_vitest_path_coverage_utils.py").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return Path(__file__).resolve().parent.parent


def ensure_artifact_dirs(metric_root: Path) -> dict[str, Path]:
    paths = {
        "root": metric_root / "artifacts",
        "raw": metric_root / "artifacts" / "raw",
        "parsed": metric_root / "artifacts" / "parsed",
        "reports": metric_root / "artifacts" / "reports",
        "temp": metric_root / "artifacts" / "temp",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def derive_clone_path(repo_url: str, workspace_dir: Path) -> Path:
    repo_name = repo_url.rstrip("/").removesuffix(".git").split("/")[-1]
    if not repo_name:
        raise ValueError(f"Unable to derive repository name from URL: {repo_url}")
    return workspace_dir / repo_name


def validate_repo_url(repo_url: str) -> None:
    if not repo_url or not isinstance(repo_url, str):
        raise ValueError("REPO_URL must be a non-empty string.")
    if not (repo_url.startswith("https://") or repo_url.startswith("git@") or repo_url.startswith("http://")):
        raise ValueError(f"Invalid repository URL format: {repo_url}")


def clone_or_reuse_repository(
    repo_url: str,
    workspace_dir: Path,
    if_clone_exists: str,
    logger: NotebookLogger,
    clone_depth: int | None = None,
) -> Path:
    validate_repo_url(repo_url)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    clone_path = derive_clone_path(repo_url, workspace_dir)
    if clone_path.exists():
        if if_clone_exists == "reclone":
            logger.info(f"Removing existing clone at {clone_path}")
            shutil.rmtree(clone_path)
        elif if_clone_exists == "reuse":
            logger.info(f"Reusing existing clone at {clone_path}")
            return clone_path.resolve()
        else:
            raise ValueError("IF_CLONE_EXISTS must be 'reuse' or 'reclone'.")
    logger.info(f"Cloning {repo_url} into {clone_path}")
    clone_kwargs: dict[str, Any] = {"depth": clone_depth} if clone_depth else {}
    try:
        Repo.clone_from(repo_url, clone_path, **clone_kwargs)
    except GitCommandError as exc:
        logger.error(f"Git clone failed: {exc}", file=repo_url)
        raise
    return clone_path.resolve()


def validate_local_repo_path(local_repo_path: Path, logger: NotebookLogger) -> Path:
    if not local_repo_path.exists():
        msg = f"Local repository path does not exist: {local_repo_path}"
        logger.error(msg, file=str(local_repo_path))
        raise FileNotFoundError(msg)
    if not local_repo_path.is_dir():
        msg = f"Local repository path is not a directory: {local_repo_path}"
        logger.error(msg, file=str(local_repo_path))
        raise NotADirectoryError(msg)
    try:
        Repo(local_repo_path)
        logger.info("Validated Git repository.")
    except InvalidGitRepositoryError:
        logger.info("Path is not a Git repository; proceeding as source directory.")
    return local_repo_path.resolve()


def resolve_repository_path(
    use_git_repo: bool,
    repo_url: str,
    local_repo: Path,
    workspace_dir: Path,
    if_clone_exists: str,
    logger: NotebookLogger,
    clone_depth: int | None = None,
) -> Path:
    if use_git_repo:
        return clone_or_reuse_repository(repo_url, workspace_dir, if_clone_exists, logger, clone_depth)
    return validate_local_repo_path(local_repo, logger)


def validate_repository_layout(repo_path: Path, logger: NotebookLogger) -> dict[str, Any]:
    package_json = repo_path / "package.json"
    tsconfig = repo_path / "tsconfig.json"
    checks = {
        "package.json": package_json.is_file(),
        "tsconfig.json": tsconfig.is_file(),
    }
    for name, ok in checks.items():
        if not ok:
            logger.error(f"Missing mandatory repository file: {name}", file=str(repo_path / name))
    return {
        "repository_name": repo_path.name,
        **checks,
        "repository_valid": all(checks.values()),
    }


def run_command(command: list[str], logger: NotebookLogger, cwd: Path | None = None) -> tuple[str, str, int, float]:
    start = time.perf_counter()
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        cwd=str(cwd) if cwd else None,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.log_command(command, completed.stdout, completed.stderr, completed.returncode, elapsed_ms)
    return completed.stdout, completed.stderr, completed.returncode, elapsed_ms


def resolve_npm(repo_path: Path) -> str:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        raise FileNotFoundError("npm not found on PATH.")
    local_npm = repo_path / "node_modules" / ".bin" / "npm"
    for candidate in (local_npm.with_suffix(".cmd"), local_npm):
        if candidate.exists():
            return str(candidate.resolve())
    return npm


def resolve_npx(repo_path: Path) -> str:
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        raise FileNotFoundError("npx not found on PATH.")
    local_npx = repo_path / "node_modules" / ".bin" / "npx"
    for candidate in (local_npx.with_suffix(".cmd"), local_npx):
        if candidate.exists():
            return str(candidate.resolve())
    return npx


def install_project_dependencies(repo_path: Path, logger: NotebookLogger) -> dict[str, Any]:
    npm = resolve_npm(repo_path)
    command = [npm, "install"]
    stdout, stderr, returncode, elapsed_ms = run_command(command, logger, cwd=repo_path)
    if returncode != 0:
        logger.error(
            f"npm install failed with exit code {returncode}: {stderr.strip() or stdout.strip()}",
            file=str(repo_path / "package.json"),
        )
    return {
        "command": " ".join(command),
        "returncode": returncode,
        "elapsed_ms": elapsed_ms,
        "stdout": stdout,
        "stderr": stderr,
    }


def read_installed_package_version(repo_path: Path, package_name: str) -> str:
    package_json = repo_path / "node_modules" / package_name / "package.json"
    if not package_json.exists():
        return "NOT INSTALLED"
    try:
        payload = json.loads(package_json.read_text(encoding="utf-8"))
        return str(payload.get("version", "unknown"))
    except json.JSONDecodeError:
        return "unknown"


def install_vitest_packages(repo_path: Path, logger: NotebookLogger) -> pd.DataFrame:
    npm = resolve_npm(repo_path)
    rows: list[dict[str, str]] = []
    for package in VITEST_PACKAGES:
        version = read_installed_package_version(repo_path, package)
        if version != "NOT INSTALLED":
            rows.append({"package": package, "version": version, "status": "OK", "action": "already present"})
            continue
        command = [npm, "install", "--save-dev", package]
        stdout, stderr, returncode, _ = run_command(command, logger, cwd=repo_path)
        version = read_installed_package_version(repo_path, package)
        status = "OK" if returncode == 0 and version != "NOT INSTALLED" else "FAIL"
        if status == "FAIL":
            logger.error(f"Failed to install required package: {package}", file=package)
        rows.append(
            {
                "package": package,
                "version": version,
                "status": status,
                "action": "installed" if status == "OK" else f"failed: {stderr.strip() or stdout.strip()}",
            }
        )
    return pd.DataFrame(rows)


def detect_vitest_config(repo_path: Path) -> Path | None:
    for name in VITEST_CONFIG_NAMES:
        candidate = repo_path / name
        if candidate.is_file() and "vitest" in candidate.read_text(encoding="utf-8", errors="replace").lower():
            return candidate
    for name in VITEST_CONFIG_NAMES:
        candidate = repo_path / name
        if candidate.is_file():
            return candidate
    return None


def _parse_reports_directory(config_text: str) -> str | None:
    match = re.search(r"reportsDirectory\s*:\s*['\"]([^'\"]+)['\"]", config_text)
    return match.group(1) if match else None


def create_temp_vitest_config(temp_dir: Path, reports_directory: Path) -> Path:
    temp_dir.mkdir(parents=True, exist_ok=True)
    config_path = temp_dir / "vitest.notebook.config.mjs"
    reports_posix = reports_directory.as_posix()
    config_path.write_text(
        "import { defineConfig } from 'vitest/config';\n\n"
        "export default defineConfig({\n"
        "  test: {\n"
        "    include: ['**/*.test.ts', '**/*.spec.ts'],\n"
        "    coverage: {\n"
        "      provider: 'v8',\n"
        "      reporter: ['json-summary', 'json', 'lcov', 'text'],\n"
        f"      reportsDirectory: '{reports_posix}',\n"
        "      all: true,\n"
        "    },\n"
        "  },\n"
        "});\n",
        encoding="utf-8",
    )
    return config_path


def collect_environment_info(repo_path: Path, logger: NotebookLogger) -> dict[str, str]:
    info: dict[str, str] = {}
    for tool, args in (("node", ["--version"]), ("npm", ["--version"])):
        executable = shutil.which(tool) or shutil.which(f"{tool}.cmd")
        if not executable:
            info[tool] = "NOT FOUND"
            logger.error(f"{tool} not found on PATH.", file=tool)
            continue
        stdout, stderr, returncode, _ = run_command([executable, *args], logger, cwd=repo_path)
        info[tool] = (stdout or stderr).strip() if returncode == 0 else f"ERROR ({returncode})"

    npx = resolve_npx(repo_path)
    stdout, stderr, returncode, _ = run_command([npx, "vitest", "--version"], logger, cwd=repo_path)
    info["vitest"] = (stdout or stderr).strip() if returncode == 0 else "NOT FOUND"
    info["@vitest/coverage-v8"] = read_installed_package_version(repo_path, "@vitest/coverage-v8")
    info["vitest_package"] = read_installed_package_version(repo_path, "vitest")
    return info


def build_vitest_command(repo_path: Path, config_path: Path | None) -> list[str]:
    package_json = repo_path / "package.json"
    if package_json.exists():
        try:
            scripts = json.loads(package_json.read_text(encoding="utf-8")).get("scripts") or {}
            if "coverage" in scripts:
                npm = resolve_npm(repo_path)
                return [npm, "run", "coverage"]
        except json.JSONDecodeError:
            pass

    npx = resolve_npx(repo_path)
    command = [npx, "vitest", "run", "--coverage"]
    if config_path is not None:
        command.extend(["--config", str(config_path.resolve())])
    return command


def execute_vitest_coverage(
    repo_path: Path,
    config_path: Path | None,
    logger: NotebookLogger,
) -> dict[str, Any]:
    command = build_vitest_command(repo_path, config_path)
    stdout, stderr, returncode, elapsed_ms = run_command(command, logger, cwd=repo_path)
    console_output = stdout + (("\n" + stderr) if stderr else "")
    if returncode != 0:
        logger.error(
            f"Vitest execution failed with exit code {returncode}: {stderr.strip() or stdout.strip()}",
            file="vitest",
        )
    return {
        "command": " ".join(command),
        "returncode": returncode,
        "elapsed_ms": elapsed_ms,
        "stdout": stdout,
        "stderr": stderr,
        "console_output": console_output,
    }


def locate_coverage_output_dir(repo_path: Path, config_path: Path | None, raw_dir: Path) -> Path | None:
    candidates: list[Path] = []
    if config_path is not None and config_path.exists():
        reports_dir = _parse_reports_directory(config_path.read_text(encoding="utf-8", errors="replace"))
        if reports_dir:
            configured = Path(reports_dir)
            if not configured.is_absolute():
                if config_path.parent.name == "temp":
                    candidates.append(configured if configured.is_absolute() else raw_dir / "coverage")
                else:
                    candidates.append((repo_path / configured).resolve())
            else:
                candidates.append(configured)

    candidates.extend(
        [
            raw_dir / "coverage",
            repo_path / "artifacts" / "training" / "coverage",
            repo_path / "coverage",
        ]
    )

    for candidate in candidates:
        summary = candidate / "coverage-summary.json"
        if summary.exists():
            return candidate.resolve()

    for summary in repo_path.rglob("coverage-summary.json"):
        if "node_modules" in summary.parts:
            continue
        return summary.parent.resolve()
    return None


def copy_file_verbatim(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree_verbatim(source_dir: Path, destination_dir: Path) -> list[str]:
    copied: list[str] = []
    if not source_dir.exists():
        return copied
    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(source_dir)
        target = destination_dir / relative
        copy_file_verbatim(path, target)
        copied.append(str(target))
    return copied


def preserve_raw_artifacts(
    coverage_dir: Path | None,
    raw_dir: Path,
    execution: dict[str, Any],
    environment: dict[str, str],
) -> dict[str, Any]:
    saved: dict[str, Any] = {"files": [], "coverage_dir": None}

    stdout_path = raw_dir / "vitest-stdout.txt"
    stderr_path = raw_dir / "vitest-stderr.txt"
    console_path = raw_dir / "vitest-console.log"
    stdout_path.write_text(execution.get("stdout", ""), encoding="utf-8")
    stderr_path.write_text(execution.get("stderr", ""), encoding="utf-8")
    console_path.write_text(execution.get("console_output", ""), encoding="utf-8")
    saved["files"].extend([str(stdout_path), str(stderr_path), str(console_path)])

    metadata = {
        "command": execution.get("command", ""),
        "returncode": execution.get("returncode"),
        "elapsed_ms": execution.get("elapsed_ms"),
        "node_version": environment.get("node", ""),
        "npm_version": environment.get("npm", ""),
        "vitest_version": environment.get("vitest", environment.get("vitest_package", "")),
        "coverage_v8_version": environment.get("@vitest/coverage-v8", ""),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path = raw_dir / "execution-metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    saved["files"].append(str(metadata_path))
    saved["execution_metadata"] = metadata

    if coverage_dir is None:
        return saved

    raw_coverage_dir = raw_dir / "coverage"
    copied = copy_tree_verbatim(coverage_dir, raw_coverage_dir)
    saved["coverage_dir"] = str(raw_coverage_dir)
    saved["files"].extend(copied)

    for name in ("coverage-summary.json", "coverage-final.json", "lcov.info"):
        source = coverage_dir / name
        if source.exists():
            target = raw_dir / name
            copy_file_verbatim(source, target)
            saved["files"].append(str(target))

    lcov_report = coverage_dir / "lcov-report"
    if lcov_report.exists():
        copied_lcov = copy_tree_verbatim(lcov_report, raw_dir / "lcov-report")
        saved["files"].extend(copied_lcov)

    return saved


def require_coverage_artifacts(raw_dir: Path, logger: NotebookLogger) -> dict[str, Path]:
    summary = raw_dir / "coverage-summary.json"
    final = raw_dir / "coverage-final.json"
    missing = [path.name for path in (summary, final) if not path.exists()]
    if missing:
        message = (
            "Coverage artifacts were not generated. Missing required files: "
            + ", ".join(missing)
            + ". Ensure Vitest coverage completed successfully."
        )
        logger.error(message, file=str(raw_dir))
        raise FileNotFoundError(message)
    return {"coverage-summary.json": summary, "coverage-final.json": final}


def read_raw_json_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_coverage_summary(summary_path: Path) -> dict[str, Any]:
    return json.loads(read_raw_json_text(summary_path))


def _total_section(summary: dict[str, Any]) -> dict[str, Any]:
    total = summary.get("total")
    if not isinstance(total, dict):
        raise ValueError("coverage-summary.json is missing a 'total' object.")
    return total


def extract_coverage_metrics(summary_path: Path) -> pd.DataFrame:
    summary = load_coverage_summary(summary_path)
    total = _total_section(summary)
    branches = total.get("branches") or {}
    functions = total.get("functions") or {}
    lines = total.get("lines") or {}
    statements = total.get("statements") or {}

    branch_total = branches.get("total")
    branch_covered = branches.get("covered")
    branch_pct = branches.get("pct")
    uncovered = None
    if isinstance(branch_total, (int, float)) and isinstance(branch_covered, (int, float)):
        uncovered = branch_total - branch_covered

    rows = [
        ("Total Branches", "total.branches.total", branch_total),
        ("Covered Branches", "total.branches.covered", branch_covered),
        ("Uncovered Branches", "total.branches.total - total.branches.covered", uncovered),
        ("Branch Coverage %", "total.branches.pct", branch_pct),
        ("Functions Covered", "total.functions.covered", functions.get("covered")),
        ("Functions Total", "total.functions.total", functions.get("total")),
        ("Lines Covered", "total.lines.covered", lines.get("covered")),
        ("Lines Total", "total.lines.total", lines.get("total")),
        ("Statements Covered", "total.statements.covered", statements.get("covered")),
        ("Statements Total", "total.statements.total", statements.get("total")),
        ("Coverage Summary", "total", json.dumps(total, sort_keys=True)),
    ]
    return pd.DataFrame(rows, columns=COVERAGE_METRIC_COLUMNS)


def _summary_contains_path_coverage_field(summary: dict[str, Any]) -> tuple[bool, str]:
    serialized = json.dumps(summary)
    for field in PATH_COVERAGE_FIELDS:
        if field in serialized:
            return True, field
    return False, ""


def validate_path_coverage_metric(summary_path: Path) -> dict[str, str]:
    summary = load_coverage_summary(summary_path)
    has_path_field, matched_field = _summary_contains_path_coverage_field(summary)
    total = _total_section(summary)
    branches = total.get("branches") or {}

    if has_path_field:
        return {
            "path_coverage_available": "YES",
            "path_coverage_statement": f"Path coverage evidence found at field: {matched_field}",
            "branch_coverage_note": (
                "Vitest also exposes branch coverage through V8 instrumentation at total.branches."
            ),
            "metric_available": "YES",
            "evidence": matched_field,
        }

    branch_evidence = (
        "total.branches.{total,covered,pct}="
        f"{branches.get('total')},{branches.get('covered')},{branches.get('pct')}"
    )
    return {
        "path_coverage_available": "NO",
        "path_coverage_statement": "Path Coverage cannot be directly measured by this tool.",
        "branch_coverage_note": (
            "Vitest + @vitest/coverage-v8 exposes Branch Coverage via V8 instrumentation "
            f"({branch_evidence}). Branch coverage counts decision outcomes, not all distinct execution paths."
        ),
        "metric_available": "NO",
        "evidence": branch_evidence,
    }


def build_final_report_table(path_validation: dict[str, str]) -> pd.DataFrame:
    row = {
        "Technique": "Control Flow Testing",
        "Classification": "Path Coverage",
        "Metric": "Path Detection Testing",
        "Definition": METRIC_DEFINITION,
        "Tool Used": "Vitest + @vitest/coverage-v8",
        "Raw Output File": "coverage-summary.json; coverage-final.json",
        "Metric Available": path_validation["metric_available"],
        "Evidence": path_validation["evidence"],
    }
    return pd.DataFrame([row], columns=FINAL_REPORT_COLUMNS)


def render_final_report_markdown(report_df: pd.DataFrame, path_validation: dict[str, str]) -> str:
    row = report_df.iloc[0]
    lines = [
        "# Vitest Path Coverage Validation Report",
        "",
        "| Field | Value |",
        "| --- | --- |",
    ]
    for column in FINAL_REPORT_COLUMNS:
        lines.append(f"| {column} | {row[column]} |")
    lines.extend(
        [
            "",
            "## Path Coverage Assessment",
            "",
            path_validation["path_coverage_statement"],
            "",
            path_validation["branch_coverage_note"],
            "",
        ]
    )
    return "\n".join(lines)


def build_output_json(
    repo_path: Path,
    repo_validation: dict[str, Any],
    environment: dict[str, str],
    install_result: dict[str, Any],
    config_info: dict[str, str],
    execution: dict[str, Any],
    metrics_payload: dict[str, Any],
    path_validation: dict[str, str],
    report_df: pd.DataFrame,
    artifact_paths: dict[str, Path],
    raw_dir: Path,
    elapsed_ms: float,
) -> dict[str, Any]:
    report_row = report_df.iloc[0].to_dict()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": {
            "name": repo_validation.get("repository_name", repo_path.name),
            "local_path": str(repo_path.resolve()),
            "package_manager": PACKAGE_MANAGER,
            "programming_language": PROGRAMMING_LANGUAGE,
            "package_json_present": repo_validation.get("package.json", False),
            "tsconfig_json_present": repo_validation.get("tsconfig.json", False),
        },
        "taxonomy": {
            "technique": "Control Flow Testing",
            "classification": "Path Coverage",
            "metric": "Path Detection Testing",
            "kpi": "Path Coverage %",
            "definition": METRIC_DEFINITION,
            "tool_used": "Vitest + @vitest/coverage-v8",
        },
        "environment": environment,
        "vitest_configuration": config_info,
        "pipeline": {
            "pipeline_success": execution.get("returncode") == 0,
            "elapsed_ms": round(elapsed_ms, 2),
            "install_command": install_result.get("command", ""),
            "install_returncode": install_result.get("returncode"),
            "install_elapsed_ms": install_result.get("elapsed_ms"),
            "test_command": execution.get("command", ""),
            "test_returncode": execution.get("returncode"),
            "test_elapsed_ms": execution.get("elapsed_ms"),
            "execution_status": "SUCCESS" if execution.get("returncode") == 0 else "FAIL",
        },
        "coverage_metrics": metrics_payload,
        "path_coverage_validation": path_validation,
        "final_metric_report": report_row,
        "raw_artifacts": {
            "coverage_summary_json": str(artifact_paths["coverage-summary.json"].resolve()),
            "coverage_final_json": str(artifact_paths["coverage-final.json"].resolve()),
            "vitest_stdout": str((raw_dir / "vitest-stdout.txt").resolve()),
            "vitest_stderr": str((raw_dir / "vitest-stderr.txt").resolve()),
            "vitest_console_log": str((raw_dir / "vitest-console.log").resolve()),
            "execution_metadata_json": str((raw_dir / "execution-metadata.json").resolve()),
        },
    }


def save_output_json(output_path: Path, payload: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_pipeline(
    repo_path: Path,
    metric_root: Path,
    logger: NotebookLogger | None = None,
) -> dict[str, Any]:
    logger = logger or NotebookLogger(metric_root / "artifacts" / "reports" / "error_log.txt")
    artifact_dirs = ensure_artifact_dirs(metric_root)
    raw_dir = artifact_dirs["raw"]
    parsed_dir = artifact_dirs["parsed"]
    reports_dir = artifact_dirs["reports"]
    started = time.perf_counter()

    repo_validation = validate_repository_layout(repo_path, logger)
    if not repo_validation["repository_valid"]:
        raise RuntimeError("Repository validation failed.")

    environment = collect_environment_info(repo_path, logger)
    env_df = pd.DataFrame([environment])
    env_df.to_csv(parsed_dir / "environment_info.csv", index=False)
    (parsed_dir / "environment_info.json").write_text(json.dumps(environment, indent=2), encoding="utf-8")

    install_result = install_project_dependencies(repo_path, logger)
    if install_result["returncode"] != 0:
        raise RuntimeError("npm install failed.")

    vitest_packages_df = install_vitest_packages(repo_path, logger)
    vitest_packages_df.to_csv(parsed_dir / "vitest_packages.csv", index=False)
    if (vitest_packages_df["status"] != "OK").any():
        raise RuntimeError("Required Vitest packages are not installed.")

    repo_config = detect_vitest_config(repo_path)
    temp_config: Path | None = None
    if repo_config is None:
        temp_config = create_temp_vitest_config(artifact_dirs["temp"], raw_dir / "coverage")
        config_used = temp_config
        config_source = "temporary notebook config"
    else:
        config_used = repo_config
        config_source = "repository config"

    config_info = {
        "repository_config": str(repo_config) if repo_config else "",
        "config_used": str(config_used),
        "config_source": config_source,
    }
    (parsed_dir / "vitest_configuration.json").write_text(json.dumps(config_info, indent=2), encoding="utf-8")

    execution = execute_vitest_coverage(repo_path, None if repo_config else temp_config, logger)
    if execution["returncode"] != 0:
        raise RuntimeError("Vitest test execution failed.")

    coverage_dir = locate_coverage_output_dir(repo_path, config_used, raw_dir)
    saved = preserve_raw_artifacts(coverage_dir, raw_dir, execution, environment)
    artifact_paths = require_coverage_artifacts(raw_dir, logger)

    summary_raw_text = read_raw_json_text(artifact_paths["coverage-summary.json"])
    final_raw_text = read_raw_json_text(artifact_paths["coverage-final.json"])

    metrics_df = extract_coverage_metrics(artifact_paths["coverage-summary.json"])
    metrics_df.to_csv(parsed_dir / "coverage_metrics.csv", index=False)
    metrics_payload = {
        row["Metric"]: {"json_field": row["JSON Field"], "value": row["Value"]}
        for _, row in metrics_df.iterrows()
    }
    (parsed_dir / "coverage_metrics.json").write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")

    path_validation = validate_path_coverage_metric(artifact_paths["coverage-summary.json"])
    (parsed_dir / "path_coverage_validation.json").write_text(json.dumps(path_validation, indent=2), encoding="utf-8")

    report_df = build_final_report_table(path_validation)
    report_df.to_csv(reports_dir / "final_metric_report.csv", index=False)
    markdown_report = render_final_report_markdown(report_df, path_validation)
    (reports_dir / "final_metric_report.md").write_text(markdown_report, encoding="utf-8")

    output_json_path = reports_dir / "output.json"
    output_payload = build_output_json(
        repo_path=repo_path,
        repo_validation=repo_validation,
        environment=environment,
        install_result=install_result,
        config_info=config_info,
        execution=execution,
        metrics_payload=metrics_payload,
        path_validation=path_validation,
        report_df=report_df,
        artifact_paths=artifact_paths,
        raw_dir=raw_dir,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )
    save_output_json(output_json_path, output_payload)

    logger.write_errors()
    elapsed_ms = (time.perf_counter() - started) * 1000

    return {
        "pipeline_success": True,
        "repository": str(repo_path),
        "config_source": config_source,
        "execution": execution,
        "environment": environment,
        "saved_raw_files": saved["files"],
        "coverage_summary_raw": summary_raw_text,
        "coverage_final_raw": final_raw_text,
        "metrics_df": metrics_df,
        "path_validation": path_validation,
        "report_markdown": markdown_report,
        "output_json": str(output_json_path),
        "output_payload": output_payload,
        "elapsed_ms": round(elapsed_ms, 2),
        "artifact_paths": {key: str(value) for key, value in artifact_paths.items()},
    }
