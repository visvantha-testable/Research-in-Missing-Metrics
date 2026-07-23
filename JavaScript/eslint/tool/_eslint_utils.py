"""ESLint raw lint analysis extraction helpers for JavaScript repositories."""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

os.environ.pop("PYTHONPATH", None)

REPO_URL = "https://github.com/visvantha-testable/javascript-testing-eslint.git"
PROGRAMMING_LANGUAGE = "JavaScript"
TOOL_NAME = "ESLint"
ANALYSIS_TYPE = "White Box Static Analysis (Lint)"

JS_GLOBS = ("*.js", "*.mjs", "*.cjs")
EXCLUDE_DIRS = {".git", "node_modules", "coverage", "dist", "build", "out", ".vscode"}
ESLINT_SUCCESS_CODES = {0, 1}

ESLINT_CONFIG_CANDIDATES = [
    "eslint.config.js",
    "eslint.config.mjs",
    "eslint.config.cjs",
    ".eslintrc.js",
    ".eslintrc.cjs",
    ".eslintrc.json",
    ".eslintrc.yml",
    ".eslintrc.yaml",
]

INVENTORY_COLUMNS = ["file_path", "file_name", "directory"]
VIOLATION_COLUMNS = [
    "file",
    "rule_id",
    "severity",
    "message",
    "line",
    "column",
    "endLine",
    "endColumn",
    "nodeType",
    "messageId",
    "fix_available",
]
FILE_SUMMARY_COLUMNS = ["file", "total_errors", "total_warnings", "fixable_errors", "fixable_warnings"]
RULE_FREQUENCY_COLUMNS = ["rule_id", "occurrence_count", "severity"]


class NotebookLogger:
    def __init__(self, error_log_path: Path) -> None:
        self.error_log_path = error_log_path
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._errors: list[dict[str, str]] = []
        self.write_errors()

    def info(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"[{timestamp}] INFO: {message}")

    def error(self, message: str, file: str = "notebook") -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"[{timestamp}] ERROR: {message}")
        self._errors.append({"timestamp": timestamp, "file": file, "error_message": message})
        self.write_errors()

    def write_errors(self) -> None:
        with self.error_log_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timestamp", "file", "error_message"])
            writer.writeheader()
            writer.writerows(self._errors)


def resolve_metric_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__).resolve().parent).resolve()
    for _ in range(8):
        if (current / "tool" / "_eslint_utils.py").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return Path(__file__).resolve().parent.parent


def ensure_output_dirs(metric_root: Path) -> dict[str, Path]:
    paths = {
        "root": metric_root,
        "outputs": metric_root / "outputs",
        "workspace": metric_root / "workspace",
        "tmp": metric_root / "tmp",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


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
    clone_depth: int | None = 1,
) -> tuple[Path, str]:
    validate_repo_url(repo_url)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    clone_path = derive_clone_path(repo_url, workspace_dir)
    if clone_path.exists():
        if if_clone_exists == "reclone":
            logger.info(f"Removing existing clone at {clone_path}")
            shutil.rmtree(clone_path, ignore_errors=True)
        elif if_clone_exists == "reuse":
            return clone_path.resolve(), f"Reusing existing repository at {clone_path}"
        else:
            raise ValueError("IF_CLONE_EXISTS must be 'reuse' or 'reclone'.")

    logger.info(f"Cloning {repo_url} into {clone_path}")
    clone_kwargs: dict[str, Any] = {"depth": clone_depth} if clone_depth else {}
    try:
        Repo.clone_from(repo_url, clone_path, **clone_kwargs)
    except GitCommandError as exc:
        logger.error(f"Git clone failed: {exc}", file=repo_url)
        raise RuntimeError(f"Failed to clone repository: {exc}") from exc
    return clone_path.resolve(), f"Cloned {repo_url} to {clone_path}"


def validate_local_repo_path(local_repo_path: Path, logger: NotebookLogger) -> Path:
    if not local_repo_path.exists():
        msg = f"Local repository path does not exist: {local_repo_path}"
        logger.error(msg, file=str(local_repo_path))
        raise FileNotFoundError(msg)
    if not local_repo_path.is_dir():
        msg = f"Local repository path is not a directory: {local_repo_path}"
        logger.error(msg, file=str(local_repo_path))
        raise NotADirectoryError(msg)
    package_json = local_repo_path / "package.json"
    if not package_json.exists():
        msg = f"package.json not found in local repository: {local_repo_path}"
        logger.error(msg, file=str(package_json))
        raise FileNotFoundError(msg)
    try:
        Repo(local_repo_path)
        logger.info("Validated Git repository.")
    except InvalidGitRepositoryError:
        logger.info("Path is not a Git repository; proceeding as source directory.")
    return local_repo_path.resolve()


def resolve_repository_path(
    use_git_url: bool,
    repo_url: str,
    local_repo_path: str | Path,
    workspace_dir: Path,
    if_clone_exists: str,
    logger: NotebookLogger,
) -> tuple[Path, str]:
    if use_git_url:
        return clone_or_reuse_repository(repo_url, workspace_dir, if_clone_exists, logger)
    return validate_local_repo_path(Path(local_repo_path), logger), f"Using local repository at {Path(local_repo_path).resolve()}"


def should_skip_path(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)


def discover_javascript_files(repo_path: Path) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for pattern in JS_GLOBS:
        for path in sorted(repo_path.rglob(pattern)):
            if should_skip_path(path):
                continue
            rel = path.relative_to(repo_path)
            rows.append(
                {
                    "file_path": str(rel).replace("\\", "/"),
                    "file_name": path.name,
                    "directory": str(rel.parent).replace("\\", "/") if rel.parent != Path(".") else ".",
                }
            )
    return pd.DataFrame(rows, columns=INVENTORY_COLUMNS)


def get_repository_commit(repo_path: Path) -> str:
    try:
        return Repo(repo_path).head.commit.hexsha
    except (InvalidGitRepositoryError, ValueError, TypeError):
        return "unknown"


def compute_repository_stats(repo_path: Path, inventory_df: pd.DataFrame) -> dict[str, Any]:
    js_files = inventory_df[inventory_df["file_name"].str.endswith((".js", ".mjs", ".cjs"), na=False)]
    total_size = sum(
        (repo_path / row["file_path"]).stat().st_size
        for _, row in js_files.iterrows()
        if (repo_path / row["file_path"]).exists()
    )
    directories = {str(Path(row["directory"])) for _, row in js_files.iterrows()}
    package_json = repo_path / "package.json"
    return {
        "repository_name": repo_path.name,
        "repository_size_bytes": total_size,
        "directory_count": len(directories),
        "javascript_file_count": len(js_files),
        "commit_hash": get_repository_commit(repo_path),
        "package_json_present": package_json.exists(),
    }


def npm_executable() -> str:
    for name in ("npm.cmd", "npm"):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    raise FileNotFoundError("npm not found on PATH")


def npx_command(*args: str) -> list[str]:
    for name in ("npx.cmd", "npx"):
        resolved = shutil.which(name)
        if resolved:
            return [resolved, *args]
    raise FileNotFoundError("npx not found on PATH")


def run_command(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env or os.environ.copy(),
        shell=False,
    )
    elapsed_ms = round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 2)
    return {
        "command": " ".join(command),
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
        "returncode": completed.returncode,
        "success": completed.returncode == 0,
        "elapsed_ms": elapsed_ms,
    }


def collect_prerequisite_versions() -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    def add(name: str, command: list[str]) -> None:
        result = run_command(command, Path.cwd())
        output = (result["stdout"] or result["stderr"]).strip()
        version = output.splitlines()[0] if output else ""
        rows.append({"component": name, "version": version, "status": "ok" if result["success"] else "error"})

    for name in ("node", "npm"):
        resolved = shutil.which(name) or shutil.which(f"{name}.cmd")
        if resolved:
            add(name, [resolved, "--version"])
        else:
            rows.append({"component": name, "version": "", "status": "missing"})

    try:
        add("npx eslint", npx_command("eslint", "--version"))
    except FileNotFoundError:
        rows.append({"component": "npx eslint", "version": "", "status": "missing"})

    for module_name in ("pandas", "git", "jupyter"):
        try:
            module = __import__(module_name)
            rows.append(
                {
                    "component": module_name,
                    "version": getattr(module, "__version__", "installed"),
                    "status": "ok",
                }
            )
        except ImportError:
            rows.append({"component": module_name, "version": "", "status": "missing"})
    return pd.DataFrame(rows)


def run_npm_install(repo_path: Path, logger: NotebookLogger) -> dict[str, Any]:
    if not (repo_path / "package.json").exists():
        msg = "package.json not found; cannot run npm install."
        logger.error(msg, file=str(repo_path / "package.json"))
        return {"success": False, "stdout": "", "stderr": msg, "returncode": 1, "elapsed_ms": 0}
    return run_command([npm_executable(), "install"], repo_path)


def discover_eslint_config(repo_path: Path) -> Path | None:
    for name in ESLINT_CONFIG_CANDIDATES:
        candidate = repo_path / name
        if candidate.exists():
            return candidate.resolve()

    package_json = repo_path / "package.json"
    if package_json.exists():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if isinstance(payload.get("eslintConfig"), dict):
            return package_json.resolve()
    return None


def verify_eslint_installation(repo_path: Path, logger: NotebookLogger) -> dict[str, Any]:
    local_eslint = repo_path / "node_modules" / ".bin" / "eslint"
    local_cmd = local_eslint.with_suffix(".cmd") if sys.platform.startswith("win") else local_eslint
    if local_cmd.exists() or local_eslint.exists():
        executable = local_cmd if local_cmd.exists() else local_eslint
        version_result = run_command([str(executable), "--version"], repo_path)
        return {
            "installed": True,
            "version": (version_result["stdout"] or version_result["stderr"]).strip(),
            "install_result": None,
        }

    version_result = run_command(npx_command("eslint", "--version"), repo_path)
    if version_result["success"]:
        return {
            "installed": True,
            "version": (version_result["stdout"] or version_result["stderr"]).strip(),
            "install_result": None,
        }

    logger.info("ESLint not found locally; installing with npm install --save-dev eslint")
    install_result = run_command([npm_executable(), "install", "--save-dev", "eslint"], repo_path)
    if not install_result["success"]:
        logger.error("Failed to install ESLint.", file=str(repo_path / "package.json"))
        return {"installed": False, "version": "", "install_result": install_result}

    version_result = run_command(npx_command("eslint", "--version"), repo_path)
    return {
        "installed": version_result["success"],
        "version": (version_result["stdout"] or version_result["stderr"]).strip(),
        "install_result": install_result,
    }


def has_lint_script(repo_path: Path) -> bool:
    package_json = repo_path / "package.json"
    if not package_json.exists():
        return False
    try:
        payload = json.loads(package_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    scripts = payload.get("scripts") or {}
    return bool(scripts.get("lint"))


def run_npm_lint(repo_path: Path, logger: NotebookLogger) -> dict[str, Any]:
    result = run_command([npm_executable(), "run", "lint"], repo_path)
    if result["returncode"] not in ESLINT_SUCCESS_CODES:
        logger.error(
            f"npm run lint failed with exit code {result['returncode']}.",
            file=str(repo_path / "package.json"),
        )
    return result


def run_eslint_json(repo_path: Path, logger: NotebookLogger) -> dict[str, Any]:
    result = run_command(npx_command("eslint", ".", "-f", "json"), repo_path)
    if result["returncode"] not in ESLINT_SUCCESS_CODES:
        logger.error(
            f"npx eslint . -f json failed with exit code {result['returncode']}.",
            file=str(repo_path),
        )
    result["success"] = result["returncode"] in ESLINT_SUCCESS_CODES
    return result


def combine_console_output(chunks: list[tuple[str, dict[str, Any]]]) -> str:
    parts: list[str] = []
    for label, result in chunks:
        parts.append(f"===== {label} =====")
        parts.append(f"command: {result.get('command', label)}")
        parts.append(f"exit_code: {result.get('returncode', '')}")
        parts.append(f"elapsed_ms: {result.get('elapsed_ms', '')}")
        parts.append("--- stdout ---")
        parts.append(result.get("stdout", ""))
        parts.append("--- stderr ---")
        parts.append(result.get("stderr", ""))
        parts.append("")
    return "\n".join(parts)


def parse_eslint_json(json_text: str) -> list[dict[str, Any]]:
    if not json_text.strip():
        return []
    payload = json.loads(json_text)
    if not isinstance(payload, list):
        raise ValueError("ESLint JSON output must be a list of file results.")
    return payload


def severity_label(value: Any) -> str:
    if value == 2 or str(value).lower() == "error":
        return "error"
    if value == 1 or str(value).lower() == "warning":
        return "warning"
    return str(value)


def build_rule_violations_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in records:
        file_path = record.get("filePath", "")
        for message in record.get("messages", []):
            if not isinstance(message, dict):
                continue
            rows.append(
                {
                    "file": file_path,
                    "rule_id": message.get("ruleId", ""),
                    "severity": severity_label(message.get("severity", "")),
                    "message": message.get("message", ""),
                    "line": message.get("line", ""),
                    "column": message.get("column", ""),
                    "endLine": message.get("endLine", ""),
                    "endColumn": message.get("endColumn", ""),
                    "nodeType": message.get("nodeType", ""),
                    "messageId": message.get("messageId", ""),
                    "fix_available": bool(message.get("fix")),
                }
            )
    return pd.DataFrame(rows, columns=VIOLATION_COLUMNS)


def build_file_summary_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in records:
        rows.append(
            {
                "file": record.get("filePath", ""),
                "total_errors": record.get("errorCount", 0),
                "total_warnings": record.get("warningCount", 0),
                "fixable_errors": record.get("fixableErrorCount", 0),
                "fixable_warnings": record.get("fixableWarningCount", 0),
            }
        )
    return pd.DataFrame(rows, columns=FILE_SUMMARY_COLUMNS)


def build_rule_frequency_dataframe(violations_df: pd.DataFrame) -> pd.DataFrame:
    if violations_df.empty:
        return pd.DataFrame(columns=RULE_FREQUENCY_COLUMNS)
    grouped = (
        violations_df.groupby(["rule_id", "severity"], dropna=False)
        .size()
        .reset_index(name="occurrence_count")
        .sort_values(["occurrence_count", "rule_id"], ascending=[False, True])
    )
    return grouped[RULE_FREQUENCY_COLUMNS]


def build_summary_dashboard(
    inventory_df: pd.DataFrame,
    violations_df: pd.DataFrame,
    records: list[dict[str, Any]],
    execution_status: str,
) -> dict[str, Any]:
    total_errors = sum(int(record.get("errorCount", 0) or 0) for record in records)
    total_warnings = sum(int(record.get("warningCount", 0) or 0) for record in records)
    fixable_errors = sum(int(record.get("fixableErrorCount", 0) or 0) for record in records)
    fixable_warnings = sum(int(record.get("fixableWarningCount", 0) or 0) for record in records)
    unique_rules = violations_df["rule_id"].nunique() if not violations_df.empty else 0
    return {
        "total_javascript_files": len(inventory_df),
        "total_violations": len(violations_df),
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "fixable_violations": fixable_errors + fixable_warnings,
        "unique_rules_triggered": unique_rules,
        "eslint_execution_status": execution_status,
    }


def collect_environment_json(
    repo_path: Path,
    eslint_version: str,
    eslint_config: Path | None,
) -> dict[str, Any]:
    node = shutil.which("node") or shutil.which("node.exe") or ""
    npm = shutil.which("npm") or shutil.which("npm.cmd") or ""
    node_version = run_command([node, "--version"], repo_path)["stdout"].strip() if node else ""
    npm_version = run_command([npm, "--version"], repo_path)["stdout"].strip() if npm else ""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "node_version": node_version,
        "npm_version": npm_version,
        "eslint_version": eslint_version,
        "eslint_config": str(eslint_config) if eslint_config else "",
        "platform": sys.platform,
        "repository": str(repo_path),
    }


def export_deliverables(
    output_dir: Path,
    inventory_df: pd.DataFrame,
    raw_json_text: str,
    violations_df: pd.DataFrame,
    file_summary_df: pd.DataFrame,
    rule_frequency_df: pd.DataFrame,
    console_output: str,
    eslint_json_result: dict[str, Any],
    execution_metadata: dict[str, Any],
    environment: dict[str, Any],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "raw_output": output_dir / "eslint_raw_output.json",
        "stdout": output_dir / "eslint_stdout.txt",
        "stderr": output_dir / "eslint_stderr.txt",
        "console": output_dir / "eslint_console_output.txt",
        "violations_csv": output_dir / "rule_violations_results.csv",
        "file_summary_csv": output_dir / "file_summary.csv",
        "rule_frequency_csv": output_dir / "rule_frequency.csv",
        "inventory_csv": output_dir / "javascript_files_inventory.csv",
        "execution_metadata": output_dir / "execution_metadata.json",
        "environment": output_dir / "environment.json",
    }
    paths["raw_output"].write_text(raw_json_text, encoding="utf-8")
    paths["stdout"].write_text(eslint_json_result.get("stdout", ""), encoding="utf-8")
    paths["stderr"].write_text(eslint_json_result.get("stderr", ""), encoding="utf-8")
    paths["console"].write_text(console_output, encoding="utf-8")
    inventory_df.to_csv(paths["inventory_csv"], index=False)
    violations_df.to_csv(paths["violations_csv"], index=False)
    file_summary_df.to_csv(paths["file_summary_csv"], index=False)
    rule_frequency_df.to_csv(paths["rule_frequency_csv"], index=False)
    paths["execution_metadata"].write_text(json.dumps(execution_metadata, indent=2, default=str), encoding="utf-8")
    paths["environment"].write_text(json.dumps(environment, indent=2), encoding="utf-8")
    return paths


def run_pipeline(
    metric_root: Path,
    *,
    use_git_url: bool,
    repo_url: str,
    local_repo_path: str,
    workspace_dir: Path,
    output_dir: Path,
    if_clone_exists: str,
    logger: NotebookLogger,
) -> dict[str, Any]:
    repo_path, clone_status = resolve_repository_path(
        use_git_url, repo_url, local_repo_path, workspace_dir, if_clone_exists, logger
    )
    inventory_df = discover_javascript_files(repo_path)
    repo_stats = compute_repository_stats(repo_path, inventory_df)

    npm_install_result = run_npm_install(repo_path, logger)
    if not npm_install_result["success"]:
        logger.error("npm install failed.", file=str(repo_path / "package.json"))

    eslint_config = discover_eslint_config(repo_path)
    eslint_verify: dict[str, Any] = {"installed": False, "version": "", "install_result": None}
    lint_script_result: dict[str, Any] | None = None
    eslint_json_result: dict[str, Any] = {
        "stdout": "[]",
        "stderr": "",
        "returncode": 1,
        "elapsed_ms": 0,
        "success": False,
    }
    records: list[dict[str, Any]] = []
    execution_status = "FAILED"

    if eslint_config is None:
        logger.error(
            "No ESLint configuration found. Stopping without modifying the repository.",
            file=str(repo_path),
        )
        execution_status = "MISSING_ESLINT_CONFIG"
    elif not npm_install_result["success"]:
        execution_status = "NPM_INSTALL_FAILED"
    else:
        eslint_verify = verify_eslint_installation(repo_path, logger)
        if eslint_verify.get("installed"):
            if has_lint_script(repo_path):
                lint_script_result = run_npm_lint(repo_path, logger)
            eslint_json_result = run_eslint_json(repo_path, logger)
            raw_text = eslint_json_result.get("stdout", "") or "[]"
            try:
                records = parse_eslint_json(raw_text)
                execution_status = "SUCCESS" if eslint_json_result["success"] else "ESLINT_FAILED"
            except (json.JSONDecodeError, ValueError) as exc:
                logger.error(f"Malformed ESLint JSON output: {exc}", file=str(output_dir / "eslint_raw_output.json"))
                execution_status = "MALFORMED_JSON"
        else:
            logger.error("ESLint installation verification failed.", file=str(repo_path))
            execution_status = "ESLINT_NOT_INSTALLED"

    violations_df = build_rule_violations_dataframe(records)
    file_summary_df = build_file_summary_dataframe(records)
    rule_frequency_df = build_rule_frequency_dataframe(violations_df)
    summary = build_summary_dashboard(inventory_df, violations_df, records, execution_status)
    environment = collect_environment_json(
        repo_path,
        str(eslint_verify.get("version", "")),
        eslint_config,
    )

    console_chunks: list[tuple[str, dict[str, Any]]] = [("npm install", npm_install_result)]
    if eslint_verify.get("install_result"):
        console_chunks.append(("npm install --save-dev eslint", eslint_verify["install_result"]))
    if lint_script_result is not None:
        console_chunks.append(("npm run lint", lint_script_result))
    console_chunks.append(("npx eslint . -f json", eslint_json_result))
    console_output = combine_console_output(console_chunks)

    execution_metadata = {
        "clone_status": clone_status,
        "repository_stats": repo_stats,
        "eslint_config": str(eslint_config) if eslint_config else "",
        "npm_install": npm_install_result,
        "eslint_verification": eslint_verify,
        "lint_script_result": lint_script_result,
        "eslint_json_result": eslint_json_result,
        "summary": summary,
    }

    raw_json_text = eslint_json_result.get("stdout", "") or "[]"
    exported_paths = export_deliverables(
        output_dir,
        inventory_df,
        raw_json_text,
        violations_df,
        file_summary_df,
        rule_frequency_df,
        console_output,
        eslint_json_result,
        execution_metadata,
        environment,
    )
    logger.write_errors()

    pipeline_success = execution_status == "SUCCESS" and bool(records or eslint_json_result["success"])
    return {
        "repo_path": repo_path,
        "clone_status": clone_status,
        "repo_stats": repo_stats,
        "eslint_config": eslint_config,
        "inventory_df": inventory_df,
        "npm_install_result": npm_install_result,
        "eslint_verify": eslint_verify,
        "lint_script_result": lint_script_result,
        "eslint_json_result": eslint_json_result,
        "records": records,
        "summary": summary,
        "exported_paths": exported_paths,
        "execution_status": execution_status,
        "pipeline_success": pipeline_success,
    }
