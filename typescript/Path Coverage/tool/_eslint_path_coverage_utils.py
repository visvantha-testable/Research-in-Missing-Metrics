"""ESLint + eslint-plugin-sonarjs Path Coverage extraction and validation helpers."""
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
TS_EXTENSIONS = {".ts", ".tsx"}
EXCLUDED_DIR_NAMES = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "vendor",
    "artifacts",
}
ESLINT_SUCCESS_CODES = {0, 1}
MANDATORY_PATHS = ("package.json", "tsconfig.json")
ESLINT_CONFIG_NAMES = (
    "eslint.config.js",
    "eslint.config.mjs",
    "eslint.config.cjs",
    ".eslintrc.json",
    ".eslintrc.js",
    ".eslintrc.cjs",
    ".eslintrc.yaml",
    ".eslintrc.yml",
)
REQUIRED_NPM_PACKAGES = ("eslint", "eslint-plugin-sonarjs", "typescript", "typescript-eslint")
SONARJS_RULE_PREFIX = "sonarjs/"
PATH_KEYWORDS = [
    "path coverage",
    "path_coverage",
    "path coverage %",
    "path_coverage_percent",
    "total_paths",
    "covered_paths",
    "uncovered_paths",
    "execution path",
    "control flow graph",
]
PATH_METRICS = [
    "Path Execution Tracking",
    "Complete Coverage Path Verification",
    "Partial Path Coverage Detection",
    "Nested Condition Path Testing",
    "Loop Path Detection",
    "Unreachable Path Detection",
    "Path Detection Testing",
    "Path Coverage %",
]
METRIC_RULE_MAP: dict[str, list[str]] = {
    "Path Execution Tracking": ["sonarjs/cognitive-complexity", "complexity"],
    "Complete Coverage Path Verification": ["sonarjs/no-all-duplicated-branches", "sonarjs/no-duplicated-branches"],
    "Partial Path Coverage Detection": ["sonarjs/no-identical-conditions", "sonarjs/no-same-line-conditional"],
    "Nested Condition Path Testing": ["sonarjs/no-nested-switch", "sonarjs/no-collapsible-if", "sonarjs/max-switch-cases"],
    "Loop Path Detection": ["sonarjs/no-one-iteration-loop", "sonarjs/prefer-while"],
    "Unreachable Path Detection": ["sonarjs/no-gratuitous-expressions", "sonarjs/no-redundant-boolean"],
    "Path Detection Testing": [
        "sonarjs/cognitive-complexity",
        "sonarjs/no-all-duplicated-branches",
        "sonarjs/no-duplicated-branches",
        "sonarjs/no-identical-conditions",
        "sonarjs/no-nested-switch",
        "sonarjs/no-one-iteration-loop",
    ],
    "Path Coverage %": [],
}
FINDINGS_COLUMNS = [
    "File Path",
    "Rule ID",
    "Rule Name",
    "Plugin",
    "Severity",
    "Message",
    "Line",
    "Column",
    "End Line",
    "End Column",
    "Node Type",
    "Source Code",
    "Fix Available",
]
CONFIG_COLUMNS = [
    "Config File",
    "Check",
    "Expected",
    "Actual",
    "Status",
]
PATH_VALIDATION_COLUMNS = [
    "Testing Type",
    "Classification",
    "Metric Name",
    "KPI",
    "Supported",
    "Directly Emitted",
    "Derived",
    "Raw Tool Evidence",
    "Supporting ESLint Rule IDs",
    "Derived Formula (if applicable)",
    "Validation Status",
    "Evidence",
    "Comments",
]
REPOSITORY_SUMMARY_COLUMNS = [
    "Repository Name",
    "Programming Language",
    "Package Manager",
    "ESLint Version",
    "SonarJS Plugin Version",
    "Total Files Scanned",
    "Total TypeScript Files",
    "Total Errors",
    "Total Warnings",
    "Total SonarJS Findings",
    "Total ESLint Findings",
]
DASHBOARD_COLUMNS = [
    "Repository",
    "ESLint Version",
    "SonarJS Version",
    "Files Analysed",
    "Errors",
    "Warnings",
    "SonarJS Issues",
    "Path Detection Support",
    "Path Coverage Support",
    "Execution Status",
]
SEVERITY_LABELS = {0: "off", 1: "warning", 2: "error"}


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
                "stdout_bytes": len(stdout.encode("utf-8", errors="replace")),
                "stderr_bytes": len(stderr.encode("utf-8", errors="replace")),
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


def ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


def resolve_metric_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__).resolve().parent).resolve()
    for _ in range(8):
        if (current / "tool" / "_eslint_path_coverage_utils.py").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return Path(__file__).resolve().parent.parent


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


def discover_typescript_files(repo_path: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo_path.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TS_EXTENSIONS:
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def find_eslint_config(repo_path: Path) -> Path | None:
    for name in ESLINT_CONFIG_NAMES:
        candidate = repo_path / name
        if candidate.is_file():
            return candidate
    return None


def validate_typescript_eslint_project(repo_path: Path, logger: NotebookLogger) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    for item in MANDATORY_PATHS:
        target = repo_path / item
        checks[item] = target.is_file()
        if not checks[item]:
            logger.error(f"Missing mandatory file: {item}", file=str(target))

    lock_path = repo_path / "package-lock.json"
    checks["package-lock.json"] = lock_path.is_file()
    if not checks["package-lock.json"]:
        logger.error("package-lock.json not found (optional but expected).", file=str(lock_path))

    eslint_config = find_eslint_config(repo_path)
    checks["eslint_configuration"] = eslint_config is not None
    if not eslint_config:
        logger.error("Missing ESLint configuration (eslint.config.* or .eslintrc.*).", file=str(repo_path))

    src_dir = repo_path / "src"
    checks["src_directory"] = src_dir.is_dir()
    if not checks["src_directory"]:
        logger.error("Missing src/ directory.", file=str(src_dir))

    ts_files = discover_typescript_files(repo_path)
    checks["typescript_source_files"] = len(ts_files) > 0
    if not checks["typescript_source_files"]:
        logger.error("No TypeScript source files found.", file=str(repo_path))

    mandatory_ok = all(checks[key] for key in ("package.json", "tsconfig.json", "eslint_configuration", "src_directory", "typescript_source_files"))
    return {
        "repository_name": repo_path.name,
        "eslint_config_path": str(eslint_config) if eslint_config else "",
        "typescript_file_count": len(ts_files),
        **checks,
        "project_valid": mandatory_ok,
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


def resolve_npx(repo_path: Path) -> str:
    local_npx = repo_path / "node_modules" / ".bin" / "npx"
    for candidate in (local_npx.with_suffix(".cmd"), local_npx):
        if candidate.exists():
            return str(candidate.resolve())
    for name in ("npx", "npx.cmd"):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    raise FileNotFoundError("npx not found on PATH.")


def install_npm_dependencies(repo_path: Path, logger: NotebookLogger) -> dict[str, Any]:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        logger.error("npm not found on PATH.", file="npm")
        return {
            "command": "npm install",
            "returncode": 127,
            "elapsed_ms": 0.0,
            "stdout": "",
            "stderr": "npm executable not found",
        }
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
    if package_json.exists():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
            return str(payload.get("version", "unknown"))
        except json.JSONDecodeError:
            return "unknown"
    return "NOT INSTALLED"


def verify_runtime_packages(repo_path: Path, logger: NotebookLogger) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for package in REQUIRED_NPM_PACKAGES:
        version = read_installed_package_version(repo_path, package)
        status = "OK" if version != "NOT INSTALLED" else "MISSING"
        if status == "MISSING":
            logger.error(f"Required npm package not installed: {package}", file=package)
        rows.append({"package": package, "version": version, "status": status})
    return pd.DataFrame(rows)


def _config_text(config_path: Path | None) -> str:
    if config_path is None or not config_path.exists():
        return ""
    return config_path.read_text(encoding="utf-8", errors="replace")


def validate_eslint_configuration(repo_path: Path, logger: NotebookLogger) -> pd.DataFrame:
    config_path = find_eslint_config(repo_path)
    text = _config_text(config_path)
    lowered = text.lower()

    sonarjs_present = "eslint-plugin-sonarjs" in lowered or "sonarjs" in lowered
    typescript_parser = "typescript-eslint" in lowered or "@typescript-eslint/parser" in lowered
    sonarjs_recommended = "sonarjs.configs.recommended" in text or "plugin:sonarjs/recommended" in lowered
    source_included = "sample_subject" in text or "src/" in text or "files:" in lowered or "files :" in lowered

    checks = [
        ("eslint-plugin-sonarjs configured", "present", "present" if sonarjs_present else "missing", sonarjs_present),
        ("TypeScript parser configured", "present", "present" if typescript_parser else "missing", typescript_parser),
        ("SonarJS recommended rules enabled", "enabled", "enabled" if sonarjs_recommended else "missing", sonarjs_recommended),
        ("TypeScript source files included", "included", "included" if source_included else "missing", source_included),
    ]
    rows: list[dict[str, str]] = []
    for check_name, expected, actual, ok in checks:
        if not ok:
            logger.error(f"ESLint configuration check failed: {check_name}", file=str(config_path or repo_path))
        rows.append(
            {
                "Config File": str(config_path) if config_path else "",
                "Check": check_name,
                "Expected": expected,
                "Actual": actual,
                "Status": "PASS" if ok else "FAIL",
            }
        )
    return pd.DataFrame(rows, columns=CONFIG_COLUMNS)


def execute_eslint(repo_path: Path, raw_output_path: Path, logger: NotebookLogger) -> dict[str, Any]:
    ensure_output_dir(raw_output_path.parent)
    npx = resolve_npx(repo_path)
    command = [npx, "eslint", ".", "--ext", ".ts", "-f", "json", "-o", str(raw_output_path)]
    stdout, stderr, returncode, elapsed_ms = run_command(command, logger, cwd=repo_path)
    console_output = stdout + (("\n" + stderr) if stderr else "")

    if returncode not in ESLINT_SUCCESS_CODES:
        logger.error(
            f"ESLint execution failed with exit code {returncode}: {stderr.strip() or stdout.strip()}",
            file="eslint",
        )
    if not raw_output_path.exists():
        logger.error("ESLint did not produce eslint_raw_output.json.", file=str(raw_output_path))
    elif raw_output_path.stat().st_size == 0:
        logger.error("ESLint JSON output file is empty.", file=str(raw_output_path))

    json_valid = False
    if raw_output_path.exists() and raw_output_path.stat().st_size > 0:
        try:
            json.loads(raw_output_path.read_text(encoding="utf-8"))
            json_valid = True
        except json.JSONDecodeError as exc:
            logger.error(f"Invalid ESLint JSON output: {exc}", file=str(raw_output_path))

    return {
        "command": " ".join(command),
        "returncode": returncode,
        "elapsed_ms": elapsed_ms,
        "stdout": stdout,
        "stderr": stderr,
        "console_output": console_output,
        "json_valid": json_valid,
        "output_path": str(raw_output_path),
    }


def load_eslint_records(raw_output_path: Path, logger: NotebookLogger) -> list[dict[str, Any]]:
    if not raw_output_path.exists():
        return []
    try:
        payload = json.loads(raw_output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.error(f"Failed to parse ESLint JSON: {exc}", file=str(raw_output_path))
        return []
    return payload if isinstance(payload, list) else []


def _extract_source_snippet(record: dict[str, Any], message: dict[str, Any]) -> str:
    source = record.get("source")
    if isinstance(source, str) and source.strip():
        line_no = message.get("line")
        if isinstance(line_no, int) and line_no > 0:
            lines = source.splitlines()
            if 0 <= line_no - 1 < len(lines):
                return lines[line_no - 1]
        return source[:500]
    return ""


def _rule_name(rule_id: str) -> str:
    if not rule_id:
        return ""
    if "/" in rule_id:
        return rule_id.split("/", 1)[1]
    return rule_id


def _plugin_name(rule_id: str) -> str:
    if not rule_id:
        return ""
    if rule_id.startswith("sonarjs/"):
        return "eslint-plugin-sonarjs"
    if rule_id.startswith("@"):
        return rule_id.split("/", 1)[0]
    return "eslint"


def parse_eslint_findings(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in records:
        file_path = record.get("filePath", "")
        for message in record.get("messages", []):
            rule_id = str(message.get("ruleId") or "")
            fix = message.get("fix")
            rows.append(
                {
                    "File Path": file_path,
                    "Rule ID": rule_id,
                    "Rule Name": _rule_name(rule_id),
                    "Plugin": _plugin_name(rule_id),
                    "Severity": SEVERITY_LABELS.get(message.get("severity"), str(message.get("severity", ""))),
                    "Message": message.get("message", ""),
                    "Line": message.get("line", ""),
                    "Column": message.get("column", ""),
                    "End Line": message.get("endLine", ""),
                    "End Column": message.get("endColumn", ""),
                    "Node Type": message.get("nodeType", ""),
                    "Source Code": _extract_source_snippet(record, message),
                    "Fix Available": "Yes" if fix else "No",
                }
            )
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def summarize_eslint_results(records: list[dict[str, Any]], findings_df: pd.DataFrame) -> dict[str, int]:
    total_errors = sum(int(record.get("errorCount", 0) or 0) for record in records)
    total_warnings = sum(int(record.get("warningCount", 0) or 0) for record in records)
    sonarjs_findings = 0
    if not findings_df.empty and "Rule ID" in findings_df.columns:
        sonarjs_findings = int(findings_df["Rule ID"].astype(str).str.startswith(SONARJS_RULE_PREFIX).sum())
    return {
        "total_files_scanned": len(records),
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "total_eslint_findings": len(findings_df),
        "total_sonarjs_findings": sonarjs_findings,
    }


def get_tool_versions(repo_path: Path, logger: NotebookLogger) -> dict[str, str]:
    eslint_version = read_installed_package_version(repo_path, "eslint")
    sonarjs_version = read_installed_package_version(repo_path, "eslint-plugin-sonarjs")
    if eslint_version == "NOT INSTALLED":
        npx = resolve_npx(repo_path)
        stdout, stderr, returncode, _ = run_command([npx, "eslint", "--version"], logger, cwd=repo_path)
        eslint_version = (stdout or stderr).strip() or eslint_version
    return {
        "eslint_version": eslint_version,
        "sonarjs_version": sonarjs_version,
    }


def build_repository_summary(
    repository_name: str,
    ts_file_count: int,
    summary: dict[str, int],
    versions: dict[str, str],
) -> pd.DataFrame:
    row = {
        "Repository Name": repository_name,
        "Programming Language": PROGRAMMING_LANGUAGE,
        "Package Manager": PACKAGE_MANAGER,
        "ESLint Version": versions.get("eslint_version", ""),
        "SonarJS Plugin Version": versions.get("sonarjs_version", ""),
        "Total Files Scanned": summary.get("total_files_scanned", 0),
        "Total TypeScript Files": ts_file_count,
        "Total Errors": summary.get("total_errors", 0),
        "Total Warnings": summary.get("total_warnings", 0),
        "Total SonarJS Findings": summary.get("total_sonarjs_findings", 0),
        "Total ESLint Findings": summary.get("total_eslint_findings", 0),
    }
    return pd.DataFrame([row], columns=REPOSITORY_SUMMARY_COLUMNS)


def _collect_rule_ids(findings_df: pd.DataFrame) -> set[str]:
    if findings_df.empty:
        return set()
    return {rule for rule in findings_df["Rule ID"].astype(str).tolist() if rule}


def _json_text_without_sources(raw_text: str) -> str:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return raw_text

    def scrub(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: scrub(item) for key, item in value.items() if key != "source"}
        if isinstance(value, list):
            return [scrub(item) for item in value]
        return value

    return json.dumps(scrub(payload))


def _keyword_evidence(raw_text: str, keywords: list[str]) -> str:
    scrubbed = _json_text_without_sources(raw_text)
    lowered = scrubbed.lower()
    for keyword in keywords:
        if keyword.lower() in lowered:
            return f'Keyword "{keyword}" found in eslint_raw_output.json metadata'
    return "No path coverage keywords found in eslint_raw_output.json metadata"


def _metric_validation_status(
    metric_name: str, rule_ids: set[str], raw_text: str
) -> tuple[str, str, str, str, str, str, str, str]:
    mapped_rules = METRIC_RULE_MAP.get(metric_name, [])
    matching_rules = sorted(rule for rule in mapped_rules if rule in rule_ids)
    scrubbed_text = _json_text_without_sources(raw_text)
    keyword_hit = any(keyword.lower() in scrubbed_text.lower() for keyword in PATH_KEYWORDS)

    if metric_name == "Path Coverage %":
        if re.search(r'"path_coverage_percent"\s*:', scrubbed_text, re.IGNORECASE):
            return (
                "Supported",
                "Yes",
                "No",
                'Field "path_coverage_percent" present in eslint_raw_output.json',
                ", ".join(matching_rules),
                "path_coverage_percent field in ESLint JSON output",
                "Directly Emitted",
                "Path Coverage % is explicitly present in the raw ESLint JSON payload.",
            )
        return (
            "Not Supported",
            "No",
            "Yes",
            _keyword_evidence(raw_text, PATH_KEYWORDS),
            ", ".join(matching_rules),
            "(covered_paths / total_paths) * 100 — requires runtime test execution data not emitted by ESLint JSON",
            "Not Supported",
            "ESLint + eslint-plugin-sonarjs JSON output does not emit Path Coverage %; it must be derived outside raw ESLint output.",
        )

    if metric_name == "Path Detection Testing":
        if matching_rules or keyword_hit:
            return (
                "Partially Supported",
                "No",
                "Yes",
                f"Control-flow findings from SonarJS rules: {', '.join(matching_rules) or 'keyword match only'}",
                ", ".join(matching_rules) or "sonarjs/* control-flow rules",
                "Infer path-related control-flow complexity from SonarJS rule violations",
                "Derived",
                "ESLint emits static control-flow smell findings; it does not enumerate executable paths or compute coverage.",
            )
        return (
            "Not Supported",
            "No",
            "No",
            _keyword_evidence(raw_text, PATH_KEYWORDS),
            "",
            "Requires path enumeration plus test execution evidence",
            "Not Supported",
            "No SonarJS path-detection evidence found in raw ESLint output.",
        )

    if matching_rules:
        return (
            "Partially Supported",
            "No",
            "Yes",
            f"SonarJS findings for rules: {', '.join(matching_rules)}",
            ", ".join(matching_rules),
            "Heuristic mapping from SonarJS control-flow rule violations",
            "Derived",
            f"{metric_name} is inferred from SonarJS static analysis findings, not directly emitted as a coverage metric.",
        )

    return (
        "Not Supported",
        "No",
        "No",
        _keyword_evidence(raw_text, PATH_KEYWORDS),
        ", ".join(matching_rules),
        "Not available from raw ESLint JSON alone",
        "Not Supported",
        f"No direct {metric_name} evidence in eslint_raw_output.json.",
    )


def build_path_coverage_validation(findings_df: pd.DataFrame, raw_output_path: Path) -> pd.DataFrame:
    raw_text = raw_output_path.read_text(encoding="utf-8", errors="replace") if raw_output_path.exists() else ""
    rule_ids = _collect_rule_ids(findings_df)
    rows: list[dict[str, str]] = []
    for metric_name in PATH_METRICS:
        supported, directly_emitted, derived, evidence, rules, formula, status, comments = _metric_validation_status(
            metric_name, rule_ids, raw_text
        )
        rows.append(
            {
                "Testing Type": "Control Flow Testing",
                "Classification": "Path Coverage",
                "Metric Name": metric_name,
                "KPI": "Path Coverage %" if metric_name != "Path Coverage %" else "Path Coverage %",
                "Supported": supported,
                "Directly Emitted": directly_emitted,
                "Derived": derived,
                "Raw Tool Evidence": evidence,
                "Supporting ESLint Rule IDs": rules,
                "Derived Formula (if applicable)": formula,
                "Validation Status": status,
                "Evidence": evidence,
                "Comments": comments,
            }
        )
    return pd.DataFrame(rows, columns=PATH_VALIDATION_COLUMNS)


def build_dashboard_summary(
    repository_name: str,
    versions: dict[str, str],
    summary: dict[str, int],
    validation_df: pd.DataFrame,
    eslint_execution_ok: bool,
) -> pd.DataFrame:
    path_detection_row = validation_df[validation_df["Metric Name"] == "Path Detection Testing"]
    path_coverage_row = validation_df[validation_df["Metric Name"] == "Path Coverage %"]
    path_detection_support = path_detection_row["Validation Status"].iloc[0] if not path_detection_row.empty else "Unknown"
    path_coverage_support = path_coverage_row["Validation Status"].iloc[0] if not path_coverage_row.empty else "Unknown"
    execution_status = "SUCCESS" if eslint_execution_ok else "FAIL"
    row = {
        "Repository": repository_name,
        "ESLint Version": versions.get("eslint_version", ""),
        "SonarJS Version": versions.get("sonarjs_version", ""),
        "Files Analysed": summary.get("total_files_scanned", 0),
        "Errors": summary.get("total_errors", 0),
        "Warnings": summary.get("total_warnings", 0),
        "SonarJS Issues": summary.get("total_sonarjs_findings", 0),
        "Path Detection Support": path_detection_support,
        "Path Coverage Support": path_coverage_support,
        "Execution Status": execution_status,
    }
    return pd.DataFrame([row], columns=DASHBOARD_COLUMNS)


def run_pipeline(
    repo_path: Path,
    output_dir: Path,
    logger: NotebookLogger | None = None,
) -> dict[str, Any]:
    logger = logger or NotebookLogger(output_dir / "error_log.txt")
    ensure_output_dir(output_dir)
    started = time.perf_counter()

    project_validation = validate_typescript_eslint_project(repo_path, logger)
    if not project_validation["project_valid"]:
        raise RuntimeError("Mandatory TypeScript ESLint project files are missing.")

    install_result = install_npm_dependencies(repo_path, logger)
    package_df = verify_runtime_packages(repo_path, logger)

    config_df = validate_eslint_configuration(repo_path, logger)
    config_csv = output_dir / "eslint_configuration.csv"
    config_df.to_csv(config_csv, index=False)

    raw_json_path = output_dir / "eslint_raw_output.json"
    eslint_result = execute_eslint(repo_path, raw_json_path, logger)
    records = load_eslint_records(raw_json_path, logger) if eslint_result["json_valid"] else []

    findings_df = parse_eslint_findings(records)
    findings_csv = output_dir / "eslint_findings.csv"
    findings_df.to_csv(findings_csv, index=False)

    summary = summarize_eslint_results(records, findings_df)
    versions = get_tool_versions(repo_path, logger)
    repo_summary_df = build_repository_summary(
        project_validation["repository_name"],
        project_validation["typescript_file_count"],
        summary,
        versions,
    )
    repo_summary_csv = output_dir / "repository_summary.csv"
    repo_summary_df.to_csv(repo_summary_csv, index=False)

    validation_df = build_path_coverage_validation(findings_df, raw_json_path)
    validation_csv = output_dir / "path_coverage_validation.csv"
    validation_df.to_csv(validation_csv, index=False)

    eslint_execution_ok = (
        install_result["returncode"] == 0
        and eslint_result["returncode"] in ESLINT_SUCCESS_CODES
        and eslint_result["json_valid"]
        and raw_json_path.exists()
    )
    dashboard_df = build_dashboard_summary(
        project_validation["repository_name"],
        versions,
        summary,
        validation_df,
        eslint_execution_ok,
    )
    dashboard_csv = output_dir / "dashboard_summary.csv"
    dashboard_df.to_csv(dashboard_csv, index=False)

    logger.write_errors()
    elapsed_ms = (time.perf_counter() - started) * 1000

    deliverables = {
        "eslint_raw_output.json": raw_json_path.exists(),
        "eslint_findings.csv": findings_csv.exists(),
        "eslint_configuration.csv": config_csv.exists(),
        "repository_summary.csv": repo_summary_csv.exists(),
        "path_coverage_validation.csv": validation_csv.exists(),
        "dashboard_summary.csv": dashboard_csv.exists(),
        "error_log.txt": (output_dir / "error_log.txt").exists(),
    }

    return {
        "pipeline_success": all(deliverables.values()) and eslint_execution_ok,
        "repository": str(repo_path),
        "project_valid": project_validation["project_valid"],
        "install_returncode": install_result["returncode"],
        "eslint_returncode": eslint_result["returncode"],
        "eslint_json_valid": eslint_result["json_valid"],
        "package_verification": package_df.to_dict(orient="records"),
        "summary": summary,
        "versions": versions,
        "elapsed_ms": round(elapsed_ms, 2),
        "outputs": deliverables,
    }
