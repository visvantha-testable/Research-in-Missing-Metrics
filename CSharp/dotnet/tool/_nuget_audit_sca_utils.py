"""NuGet Audit (`dotnet package list --include-transitive --vulnerable --format json`) extraction helpers."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

os.environ.pop("PYTHONPATH", None)

REPO_URL = "https://github.com/visvantha-testable/csharp-testing-nuget-audit.git"
PROGRAMMING_LANGUAGE = "C#"
TOOL_NAME = "dotnet package list --include-transitive --vulnerable --format json"
ANALYSIS_TYPE = "Software Composition Analysis (SCA)"
DOTNET_CHANNEL = "9.0"
AUDIT_PROJECT_RELATIVE = "sample_subject/SampleSubject.csproj"
NO_EVIDENCE_MESSAGE = "No evidence found in the current NuGet Audit analysis."

METRIC_DEFINITIONS: list[dict[str, str]] = [
    {
        "tool": TOOL_NAME,
        "metric": "Hidden Relationship Mapping",
        "classification": "Dependency Risk (SCA)",
        "technique": "Transitive Dependency Analysis",
    },
    {
        "tool": TOOL_NAME,
        "metric": "Legal Risk Validation",
        "classification": "Dependency Risk (SCA)",
        "technique": "License Compliance Testing",
    },
    {
        "tool": TOOL_NAME,
        "metric": "Trust Integrity Verification",
        "classification": "Dependency Risk (SCA)",
        "technique": "Supply Chain Security Analysis",
    },
    {
        "tool": TOOL_NAME,
        "metric": "Community Vitality Tracking",
        "classification": "Dependency Risk (SCA)",
        "technique": "Dependency Health Monitoring",
    },
    {
        "tool": TOOL_NAME,
        "metric": "Mitigation Effort Ranking",
        "classification": "Dependency Risk (SCA)",
        "technique": "Risk Prioritization",
    },
    {
        "tool": TOOL_NAME,
        "metric": "Real-Time Alerting",
        "classification": "Dependency Risk (SCA)",
        "technique": "Continuous Dependency Monitoring",
    },
    {
        "tool": TOOL_NAME,
        "metric": "Known CVE Count",
        "classification": "Dependency Risk (SCA)",
        "technique": "Vulnerability Dependency Detection",
    },
    {
        "tool": TOOL_NAME,
        "metric": "Version Lag Assessment",
        "classification": "Dependency Risk (SCA)",
        "technique": "Outdated Dependency Detection",
    },
]

FINDINGS_COLUMNS = [
    "Project Name",
    "Package Name",
    "Requested Version",
    "Resolved Version",
    "Latest Version",
    "Dependency Type",
    "Direct / Transitive",
    "Severity",
    "Advisory URL",
    "Advisory ID",
    "Vulnerability ID",
    "CVE",
    "Description",
    "Source",
    "Framework",
]

EVIDENCE_COLUMNS = [
    "Tool",
    "Metric",
    "Classification",
    "Technique",
    "Project",
    "Package",
    "Dependency Type",
    "Severity",
    "CVE",
    "Advisory",
    "Current Version",
    "Latest Version",
    "Evidence",
]

CVE_PATTERN = re.compile(r"(CVE-\d{4}-\d+)", re.IGNORECASE)
GHSA_PATTERN = re.compile(r"(GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4})", re.IGNORECASE)
RESTORED_PACKAGE_PATTERN = re.compile(r"Restored\s+(.+?)\s+in\s+", re.IGNORECASE)


class NotebookLogger:
    def __init__(self, error_log_path: Path) -> None:
        self.error_log_path = error_log_path
        self._entries: list[str] = []

    def info(self, message: str, **context: Any) -> None:
        suffix = " ".join(f"{key}={value}" for key, value in context.items())
        line = f"[INFO] {message}" + (f" ({suffix})" if suffix else "")
        self._entries.append(line)
        print(line)

    def error(self, message: str, **context: Any) -> None:
        suffix = " ".join(f"{key}={value}" for key, value in context.items())
        line = f"[ERROR] {message}" + (f" ({suffix})" if suffix else "")
        self._entries.append(line)
        print(line)

    def write_errors(self) -> None:
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.error_log_path.write_text(
            "\n".join(self._entries) + ("\n" if self._entries else ""),
            encoding="utf-8",
        )


def resolve_metric_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__).resolve().parent).resolve()
    for _ in range(8):
        if (current / "tool" / "_nuget_audit_sca_utils.py").exists():
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
        "workspace": metric_root / "workspace",
        "runtimes": metric_root / "runtimes" / "dotnet-sdk-9",
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


def clone_repository(repo_url: str, workspace_dir: Path, *, reuse: bool = True) -> tuple[Path, str]:
    workspace_dir.mkdir(parents=True, exist_ok=True)
    repo_path = derive_clone_path(repo_url, workspace_dir)
    if reuse and repo_path.exists():
        try:
            Repo(str(repo_path))
            return repo_path.resolve(), f"Repository already exists at {repo_path}; skipping clone."
        except InvalidGitRepositoryError:
            shutil.rmtree(repo_path, ignore_errors=True)

    try:
        Repo.clone_from(repo_url, repo_path, depth=1)
        return repo_path.resolve(), f"Cloned {repo_url} to {repo_path}."
    except GitCommandError as exc:
        raise RuntimeError(f"Failed to clone repository: {exc}") from exc


def list_repository_structure(repo_path: Path, *, max_entries: int = 80) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for index, path in enumerate(sorted(repo_path.rglob("*"))):
        if index >= max_entries:
            rows.append({"path": "...", "type": "truncated", "size_bytes": ""})
            break
        if any(part in {".git", "bin", "obj"} for part in path.parts):
            continue
        rel = path.relative_to(repo_path)
        rows.append(
            {
                "path": str(rel),
                "type": "directory" if path.is_dir() else "file",
                "size_bytes": "" if path.is_dir() else str(path.stat().st_size),
            }
        )
    return pd.DataFrame(rows)


def dotnet_executable(dotnet_root: Path) -> Path:
    return dotnet_root / ("dotnet.exe" if sys.platform.startswith("win") else "dotnet")


def download_dotnet_sdk(install_dir: Path, channel: str = DOTNET_CHANNEL, tmp_dir: Path | None = None) -> Path:
    install_dir = install_dir.resolve()
    install_dir.mkdir(parents=True, exist_ok=True)
    dotnet = dotnet_executable(install_dir)
    if dotnet.exists():
        return install_dir

    shared_root = install_dir.parents[2] / "runtimes" / "dotnet-sdk-9"
    shared_dotnet = dotnet_executable(shared_root)
    if shared_dotnet.exists():
        return shared_root.resolve()

    if tmp_dir is not None:
        tmp_dir.mkdir(parents=True, exist_ok=True)
        os.environ["TEMP"] = str(tmp_dir)
        os.environ["TMP"] = str(tmp_dir)
        os.environ["TMPDIR"] = str(tmp_dir)

    if sys.platform.startswith("win"):
        script_path = install_dir / "dotnet-install.ps1"
        urllib.request.urlretrieve("https://dot.net/v1/dotnet-install.ps1", script_path)
        subprocess.run(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                "-InstallDir",
                str(install_dir),
                "-Channel",
                channel,
                "-Architecture",
                "x64",
                "-Quality",
                "ga",
            ],
            check=True,
        )
    else:
        script_path = install_dir / "dotnet-install.sh"
        urllib.request.urlretrieve("https://dot.net/v1/dotnet-install.sh", script_path)
        script_path.chmod(0o755)
        subprocess.run(
            [str(script_path), "--install-dir", str(install_dir), "--channel", channel, "--quality", "ga"],
            check=True,
        )

    if not dotnet.exists():
        raise RuntimeError(f".NET SDK installation failed; expected executable at {dotnet}")
    return install_dir


def dotnet_env(dotnet_root: Path, tmp_dir: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["DOTNET_ROOT"] = str(dotnet_root)
    env["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"
    env["PATH"] = str(dotnet_root) + os.pathsep + env.get("PATH", "")
    env.pop("PYTHONPATH", None)
    if tmp_dir is not None:
        env["TEMP"] = str(tmp_dir)
        env["TMP"] = str(tmp_dir)
    return env


def run_command(command: list[str], cwd: Path, env: dict[str, str]) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )
    elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    raw = stdout
    if stderr:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += stderr
    return {
        "command": " ".join(command),
        "stdout": stdout,
        "stderr": stderr,
        "raw": raw,
        "returncode": completed.returncode,
        "success": completed.returncode == 0,
        "elapsed_ms": elapsed_ms,
    }


def collect_prerequisite_versions(dotnet_root: Path, env: dict[str, str]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    def add(name: str, command: list[str]) -> None:
        result = run_command(command, Path.cwd(), env if command[0] == str(dotnet_executable(dotnet_root)) else os.environ.copy())
        version = (result["stdout"] or result["stderr"]).strip().splitlines()[0] if (result["stdout"] or result["stderr"]) else ""
        rows.append({"component": name, "version": version, "status": "ok" if result["success"] else "error"})

    add(".NET SDK", [str(dotnet_executable(dotnet_root)), "--version"])
    add("Git", ["git", "--version"])
    add("Python", [sys.executable, "--version"])
    for module_name in ("pandas", "json", "pathlib", "tabulate"):
        if module_name in {"json", "pathlib"}:
            rows.append({"component": module_name, "version": "stdlib", "status": "ok"})
            continue
        try:
            module = __import__(module_name)
            rows.append({"component": module_name, "version": getattr(module, "__version__", "installed"), "status": "ok"})
        except ImportError:
            rows.append({"component": module_name, "version": "", "status": "missing"})
    return pd.DataFrame(rows)


def discover_solution(repo_path: Path) -> Path:
    solutions = sorted(repo_path.glob("*.sln"))
    if not solutions:
        raise FileNotFoundError(f"No .sln file found under {repo_path}")
    return solutions[0].resolve()


def discover_projects(repo_path: Path) -> list[Path]:
    projects = [path.resolve() for path in sorted(repo_path.rglob("*.csproj")) if "bin" not in path.parts and "obj" not in path.parts]
    return projects


def count_restored_packages(restore_log: str) -> int:
    return len(RESTORED_PACKAGE_PATTERN.findall(restore_log))


def run_dotnet_restore(repo_path: Path, solution_path: Path, dotnet_root: Path, env: dict[str, str]) -> dict[str, Any]:
    result = run_command([str(dotnet_executable(dotnet_root)), "restore", str(solution_path.name)], repo_path, env)
    result["restored_packages"] = count_restored_packages(result["raw"])
    result["restore_status"] = "success" if result["success"] else "failed"
    return result


def run_dotnet_build(repo_path: Path, solution_path: Path, dotnet_root: Path, env: dict[str, str]) -> dict[str, Any]:
    result = run_command([str(dotnet_executable(dotnet_root)), "build", str(solution_path.name), "--no-restore"], repo_path, env)
    result["project_count"] = len(discover_projects(repo_path))
    result["build_status"] = "success" if result["success"] else "failed"
    return result


def run_nuget_audit(repo_path: Path, project_relative: str, dotnet_root: Path, env: dict[str, str]) -> dict[str, Any]:
    flags = ["--include-transitive", "--vulnerable", "--format", "json", "--output-version", "1"]
    attempts = [
        ["dotnet", "list", project_relative, "package", *flags],
        ["dotnet", "package", "list", project_relative, *flags],
    ]
    last_result: dict[str, Any] | None = None
    dotnet = str(dotnet_executable(dotnet_root))
    for attempt in attempts:
        command = [dotnet if part == "dotnet" else part for part in attempt]
        result = run_command(command, repo_path, env)
        result["command_attempt"] = " ".join(attempt)
        last_result = result
        if result["success"] and result["stdout"].strip():
            result["audit_status"] = "success"
            return result
    if last_result is None:
        raise RuntimeError("NuGet audit command was not executed.")
    last_result["audit_status"] = "failed"
    return last_result


def preserve_raw_audit_output(audit_result: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_json_path = output_dir / "nuget_audit_raw.json"
    raw_console_path = output_dir / "nuget_audit_console_output.txt"
    audit_log_path = output_dir / "nuget_audit_execution.log"

    stdout = audit_result.get("stdout", "")
    raw_json_path.write_text(stdout, encoding="utf-8")
    raw_console_path.write_text(audit_result.get("raw", ""), encoding="utf-8")
    audit_log_path.write_text(
        "\n".join(
            [
                f"command: {audit_result.get('command_attempt') or audit_result.get('command')}",
                f"returncode: {audit_result.get('returncode')}",
                f"elapsed_ms: {audit_result.get('elapsed_ms')}",
                "",
                "--- stdout ---",
                audit_result.get("stdout", ""),
                "",
                "--- stderr ---",
                audit_result.get("stderr", ""),
            ]
        ),
        encoding="utf-8",
    )
    return {"raw_json": raw_json_path, "raw_console": raw_console_path, "audit_log": audit_log_path}


def _project_name(project_path: str) -> str:
    return Path(project_path).stem


def _extract_advisory_id(advisory_url: str) -> str:
    if not advisory_url:
        return ""
    match = GHSA_PATTERN.search(advisory_url) or CVE_PATTERN.search(advisory_url)
    return match.group(1) if match else advisory_url.rstrip("/").split("/")[-1]


def _extract_cve(advisory_url: str, vulnerability_id: str = "") -> str:
    for candidate in (advisory_url, vulnerability_id):
        match = CVE_PATTERN.search(candidate or "")
        if match:
            return match.group(1).upper()
    ghsa = GHSA_PATTERN.search(advisory_url or "")
    return ghsa.group(1).upper() if ghsa else ""


def _fix_versions(vulnerability: dict[str, Any]) -> str:
    if "fixVersions" in vulnerability and isinstance(vulnerability["fixVersions"], list):
        return ", ".join(str(item) for item in vulnerability["fixVersions"])
    if "fixVersion" in vulnerability:
        return str(vulnerability["fixVersion"])
    return ""


def parse_audit_json(raw_json_text: str, audit_payload: dict[str, Any] | None = None) -> pd.DataFrame:
    payload = audit_payload if audit_payload is not None else json.loads(raw_json_text)
    sources = payload.get("sources") or []
    source_text = "; ".join(str(item) for item in sources)
    rows: list[dict[str, str]] = []

    for project in payload.get("projects") or []:
        project_path = str(project.get("path") or "")
        project_name = _project_name(project_path)
        frameworks = project.get("frameworks") or []
        if not frameworks:
            rows.append(
                {
                    "Project Name": project_name,
                    "Package Name": "",
                    "Requested Version": "",
                    "Resolved Version": "",
                    "Latest Version": "",
                    "Dependency Type": "",
                    "Direct / Transitive": "",
                    "Severity": "",
                    "Advisory URL": "",
                    "Advisory ID": "",
                    "Vulnerability ID": "",
                    "CVE": "",
                    "Description": "",
                    "Source": source_text,
                    "Framework": "",
                }
            )
            continue

        for framework_entry in frameworks:
            framework_name = str(framework_entry.get("framework") or "")
            for section_name, dependency_type in (
                ("topLevelPackages", "direct"),
                ("transitivePackages", "transitive"),
            ):
                for package in framework_entry.get(section_name) or []:
                    package_id = str(package.get("id") or "")
                    requested = str(package.get("requestedVersion") or "")
                    resolved = str(package.get("resolvedVersion") or "")
                    latest = str(package.get("latestVersion") or "")
                    vulnerabilities = package.get("vulnerabilities") or []
                    if not vulnerabilities:
                        rows.append(
                            {
                                "Project Name": project_name,
                                "Package Name": package_id,
                                "Requested Version": requested,
                                "Resolved Version": resolved,
                                "Latest Version": latest,
                                "Dependency Type": dependency_type,
                                "Direct / Transitive": "Direct" if dependency_type == "direct" else "Transitive",
                                "Severity": "",
                                "Advisory URL": "",
                                "Advisory ID": "",
                                "Vulnerability ID": "",
                                "CVE": "",
                                "Description": "",
                                "Source": source_text,
                                "Framework": framework_name,
                            }
                        )
                        continue
                    for vulnerability in vulnerabilities:
                        advisory_url = str(vulnerability.get("advisoryurl") or vulnerability.get("advisoryUrl") or "")
                        vulnerability_id = str(vulnerability.get("id") or vulnerability.get("vulnerabilityId") or "")
                        description = str(vulnerability.get("description") or "")
                        if not description and _fix_versions(vulnerability):
                            description = f"fixVersions={_fix_versions(vulnerability)}"
                        rows.append(
                            {
                                "Project Name": project_name,
                                "Package Name": package_id,
                                "Requested Version": requested,
                                "Resolved Version": resolved,
                                "Latest Version": latest,
                                "Dependency Type": dependency_type,
                                "Direct / Transitive": "Direct" if dependency_type == "direct" else "Transitive",
                                "Severity": str(vulnerability.get("severity") or ""),
                                "Advisory URL": advisory_url,
                                "Advisory ID": _extract_advisory_id(advisory_url),
                                "Vulnerability ID": vulnerability_id,
                                "CVE": _extract_cve(advisory_url, vulnerability_id),
                                "Description": description,
                                "Source": source_text,
                                "Framework": framework_name,
                            }
                        )
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def _metric_support_rows(metric: str, findings_df: pd.DataFrame, audit_payload: dict[str, Any]) -> pd.DataFrame:
    if metric == "Hidden Relationship Mapping":
        mask = findings_df["Direct / Transitive"].eq("Transitive")
        return findings_df[mask].copy()

    if metric == "Legal Risk Validation":
        return findings_df.iloc[0:0].copy()

    if metric == "Trust Integrity Verification":
        mask = findings_df["Severity"].astype(str).str.len() > 0
        return findings_df[mask].copy()

    if metric == "Community Vitality Tracking":
        return findings_df.iloc[0:0].copy()

    if metric == "Mitigation Effort Ranking":
        mask = findings_df["Description"].astype(str).str.contains("fixVersions=", case=False, na=False)
        return findings_df[mask].copy()

    if metric == "Real-Time Alerting":
        return findings_df.iloc[0:0].copy()

    if metric == "Known CVE Count":
        mask = findings_df["Severity"].astype(str).str.len() > 0
        return findings_df[mask].copy()

    if metric == "Version Lag Assessment":
        latest = findings_df["Latest Version"].astype(str).str.len() > 0
        requested = findings_df["Requested Version"].astype(str).str.len() > 0
        resolved = findings_df["Resolved Version"].astype(str).str.len() > 0
        mask = latest & (requested | resolved)
        lag_mask = mask & (
            findings_df["Latest Version"].astype(str) != findings_df["Resolved Version"].astype(str)
        )
        version_mask = mask & findings_df["Latest Version"].astype(str).ne(findings_df["Requested Version"].astype(str))
        return findings_df[lag_mask | version_mask].copy()

    return findings_df.iloc[0:0].copy()


def build_metric_mapping(findings_df: pd.DataFrame, audit_payload: dict[str, Any]) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    for definition in METRIC_DEFINITIONS:
        metric = definition["metric"]
        supporting_rows = _metric_support_rows(metric, findings_df, audit_payload)
        if metric == "Trust Integrity Verification":
            vuln_rows = findings_df[findings_df["Severity"].astype(str).str.len() > 0]
            if not vuln_rows.empty:
                has_evidence = True
                supporting_rows = vuln_rows
                rationale = (
                    "NuGet Audit reported vulnerable package entries with severity and advisory metadata "
                    "in the raw JSON output."
                )
            else:
                has_evidence = False
                rationale = NO_EVIDENCE_MESSAGE
        elif metric == "Hidden Relationship Mapping":
            transitive_rows = findings_df[findings_df["Direct / Transitive"].eq("Transitive")]
            if not transitive_rows.empty:
                has_evidence = True
                supporting_rows = transitive_rows
                rationale = (
                    "The audit JSON includes transitive package entries produced by the "
                    "`--include-transitive` NuGet Audit scan."
                )
            else:
                has_evidence = False
                rationale = NO_EVIDENCE_MESSAGE
        elif metric == "Known CVE Count":
            vuln_rows = findings_df[findings_df["Severity"].astype(str).str.len() > 0]
            if not vuln_rows.empty:
                has_evidence = True
                supporting_rows = vuln_rows
                rationale = "Vulnerability records in the audit JSON include severity and advisory identifiers."
            else:
                has_evidence = False
                rationale = NO_EVIDENCE_MESSAGE
        elif metric == "Mitigation Effort Ranking":
            fix_rows = findings_df[findings_df["Description"].astype(str).str.contains("fixVersions=", case=False, na=False)]
            if not fix_rows.empty:
                has_evidence = True
                supporting_rows = fix_rows
                rationale = "Vulnerability entries expose fixVersions/fixVersion fields usable for mitigation ranking."
            else:
                has_evidence = False
                rationale = NO_EVIDENCE_MESSAGE
        elif metric == "Version Lag Assessment":
            version_rows = _metric_support_rows(metric, findings_df, audit_payload)
            if not version_rows.empty:
                has_evidence = True
                supporting_rows = version_rows
                rationale = (
                    "Package entries in the audit JSON include requested, resolved, and latest version fields "
                    "that differ."
                )
            else:
                has_evidence = False
                rationale = NO_EVIDENCE_MESSAGE
        elif metric in {"Legal Risk Validation", "Community Vitality Tracking", "Real-Time Alerting"}:
            has_evidence = False
            rationale = NO_EVIDENCE_MESSAGE
        else:
            has_evidence = not supporting_rows.empty
            rationale = (
                "Supporting rows were extracted directly from the NuGet Audit JSON output."
                if has_evidence
                else NO_EVIDENCE_MESSAGE
            )

        mappings.append(
            {
                **definition,
                "has_evidence": has_evidence,
                "evidence_status": "supported" if has_evidence else "unsupported",
                "supporting_rows": supporting_rows,
                "rationale": rationale,
            }
        )
    return mappings


def build_evidence_table(findings_df: pd.DataFrame, metric_mappings: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for mapping in metric_mappings:
        supporting_rows: pd.DataFrame = mapping["supporting_rows"]
        if supporting_rows.empty or not mapping["has_evidence"]:
            rows.append(
                {
                    "Tool": mapping["tool"],
                    "Metric": mapping["metric"],
                    "Classification": mapping["classification"],
                    "Technique": mapping["technique"],
                    "Project": "",
                    "Package": "",
                    "Dependency Type": "",
                    "Severity": "",
                    "CVE": "",
                    "Advisory": "",
                    "Current Version": "",
                    "Latest Version": "",
                    "Evidence": NO_EVIDENCE_MESSAGE,
                }
            )
            continue

        for _, finding in supporting_rows.iterrows():
            advisory = str(finding.get("Advisory URL") or finding.get("Advisory ID") or "")
            evidence_text = json.dumps(
                {
                    "project": finding.get("Project Name", ""),
                    "package": finding.get("Package Name", ""),
                    "dependency_type": finding.get("Dependency Type", ""),
                    "severity": finding.get("Severity", ""),
                    "advisory": advisory,
                    "cve": finding.get("CVE", ""),
                    "requested_version": finding.get("Requested Version", ""),
                    "resolved_version": finding.get("Resolved Version", ""),
                    "latest_version": finding.get("Latest Version", ""),
                    "description": finding.get("Description", ""),
                },
                sort_keys=True,
            )
            rows.append(
                {
                    "Tool": mapping["tool"],
                    "Metric": mapping["metric"],
                    "Classification": mapping["classification"],
                    "Technique": mapping["technique"],
                    "Project": str(finding.get("Project Name", "")),
                    "Package": str(finding.get("Package Name", "")),
                    "Dependency Type": str(finding.get("Direct / Transitive", "")),
                    "Severity": str(finding.get("Severity", "")),
                    "CVE": str(finding.get("CVE", "")),
                    "Advisory": advisory,
                    "Current Version": str(finding.get("Resolved Version", "") or finding.get("Requested Version", "")),
                    "Latest Version": str(finding.get("Latest Version", "")),
                    "Evidence": evidence_text,
                }
            )
    return pd.DataFrame(rows, columns=EVIDENCE_COLUMNS)


def summarize_dependencies(findings_df: pd.DataFrame) -> dict[str, int]:
    package_rows = findings_df[findings_df["Package Name"].astype(str).str.len() > 0].copy()
    direct = int((package_rows["Direct / Transitive"] == "Direct").sum())
    transitive = int((package_rows["Direct / Transitive"] == "Transitive").sum())
    total = direct + transitive
    vulnerable_packages = package_rows[package_rows["Severity"].astype(str).str.len() > 0]["Package Name"].nunique()
    return {
        "total_dependencies": total,
        "direct_dependencies": direct,
        "transitive_dependencies": transitive,
        "vulnerable_packages": int(vulnerable_packages),
    }


def summarize_severity(findings_df: pd.DataFrame) -> dict[str, int]:
    severities = findings_df["Severity"].astype(str).str.strip().str.lower()
    return {
        "critical": int((severities == "critical").sum()),
        "high": int((severities == "high").sum()),
        "medium": int(severities.isin({"medium", "moderate"}).sum()),
        "low": int((severities == "low").sum()),
    }


def build_final_summary(
    repo_path: Path,
    findings_df: pd.DataFrame,
    metric_mappings: list[dict[str, Any]],
    audit_payload: dict[str, Any],
    restore_result: dict[str, Any],
    build_result: dict[str, Any],
) -> dict[str, Any]:
    dependency_summary = summarize_dependencies(findings_df)
    severity_summary = summarize_severity(findings_df)
    projects = audit_payload.get("projects") or []
    return {
        "repository_name": repo_path.name,
        "programming_language": PROGRAMMING_LANGUAGE,
        "tool_used": TOOL_NAME,
        "total_projects_analysed": len(projects),
        "total_dependencies": dependency_summary["total_dependencies"],
        "direct_dependencies": dependency_summary["direct_dependencies"],
        "transitive_dependencies": dependency_summary["transitive_dependencies"],
        "vulnerable_packages": dependency_summary["vulnerable_packages"],
        "critical_vulnerabilities": severity_summary["critical"],
        "high_vulnerabilities": severity_summary["high"],
        "medium_vulnerabilities": severity_summary["medium"],
        "low_vulnerabilities": severity_summary["low"],
        "metrics_evaluated": len(metric_mappings),
        "metrics_with_supporting_evidence": sum(1 for item in metric_mappings if item["has_evidence"]),
        "metrics_without_supporting_evidence": sum(1 for item in metric_mappings if not item["has_evidence"]),
        "restore_status": restore_result.get("restore_status"),
        "build_status": build_result.get("build_status"),
        "restored_packages": restore_result.get("restored_packages", 0),
        "project_count": build_result.get("project_count", 0),
    }


def export_results(
    output_dir: Path,
    raw_paths: dict[str, Path],
    findings_df: pd.DataFrame,
    evidence_df: pd.DataFrame,
    metric_mappings: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    parsed_csv = output_dir / "parsed_findings.csv"
    parsed_json = output_dir / "parsed_findings.json"
    evidence_csv = output_dir / "metric_evidence.csv"
    evidence_json = output_dir / "metric_evidence.json"
    summary_json = output_dir / "final_summary.json"

    findings_df.to_csv(parsed_csv, index=False)
    parsed_json.write_text(findings_df.to_json(orient="records", indent=2), encoding="utf-8")
    evidence_df.to_csv(evidence_csv, index=False)
    evidence_json.write_text(evidence_df.to_json(orient="records", indent=2), encoding="utf-8")
    summary_json.write_text(
        json.dumps(
            {
                "summary": summary,
                "metric_mappings": [
                    {
                        key: value
                        for key, value in mapping.items()
                        if key not in {"supporting_rows"}
                    }
                    for mapping in metric_mappings
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    exported = {
        "raw_json": raw_paths["raw_json"],
        "raw_console_output": raw_paths["raw_console"],
        "audit_log": raw_paths["audit_log"],
        "parsed_findings_csv": parsed_csv,
        "parsed_findings_json": parsed_json,
        "metric_evidence_csv": evidence_csv,
        "metric_evidence_json": evidence_json,
        "final_summary_json": summary_json,
    }
    return exported


def run_pipeline(metric_root: Path, logger: NotebookLogger) -> dict[str, Any]:
    dirs = ensure_output_dirs(metric_root)
    output_dir = dirs["output"]
    dotnet_root = download_dotnet_sdk(dirs["runtimes"], tmp_dir=dirs["tmp"])
    env = dotnet_env(dotnet_root, tmp_dir=dirs["tmp"])

    repo_path, clone_status = clone_repository(REPO_URL, dirs["workspace"], reuse=True)
    solution_path = discover_solution(repo_path)
    project_relative = AUDIT_PROJECT_RELATIVE

    restore_result = run_dotnet_restore(repo_path, solution_path, dotnet_root, env)
    if not restore_result["success"]:
        logger.error("dotnet restore failed", returncode=restore_result["returncode"])
        raise RuntimeError("dotnet restore failed.")

    build_result = run_dotnet_build(repo_path, solution_path, dotnet_root, env)
    if not build_result["success"]:
        logger.error("dotnet build failed", returncode=build_result["returncode"])
        raise RuntimeError("dotnet build failed.")

    audit_result = run_nuget_audit(repo_path, project_relative, dotnet_root, env)
    if not audit_result["success"] or not audit_result["stdout"].strip():
        logger.error("NuGet audit failed", returncode=audit_result["returncode"])
        raise RuntimeError("NuGet audit command failed.")

    raw_paths = preserve_raw_audit_output(audit_result, output_dir)
    audit_payload = json.loads(audit_result["stdout"])
    findings_df = parse_audit_json(audit_result["stdout"], audit_payload)
    metric_mappings = build_metric_mapping(findings_df, audit_payload)
    evidence_df = build_evidence_table(findings_df, metric_mappings)
    summary = build_final_summary(
        repo_path,
        findings_df,
        metric_mappings,
        audit_payload,
        restore_result,
        build_result,
    )
    exported = export_results(output_dir, raw_paths, findings_df, evidence_df, metric_mappings, summary)

    return {
        "clone_status": clone_status,
        "repo_path": repo_path,
        "restore_result": restore_result,
        "build_result": build_result,
        "audit_result": audit_result,
        "raw_paths": raw_paths,
        "findings_df": findings_df,
        "metric_mappings": metric_mappings,
        "evidence_df": evidence_df,
        "summary": summary,
        "exported_paths": exported,
        "pipeline_success": True,
    }
