"""CodeQL CLI raw output extraction helpers for TypeScript static analysis metrics."""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from git import Repo
from git.exc import GitCommandError

os.environ.pop("PYTHONPATH", None)

REPO_URL = "https://github.com/visvantha-testable/typescript-tool-testing-vitest-coverage-v8.git"
PROGRAMMING_LANGUAGE = "TypeScript"
TOOL_NAME = "CodeQL CLI"
ANALYSIS_TYPE = "Static Code Analysis"

METRIC_DEFINITIONS: list[dict[str, Any]] = [
    {
        "tool": "CodeQL",
        "metric": "Unreachable Logic Identification",
        "classification": "Logic Verification",
        "technique": "Static Code Analysis",
        "rule_patterns": [
            r"(^|/)unreachable",
            r"(^|/)constant-condition",
            r"(^|/)useless-compare",
            r"(^|/)useless-expression",
            r"(^|/)dead-code",
        ],
        "rule_tags": ["logic", "unreachable", "dead-code"],
    },
    {
        "tool": "CodeQL",
        "metric": "Sequence Integrity Mapping",
        "classification": "Control Flow Validation",
        "technique": "Control Flow Analysis",
        "rule_patterns": [
            r"(^|/)missing-return",
            r"(^|/)inconsistent-loop",
            r"(^|/)loop-direction",
            r"(^|/)control-flow",
            r"(^|/)redundant-assignment",
            r"(^|/)use-before-declaration",
        ],
        "rule_tags": ["control-flow", "control flow", "maintainability"],
    },
    {
        "tool": "CodeQL",
        "metric": "Ghost Code Discovery",
        "classification": "Code Quality Assessment",
        "technique": "Static Code Analysis",
        "rule_patterns": [
            r"(^|/)unused-",
            r"(^|/)dead-store",
            r"(^|/)useless-assignment",
            r"(^|/)redundant-operation",
            r"(^|/)empty-block",
        ],
        "rule_tags": ["unused", "dead-code", "maintainability"],
    },
    {
        "tool": "CodeQL",
        "metric": "Ripple Effect Mapping",
        "classification": "Change Impact Analysis",
        "technique": "Data Flow Analysis",
        "rule_patterns": [
            r"(^|/)remote-property",
            r"(^|/)prototype-pollut",
            r"(^|/)tainted-",
            r"(^|/)unsafe-",
            r"(^|/)dataflow",
            r"(^|/)path-problem",
            r"(^|/)incomplete-sanitization",
            r"(^|/)missing-rate-limit",
        ],
        "rule_tags": ["security", "dataflow", "data flow", "taint", "path-problem"],
    },
    {
        "tool": "CodeQL",
        "metric": "Structural Health Benchmarking",
        "classification": "Quality Improvement Measurement",
        "technique": "Static Code Analysis",
        "rule_patterns": [
            r"(^|/)complexity",
            r"(^|/)cyclomatic",
            r"(^|/)high-complexity",
            r"(^|/)overly-large",
            r"(^|/)duplicate",
            r"(^|/)similar-file",
            r"(^|/)maintainability",
        ],
        "rule_tags": ["complexity", "maintainability", "quality"],
    },
]

CODEQL_RELEASE_API = "https://api.github.com/repos/github/codeql-cli-binaries/releases/latest"
CODEQL_QUERY_SUITE = "codeql/javascript-queries:codeql-suites/javascript-security-and-quality.qls"
FINDINGS_COLUMNS = [
    "Rule ID",
    "Rule Name",
    "Severity",
    "Message",
    "File Name",
    "File Path",
    "Start Line",
    "End Line",
    "Start Column",
    "End Column",
    "Rule Description",
    "Help URL",
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
        if (current / "tool" / "_codeql_static_analysis_utils.py").exists():
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
        "workspace": metric_root / "workspace",
        "codeql_home": metric_root / "output" / "codeql-cli",
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


def run_command(command: list[str], cwd: Path, label: str, env: dict[str, str] | None = None) -> dict[str, Any]:
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
        env=env,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "label": label,
        "command": " ".join(cmd),
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


def list_repository_structure(repo_path: Path, max_entries: int = 80) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    skip = {".git", "node_modules", ".stryker-tmp", "coverage", "dist"}
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
    add("unzip", ["unzip", "-v"] if platform.system() != "Windows" else ["powershell", "-Command", "Expand-Archive -?"])
    add("wget/curl", ["curl", "--version"] if resolve_executable("curl") else ["wget", "--version"])
    add("jq", ["jq", "--version"])
    return pd.DataFrame(rows)


def _codeql_platform_asset() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows":
        return "codeql-win64.zip"
    if system == "darwin":
        return "codeql-osx64.zip" if machine != "arm64" else "codeql-osx64.zip"
    return "codeql-linux64.zip"


def download_codeql_cli(codeql_home: Path, logger: NotebookLogger) -> Path:
    codeql_exe = codeql_home / "codeql" / ("codeql.exe" if platform.system() == "Windows" else "codeql")
    if codeql_exe.exists():
        logger.info("Reusing existing CodeQL CLI", path=str(codeql_exe))
        return codeql_exe

    asset_name = _codeql_platform_asset()
    with urllib.request.urlopen(CODEQL_RELEASE_API, timeout=60) as response:
        release = json.loads(response.read().decode("utf-8"))
    asset_url = next((asset["browser_download_url"] for asset in release.get("assets", []) if asset["name"] == asset_name), "")
    if not asset_url:
        raise RuntimeError(f"Could not find CodeQL asset {asset_name} in latest release.")

    zip_path = codeql_home / asset_name
    logger.info("Downloading CodeQL CLI", asset=asset_name)
    urllib.request.urlretrieve(asset_url, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(codeql_home)
    zip_path.unlink(missing_ok=True)
    if not codeql_exe.exists():
        raise RuntimeError(f"CodeQL executable not found after extraction: {codeql_exe}")
    return codeql_exe


def codeql_env(codeql_exe: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = str(codeql_exe.parent) + os.pathsep + env.get("PATH", "")
    return env


def verify_codeql(codeql_exe: Path) -> dict[str, Any]:
    result = run_command([str(codeql_exe), "version"], codeql_exe.parent, "codeql version")
    return result


def count_source_files(repo_path: Path) -> int:
    extensions = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
    skip = {".git", "node_modules", "dist", "coverage", "output", "codeql-db"}
    count = 0
    for path in repo_path.rglob("*"):
        if path.is_file() and path.suffix.lower() in extensions and not any(part in skip for part in path.parts):
            count += 1
    return count


def create_codeql_database(
    codeql_exe: Path,
    repo_path: Path,
    database_path: Path,
    logs_dir: Path,
    logger: NotebookLogger,
    reuse: bool = False,
) -> dict[str, Any]:
    if reuse and database_path.exists():
        source_files = count_source_files(repo_path)
        logger.info("Reusing existing CodeQL database", path=str(database_path))
        return {
            "label": "codeql database create",
            "command": "reuse existing database",
            "returncode": 0,
            "stdout": "",
            "stderr": "",
            "elapsed_ms": 0.0,
            "success": True,
            "database_path": str(database_path),
            "source_files_indexed": source_files,
            "log_path": str(logs_dir / "codeql_database_create.log"),
            "reused": True,
        }
    if database_path.exists():
        shutil.rmtree(database_path)
    env = codeql_env(codeql_exe)
    command = [
        str(codeql_exe),
        "database",
        "create",
        str(database_path),
        "--language=javascript-typescript",
        f"--source-root={repo_path}",
        "--overwrite",
    ]
    result = run_command(command, repo_path, "codeql database create", env=env)
    log_path = logs_dir / "codeql_database_create.log"
    log_path.write_text(
        f"$ {' '.join(command)}\n\n--- stdout ---\n{result['stdout']}\n\n--- stderr ---\n{result['stderr']}",
        encoding="utf-8",
    )
    source_files = count_source_files(repo_path)
    logger.info("CodeQL database created", success=result["success"], source_files=source_files)
    return {
        **result,
        "database_path": str(database_path),
        "source_files_indexed": source_files,
        "log_path": str(log_path),
    }


def analyze_codeql_database(
    codeql_exe: Path,
    database_path: Path,
    sarif_path: Path,
    logs_dir: Path,
    logger: NotebookLogger,
) -> dict[str, Any]:
    env = codeql_env(codeql_exe)
    pack_result = run_command(
        [str(codeql_exe), "pack", "download", "codeql/javascript-queries"],
        database_path.parent,
        "codeql pack download",
        env=env,
    )
    command = [
        str(codeql_exe),
        "database",
        "analyze",
        str(database_path),
        CODEQL_QUERY_SUITE,
        f"--format=sarifv2.1.0",
        f"--output={sarif_path}",
        "--threads=0",
    ]
    result = run_command(command, database_path.parent, "codeql database analyze", env=env)
    log_path = logs_dir / "codeql_database_analyze.log"
    log_path.write_text(
        f"$ {' '.join(command)}\n\n"
        f"--- pack download stdout ---\n{pack_result['stdout']}\n\n"
        f"--- pack download stderr ---\n{pack_result['stderr']}\n\n"
        f"--- analyze stdout ---\n{result['stdout']}\n\n"
        f"--- analyze stderr ---\n{result['stderr']}",
        encoding="utf-8",
    )
    combined_output = result["stderr"] + result["stdout"] + pack_result["stderr"] + pack_result["stdout"]
    query_matches = re.findall(r"\[(\d+)/(\d+) eval", combined_output)
    query_count = int(query_matches[-1][1]) if query_matches else 0
    if query_count == 0:
        query_count = len(re.findall(r"Interpreted query", combined_output))
    if query_count == 0:
        query_count = len(re.findall(r"Compiling query plan for", combined_output))
    logger.info("CodeQL analysis completed", success=result["success"], query_count=query_count)
    return {
        **result,
        "pack_download": pack_result,
        "sarif_path": str(sarif_path),
        "queries_executed": query_count,
        "log_path": str(log_path),
    }


def _rule_lookup(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rules: dict[str, dict[str, Any]] = {}
    driver = (run.get("tool") or {}).get("driver") or {}
    for rule in driver.get("rules") or []:
        rule_id = str(rule.get("id") or rule.get("ruleId") or "")
        if rule_id:
            rules[rule_id] = rule
    return rules


def _rule_name(rule: dict[str, Any]) -> str:
    return str(rule.get("name") or rule.get("shortDescription", {}).get("text") or rule.get("id") or "")


def _rule_description(rule: dict[str, Any]) -> str:
    if rule.get("fullDescription", {}).get("text"):
        return str(rule["fullDescription"]["text"])
    if rule.get("shortDescription", {}).get("text"):
        return str(rule["shortDescription"]["text"])
    return str(rule.get("description", ""))


def _rule_help_url(rule: dict[str, Any]) -> str:
    return str(rule.get("helpUri") or rule.get("helpURL") or "")


def _rule_tags(rule: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for prop in rule.get("properties") or {}:
        value = rule["properties"][prop]
        if isinstance(value, str):
            tags.append(value.lower())
        elif isinstance(value, list):
            tags.extend(str(item).lower() for item in value)
    for relation in rule.get("relationships") or []:
        target = relation.get("target", {})
        if target.get("id"):
            tags.append(str(target["id"]).lower())
    return tags


def parse_sarif_findings(sarif_path: Path) -> pd.DataFrame:
    if not sarif_path.exists() or sarif_path.stat().st_size == 0:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    payload = json.loads(sarif_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for run in payload.get("runs", []):
        rules = _rule_lookup(run)
        for result in run.get("results", []):
            rule_id = str(result.get("ruleId") or result.get("rule", {}).get("id") or "")
            rule = rules.get(rule_id, {})
            message_obj = result.get("message", {})
            message = message_obj.get("text", "") if isinstance(message_obj, dict) else str(message_obj)
            severity = str(result.get("level") or rule.get("defaultConfiguration", {}).get("level") or "warning")
            for location in result.get("locations") or [{}]:
                physical = location.get("physicalLocation", {})
                artifact = physical.get("artifactLocation", {})
                region = physical.get("region", {})
                file_path = str(artifact.get("uri") or artifact.get("uriBaseId") or "")
                file_name = Path(file_path).name if file_path else ""
                rows.append(
                    {
                        "Rule ID": rule_id,
                        "Rule Name": _rule_name(rule),
                        "Severity": severity,
                        "Message": message,
                        "File Name": file_name,
                        "File Path": file_path,
                        "Start Line": region.get("startLine", ""),
                        "End Line": region.get("endLine", ""),
                        "Start Column": region.get("startColumn", ""),
                        "End Column": region.get("endColumn", ""),
                        "Rule Description": _rule_description(rule),
                        "Help URL": _rule_help_url(rule),
                    }
                )
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def _rule_matches_metric(rule_id: str, rule_meta: dict[str, Any], metric: dict[str, Any]) -> bool:
    normalized = rule_id.lower()
    for pattern in metric.get("rule_patterns", []):
        if re.search(pattern, normalized):
            return True
    tags = _rule_tags(rule_meta)
    tag_blob = " ".join(tags)
    for tag in metric.get("rule_tags", []):
        if tag.lower() in normalized or tag.lower() in tag_blob:
            return True
    return False


def build_metric_mapping(findings_df: pd.DataFrame, sarif_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(sarif_path.read_text(encoding="utf-8")) if sarif_path.exists() else {"runs": []}
    rule_meta: dict[str, dict[str, Any]] = {}
    for run in payload.get("runs", []):
        rule_meta.update(_rule_lookup(run))

    mappings: list[dict[str, Any]] = []
    for metric in METRIC_DEFINITIONS:
        supporting_rules = sorted(
            {
                rule_id
                for rule_id in findings_df.get("Rule ID", pd.Series(dtype=str)).dropna().astype(str).unique()
                if _rule_matches_metric(rule_id, rule_meta.get(rule_id, {}), metric)
            }
        )
        evidence_df = findings_df[findings_df["Rule ID"].isin(supporting_rules)] if supporting_rules else pd.DataFrame(columns=FINDINGS_COLUMNS)
        if evidence_df.empty:
            mappings.append(
                {
                    **metric,
                    "supporting_rule_ids": [],
                    "supporting_findings_count": 0,
                    "evidence_status": "No evidence found in the current CodeQL analysis.",
                    "evidence_rows": [],
                    "rationale": "No SARIF findings matched the CodeQL rules associated with this metric.",
                }
            )
            continue

        rationale_parts = []
        for rule_id in supporting_rules[:5]:
            sample = evidence_df[evidence_df["Rule ID"] == rule_id].iloc[0]
            rationale_parts.append(
                f"Rule `{rule_id}` ({sample['Rule Name']}) reported `{sample['Severity']}` in "
                f"`{sample['File Path']}` at line {sample['Start Line']}: {sample['Message']}"
            )
        mappings.append(
            {
                **metric,
                "supporting_rule_ids": supporting_rules,
                "supporting_findings_count": int(len(evidence_df)),
                "evidence_status": "Evidence found in SARIF output.",
                "evidence_rows": evidence_df.to_dict(orient="records"),
                "rationale": " ".join(rationale_parts),
            }
        )
    return mappings


def build_evidence_table(findings_df: pd.DataFrame, metric_mappings: list[dict[str, Any]]) -> pd.DataFrame:
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
                    "CodeQL Rule ID": "",
                    "Rule Name": "",
                    "Severity": "",
                    "File": "",
                    "Line": "",
                    "Message": mapping["evidence_status"],
                }
            )
            continue
        for item in evidence_rows:
            rows.append(
                {
                    "Tool": mapping["tool"],
                    "Metric": mapping["metric"],
                    "Classification": mapping["classification"],
                    "Technique": mapping["technique"],
                    "CodeQL Rule ID": item.get("Rule ID", ""),
                    "Rule Name": item.get("Rule Name", ""),
                    "Severity": item.get("Severity", ""),
                    "File": item.get("File Path", ""),
                    "Line": item.get("Start Line", ""),
                    "Message": item.get("Message", ""),
                }
            )
    return pd.DataFrame(rows)


def build_final_summary(
    repo_path: Path,
    findings_df: pd.DataFrame,
    metric_mappings: list[dict[str, Any]],
    db_result: dict[str, Any],
    analyze_result: dict[str, Any],
) -> dict[str, Any]:
    severity_counts = findings_df["Severity"].value_counts(dropna=False).to_dict() if not findings_df.empty else {}
    rule_counts = findings_df["Rule ID"].value_counts(dropna=False).to_dict() if not findings_df.empty else {}
    with_evidence = [m["metric"] for m in metric_mappings if m.get("supporting_findings_count", 0) > 0]
    without_evidence = [m["metric"] for m in metric_mappings if m.get("supporting_findings_count", 0) == 0]
    return {
        "repository_name": repo_path.name,
        "programming_language": PROGRAMMING_LANGUAGE,
        "tool_used": TOOL_NAME,
        "total_source_files_analysed": db_result.get("source_files_indexed", 0),
        "total_codeql_queries_executed": analyze_result.get("queries_executed", 0),
        "total_findings": int(len(findings_df)),
        "findings_by_severity": severity_counts,
        "findings_by_rule": rule_counts,
        "metrics_evaluated": [m["metric"] for m in METRIC_DEFINITIONS],
        "metrics_with_supporting_evidence": with_evidence,
        "metrics_without_supporting_evidence": without_evidence,
        "analysis_duration_ms": round(db_result.get("elapsed_ms", 0) + analyze_result.get("elapsed_ms", 0), 2),
    }


def export_results(
    output_dir: Path,
    sarif_path: Path,
    findings_df: pd.DataFrame,
    evidence_df: pd.DataFrame,
    metric_mappings: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, str]:
    paths = {
        "raw_sarif": output_dir / "results.sarif",
        "parsed_findings_csv": output_dir / "parsed_findings.csv",
        "parsed_findings_json": output_dir / "parsed_findings.json",
        "metric_evidence_csv": output_dir / "metric_evidence_mapping.csv",
        "metric_evidence_json": output_dir / "metric_evidence_mapping.json",
        "final_summary_json": output_dir / "final_analysis_summary.json",
    }
    copy_file_verbatim(sarif_path, paths["raw_sarif"])
    findings_df.to_csv(paths["parsed_findings_csv"], index=False)
    paths["parsed_findings_json"].write_text(findings_df.to_json(orient="records", indent=2), encoding="utf-8")
    evidence_df.to_csv(paths["metric_evidence_csv"], index=False)
    paths["metric_evidence_json"].write_text(json.dumps(metric_mappings, indent=2), encoding="utf-8")
    paths["final_summary_json"].write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return {key: str(path.resolve()) for key, path in paths.items()}


def run_pipeline(repo_path: Path, metric_root: Path, logger: NotebookLogger) -> dict[str, Any]:
    started = time.perf_counter()
    dirs = ensure_output_dirs(metric_root)
    codeql_exe = download_codeql_cli(dirs["codeql_home"], logger)
    codeql_version = verify_codeql(codeql_exe)

    install_result = run_command(["npm", "install"], repo_path, "npm install")
    (dirs["raw"] / "npm_install.log").write_text(
        f"--- stdout ---\n{install_result['stdout']}\n\n--- stderr ---\n{install_result['stderr']}",
        encoding="utf-8",
    )
    if not install_result["success"]:
        logger.error("npm install failed", returncode=install_result["returncode"])

    database_path = dirs["output"] / "codeql-db"
    db_result = create_codeql_database(codeql_exe, repo_path, database_path, dirs["raw"], logger, reuse=True)
    sarif_path = dirs["output"] / "results.sarif"
    analyze_result = analyze_codeql_database(codeql_exe, database_path, sarif_path, dirs["raw"], logger)

    raw_console = "\n\n".join(
        [
            read_text(Path(db_result["log_path"])),
            read_text(Path(analyze_result["log_path"])),
        ]
    )
    (dirs["raw"] / "codeql_cli_execution.log").write_text(raw_console, encoding="utf-8")
    copy_file_verbatim(sarif_path, dirs["raw"] / "results.sarif")

    if not sarif_path.exists():
        logger.error("SARIF report was not generated", path=str(sarif_path))
        logger.write_errors()
        return {
            "pipeline_success": False,
            "codeql_version": codeql_version,
            "install_result": install_result,
            "db_result": db_result,
            "analyze_result": analyze_result,
            "findings_df": pd.DataFrame(columns=FINDINGS_COLUMNS),
            "metric_mappings": [],
            "evidence_df": pd.DataFrame(),
            "summary": {},
            "exported_paths": {},
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    findings_df = parse_sarif_findings(sarif_path)
    metric_mappings = build_metric_mapping(findings_df, sarif_path)
    evidence_df = build_evidence_table(findings_df, metric_mappings)
    summary = build_final_summary(repo_path, findings_df, metric_mappings, db_result, analyze_result)
    exported = export_results(dirs["output"], sarif_path, findings_df, evidence_df, metric_mappings, summary)

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.write_errors()
    pipeline_success = db_result["success"] and analyze_result["success"] and sarif_path.exists()
    return {
        "pipeline_success": pipeline_success,
        "codeql_version": codeql_version,
        "install_result": install_result,
        "db_result": db_result,
        "analyze_result": analyze_result,
        "findings_df": findings_df,
        "metric_mappings": metric_mappings,
        "evidence_df": evidence_df,
        "summary": summary,
        "exported_paths": exported,
        "elapsed_ms": elapsed_ms,
    }
