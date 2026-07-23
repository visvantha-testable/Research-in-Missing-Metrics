"""@stryker-mutator/core raw output extraction for vitest-coverage-v8 metrics."""
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

REPO_URL = "https://github.com/visvantha-testable/typescript-tool-testing-vitest-coverage-v8.git"
PROGRAMMING_LANGUAGE = "TypeScript"
TOOL_NAME = "@stryker-mutator/core"
TEST_FRAMEWORK = "Vitest"
COVERAGE_PROVIDER = "@vitest/coverage-v8"
ANALYSIS_TYPE = "Mutation Testing"
STRYKER_CONFIG_NAMES = ("stryker.config.json", "stryker.config.js", "stryker.config.mjs", "stryker.conf.json", "stryker.conf.js")
REQUIRED_PACKAGES = ("vitest", "@vitest/coverage-v8", "@stryker-mutator/core", "@stryker-mutator/vitest-runner", "typescript")
KNOWN_ARTIFACT_PATTERNS = (
    "mutation-report.json",
    "mutation-report.html",
    "mutation.html",
    "dashboard.json",
    "event-recorder.json",
    "stryker-incremental.json",
)

METRIC_DEFINITIONS: list[dict[str, Any]] = [
    {
        "tool": TOOL_NAME,
        "metric": "Boundary Failure Identification",
        "classification": "Fault Detection Capability",
        "technique": "Mutation Testing",
        "mutator_patterns": [
            r"EqualityOperator",
            r"RelationalOperator",
            r"ConditionalExpression",
            r"UpdateOperator",
            r"UnaryOperator",
            r"AssignmentOperator",
        ],
        "replacement_patterns": [r"[<>=!]=?", r"\+\+|--"],
    },
    {
        "tool": TOOL_NAME,
        "metric": "Branch Misdirection Discovery",
        "classification": "Logic Verification",
        "technique": "Mutation Testing",
        "mutator_patterns": [
            r"ConditionalExpression",
            r"LogicalOperator",
            r"BlockStatement",
            r"BooleanLiteral",
            r"MethodExpression",
            r"ArithmeticOperator",
        ],
        "replacement_patterns": [],
    },
    {
        "tool": TOOL_NAME,
        "metric": "Discovery Power Assessment",
        "classification": "Test Effectiveness Assessment",
        "technique": "Mutation Testing",
        "mutator_patterns": [r".*"],
        "statuses": ["Killed", "Timeout"],
        "replacement_patterns": [],
    },
]

MUTANTS_COLUMNS = [
    "Mutant ID",
    "Source File",
    "Mutator Name",
    "Mutation Type",
    "Original Code",
    "Mutated Code",
    "Status",
    "Replacement",
    "Line Number",
    "Start Column",
    "End Column",
    "End Line",
    "Duration",
    "Covered By Tests",
    "Killing Test",
    "Status Reason",
]


class NotebookLogger:
    def __init__(self, error_log_path: Path) -> None:
        self.error_log_path = error_log_path
        self._entries: list[str] = []

    def info(self, message: str, **context: Any) -> None:
        suffix = " ".join(f"{key}={value}" for key, value in context.items())
        self._entries.append(f"[INFO] {message}" + (f" ({suffix})" if suffix else ""))

    def error(self, message: str, **context: Any) -> None:
        suffix = " ".join(f"{key}={value}" for key, value in context.items())
        self._entries.append(f"[ERROR] {message}" + (f" ({suffix})" if suffix else ""))

    def write_errors(self) -> None:
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.error_log_path.write_text("\n".join(self._entries) + ("\n" if self._entries else ""), encoding="utf-8")


def resolve_metric_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__).resolve().parent).resolve()
    for _ in range(8):
        if (current / "tool" / "_stryker_vitest_coverage_utils.py").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return Path(__file__).resolve().parent.parent


def ensure_output_dirs(metric_root: Path) -> dict[str, Path]:
    paths = {
        "root": metric_root,
        "output": metric_root / "output",
        "raw": metric_root / "output" / "raw",
        "parsed": metric_root / "output" / "parsed",
        "reports": metric_root / "output" / "reports",
        "temp": metric_root / "output" / "temp",
        "workspace": metric_root / "workspace",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def copy_file_verbatim(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() == destination.resolve():
        return
    shutil.copy2(source, destination)


def resolve_executable(*names: str) -> str | None:
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return None


def build_shell_command(command: list[str]) -> tuple[list[str], bool]:
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


def run_command(command: list[str], cwd: Path, label: str) -> dict[str, Any]:
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
    return {
        "label": label,
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
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


def list_repository_structure(repo_path: Path, max_entries: int = 80) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    skip = {".git", "node_modules", ".stryker-tmp", "vitest", "knip", "coverage", "dist"}
    for path in sorted(repo_path.rglob("*")):
        if any(part in skip for part in path.parts):
            continue
        rel = path.relative_to(repo_path)
        rows.append({"path": str(rel), "type": "dir" if path.is_dir() else "file"})
        if len(rows) >= max_entries:
            break
    return pd.DataFrame(rows)


def collect_prerequisite_versions() -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    def add(name: str, command: list[str]) -> None:
        result = run_command(command, Path.cwd(), name)
        version = (result["stdout"] or result["stderr"]).strip().splitlines()
        rows.append(
            {
                "Dependency": name,
                "Available": "Yes" if result["success"] else "No",
                "Version Output": version[0] if version else result["stderr"].strip() or "Not found",
            }
        )

    add("Git", ["git", "--version"])
    add("Node.js", ["node", "--version"])
    add("npm", ["npm", "--version"])
    add("Python", [sys.executable, "--version"])
    add("pandas", [sys.executable, "-c", "import pandas; print(pandas.__version__)"])
    add("tabulate", [sys.executable, "-c", "import tabulate; print(tabulate.__version__)"])
    return pd.DataFrame(rows)


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(read_text(path))
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        return None


def locate_stryker_config(repo_path: Path) -> Path | None:
    for name in STRYKER_CONFIG_NAMES:
        candidate = repo_path / name
        if candidate.exists():
            return candidate.resolve()
    return None


def generate_temp_stryker_config(temp_dir: Path) -> Path:
    config = {
        "$schema": "./node_modules/@stryker-mutator/core/schema/stryker-schema.json",
        "packageManager": "npm",
        "plugins": ["@stryker-mutator/vitest-runner"],
        "testRunner": "vitest",
        "reporters": ["json", "clear-text"],
        "jsonReporter": {"fileName": "artifacts/training/mutation/mutation-report.json"},
        "coverageAnalysis": "perTest",
        "mutate": ["sample_subject/src/**/*.ts", "!sample_subject/src/index.ts"],
        "vitest": {"configFile": "vitest.stryker.config.ts"},
        "thresholds": {"high": 80, "break": 70, "low": 60},
        "timeoutMS": 60000,
        "concurrency": 2,
    }
    path = temp_dir / "stryker.config.generated.json"
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path


def resolve_stryker_config(repo_path: Path, temp_dir: Path) -> tuple[Path, bool]:
    existing = locate_stryker_config(repo_path)
    if existing:
        return existing, False
    return generate_temp_stryker_config(temp_dir), True


def verify_required_packages(repo_path: Path, logger: NotebookLogger) -> pd.DataFrame:
    package_json = load_json(repo_path / "package.json") or {}
    dev_deps = package_json.get("devDependencies") or {}
    deps = package_json.get("dependencies") or {}
    all_deps = {**deps, **dev_deps}
    rows: list[dict[str, str]] = []
    missing: list[str] = []
    for package in REQUIRED_PACKAGES:
        if package in all_deps:
            rows.append({"Package": package, "Status": "installed", "Version": str(all_deps[package]), "Action": "verified"})
        else:
            missing.append(package)
            rows.append({"Package": package, "Status": "missing", "Version": "", "Action": "pending install"})
    if "@stryker-mutator/core" in missing or "@stryker-mutator/vitest-runner" in missing:
        result = run_command(
            ["npm", "install", "--save-dev", "@stryker-mutator/core", "@stryker-mutator/vitest-runner"],
            repo_path,
            "install stryker packages",
        )
        if not result["success"]:
            logger.error("Stryker package install failed")
        package_json = load_json(repo_path / "package.json") or {}
        dev_deps = package_json.get("devDependencies") or {}
        for package in ("@stryker-mutator/core", "@stryker-mutator/vitest-runner"):
            if package in dev_deps:
                for row in rows:
                    if row["Package"] == package:
                        row["Status"] = "installed"
                        row["Version"] = str(dev_deps[package])
                        row["Action"] = result["command"]
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
            if any(part in {"node_modules", ".git", ".stryker-tmp"} for part in path.parts):
                continue
            if path.name.lower() in {pattern.lower() for pattern in KNOWN_ARTIFACT_PATTERNS}:
                key = str(path.resolve())
                if key not in seen:
                    seen.add(key)
                    found.append(path.resolve())
    configured = locate_stryker_config(repo_path)
    if configured:
        payload = load_json(configured)
        if payload:
            for key in ("jsonReporter", "htmlReporter"):
                reporter = payload.get(key)
                if isinstance(reporter, dict) and reporter.get("fileName"):
                    candidate = repo_path / str(reporter["fileName"])
                    if candidate.exists():
                        resolved = str(candidate.resolve())
                        if resolved not in seen:
                            seen.add(resolved)
                            found.append(candidate.resolve())
    return sorted(found)


def preserve_stryker_artifacts(repo_path: Path, raw_dir: Path) -> dict[str, str]:
    copied: dict[str, str] = {}
    for source in discover_stryker_artifacts(repo_path):
        target = raw_dir / source.name
        copy_file_verbatim(source, target)
        copied[source.name] = str(target.resolve())
    return copied


def _killing_test(mutant: dict[str, Any]) -> str:
    killed_by = mutant.get("killedBy") or []
    if isinstance(killed_by, list) and killed_by:
        first = killed_by[0]
        if isinstance(first, dict):
            return str(first.get("name") or first.get("id") or json.dumps(first, ensure_ascii=False))
        return str(first)
    return ""


def flatten_mutants(report: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    files = report.get("files") or {}
    if not isinstance(files, dict):
        return pd.DataFrame(columns=MUTANTS_COLUMNS)
    for file_path, payload in files.items():
        if not isinstance(payload, dict):
            continue
        for mutant in payload.get("mutants") or []:
            if not isinstance(mutant, dict):
                continue
            location = mutant.get("location") or {}
            start = location.get("start") or {}
            end = location.get("end") or {}
            replacement = str(mutant.get("replacement") or "")
            rows.append(
                {
                    "Mutant ID": mutant.get("id", ""),
                    "Source File": file_path,
                    "Mutator Name": mutant.get("mutatorName", ""),
                    "Mutation Type": mutant.get("mutatorName", ""),
                    "Original Code": mutant.get("originalLines", mutant.get("original", "")),
                    "Mutated Code": replacement,
                    "Status": mutant.get("status", ""),
                    "Replacement": replacement,
                    "Line Number": start.get("line", ""),
                    "Start Column": start.get("column", ""),
                    "End Column": end.get("column", ""),
                    "End Line": end.get("line", ""),
                    "Duration": mutant.get("duration", mutant.get("testDuration", "")),
                    "Covered By Tests": json.dumps(mutant.get("coveredBy", []), ensure_ascii=False),
                    "Killing Test": _killing_test(mutant),
                    "Status Reason": mutant.get("statusReason", ""),
                }
            )
    return pd.DataFrame(rows, columns=MUTANTS_COLUMNS)


def count_mutant_statuses(mutants_df: pd.DataFrame) -> dict[str, int]:
    if mutants_df.empty or "Status" not in mutants_df.columns:
        return {}
    return mutants_df["Status"].value_counts(dropna=False).astype(int).to_dict()


def parse_mutation_score(console_output: str, mutants_df: pd.DataFrame) -> float | None:
    match = re.search(r"Final mutation score of ([0-9.]+)", console_output)
    if match:
        return float(match.group(1))
    if mutants_df.empty:
        return None
    valid_statuses = {"Killed", "Survived", "Timeout", "RuntimeError"}
    subset = mutants_df[mutants_df["Status"].isin(valid_statuses)]
    if subset.empty:
        return None
    detected = len(subset[subset["Status"].isin(["Killed", "Timeout"])])
    return round((detected / len(subset)) * 100, 2)


def _mutant_matches_metric(row: pd.Series, metric: dict[str, Any]) -> bool:
    mutator = str(row.get("Mutator Name", ""))
    replacement = str(row.get("Replacement", ""))
    status = str(row.get("Status", ""))
    statuses = metric.get("statuses")
    if statuses and status not in statuses:
        return False
    mutator_match = any(re.search(pattern, mutator) for pattern in metric.get("mutator_patterns", []))
    replacement_match = any(re.search(pattern, replacement) for pattern in metric.get("replacement_patterns", []))
    if metric.get("replacement_patterns"):
        return mutator_match or replacement_match
    return mutator_match


def build_metric_mappings(mutants_df: pd.DataFrame) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    for metric in METRIC_DEFINITIONS:
        if mutants_df.empty:
            mappings.append(
                {
                    **metric,
                    "supporting_mutant_ids": [],
                    "supporting_mutators": [],
                    "supporting_files": [],
                    "supporting_statuses": [],
                    "supporting_findings_count": 0,
                    "evidence_status": "No evidence found in the current mutation testing analysis.",
                    "rationale": "No mutation report records were available.",
                    "evidence_rows": [],
                }
            )
            continue
        mask = mutants_df.apply(lambda row: _mutant_matches_metric(row, metric), axis=1)
        evidence_df = mutants_df[mask].copy()
        if evidence_df.empty:
            mappings.append(
                {
                    **metric,
                    "supporting_mutant_ids": [],
                    "supporting_mutators": [],
                    "supporting_files": [],
                    "supporting_statuses": [],
                    "supporting_findings_count": 0,
                    "evidence_status": "No evidence found in the current mutation testing analysis.",
                    "rationale": "No mutants in the Stryker JSON report matched this metric mapping rules.",
                    "evidence_rows": [],
                }
            )
            continue
        sample = evidence_df.iloc[0]
        mappings.append(
            {
                **metric,
                "supporting_mutant_ids": evidence_df["Mutant ID"].astype(str).tolist(),
                "supporting_mutators": sorted(evidence_df["Mutator Name"].dropna().astype(str).unique().tolist()),
                "supporting_files": sorted(evidence_df["Source File"].dropna().astype(str).unique().tolist()),
                "supporting_statuses": sorted(evidence_df["Status"].dropna().astype(str).unique().tolist()),
                "supporting_findings_count": int(len(evidence_df)),
                "evidence_status": "Evidence found in mutation-report.json.",
                "rationale": (
                    f"Mutant `{sample['Mutant ID']}` using `{sample['Mutator Name']}` in `{sample['Source File']}` "
                    f"at line {sample['Line Number']} has status `{sample['Status']}`."
                ),
                "evidence_rows": evidence_df.to_dict(orient="records"),
            }
        )
    return mappings


def build_evidence_table(metric_mappings: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for mapping in metric_mappings:
        evidence_rows = mapping.get("evidence_rows") or []
        if not evidence_rows:
            rows.append(
                {
                    "Tool": mapping["tool"],
                    "Metric": mapping["metric"],
                    "Classification": mapping["classification"],
                    "Technique": mapping["technique"],
                    "Mutant ID": "",
                    "Mutator": "",
                    "Mutation Type": "",
                    "File": "",
                    "Line": "",
                    "Status": "",
                    "Message": mapping["evidence_status"],
                }
            )
            continue
        for item in evidence_rows:
            message = str(item.get("Status Reason") or item.get("Replacement") or "")
            rows.append(
                {
                    "Tool": mapping["tool"],
                    "Metric": mapping["metric"],
                    "Classification": mapping["classification"],
                    "Technique": mapping["technique"],
                    "Mutant ID": item.get("Mutant ID", ""),
                    "Mutator": item.get("Mutator Name", ""),
                    "Mutation Type": item.get("Mutation Type", ""),
                    "File": item.get("Source File", ""),
                    "Line": item.get("Line Number", ""),
                    "Status": item.get("Status", ""),
                    "Message": message,
                }
            )
    return pd.DataFrame(rows)


def build_final_summary(
    repo_path: Path,
    mutants_df: pd.DataFrame,
    metric_mappings: list[dict[str, Any]],
    mutation_score: float | None,
) -> dict[str, Any]:
    status_counts = count_mutant_statuses(mutants_df)
    with_evidence = [m["metric"] for m in metric_mappings if m.get("supporting_findings_count", 0) > 0]
    without_evidence = [m["metric"] for m in metric_mappings if m.get("supporting_findings_count", 0) == 0]
    files_analysed = mutants_df["Source File"].nunique() if not mutants_df.empty else 0
    return {
        "repository_name": repo_path.name,
        "programming_language": PROGRAMMING_LANGUAGE,
        "tool_used": TOOL_NAME,
        "total_files_analysed": int(files_analysed),
        "total_mutants_generated": int(len(mutants_df)),
        "total_mutants_killed": int(status_counts.get("Killed", 0)),
        "total_survived_mutants": int(status_counts.get("Survived", 0)),
        "total_timeout_mutants": int(status_counts.get("Timeout", 0)),
        "total_runtime_errors": int(status_counts.get("RuntimeError", 0)),
        "total_nocoverage_mutants": int(status_counts.get("NoCoverage", 0)),
        "total_compile_errors": int(status_counts.get("CompileError", 0)),
        "mutation_score": mutation_score,
        "metrics_evaluated": [m["metric"] for m in METRIC_DEFINITIONS],
        "metrics_with_supporting_evidence": with_evidence,
        "metrics_without_supporting_evidence": without_evidence,
    }


def export_results(
    output_dir: Path,
    raw_dir: Path,
    mutants_df: pd.DataFrame,
    evidence_df: pd.DataFrame,
    metric_mappings: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, str]:
    paths = {
        "parsed_findings_csv": output_dir / "parsed_findings.csv",
        "parsed_findings_json": output_dir / "parsed_findings.json",
        "metric_evidence_csv": output_dir / "metric_evidence_mapping.csv",
        "metric_evidence_json": output_dir / "metric_evidence_mapping.json",
        "final_summary_json": output_dir / "final_analysis_summary.json",
        "raw_json_report": output_dir / "mutation-report.json",
        "raw_console_log": output_dir / "console_output.txt",
    }
    source_json = raw_dir / "mutation-report.json"
    if source_json.exists():
        copy_file_verbatim(source_json, paths["raw_json_report"])
    source_console = raw_dir / "console_output.txt"
    if source_console.exists():
        copy_file_verbatim(source_console, paths["raw_console_log"])
    mutants_df.to_csv(paths["parsed_findings_csv"], index=False)
    paths["parsed_findings_json"].write_text(mutants_df.to_json(orient="records", indent=2), encoding="utf-8")
    evidence_df.to_csv(paths["metric_evidence_csv"], index=False)
    paths["metric_evidence_json"].write_text(json.dumps(metric_mappings, indent=2), encoding="utf-8")
    paths["final_summary_json"].write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return {key: str(path.resolve()) for key, path in paths.items()}


def run_pipeline(repo_path: Path, metric_root: Path, logger: NotebookLogger | None = None) -> dict[str, Any]:
    logger = logger or NotebookLogger(metric_root / "output" / "reports" / "error_log.txt")
    dirs = ensure_output_dirs(metric_root)
    started = time.perf_counter()

    install_result = run_command(["npm", "install"], repo_path, "npm install")
    (dirs["raw"] / "npm_install.log").write_text(
        f"--- stdout ---\n{install_result['stdout']}\n\n--- stderr ---\n{install_result['stderr']}",
        encoding="utf-8",
    )
    if not install_result["success"]:
        raise RuntimeError("npm install failed.")

    packages_df = verify_required_packages(repo_path, logger)
    stryker_config, generated = resolve_stryker_config(repo_path, dirs["temp"])

    baseline_result = run_command(["npm", "test"], repo_path, "npm test")
    coverage_script = load_json(repo_path / "package.json") or {}
    coverage_result = None
    if "coverage" in (coverage_script.get("scripts") or {}):
        coverage_result = run_command(["npm", "run", "coverage"], repo_path, "npm run coverage")

    stryker_command = ["npx", "stryker", "run"]
    if generated:
        stryker_command.extend(["--config", str(stryker_config)])
    stryker_result = run_command(stryker_command, repo_path, "stryker run")

    (dirs["raw"] / "console_output.txt").write_text(stryker_result.get("stdout", ""), encoding="utf-8")
    (dirs["raw"] / "stderr_output.txt").write_text(stryker_result.get("stderr", ""), encoding="utf-8")
    (dirs["raw"] / "execution.log").write_text(
        "\n\n".join(
            [
                "=== Baseline Tests ===",
                baseline_result.get("stdout", ""),
                baseline_result.get("stderr", ""),
                "=== Coverage ===",
                (coverage_result or {}).get("stdout", "") if coverage_result else "No coverage script executed.",
                (coverage_result or {}).get("stderr", "") if coverage_result else "",
                "=== Stryker ===",
                stryker_result.get("stdout", ""),
                stryker_result.get("stderr", ""),
            ]
        ),
        encoding="utf-8",
    )
    preserved = preserve_stryker_artifacts(repo_path, dirs["raw"])

    report_path = dirs["raw"] / "mutation-report.json"
    if not report_path.exists():
        candidate = repo_path / "artifacts" / "training" / "mutation" / "mutation-report.json"
        if candidate.exists():
            copy_file_verbatim(candidate, report_path)
            preserved["mutation-report.json"] = str(report_path.resolve())

    report = load_json(report_path) or {}
    mutants_df = flatten_mutants(report)
    mutation_score = parse_mutation_score(stryker_result.get("stdout", ""), mutants_df)
    metric_mappings = build_metric_mappings(mutants_df)
    evidence_df = build_evidence_table(metric_mappings)
    summary = build_final_summary(repo_path, mutants_df, metric_mappings, mutation_score)
    exported = export_results(dirs["output"], dirs["raw"], mutants_df, evidence_df, metric_mappings, summary)

    logger.write_errors()
    return {
        "pipeline_success": report_path.exists() and stryker_result["success"],
        "install_result": install_result,
        "packages_df": packages_df,
        "stryker_config_path": str(stryker_config),
        "stryker_config_generated": generated,
        "baseline_result": baseline_result,
        "coverage_result": coverage_result,
        "stryker_result": stryker_result,
        "preserved_artifacts": preserved,
        "mutants_df": mutants_df,
        "metric_mappings": metric_mappings,
        "evidence_df": evidence_df,
        "summary": summary,
        "exported_paths": exported,
        "mutation_score": mutation_score,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    }
