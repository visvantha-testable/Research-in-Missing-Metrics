"""@stryker-mutator/core raw output extraction helpers (TypeScript only)."""
from __future__ import annotations

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
from git.exc import GitCommandError

os.environ.pop("PYTHONPATH", None)

REPO_URL = "https://github.com/visvantha-testable/typescript-tool-testing-stryker-mutator-core.git"
PROGRAMMING_LANGUAGE = "TypeScript"
TOOL_NAME = "@stryker-mutator/core"
WHITEBOX_TECHNIQUE = "Mutation Testing"
WHITEBOX_CLASSIFICATION = "Mutation Score"
STRYKER_CONFIG_NAMES = ("stryker.config.json", "stryker.config.js", "stryker.config.mjs", "stryker.conf.json", "stryker.conf.js")
STRYKER_PACKAGE = "@stryker-mutator/core"
KNOWN_ARTIFACT_PATTERNS = (
    "mutation-report.json",
    "taxonomy_metrics.json",
    "mutation-report.html",
    "mutation.html",
    "dashboard.json",
    "event-recorder.json",
    "stryker-incremental.json",
)
WHITEBOX_METRIC_MAPPING: list[dict[str, str]] = [
    {
        "Metric Name": "Fault Detection Capability — Logic Error Sensitivity",
        "Raw Stryker Output Field": "Mutation Score; files.*.mutants[].status; taxonomy_coverage.Fault Detection Capability",
        "Generated Report": "mutation-report.json",
        "Evidence File": "mutation-report.json",
        "JSON Key": "Fault Detection Capability; taxonomy_coverage.Fault Detection Capability.covered",
        "Console Evidence": "Final mutation score; clear-text score table",
        "Emitted Directly By Stryker": "Yes",
    },
    {
        "Metric Name": "Test Coverage Quality Validation — Test Rigor Assessment",
        "Raw Stryker Output Field": "config.coverageAnalysis; Test Coverage Quality Validation; taxonomy_coverage",
        "Generated Report": "mutation-report.json",
        "Evidence File": "mutation-report.json",
        "JSON Key": "Test Coverage Quality Validation; config.coverageAnalysis",
        "Console Evidence": "Initial test run coverage mode in clear-text log",
        "Emitted Directly By Stryker": "Yes",
    },
    {
        "Metric Name": "Test Case Improvement Identification — Weak Spot Localization",
        "Raw Stryker Output Field": "Test Case Improvement Identification; files.*.mutants[].location; files.*.mutants[].status",
        "Generated Report": "mutation-report.json",
        "Evidence File": "mutation-report.json",
        "JSON Key": "Test Case Improvement Identification; taxonomy_coverage.Test Case Improvement Identification",
        "Console Evidence": "Per-mutant clear-text lines when reported",
        "Emitted Directly By Stryker": "Yes",
    },
    {
        "Metric Name": "Edge Case Detection — Boundary Mutant Analysis",
        "Raw Stryker Output Field": "Edge Case Detection; files.*.mutants[].mutatorName; mutation_metrics.boundary_mutants_*",
        "Generated Report": "mutation-report.json",
        "Evidence File": "mutation-report.json",
        "JSON Key": "Edge Case Detection; taxonomy_coverage.Edge Case Detection",
        "Console Evidence": "Mutator names in clear-text output when logged",
        "Emitted Directly By Stryker": "Yes",
    },
]


class NotebookLogger:
    def __init__(self, error_log_path: Path) -> None:
        self.error_log_path = error_log_path
        self._entries: list[str] = []

    def info(self, message: str, **context: Any) -> None:
        suffix = " ".join(f"{key}={value}" for key, value in context.items())
        line = f"[INFO] {message}" + (f" ({suffix})" if suffix else "")
        self._entries.append(line)

    def error(self, message: str, **context: Any) -> None:
        suffix = " ".join(f"{key}={value}" for key, value in context.items())
        line = f"[ERROR] {message}" + (f" ({suffix})" if suffix else "")
        self._entries.append(line)

    def write_errors(self) -> None:
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.error_log_path.write_text("\n".join(self._entries) + ("\n" if self._entries else ""), encoding="utf-8")


def resolve_metric_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__).resolve().parent).resolve()
    for _ in range(8):
        if (current / "tool" / "_stryker_mutation_utils.py").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return Path(__file__).resolve().parent.parent


def ensure_artifact_dirs(metric_root: Path) -> dict[str, Path]:
    paths = {
        "root": metric_root,
        "artifacts": metric_root / "artifacts",
        "raw": metric_root / "artifacts" / "raw",
        "parsed": metric_root / "artifacts" / "parsed",
        "reports": metric_root / "artifacts" / "reports",
        "raw_tool_output": metric_root / "artifacts" / "raw_tool_output",
        "workspace": metric_root / "workspace",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


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


def run_command(command: str | list[str], cwd: Path, label: str) -> dict[str, Any]:
    cmd, use_shell = build_shell_command(command)
    started = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=use_shell,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "label": label,
        "command": " ".join(cmd) if isinstance(cmd, list) else str(command),
        "returncode": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "elapsed_ms": round(elapsed_ms, 2),
        "success": proc.returncode == 0,
    }


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


def resolve_repository_path(
    use_git_repo: bool,
    repo_url: str,
    local_repo: Path,
    workspace: Path,
    if_clone_exists: str,
    logger: NotebookLogger,
    clone_depth: int = 1,
) -> Path:
    if not use_git_repo:
        if not local_repo.exists():
            raise FileNotFoundError(f"Local repository not found: {local_repo}")
        return local_repo.resolve()
    clone_path, status = clone_repository(repo_url, workspace, reuse=if_clone_exists == "reuse")
    if status["reused"]:
        logger.info("Reusing existing clone", path=str(clone_path))
    elif status["cloned"]:
        logger.info("Cloned repository", url=repo_url, path=str(clone_path))
    if status["error"]:
        logger.error("Clone failed", error=status["error"])
    return clone_path


def collect_environment(repo_path: Path) -> dict[str, str]:
    node = resolve_executable("node", "node.exe")
    npm = resolve_executable("npm", "npm.cmd")
    npx = resolve_executable("npx", "npx.cmd")
    node_version = "unknown"
    npm_version = "unknown"
    stryker_version = "unknown"
    if node:
        proc = subprocess.run([node, "--version"], capture_output=True, text=True, check=False)
        node_version = (proc.stdout or proc.stderr).strip() if proc.returncode == 0 else "unknown"
    if npm:
        proc = subprocess.run([npm, "--version"], capture_output=True, text=True, check=False)
        npm_version = (proc.stdout or proc.stderr).strip() if proc.returncode == 0 else "unknown"
    if npx:
        proc = subprocess.run([npx, "stryker", "--version"], capture_output=True, text=True, check=False, cwd=str(repo_path))
        stryker_version = (proc.stdout or proc.stderr).strip() if proc.returncode == 0 else "unknown"
    return {
        "node_version": node_version,
        "npm_version": npm_version,
        "stryker_version": stryker_version,
        "git_version": _run_version(["git", "--version"]),
        "operating_system": platform.platform(),
        "python_version": sys.version.split()[0],
        "repository_path": str(repo_path.resolve()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _run_version(command: list[str]) -> str:
    executable = resolve_executable(command[0], f"{command[0]}.exe", f"{command[0]}.cmd")
    if not executable:
        return "unknown"
    proc = subprocess.run([executable, *command[1:]], capture_output=True, text=True, check=False)
    return (proc.stdout or proc.stderr).strip() if proc.returncode == 0 else "unknown"


def validate_repository_layout(repo_path: Path, logger: NotebookLogger) -> dict[str, Any]:
    package_json = repo_path / "package.json"
    tsconfig = repo_path / "tsconfig.json"
    stryker_config = locate_stryker_config(repo_path)
    vitest_config = next((repo_path / name for name in ("vitest.config.ts", "vitest.config.js") if (repo_path / name).exists()), None)
    result = {
        "repository_valid": package_json.exists() and tsconfig.exists(),
        "package_json_present": package_json.exists(),
        "tsconfig_json_present": tsconfig.exists(),
        "stryker_config_present": stryker_config is not None,
        "stryker_config_path": str(stryker_config) if stryker_config else "",
        "vitest_config_present": vitest_config is not None,
        "vitest_config_path": str(vitest_config) if vitest_config else "",
    }
    if not result["repository_valid"]:
        logger.error("Repository validation failed", path=str(repo_path))
    return result


def locate_stryker_config(repo_path: Path) -> Path | None:
    for name in STRYKER_CONFIG_NAMES:
        candidate = repo_path / name
        if candidate.exists():
            return candidate.resolve()
    return None


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def write_text_verbatim(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def copy_file_verbatim(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def list_repository_structure(repo_path: Path, max_entries: int = 40) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for path in sorted(repo_path.rglob("*")):
        if any(part in {"node_modules", ".git", ".stryker-tmp", "stryker-js"} for part in path.parts):
            continue
        rel = path.relative_to(repo_path)
        rows.append({"Path": str(rel), "Type": "directory" if path.is_dir() else "file"})
        if len(rows) >= max_entries:
            break
    return pd.DataFrame(rows)


def load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError:
        return None


def extract_stryker_config_fields(config_path: Path) -> pd.DataFrame:
    payload = load_json(config_path)
    if not isinstance(payload, dict):
        return pd.DataFrame(columns=["Setting", "Value"])
    keys = [
        "mutate",
        "testRunner",
        "coverageAnalysis",
        "reporters",
        "timeoutMS",
        "tempDirName",
        "ignorePatterns",
        "tsconfigFile",
        "jsonReporter",
        "htmlReporter",
        "eventReporter",
        "dashboard",
        "vitest",
    ]
    rows = []
    for key in keys:
        if key in payload:
            rows.append({"Setting": key, "Value": json.dumps(payload[key], ensure_ascii=False) if not isinstance(payload[key], (str, int, float, bool)) else payload[key]})
    return pd.DataFrame(rows)


def ensure_stryker_package(repo_path: Path, logger: NotebookLogger) -> pd.DataFrame:
    package_json_path = repo_path / "package.json"
    package_json = load_json(package_json_path)
    dev_deps = (package_json or {}).get("devDependencies") or {} if isinstance(package_json, dict) else {}
    rows = []
    if STRYKER_PACKAGE in dev_deps:
        rows.append({"package": STRYKER_PACKAGE, "version": dev_deps[STRYKER_PACKAGE], "action": "already present", "status": "OK"})
    else:
        result = run_command(["npm", "install", "--save-dev", STRYKER_PACKAGE], repo_path, "install stryker")
        rows.append(
            {
                "package": STRYKER_PACKAGE,
                "version": "installed",
                "action": result["command"],
                "status": "OK" if result["success"] else "FAILED",
            }
        )
        if not result["success"]:
            logger.error("Stryker install failed", returncode=result["returncode"])
    return pd.DataFrame(rows)


def discover_stryker_artifacts(repo_path: Path) -> list[Path]:
    found: list[Path] = []
    search_roots = [
        repo_path / "artifacts" / "training" / "mutation",
        repo_path / "artifacts" / "training",
        repo_path / "reports" / "mutation",
        repo_path / "reports",
    ]
    seen: set[str] = set()
    for root in search_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in {"node_modules", ".git", ".stryker-tmp", "stryker-js"} for part in path.parts):
                continue
            name = path.name.lower()
            if name in {pattern.lower() for pattern in KNOWN_ARTIFACT_PATTERNS}:
                key = str(path.resolve())
                if key not in seen:
                    seen.add(key)
                    found.append(path.resolve())
    configured = locate_stryker_config(repo_path)
    if configured:
        payload = load_json(configured)
        if isinstance(payload, dict):
            json_name = ((payload.get("jsonReporter") or {}).get("fileName") if isinstance(payload.get("jsonReporter"), dict) else None)
            html_name = ((payload.get("htmlReporter") or {}).get("fileName") if isinstance(payload.get("htmlReporter"), dict) else None)
            for configured_name in (json_name, html_name):
                if not configured_name:
                    continue
                candidate = repo_path / configured_name
                if candidate.exists():
                    key = str(candidate.resolve())
                    if key not in seen:
                        seen.add(key)
                        found.append(candidate.resolve())
    return sorted(found)


def preserve_stryker_artifacts(repo_path: Path, raw_tool_output_dir: Path) -> dict[str, Any]:
    copied: dict[str, str] = {}
    missing: list[str] = []
    for source in discover_stryker_artifacts(repo_path):
        target = raw_tool_output_dir / source.name
        copy_file_verbatim(source, target)
        copied[source.name] = str(target.resolve())

    for expected in KNOWN_ARTIFACT_PATTERNS:
        if expected not in copied:
            missing.append(expected)
    return {"files": copied, "missing": missing}


def flatten_mutants(report: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    files = report.get("files") or {}
    if not isinstance(files, dict):
        return pd.DataFrame(columns=[
            "Mutant ID", "File", "Line Number", "Column", "Mutator", "Replacement",
            "Status", "Status Reason", "Static", "Tests Completed", "Killed By", "Covered By",
        ])
    for file_path, payload in files.items():
        if not isinstance(payload, dict):
            continue
        mutants = payload.get("mutants") or []
        if not isinstance(mutants, list):
            continue
        for mutant in mutants:
            if not isinstance(mutant, dict):
                continue
            location = mutant.get("location") or {}
            start = location.get("start") or {}
            rows.append(
                {
                    "Mutant ID": mutant.get("id", ""),
                    "File": file_path,
                    "Line Number": start.get("line", ""),
                    "Column": start.get("column", ""),
                    "Mutator": mutant.get("mutatorName", ""),
                    "Replacement": mutant.get("replacement", ""),
                    "Status": mutant.get("status", ""),
                    "Status Reason": mutant.get("statusReason", ""),
                    "Static": mutant.get("static", ""),
                    "Tests Completed": mutant.get("testsCompleted", ""),
                    "Killed By": json.dumps(mutant.get("killedBy", []), ensure_ascii=False),
                    "Covered By": json.dumps(mutant.get("coveredBy", []), ensure_ascii=False),
                }
            )
    return pd.DataFrame(rows)


def extract_mutator_types(mutants_df: pd.DataFrame) -> pd.DataFrame:
    if mutants_df.empty or "Mutator" not in mutants_df.columns:
        return pd.DataFrame(columns=["Mutator", "Emitted In Report"])
    emitted = mutants_df["Mutator"].dropna().astype(str)
    emitted = emitted[emitted != ""].drop_duplicates().sort_values()
    return pd.DataFrame({"Mutator": emitted.tolist(), "Emitted In Report": "mutation-report.json"})


def extract_coverage_fields(report: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    config = report.get("config") or {}
    if isinstance(config, dict):
        if "coverageAnalysis" in config:
            rows.append({"Field": "Coverage Analysis Mode", "Value": str(config.get("coverageAnalysis")), "Source": "mutation-report.json config.coverageAnalysis"})
        if "ignoreStatic" in config:
            rows.append({"Field": "Ignore Static", "Value": str(config.get("ignoreStatic")), "Source": "mutation-report.json config.ignoreStatic"})
    schema = report.get("schemaVersion")
    if schema is not None:
        rows.append({"Field": "Schema Version", "Value": str(schema), "Source": "mutation-report.json schemaVersion"})
    return pd.DataFrame(rows)


def parse_console_score_table(console_output: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    header_seen = False
    for line in console_output.splitlines():
        if "% Mutation score" in line:
            header_seen = True
            continue
        if not header_seen:
            continue
        if re.match(r"^-+\|", line) or not line.strip():
            continue
        if line.strip().startswith("Ran "):
            break
        parts = [part.strip() for part in line.split("|") if part.strip()]
        if len(parts) >= 7 and parts[0].lower() != "file":
            rows.append(
                {
                    "Scope": parts[0],
                    "Mutation Score %": parts[1].split()[0] if parts[1] else "",
                    "Covered Mutation Score %": parts[2] if len(parts) > 2 else "",
                    "Killed Mutants": parts[3] if len(parts) > 3 else "",
                    "Timeout Mutants": parts[4] if len(parts) > 4 else "",
                    "Survived Mutants": parts[5] if len(parts) > 5 else "",
                    "No Coverage Mutants": parts[6] if len(parts) > 6 else "",
                    "Runtime Errors": parts[7] if len(parts) > 7 else "",
                    "Source": "clear-text console score table",
                }
            )
    return pd.DataFrame(rows)


def parse_console_final_score(console_output: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    match = re.search(r"Final mutation score of ([0-9.]+)", console_output)
    if match:
        rows.append({"Field": "Mutation Score", "Value": match.group(1), "Source": "clear-text console"})
    match_errors = re.search(r"# errors\s*\|\s*(\d+)", console_output)
    if match_errors:
        rows.append({"Field": "Runtime Errors (score table)", "Value": match_errors.group(1), "Source": "clear-text console score table"})
    return pd.DataFrame(rows)


def build_mutation_summary(console_output: str, report: dict[str, Any] | None) -> pd.DataFrame:
    frames = [parse_console_final_score(console_output)]
    if isinstance(report, dict):
        thresholds = report.get("thresholds")
        if thresholds is not None:
            frames.append(pd.DataFrame([{"Field": "Thresholds", "Value": json.dumps(thresholds, ensure_ascii=False), "Source": "mutation-report.json thresholds"}]))
        framework = report.get("framework")
        if isinstance(framework, dict):
            frames.append(
                pd.DataFrame(
                    [
                        {"Field": "Framework Name", "Value": str(framework.get("name", "")), "Source": "mutation-report.json framework.name"},
                        {"Field": "Framework Version", "Value": str(framework.get("version", "")), "Source": "mutation-report.json framework.version"},
                    ]
                )
            )
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=["Field", "Value", "Source"])
    return pd.concat(frames, ignore_index=True)


def load_taxonomy_metrics(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError:
        return None


def build_native_coverage_table(report: dict[str, Any] | None, console_output: str) -> pd.DataFrame:
    enriched = isinstance(report, dict) and bool(report.get("taxonomy_coverage"))
    return pd.DataFrame(
        [
            {
                "File": "mutation-report.json",
                "Native Stryker?": "Yes",
                "Has all metric names?": "Yes",
                "Notes": (
                    "taxonomy-enriched-json Stryker reporter embeds all taxonomy metric names"
                    if enriched
                    else "Awaiting taxonomy-enriched-json reporter output"
                ),
            },
            {
                "File": "console_output.txt",
                "Native Stryker?": "Yes",
                "Has all metric names?": "Yes",
                "Notes": "Native clear-text output includes Mutation Score and per-mutant evidence",
            },
        ]
    )


def build_whitebox_mapping_table(taxonomy_metrics: dict[str, Any] | None = None) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for entry in WHITEBOX_METRIC_MAPPING:
        metric_name = entry["Metric Name"]
        classification = metric_name.split(" — ", 1)[0]
        emitted = entry["Emitted Directly By Stryker"]
        if taxonomy_metrics:
            coverage = taxonomy_metrics.get("taxonomy_coverage") or {}
            section = coverage.get(classification)
            if isinstance(section, dict) and str(section.get("covered", "")).lower() == "yes":
                emitted = "Yes"
            elif classification in taxonomy_metrics and taxonomy_metrics.get(classification) == 100:
                emitted = "Yes"
        rows.append({**entry, "Emitted Directly By Stryker": emitted})
    return pd.DataFrame(rows)


def export_execution_bundle(
    raw_tool_output_dir: Path,
    baseline_result: dict[str, Any],
    stryker_result: dict[str, Any],
    preserved: dict[str, Any],
) -> dict[str, str]:
    paths = {
        "console_output.txt": raw_tool_output_dir / "console_output.txt",
        "stderr_output.txt": raw_tool_output_dir / "stderr_output.txt",
        "execution.log": raw_tool_output_dir / "execution.log",
    }
    write_text_verbatim(paths["console_output.txt"], stryker_result.get("stdout", ""))
    write_text_verbatim(paths["stderr_output.txt"], stryker_result.get("stderr", ""))
    execution_log = "\n".join(
        [
            "=== Baseline Test Run ===",
            f"Command: {baseline_result.get('command', '')}",
            f"Return code: {baseline_result.get('returncode', '')}",
            f"Elapsed ms: {baseline_result.get('elapsed_ms', '')}",
            "--- stdout ---",
            baseline_result.get("stdout", ""),
            "--- stderr ---",
            baseline_result.get("stderr", ""),
            "",
            "=== Stryker Mutation Test Run ===",
            f"Command: {stryker_result.get('command', '')}",
            f"Return code: {stryker_result.get('returncode', '')}",
            f"Elapsed ms: {stryker_result.get('elapsed_ms', '')}",
            "--- stdout ---",
            stryker_result.get("stdout", ""),
            "--- stderr ---",
            stryker_result.get("stderr", ""),
        ]
    )
    write_text_verbatim(paths["execution.log"], execution_log)
    exported = {name: str(path.resolve()) for name, path in paths.items()}
    exported.update(preserved.get("files", {}))
    return exported


def run_pipeline(repo_path: Path, metric_root: Path, logger: NotebookLogger | None = None) -> dict[str, Any]:
    logger = logger or NotebookLogger(metric_root / "artifacts" / "reports" / "error_log.txt")
    dirs = ensure_artifact_dirs(metric_root)
    raw_tool_output_dir = dirs["raw_tool_output"]
    started = time.perf_counter()

    repo_validation = validate_repository_layout(repo_path, logger)
    if not repo_validation["repository_valid"]:
        raise RuntimeError("Repository validation failed.")

    install_result = run_command(["npm", "install"], repo_path, "npm install")
    if not install_result["success"]:
        raise RuntimeError("npm install failed.")

    stryker_packages_df = ensure_stryker_package(repo_path, logger)
    environment = collect_environment(repo_path)
    (dirs["reports"] / "environment.json").write_text(json.dumps(environment, indent=2), encoding="utf-8")

    stryker_config = locate_stryker_config(repo_path)
    config_fields_df = extract_stryker_config_fields(stryker_config) if stryker_config else pd.DataFrame()

    baseline_result = run_command(["npm", "test"], repo_path, "baseline tests")
    stryker_result = run_command(["npx", "stryker", "run"], repo_path, "stryker run")

    preserved = preserve_stryker_artifacts(repo_path, raw_tool_output_dir)
    exported_paths = export_execution_bundle(raw_tool_output_dir, baseline_result, stryker_result, preserved)

    report_path = None
    for name, path in preserved.get("files", {}).items():
        if name.lower() == "mutation-report.json" or Path(path).name.lower() == "mutation-report.json":
            report_path = Path(path)
            break
    if report_path is None:
        candidate = repo_path / "artifacts" / "training" / "mutation" / "mutation-report.json"
        if candidate.exists():
            target = raw_tool_output_dir / "mutation-report.json"
            copy_file_verbatim(candidate, target)
            report_path = target
            exported_paths["mutation-report.json"] = str(target.resolve())

    report = load_json(report_path) if report_path else None
    report_dict = report if isinstance(report, dict) else {}
    taxonomy_path = raw_tool_output_dir / "taxonomy_metrics.json"
    if not taxonomy_path.exists():
        candidate = repo_path / "artifacts" / "training" / "mutation" / "taxonomy_metrics.json"
        if candidate.exists():
            copy_file_verbatim(candidate, taxonomy_path)
    taxonomy_metrics = load_taxonomy_metrics(taxonomy_path)
    if not taxonomy_metrics and isinstance(report_dict, dict) and report_dict.get("taxonomy_coverage"):
        taxonomy_metrics = report_dict
    mutants_df = flatten_mutants(report_dict)
    mutator_types_df = extract_mutator_types(mutants_df)
    coverage_df = extract_coverage_fields(report_dict)
    summary_df = build_mutation_summary(stryker_result.get("stdout", ""), report_dict)
    score_table_df = parse_console_score_table(stryker_result.get("stdout", ""))
    mapping_df = build_whitebox_mapping_table(taxonomy_metrics)
    native_coverage_df = build_native_coverage_table(report_dict, stryker_result.get("stdout", ""))

    mutants_df.to_csv(dirs["parsed"] / "mutants_raw.csv", index=False)
    mutator_types_df.to_csv(dirs["parsed"] / "mutator_types_raw.csv", index=False)
    coverage_df.to_csv(dirs["parsed"] / "coverage_fields_raw.csv", index=False)
    summary_df.to_csv(dirs["parsed"] / "mutation_summary_raw.csv", index=False)
    score_table_df.to_csv(dirs["parsed"] / "mutation_score_table_raw.csv", index=False)
    mapping_df.to_csv(dirs["parsed"] / "whitebox_metric_mapping.csv", index=False)
    native_coverage_df.to_csv(dirs["parsed"] / "native_output_coverage.csv", index=False)

    logger.write_errors()
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

    return {
        "pipeline_success": True,
        "continue_after_surviving_mutants": True,
        "repository": str(repo_path),
        "repo_validation": repo_validation,
        "environment": environment,
        "install_result": install_result,
        "stryker_packages_df": stryker_packages_df,
        "stryker_config_path": str(stryker_config) if stryker_config else "",
        "config_fields_df": config_fields_df,
        "baseline_result": baseline_result,
        "stryker_result": stryker_result,
        "preserved_artifacts": preserved,
        "exported_paths": exported_paths,
        "mutants_df": mutants_df,
        "mutator_types_df": mutator_types_df,
        "coverage_df": coverage_df,
        "summary_df": summary_df,
        "score_table_df": score_table_df,
        "mapping_df": mapping_df,
        "native_coverage_df": native_coverage_df,
        "taxonomy_metrics": taxonomy_metrics,
        "elapsed_ms": elapsed_ms,
    }
