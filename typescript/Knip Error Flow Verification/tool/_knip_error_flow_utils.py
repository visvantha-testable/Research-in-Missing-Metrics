"""Knip Error Flow Verification extraction and validation helpers."""
from __future__ import annotations

import csv
import json
import os
import platform
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

DEFAULT_REPO_URL = "https://github.com/visvantha-testable/typescript-tool-testing-knip.git"
PROGRAMMING_LANGUAGE = "TypeScript"
TOOL_NAME = "Knip"
KNIP_PACKAGE = "knip"
METRIC_DEFINITION = (
    "Measures the code's ability to gracefully handle and recover from unexpected errors or "
    "try-catch blocks, ensuring the system does not crash when forced into a failure state."
)
EXCEPTION_PATH_STATEMENT = (
    "Knip is a static dependency analysis tool and does not execute the application. "
    "Therefore Exception Path Handling and Error Flow Verification cannot be directly measured."
)
PLATFORM_KNIP_JSON_MARKERS = {
    "status",
    "tool",
    "strategy",
    "l5_metric",
    "l5_kpi",
    "error_flow_verification_percent",
    "Exception Path Handling",
}
KNIP_CONFIG_FILENAMES = (
    "knip.config.ts",
    "knip.config.js",
    "knip.config.mjs",
    "knip.config.cjs",
    "knip.ts",
    "knip.js",
    "knip.json",
    "knip.jsonc",
)
ISSUE_FIELD_MAP = {
    "files": "Unused Files",
    "dependencies": "Unused Dependencies",
    "devDependencies": "Unused Dev Dependencies",
    "optionalPeerDependencies": "Unused Optional Peer Dependencies",
    "unlisted": "Unlisted Dependencies",
    "binaries": "Unused Binaries",
    "unresolved": "Unresolved Imports",
    "exports": "Unused Exports",
    "types": "Unused Types",
    "duplicates": "Duplicate Exports",
    "enumMembers": "Unused Enum Members",
    "namespaceMembers": "Unused Class Members",
    "nsExports": "Unused Namespace Exports",
    "nsTypes": "Unused Namespace Types",
    "catalog": "Catalog Issues",
    "cycles": "Circular Dependencies",
}
EXCEPTION_FLOW_KEYWORDS = (
    "exception",
    "error_flow",
    "error flow",
    "try_catch",
    "try-catch",
    "recovery_path",
    "exception_path",
    "Error Flow Verification",
)
TAXONOMY_LEVELS = [
    ("Technique", "Control Flow Testing"),
    ("Classification", "Path Coverage"),
    ("Metric", "Exception Path Handling"),
    ("KPI", "Error Flow Verification"),
]
METRIC_COLUMNS = ["Metric", "JSON Field", "Value"]
TAXONOMY_COLUMNS = ["Taxonomy Level", "Value", "Supported", "Evidence"]
FINAL_REPORT_COLUMNS = [
    "Technique",
    "Classification",
    "Metric",
    "Definition",
    "Tool",
    "Raw Output File",
    "Supported",
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
        if (current / "tool" / "_knip_error_flow_utils.py").exists():
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


def ensure_knip_installed(repo_path: Path, package_manager: str, logger: NotebookLogger) -> dict[str, str]:
    version = read_installed_package_version(repo_path, KNIP_PACKAGE)
    if version != "NOT INSTALLED":
        return {"package": KNIP_PACKAGE, "version": version, "status": "OK", "action": "already present"}

    executable = resolve_package_manager_executable(package_manager)
    install_commands = {
        "npm": [executable, "install", "--save-dev", KNIP_PACKAGE],
        "pnpm": [executable, "add", "-D", KNIP_PACKAGE],
        "yarn": [executable, "add", "-D", KNIP_PACKAGE],
        "bun": [executable, "add", "-d", KNIP_PACKAGE],
    }
    command = install_commands.get(package_manager, install_commands["npm"])
    stdout, stderr, returncode, _ = run_command(command, logger, cwd=repo_path)
    version = read_installed_package_version(repo_path, KNIP_PACKAGE)
    status = "OK" if returncode == 0 and version != "NOT INSTALLED" else "FAIL"
    if status == "FAIL":
        logger.error(f"Failed to install {KNIP_PACKAGE}: {stderr.strip() or stdout.strip()}", file=KNIP_PACKAGE)
    return {
        "package": KNIP_PACKAGE,
        "version": version,
        "status": status,
        "action": "installed" if status == "OK" else "failed",
    }


def get_repository_commit_hash(repo_path: Path) -> str:
    try:
        return Repo(repo_path).head.commit.hexsha
    except Exception:
        return "unknown"


def _looks_like_platform_knip_json(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    marker_hits = sum(1 for marker in PLATFORM_KNIP_JSON_MARKERS if marker in payload)
    return marker_hits >= 2


def _read_package_json_knip_config(repo_path: Path) -> dict[str, Any] | None:
    package_json = repo_path / "package.json"
    if not package_json.exists():
        return None
    try:
        payload = json.loads(package_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    knip_config = payload.get("knip")
    return knip_config if isinstance(knip_config, dict) else None


def resolve_knip_config(repo_path: Path, temp_dir: Path, logger: NotebookLogger) -> dict[str, Any]:
    notes: list[str] = []
    selected_path: Path | None = None
    source = ""

    for name in KNIP_CONFIG_FILENAMES:
        candidate = repo_path / name
        if not candidate.exists():
            continue
        if candidate.name in {"knip.json", "knip.jsonc"} and _looks_like_platform_knip_json(candidate):
            notes.append(
                f"Ignored {candidate.name} because it contains platform metric output, not Knip configuration."
            )
            continue
        if candidate.suffix in {".ts", ".js", ".mjs", ".cjs"} or candidate.name.startswith("knip.config"):
            selected_path = candidate
            source = "repository config file"
            break

    if selected_path is None:
        package_knip = _read_package_json_knip_config(repo_path)
        if package_knip is not None:
            temp_dir.mkdir(parents=True, exist_ok=True)
            selected_path = temp_dir / "knip.notebook.config.json"
            selected_path.write_text(json.dumps(package_knip, indent=2), encoding="utf-8")
            source = "package.json#knip copied to temporary notebook config"
            notes.append(
                "Using temporary Knip config extracted from package.json to avoid invalid root knip.json platform output."
            )
        else:
            logger.error("No usable Knip configuration found in repository.", file=str(repo_path))
            raise FileNotFoundError("No usable Knip configuration found.")

    return {
        "config_path": str(selected_path.resolve()),
        "config_source": source,
        "notes": notes,
    }


def collect_environment_details(
    repo_path: Path,
    package_manager: str,
    logger: NotebookLogger,
) -> dict[str, Any]:
    npx = resolve_npx(repo_path)
    stdout, stderr, returncode, _ = run_command([npx, "knip", "--version"], logger, cwd=repo_path)
    knip_version = (stdout or stderr).strip() if returncode == 0 else read_installed_package_version(repo_path, KNIP_PACKAGE)
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

    return {
        "operating_system": platform.platform(),
        "node_version": node_version,
        "npm_version": npm_version,
        "package_manager": package_manager,
        "knip_version": knip_version,
        "repository_commit_hash": get_repository_commit_hash(repo_path),
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
    }


def build_knip_command(repo_path: Path, config_path: Path, json_output: bool = False) -> list[str]:
    npx = resolve_npx(repo_path)
    command = [npx, "knip", "-c", str(config_path.resolve())]
    if json_output:
        command.extend(["--reporter", "json"])
    return command


def execute_knip(
    repo_path: Path,
    config_path: Path,
    logger: NotebookLogger,
    json_output: bool = False,
) -> dict[str, Any]:
    command = build_knip_command(repo_path, config_path, json_output=json_output)
    stdout, stderr, returncode, elapsed_ms = run_command(command, logger, cwd=repo_path)
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


def save_execution_report(
    reports_dir: Path,
    console_execution: dict[str, Any],
    json_execution: dict[str, Any],
    environment: dict[str, Any],
) -> Path:
    payload = {
        "environment": environment,
        "console_run": {
            "command": console_execution["command"],
            "returncode": console_execution["returncode"],
            "elapsed_ms": console_execution["elapsed_ms"],
        },
        "json_run": {
            "command": json_execution["command"],
            "returncode": json_execution["returncode"],
            "elapsed_ms": json_execution["elapsed_ms"],
        },
    }
    path = reports_dir / "execution.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def require_knip_json_report(raw_dir: Path, json_execution: dict[str, Any], logger: NotebookLogger) -> Path:
    report_path = raw_dir / "knip-report.json"
    stdout = json_execution.get("stdout", "")
    stderr = json_execution.get("stderr", "")

    candidate_text = stdout.strip()
    if not candidate_text and stderr.strip():
        try:
            json.loads(stderr)
            candidate_text = stderr.strip()
        except json.JSONDecodeError:
            pass

    if not candidate_text:
        logger.error(
            "Knip JSON reporter produced empty stdout and no JSON in stderr.",
            file="knip",
        )
        raise RuntimeError("Knip JSON reporter produced empty stdout.")

    try:
        json.loads(candidate_text)
    except json.JSONDecodeError as exc:
        logger.error(f"Knip JSON reporter output is not valid JSON: {exc}", file="knip")
        raise RuntimeError("Knip JSON reporter output is not valid JSON.") from exc

    write_text_verbatim(report_path, candidate_text if candidate_text.endswith("\n") else candidate_text + "\n")
    return report_path


def load_knip_report(report_path: Path) -> dict[str, Any]:
    return json.loads(report_path.read_text(encoding="utf-8"))


def _count_issue_items(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return sum(_count_issue_items(item) for item in value.values())
    return 0


def extract_knip_metrics(report_path: Path) -> pd.DataFrame:
    payload = load_knip_report(report_path)
    rows: list[tuple[str, str, Any]] = []

    if "issues" in payload:
        issues = payload["issues"]
        rows.append(("Issues", "issues", issues))
        rows.append(("Issues Count", "issues", _count_issue_items(issues)))

    for field, label in ISSUE_FIELD_MAP.items():
        if field not in payload:
            continue
        value = payload[field]
        rows.append((label, field, value))
        rows.append((f"{label} Count", field, _count_issue_items(value)))

    if "entry" in payload:
        rows.append(("Entry Points", "entry", payload["entry"]))
    if "project" in payload:
        rows.append(("Project Files Pattern", "project", payload["project"]))

    if not rows:
        rows.append(("Raw Payload Keys", "root", sorted(payload.keys())))

    return pd.DataFrame(rows, columns=METRIC_COLUMNS)


def _raw_text_for_validation(report_path: Path, console_stdout: str, console_stderr: str) -> str:
    parts = [
        report_path.read_text(encoding="utf-8", errors="replace"),
        console_stdout or "",
        console_stderr or "",
    ]
    return "\n".join(parts)


def _keyword_evidence(raw_text: str) -> str:
    lowered = raw_text.lower()
    hits = [keyword for keyword in EXCEPTION_FLOW_KEYWORDS if keyword.lower() in lowered]
    if hits:
        return f"Keywords found in raw Knip output: {', '.join(hits)}"
    return "No exception-flow or error-flow fields found in raw Knip output."


def validate_taxonomy_levels(report_path: Path, console_stdout: str, console_stderr: str) -> pd.DataFrame:
    raw_text = _raw_text_for_validation(report_path, console_stdout, console_stderr)
    payload = load_knip_report(report_path)
    serialized = json.dumps(payload)

    exception_fields = [keyword for keyword in EXCEPTION_FLOW_KEYWORDS if keyword.lower() in serialized.lower()]
    if exception_fields:
        supported = "Partially Supported"
        evidence = f"Raw JSON contains keyword(s): {', '.join(exception_fields)}"
    else:
        supported = "Not Supported"
        evidence = _keyword_evidence(raw_text)

    rows = []
    for level, value in TAXONOMY_LEVELS:
        rows.append(
            {
                "Taxonomy Level": level,
                "Value": value,
                "Supported": supported,
                "Evidence": evidence,
            }
        )
    rows.append(
        {
            "Taxonomy Level": "Assessment",
            "Value": EXCEPTION_PATH_STATEMENT,
            "Supported": "Not Supported",
            "Evidence": evidence,
        }
    )
    return pd.DataFrame(rows, columns=TAXONOMY_COLUMNS)


def build_final_report_table(report_path: Path, console_stdout: str, console_stderr: str) -> pd.DataFrame:
    validation = validate_taxonomy_levels(report_path, console_stdout, console_stderr)
    metric_row = validation[validation["Taxonomy Level"] == "Metric"].iloc[0]
    supported_label = metric_row["Supported"]
    if supported_label == "Not Supported":
        supported = "NO"
    elif supported_label == "Partially Supported":
        supported = "PARTIAL"
    else:
        supported = "YES"

    row = {
        "Technique": "Control Flow Testing",
        "Classification": "Path Coverage",
        "Metric": "Exception Path Handling",
        "Definition": METRIC_DEFINITION,
        "Tool": TOOL_NAME,
        "Raw Output File": "knip-report.json",
        "Supported": supported,
        "Evidence": metric_row["Evidence"],
    }
    return pd.DataFrame([row], columns=FINAL_REPORT_COLUMNS)


def render_final_report_markdown(report_df: pd.DataFrame, taxonomy_df: pd.DataFrame) -> str:
    row = report_df.iloc[0]
    lines = [
        "# Knip Error Flow Verification Report",
        "",
        "| Field | Value |",
        "| --- | --- |",
    ]
    for column in FINAL_REPORT_COLUMNS:
        lines.append(f"| {column} | {row[column]} |")
    lines.extend(["", "## Taxonomy Validation", ""])
    for _, tax_row in taxonomy_df.iterrows():
        lines.append(
            f"- **{tax_row['Taxonomy Level']}** ({tax_row['Value']}): "
            f"{tax_row['Supported']} — {tax_row['Evidence']}"
        )
    lines.extend(["", "## Assessment", "", EXCEPTION_PATH_STATEMENT, ""])
    return "\n".join(lines)


def build_output_json(
    repo_path: Path,
    repo_validation: dict[str, Any],
    environment: dict[str, Any],
    config_info: dict[str, Any],
    install_result: dict[str, Any],
    knip_install: dict[str, str],
    console_execution: dict[str, Any],
    json_execution: dict[str, Any],
    metrics_payload: dict[str, Any],
    taxonomy_df: pd.DataFrame,
    report_df: pd.DataFrame,
    artifact_paths: dict[str, str],
    elapsed_ms: float,
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": {
            "name": repo_validation.get("repository_name", repo_path.name),
            "local_path": str(repo_path.resolve()),
            "commit_hash": environment.get("repository_commit_hash", ""),
            "programming_language": PROGRAMMING_LANGUAGE,
        },
        "environment": environment,
        "knip_configuration": config_info,
        "pipeline": {
            "elapsed_ms": round(elapsed_ms, 2),
            "package_manager": environment.get("package_manager", ""),
            "install_command": install_result.get("command", ""),
            "install_returncode": install_result.get("returncode"),
            "knip_install": knip_install,
            "console_command": console_execution.get("command", ""),
            "console_returncode": console_execution.get("returncode"),
            "json_command": json_execution.get("command", ""),
            "json_returncode": json_execution.get("returncode"),
        },
        "knip_metrics": metrics_payload,
        "taxonomy_validation": taxonomy_df.to_dict(orient="records"),
        "final_metric_report": report_df.iloc[0].to_dict(),
        "assessment": EXCEPTION_PATH_STATEMENT,
        "raw_artifacts": artifact_paths,
    }


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
        raise RuntimeError("Repository validation failed: missing package.json or tsconfig.json.")

    package_manager = detect_package_manager(repo_path)
    if package_manager == "unknown":
        logger.error("Unable to detect package manager.", file=str(repo_path))
        raise RuntimeError("Unable to detect package manager.")

    environment = collect_environment_details(repo_path, package_manager, logger)
    environment_path = reports_dir / "environment.json"
    environment_path.write_text(json.dumps(environment, indent=2), encoding="utf-8")

    install_result = install_project_dependencies(repo_path, package_manager, logger)
    if install_result["returncode"] != 0:
        raise RuntimeError(f"{package_manager} install failed.")

    knip_install = ensure_knip_installed(repo_path, package_manager, logger)
    if knip_install["status"] != "OK":
        raise RuntimeError("Knip is not installed and could not be installed.")

    config_info = resolve_knip_config(repo_path, artifact_dirs["temp"], logger)
    config_path = Path(config_info["config_path"])
    if not config_path.exists():
        logger.error(f"Knip config file not found: {config_path}", file=str(config_path))
        raise FileNotFoundError(f"Knip config file not found: {config_path}")
    (parsed_dir / "knip_configuration.json").write_text(json.dumps(config_info, indent=2), encoding="utf-8")

    json_execution = execute_knip(repo_path, config_path, logger, json_output=True)
    console_execution = execute_knip(repo_path, config_path, logger, json_output=False)

    write_text_verbatim(raw_dir / "knip_stdout.txt", console_execution["stdout"])
    write_text_verbatim(raw_dir / "knip_stderr.txt", console_execution["stderr"] + json_execution["stderr"])
    json_stdout_path = raw_dir / "knip_json_stdout.txt"
    write_text_verbatim(json_stdout_path, json_execution["stdout"])

    if json_execution["returncode"] not in {0, 1} and not json_execution["stdout"].strip():
        logger.error(
            f"Knip JSON execution failed with exit code {json_execution['returncode']}.",
            file="knip",
        )
        raise RuntimeError("Knip JSON execution failed.")

    report_path = require_knip_json_report(raw_dir, json_execution, logger)
    execution_path = save_execution_report(reports_dir, console_execution, json_execution, environment)

    metrics_df = extract_knip_metrics(report_path)
    metrics_df.to_csv(parsed_dir / "knip_metrics.csv", index=False)
    metrics_payload = {
        str(row["Metric"]): {"json_field": row["JSON Field"], "value": row["Value"]}
        for _, row in metrics_df.iterrows()
    }
    (parsed_dir / "knip_metrics.json").write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")

    taxonomy_df = validate_taxonomy_levels(report_path, console_execution["stdout"], console_execution["stderr"])
    taxonomy_df.to_csv(parsed_dir / "taxonomy_validation.csv", index=False)
    (parsed_dir / "taxonomy_validation.json").write_text(
        json.dumps(taxonomy_df.to_dict(orient="records"), indent=2),
        encoding="utf-8",
    )

    report_df = build_final_report_table(report_path, console_execution["stdout"], console_execution["stderr"])
    report_df.to_csv(reports_dir / "final_metric_report.csv", index=False)
    markdown_report = render_final_report_markdown(report_df, taxonomy_df)
    (reports_dir / "final_metric_report.md").write_text(markdown_report, encoding="utf-8")

    artifact_paths = {
        "knip_report_json": str(report_path.resolve()),
        "knip_stdout_txt": str((raw_dir / "knip_stdout.txt").resolve()),
        "knip_stderr_txt": str((raw_dir / "knip_stderr.txt").resolve()),
        "knip_json_stdout_txt": str(json_stdout_path.resolve()),
        "execution_json": str(execution_path.resolve()),
        "environment_json": str(environment_path.resolve()),
    }
    output_payload = build_output_json(
        repo_path=repo_path,
        repo_validation=repo_validation,
        environment=environment,
        config_info=config_info,
        install_result=install_result,
        knip_install=knip_install,
        console_execution=console_execution,
        json_execution=json_execution,
        metrics_payload=metrics_payload,
        taxonomy_df=taxonomy_df,
        report_df=report_df,
        artifact_paths=artifact_paths,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )
    output_json_path = reports_dir / "output.json"
    output_json_path.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")

    logger.write_errors()
    elapsed_ms = (time.perf_counter() - started) * 1000

    return {
        "pipeline_success": True,
        "repository": str(repo_path),
        "package_manager": package_manager,
        "knip_report_raw": report_path.read_text(encoding="utf-8"),
        "metrics_df": metrics_df,
        "taxonomy_df": taxonomy_df,
        "report_df": report_df,
        "report_markdown": markdown_report,
        "output_json": str(output_json_path),
        "output_payload": output_payload,
        "elapsed_ms": round(elapsed_ms, 2),
        "artifact_paths": artifact_paths,
    }
