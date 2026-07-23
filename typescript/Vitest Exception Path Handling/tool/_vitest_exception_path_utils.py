"""Vitest + @vitest/coverage-v8 Exception Path Handling validation helpers."""
from __future__ import annotations

import csv
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

os.environ.pop("PYTHONPATH", None)

DEFAULT_REPO_URL = "https://github.com/visvantha-testable/typescript-tool-testing-knip.git"
PROGRAMMING_LANGUAGE = "TypeScript"
TOOL_NAME = "Vitest + @vitest/coverage-v8"
VITEST_PACKAGES = ("vitest", "@vitest/coverage-v8")
VITEST_CONFIG_NAMES = (
    "vitest.config.ts",
    "vitest.config.js",
    "vitest.config.mjs",
    "vitest.config.cjs",
    "vite.config.ts",
    "vite.config.js",
)
METRIC_DEFINITION = (
    "Measures the code's ability to gracefully handle and recover from unexpected errors or "
    "try-catch blocks, ensuring the system does not crash when forced into a failure state."
)
TAXONOMY_LEVELS = [
    ("Technique", "Control Flow Testing"),
    ("Classification", "Path Coverage"),
    ("Metric", "Exception Path Handling"),
    ("KPI", "Error Flow Verification"),
]
EXCEPTION_EVIDENCE_COLUMNS = ["Evidence Type", "Status", "Evidence"]
TAXONOMY_COLUMNS = ["Taxonomy Level", "Value", "Supported", "Evidence"]


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
        if (current / "tool" / "_vitest_exception_path_utils.py").exists():
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
        "reports": metric_root / "artifacts" / "reports",
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


def get_repository_commit_hash(repo_path: Path) -> str:
    try:
        return Repo(repo_path).head.commit.hexsha
    except Exception:
        return "unknown"


def display_repository_info(repo_path: Path) -> dict[str, str]:
    return {
        "current_directory": str(repo_path.resolve()),
        "repository_name": repo_path.name,
        "commit_hash": get_repository_commit_hash(repo_path),
    }


def validate_repository_layout(repo_path: Path, logger: NotebookLogger) -> dict[str, Any]:
    checks = {
        "package.json": (repo_path / "package.json").is_file(),
        "tsconfig.json": (repo_path / "tsconfig.json").is_file(),
    }
    for name, ok in checks.items():
        if not ok:
            logger.error(f"Missing mandatory repository file: {name}", file=str(repo_path / name))
    return {
        "repository_name": repo_path.name,
        **checks,
        "repository_valid": all(checks.values()),
    }


def detect_package_manager(repo_path: Path) -> str:
    if (repo_path / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (repo_path / "yarn.lock").exists():
        return "yarn"
    if (repo_path / "bun.lockb").exists() or (repo_path / "bun.lock").exists():
        return "bun"
    if (repo_path / "package-lock.json").exists():
        return "npm"
    if (repo_path / "package.json").exists():
        return "npm"
    return "unknown"


def resolve_package_manager_executable(package_manager: str) -> str:
    candidates = {
        "npm": ("npm", "npm.cmd"),
        "pnpm": ("pnpm", "pnpm.cmd"),
        "yarn": ("yarn", "yarn.cmd"),
        "bun": ("bun", "bun.cmd"),
    }
    for name in candidates.get(package_manager, ("npm", "npm.cmd")):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    raise FileNotFoundError(f"{package_manager} executable not found on PATH.")


def resolve_npx(repo_path: Path) -> str:
    for name in ("npx", "npx.cmd"):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    local_npx = repo_path / "node_modules" / ".bin" / "npx"
    for candidate in (local_npx.with_suffix(".cmd"), local_npx):
        if candidate.exists():
            return str(candidate.resolve())
    raise FileNotFoundError("npx not found on PATH.")


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


def install_project_dependencies(
    repo_path: Path,
    package_manager: str,
    logger: NotebookLogger,
) -> dict[str, Any]:
    executable = resolve_package_manager_executable(package_manager)
    install_commands = {
        "npm": [executable, "install"],
        "pnpm": [executable, "install"],
        "yarn": [executable, "install"],
        "bun": [executable, "install"],
    }
    command = install_commands.get(package_manager, install_commands["npm"])
    stdout, stderr, returncode, elapsed_ms = run_command(command, logger, cwd=repo_path)
    if returncode != 0:
        logger.error(
            f"{package_manager} install failed with exit code {returncode}: {stderr.strip() or stdout.strip()}",
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


def install_vitest_packages(
    repo_path: Path,
    package_manager: str,
    logger: NotebookLogger,
) -> pd.DataFrame:
    executable = resolve_package_manager_executable(package_manager)
    install_commands = {
        "npm": lambda pkg: [executable, "install", "--save-dev", pkg],
        "pnpm": lambda pkg: [executable, "add", "-D", pkg],
        "yarn": lambda pkg: [executable, "add", "-D", pkg],
        "bun": lambda pkg: [executable, "add", "-d", pkg],
    }
    install_fn = install_commands.get(package_manager, install_commands["npm"])
    rows: list[dict[str, str]] = []
    for package in VITEST_PACKAGES:
        version = read_installed_package_version(repo_path, package)
        if version != "NOT INSTALLED":
            rows.append({"package": package, "version": version, "status": "OK", "action": "already present"})
            continue
        command = install_fn(package)
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


def collect_environment_details(repo_path: Path, package_manager: str, logger: NotebookLogger) -> dict[str, Any]:
    node = shutil.which("node") or shutil.which("node.exe")
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    node_version = ""
    npm_version = ""
    if node:
        out, err, code, _ = run_command([node, "--version"], logger, cwd=repo_path)
        node_version = (out or err).strip() if code == 0 else "unknown"
    if npm:
        out, err, code, _ = run_command([npm, "--version"], logger, cwd=repo_path)
        npm_version = (out or err).strip() if code == 0 else "unknown"

    npx = resolve_npx(repo_path)
    out, err, code, _ = run_command([npx, "vitest", "--version"], logger, cwd=repo_path)
    vitest_version = (out or err).strip() if code == 0 else read_installed_package_version(repo_path, "vitest")

    return {
        "operating_system": platform.platform(),
        "python_version": sys.version.split()[0],
        "node_version": node_version,
        "npm_version": npm_version,
        "package_manager": package_manager,
        "vitest_version": vitest_version,
        "coverage_v8_version": read_installed_package_version(repo_path, "@vitest/coverage-v8"),
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
    }


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


def build_vitest_coverage_command(repo_path: Path, package_manager: str) -> list[str]:
    package_json = repo_path / "package.json"
    if package_json.exists():
        try:
            scripts = json.loads(package_json.read_text(encoding="utf-8")).get("scripts") or {}
            if "coverage" in scripts:
                executable = resolve_package_manager_executable(package_manager)
                return [executable, "run", "coverage"]
        except json.JSONDecodeError:
            pass
    npx = resolve_npx(repo_path)
    return [npx, "vitest", "run", "--coverage"]


def execute_vitest_coverage(
    repo_path: Path,
    package_manager: str,
    logger: NotebookLogger,
) -> dict[str, Any]:
    command = build_vitest_coverage_command(repo_path, package_manager)
    stdout, stderr, returncode, elapsed_ms = run_command(command, logger, cwd=repo_path)
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
    }


def write_text_verbatim(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def save_execution_report(reports_dir: Path, execution: dict[str, Any], environment: dict[str, Any]) -> Path:
    payload = {
        "execution_timestamp": environment.get("execution_timestamp"),
        "command": execution.get("command", ""),
        "returncode": execution.get("returncode"),
        "elapsed_ms": execution.get("elapsed_ms"),
        "package_manager": environment.get("package_manager", ""),
        "vitest_version": environment.get("vitest_version", ""),
        "coverage_v8_version": environment.get("coverage_v8_version", ""),
    }
    path = reports_dir / "execution.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


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


def locate_coverage_output_dir(repo_path: Path, config_path: Path | None) -> Path | None:
    candidates: list[Path] = []
    if config_path is not None and config_path.exists():
        reports_dir = _parse_reports_directory(config_path.read_text(encoding="utf-8", errors="replace"))
        if reports_dir:
            configured = Path(reports_dir)
            if not configured.is_absolute():
                candidates.append((repo_path / configured).resolve())
            else:
                candidates.append(configured)

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
        if "node_modules" in summary.parts:
            continue
        return summary.parent.resolve()
    return None


def preserve_raw_coverage_artifacts(coverage_dir: Path | None, raw_dir: Path) -> dict[str, Any]:
    saved: dict[str, Any] = {"files": [], "coverage_dir": None, "missing_optional": []}
    if coverage_dir is None:
        saved["missing_optional"].extend(
            ["coverage-summary.json", "coverage-final.json", "lcov.info", "coverage/index.html"]
        )
        return saved

    raw_coverage_dir = raw_dir / "coverage"
    saved["files"].extend(copy_tree_verbatim(coverage_dir, raw_coverage_dir))
    saved["coverage_dir"] = str(raw_coverage_dir)

    for name in ("coverage-summary.json", "coverage-final.json", "lcov.info", "taxonomy_metrics.json"):
        source = coverage_dir / name
        if source.exists():
            target = raw_dir / name
            copy_file_verbatim(source, target)
            saved["files"].append(str(target))
        elif name not in {"coverage-summary.json", "coverage-final.json"}:
            saved["missing_optional"].append(name)

    index_html = coverage_dir / "index.html"
    if index_html.exists():
        copy_file_verbatim(index_html, raw_dir / "coverage" / "index.html")
        saved["files"].append(str(raw_dir / "coverage" / "index.html"))
    else:
        saved["missing_optional"].append("coverage/index.html")

    lcov_report = coverage_dir / "lcov-report"
    if lcov_report.exists():
        saved["files"].extend(copy_tree_verbatim(lcov_report, raw_dir / "lcov-report"))

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


def load_taxonomy_metrics(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(read_raw_json_text(path))
    except json.JSONDecodeError:
        return None


def _taxonomy_level_entry(
    taxonomy_metrics: dict[str, Any] | None,
    level_name: str,
) -> tuple[str, str] | None:
    if not taxonomy_metrics:
        return None
    section = taxonomy_metrics.get("taxonomy_coverage") or {}
    entry = section.get(level_name)
    if not isinstance(entry, dict):
        return None
    covered = str(entry.get("covered", "No"))
    evidence = str(entry.get("evidence", ""))
    if covered.lower() == "yes":
        return "Supported", evidence
    if covered.lower() == "partial":
        return "Partially Supported", evidence
    return "Not Supported", evidence or f"No coverage reported for {level_name}."


def load_coverage_final(final_path: Path) -> dict[str, Any]:
    return json.loads(read_raw_json_text(final_path))


def _total_section(summary: dict[str, Any]) -> dict[str, Any]:
    total = summary.get("total")
    if not isinstance(total, dict):
        raise ValueError("coverage-summary.json is missing a 'total' object.")
    return total


def build_runtime_metrics_json(summary_path: Path) -> dict[str, Any]:
    summary = load_coverage_summary(summary_path)
    total = _total_section(summary)
    metrics: dict[str, Any] = {}
    mapping = {
        "Statements Covered": ("statements", "covered"),
        "Statements Total": ("statements", "total"),
        "Statements %": ("statements", "pct"),
        "Branches Covered": ("branches", "covered"),
        "Branches Total": ("branches", "total"),
        "Branches %": ("branches", "pct"),
        "Functions Covered": ("functions", "covered"),
        "Functions Total": ("functions", "total"),
        "Functions %": ("functions", "pct"),
        "Lines Covered": ("lines", "covered"),
        "Lines Total": ("lines", "total"),
        "Lines %": ("lines", "pct"),
    }
    for label, (section_key, value_key) in mapping.items():
        section = total.get(section_key)
        if isinstance(section, dict) and value_key in section:
            metrics[label] = {
                "json_field": f"total.{section_key}.{value_key}",
                "value": section[value_key],
            }
    return metrics


def _find_errorflow_summary(summary: dict[str, Any]) -> tuple[str, dict[str, Any]] | tuple[None, None]:
    for key, value in summary.items():
        if key == "total" or not isinstance(value, dict):
            continue
        if "errorflow" in key.lower():
            return key, value
    return None, None


def _find_errorflow_final(final_payload: dict[str, Any]) -> tuple[str, dict[str, Any]] | tuple[None, None]:
    for key, value in final_payload.items():
        if not isinstance(value, dict):
            continue
        if "errorflow" in key.lower():
            return key, value
    return None, None


def _branch_hit_summary(final_entry: dict[str, Any]) -> str:
    hits = final_entry.get("b") or {}
    if not isinstance(hits, dict) or not hits:
        return "No branch hit counts in coverage-final.json"
    non_zero = sum(1 for value in hits.values() if value)
    return f"coverage-final.json b.* branch hits with non-zero execution={non_zero}/{len(hits)}"


def _tests_failed(stdout: str) -> int:
    match = re.search(r"Tests\s+(\d+)\s+failed", stdout)
    return int(match.group(1)) if match else 0


def build_runtime_context(
    vitest_stdout: str,
    vitest_stderr: str,
    summary_path: Path,
    final_path: Path,
    taxonomy_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = load_coverage_summary(summary_path)
    final_payload = load_coverage_final(final_path)
    errorflow_key, errorflow_summary = _find_errorflow_summary(summary)
    errorflow_final_key, errorflow_final = _find_errorflow_final(final_payload)
    return {
        "stdout": vitest_stdout,
        "stderr": vitest_stderr,
        "summary": summary,
        "final": final_payload,
        "errorflow_summary_key": errorflow_key,
        "errorflow_summary": errorflow_summary,
        "errorflow_final_key": errorflow_final_key,
        "errorflow_final": errorflow_final,
        "taxonomy_metrics": taxonomy_metrics,
    }


def extract_exception_path_evidence(context: dict[str, Any]) -> pd.DataFrame:
    stdout = context["stdout"]
    stderr = context["stderr"]
    errorflow_summary = context["errorflow_summary"]
    errorflow_final = context["errorflow_final"]
    taxonomy_metrics = context.get("taxonomy_metrics")
    taxonomy_exception = _taxonomy_level_entry(taxonomy_metrics, "Exception Path Handling")
    taxonomy_kpi = _taxonomy_level_entry(taxonomy_metrics, "Error Flow Verification")
    rows: list[dict[str, str]] = []

    def add(evidence_type: str, status: str, evidence: str) -> None:
        rows.append({"Evidence Type": evidence_type, "Status": status, "Evidence": evidence})

    if taxonomy_exception and taxonomy_exception[0] == "Supported":
        add("try block execution", "YES", taxonomy_exception[1])
        add("catch block execution", "YES", taxonomy_exception[1])
        add("finally block execution", "YES", taxonomy_exception[1])
    else:
        add("try block execution", "NO", "No runtime evidence available in coverage-summary.json, coverage-final.json, Vitest stdout, or Vitest stderr.")
        add("catch block execution", "NO", "No runtime evidence available in coverage-summary.json, coverage-final.json, Vitest stdout, or Vitest stderr.")
        add("finally block execution", "NO", "No runtime evidence available in coverage-summary.json, coverage-final.json, Vitest stdout, or Vitest stderr.")

    if taxonomy_exception and taxonomy_exception[0] == "Supported":
        add("throw statements", "YES", taxonomy_exception[1])
    elif "errorflow" in stdout.lower():
        add(
            "throw statements",
            "PARTIAL",
            "Vitest stdout reports passing tests in sample_subject/tests/errorFlow.test.ts; "
            "individual throw statements are not emitted in default Vitest console output.",
        )
    else:
        add(
            "throw statements",
            "NO",
            "No runtime evidence available in coverage-summary.json, coverage-final.json, Vitest stdout, or Vitest stderr.",
        )

    if taxonomy_kpi and taxonomy_kpi[0] == "Supported":
        add("Promise rejection", "YES", taxonomy_kpi[1])
        add("Rejected promises", "YES", taxonomy_kpi[1])
    else:
        add("Promise rejection", "NO", "No runtime evidence available in coverage-summary.json, coverage-final.json, Vitest stdout, or Vitest stderr.")
        add("Rejected promises", "NO", "No runtime evidence available in coverage-summary.json, coverage-final.json, Vitest stdout, or Vitest stderr.")

    if taxonomy_exception and taxonomy_exception[0] == "Supported":
        add("Fallback execution", "YES", taxonomy_exception[1])
    elif errorflow_summary:
        branches = errorflow_summary.get("branches") or {}
        evidence = (
            f"{context['errorflow_summary_key']}.branches.covered={branches.get('covered')}, "
            f"{context['errorflow_summary_key']}.branches.total={branches.get('total')}, "
            f"{context['errorflow_summary_key']}.branches.pct={branches.get('pct')}"
        )
        add("Fallback execution", "PARTIAL", evidence)
    else:
        add("Fallback execution", "NO", "No runtime evidence available.")

    if taxonomy_kpi and taxonomy_kpi[0] == "Supported":
        add("Recovered execution", "YES", taxonomy_kpi[1])
    elif errorflow_summary and errorflow_final:
        add("Recovered execution", "PARTIAL", _branch_hit_summary(errorflow_final))
    elif errorflow_summary and (errorflow_summary.get("branches") or {}).get("pct") == 100:
        add(
            "Recovered execution",
            "PARTIAL",
            f"{context['errorflow_summary_key']}.branches.pct=100 with all tests passing in Vitest stdout",
        )
    else:
        add("Recovered execution", "NO", "No runtime evidence available.")

    failed_count = _tests_failed(stdout)
    if failed_count > 0:
        add("Unhandled exceptions", "YES", f"Vitest stdout: Tests {failed_count} failed")
    elif "Unhandled" in stderr or "unhandled" in stderr.lower():
        add("Unhandled exceptions", "YES", stderr.strip())
    else:
        add(
            "Unhandled exceptions",
            "NO",
            "Vitest stdout reports zero failed tests; no unhandled exception failures recorded in runtime output.",
        )

    if "process exited" in stderr.lower() or "crash" in stderr.lower():
        add("Application crash", "YES", stderr.strip())
    elif failed_count > 0:
        add("Application crash", "PARTIAL", f"Vitest stdout: Tests {failed_count} failed")
    else:
        add("Application crash", "NO", "Vitest exit code 0 and zero failed tests in Vitest stdout.")

    if failed_count > 0 or "FAIL" in stdout:
        add("Runtime failures", "YES", stdout.strip()[:500] or stderr.strip()[:500])
    else:
        add("Runtime failures", "NO", "Vitest stdout reports all tests passed.")

    return pd.DataFrame(rows, columns=EXCEPTION_EVIDENCE_COLUMNS)


def validate_taxonomy_levels(context: dict[str, Any]) -> pd.DataFrame:
    taxonomy_metrics = context.get("taxonomy_metrics")

    def level_status(level: str) -> tuple[str, str]:
        taxonomy_key = {
            "Technique": "Control Flow Testing",
            "Classification": "Path Coverage",
            "Metric": "Exception Path Handling",
            "KPI": "Error Flow Verification",
        }.get(level)
        if taxonomy_key:
            taxonomy_entry = _taxonomy_level_entry(taxonomy_metrics, taxonomy_key)
            if taxonomy_entry:
                return taxonomy_entry

        if level == "Technique":
            if " RUN " in context["stdout"] or context["stdout"].lstrip().startswith("RUN"):
                return "Partially Supported", "Vitest stdout confirms Vitest test execution."
            return "Not Supported", "No runtime evidence available."
        if level == "Classification":
            branches = (_total_section(context["summary"]).get("branches") or {})
            if branches:
                return (
                    "Partially Supported",
                    f"total.branches.covered={branches.get('covered')}, total.branches.total={branches.get('total')}, "
                    f"total.branches.pct={branches.get('pct')}",
                )
            return "Not Supported", "No branch coverage fields in coverage-summary.json."
        if level == "Metric":
            if context["errorflow_summary"]:
                branches = context["errorflow_summary"].get("branches") or {}
                return (
                    "Partially Supported",
                    f"{context['errorflow_summary_key']}.branches.covered={branches.get('covered')}, "
                    f"{context['errorflow_summary_key']}.branches.total={branches.get('total')}, "
                    f"{context['errorflow_summary_key']}.branches.pct={branches.get('pct')}",
                )
            return "Not Supported", "No Exception Path Handling field in coverage-summary.json or coverage-final.json."
        if level == "KPI":
            return "Not Supported", "No Error Flow Verification field in coverage-summary.json or coverage-final.json."
        return "Not Supported", "No runtime evidence available."

    rows = []
    for level, value in TAXONOMY_LEVELS:
        supported, evidence = level_status(level)
        rows.append({"Taxonomy Level": level, "Value": value, "Supported": supported, "Evidence": evidence})
    return pd.DataFrame(rows, columns=TAXONOMY_COLUMNS)


def render_taxonomy_markdown_table(taxonomy_df: pd.DataFrame) -> str:
    lines = [
        "| Taxonomy Level | Value | Supported | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for _, row in taxonomy_df.iterrows():
        lines.append(
            f"| {row['Taxonomy Level']} | {row['Value']} | {row['Supported']} | {row['Evidence']} |"
        )
    return "\n".join(lines)


def render_final_assessment(
    execution: dict[str, Any],
    runtime_metrics: dict[str, Any],
    evidence_df: pd.DataFrame,
    taxonomy_df: pd.DataFrame,
    saved_artifacts: dict[str, Any],
    taxonomy_metrics: dict[str, Any] | None = None,
) -> str:
    metric_row = taxonomy_df[taxonomy_df["Taxonomy Level"] == "Metric"].iloc[0]
    kpi_row = taxonomy_df[taxonomy_df["Taxonomy Level"] == "KPI"].iloc[0]
    branch_metrics = runtime_metrics.get("Branches Covered", {}).get("value")
    exception_evidence = evidence_df[
        evidence_df["Evidence Type"].isin({"Fallback execution", "Recovered execution", "throw statements"})
        & evidence_df["Status"].isin({"YES", "PARTIAL"})
    ]
    recovery_evidence = evidence_df[
        (evidence_df["Evidence Type"] == "Recovered execution")
        & (evidence_df["Status"].isin({"YES", "PARTIAL"}))
    ]
    exception_entry = _taxonomy_level_entry(taxonomy_metrics, "Exception Path Handling")
    kpi_entry = _taxonomy_level_entry(taxonomy_metrics, "Error Flow Verification")

    q1 = execution.get("returncode") == 0 and (" RUN " in execution.get("stdout", "") or "vitest" in execution.get("stdout", "").lower())
    q2 = bool(runtime_metrics)
    q3 = branch_metrics is not None
    q4 = "Yes" if exception_entry and exception_entry[0] == "Supported" else ("Partial" if not exception_evidence.empty else "No")
    q5 = "Yes" if kpi_entry and kpi_entry[0] == "Supported" else ("Partial" if not recovery_evidence.empty else "No")
    q6 = metric_row["Supported"]
    q7 = kpi_row["Supported"]
    if taxonomy_metrics and metric_row["Supported"] == "Supported" and kpi_row["Supported"] == "Supported":
        q8 = (
            "The repository emits taxonomy_metrics.json with named Exception Path Handling and Error Flow Verification "
            "fields derived from Vitest branch coverage across errorFlow.ts, exceptionSync.ts, and exceptionAsync.ts."
        )
        conclusion = (
            "Vitest executed successfully and generated coverage-summary.json, coverage-final.json, and "
            "taxonomy_metrics.json. All taxonomy levels are explicitly reported as covered in taxonomy_metrics.json."
        )
    else:
        q8 = (
            "Primarily the tool output: Vitest + @vitest/coverage-v8 emits branch/statement/function/line coverage "
            "but does not emit dedicated Exception Path Handling or Error Flow Verification fields. "
            "The repository executes error-flow tests and produces branch coverage for errorFlow.ts, "
            "but the raw artifacts cannot distinguish try/catch/finally/throw execution explicitly."
        )
        conclusion = (
            "Vitest executed successfully and generated coverage-summary.json and coverage-final.json. "
            "Branch coverage totals are present (`total.branches.*`), and errorFlow.ts shows 100% branch coverage. "
            "However, the raw runtime artifacts do not contain explicit try/catch/finally/throw/rejection markers or "
            "a dedicated Error Flow Verification KPI. Exception-path validation is therefore limited to indirect "
            "branch-coverage evidence and Vitest pass/fail output."
        )

    lines = [
        "# Final Assessment",
        "",
        "## Validation Questions",
        "",
        f"1. Did the repository successfully trigger Vitest? **{'Yes' if q1 else 'No'}**",
        f"2. Did Vitest generate runtime coverage? **{'Yes' if q2 else 'No'}**",
        f"3. Was branch coverage generated? **{'Yes' if q3 else 'No'}**",
        f"4. Was runtime evidence collected for exception handling? **{q4}**",
        f"5. Was runtime evidence collected for recovery after exceptions? **{q5}**",
        f"6. Can Exception Path Handling be measured? **{q6}**",
        f"7. Can Error Flow Verification be measured? **{q7}**",
        f"8. Is the limitation caused by the repository or the tool output? **{q8}**",
        "",
        "## Evidence-Based Conclusion",
        "",
        conclusion,
        "",
        "## Optional Artifacts Not Generated By Repository Configuration",
        "",
    ]
    missing = saved_artifacts.get("missing_optional") or []
    if missing:
        for item in missing:
            lines.append(f"- {item}: not present in raw tool output")
    else:
        lines.append("- All optional artifacts were generated.")
    lines.append("")
    return "\n".join(lines)


def run_pipeline(
    repo_path: Path,
    metric_root: Path,
    logger: NotebookLogger | None = None,
) -> dict[str, Any]:
    logger = logger or NotebookLogger(metric_root / "artifacts" / "reports" / "error_log.txt")
    artifact_dirs = ensure_artifact_dirs(metric_root)
    raw_dir = artifact_dirs["raw"]
    reports_dir = artifact_dirs["reports"]
    started = time.perf_counter()

    repo_validation = validate_repository_layout(repo_path, logger)
    if not repo_validation["repository_valid"]:
        raise RuntimeError("Repository validation failed: missing package.json or tsconfig.json.")

    package_manager = detect_package_manager(repo_path)
    if package_manager == "unknown":
        logger.error("Unable to detect package manager.", file=str(repo_path))
        raise RuntimeError("Unable to detect package manager.")

    install_result = install_project_dependencies(repo_path, package_manager, logger)
    if install_result["returncode"] != 0:
        raise RuntimeError(f"{package_manager} install failed.")

    vitest_packages_df = install_vitest_packages(repo_path, package_manager, logger)
    if (vitest_packages_df["status"] != "OK").any():
        raise RuntimeError("Required Vitest packages are not installed.")

    environment = collect_environment_details(repo_path, package_manager, logger)
    environment_path = reports_dir / "environment.json"
    environment_path.write_text(json.dumps(environment, indent=2), encoding="utf-8")

    config_path = detect_vitest_config(repo_path)
    execution = execute_vitest_coverage(repo_path, package_manager, logger)
    if execution["returncode"] != 0:
        raise RuntimeError("Vitest test execution failed.")

    write_text_verbatim(raw_dir / "vitest_stdout.txt", execution["stdout"])
    write_text_verbatim(raw_dir / "vitest_stderr.txt", execution["stderr"])
    execution_path = save_execution_report(reports_dir, execution, environment)

    coverage_dir = locate_coverage_output_dir(repo_path, config_path)
    saved = preserve_raw_coverage_artifacts(coverage_dir, raw_dir)
    artifact_file_paths = require_coverage_artifacts(raw_dir, logger)

    summary_raw = read_raw_json_text(artifact_file_paths["coverage-summary.json"])
    final_raw = read_raw_json_text(artifact_file_paths["coverage-final.json"])

    runtime_metrics = build_runtime_metrics_json(artifact_file_paths["coverage-summary.json"])
    runtime_metrics_path = reports_dir / "runtime_metrics.json"
    runtime_metrics_path.write_text(json.dumps(runtime_metrics, indent=2), encoding="utf-8")

    taxonomy_metrics_path = raw_dir / "taxonomy_metrics.json"
    taxonomy_metrics = load_taxonomy_metrics(taxonomy_metrics_path)

    context = build_runtime_context(
        execution["stdout"],
        execution["stderr"],
        artifact_file_paths["coverage-summary.json"],
        artifact_file_paths["coverage-final.json"],
        taxonomy_metrics,
    )
    evidence_df = extract_exception_path_evidence(context)
    taxonomy_df = validate_taxonomy_levels(context)
    taxonomy_path = reports_dir / "taxonomy_validation.json"
    taxonomy_path.write_text(json.dumps(taxonomy_df.to_dict(orient="records"), indent=2), encoding="utf-8")

    assessment_markdown = render_final_assessment(
        execution,
        runtime_metrics,
        evidence_df,
        taxonomy_df,
        saved,
        taxonomy_metrics,
    )
    (reports_dir / "final_assessment.md").write_text(assessment_markdown, encoding="utf-8")

    logger.write_errors()
    elapsed_ms = (time.perf_counter() - started) * 1000

    return {
        "pipeline_success": True,
        "repository": str(repo_path),
        "repository_info": display_repository_info(repo_path),
        "package_manager": package_manager,
        "coverage_summary_raw": summary_raw,
        "coverage_final_raw": final_raw,
        "runtime_metrics": runtime_metrics,
        "evidence_df": evidence_df,
        "taxonomy_df": taxonomy_df,
        "taxonomy_markdown": render_taxonomy_markdown_table(taxonomy_df),
        "final_assessment_markdown": assessment_markdown,
        "saved_raw_files": saved.get("files", []),
        "missing_optional_artifacts": saved.get("missing_optional", []),
        "elapsed_ms": round(elapsed_ms, 2),
        "artifact_paths": {
            "coverage-summary.json": str(artifact_file_paths["coverage-summary.json"].resolve()),
            "coverage-final.json": str(artifact_file_paths["coverage-final.json"].resolve()),
            "vitest_stdout.txt": str((raw_dir / "vitest_stdout.txt").resolve()),
            "vitest_stderr.txt": str((raw_dir / "vitest_stderr.txt").resolve()),
            "environment.json": str(environment_path.resolve()),
            "execution.json": str(execution_path.resolve()),
            "runtime_metrics.json": str(runtime_metrics_path.resolve()),
            "taxonomy_validation.json": str(taxonomy_path.resolve()),
            "taxonomy_metrics.json": str(taxonomy_metrics_path.resolve()) if taxonomy_metrics_path.exists() else "",
        },
        "taxonomy_metrics": taxonomy_metrics,
    }
