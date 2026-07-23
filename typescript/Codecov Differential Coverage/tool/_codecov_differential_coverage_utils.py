"""Codecov differential coverage raw output extraction helpers."""
from __future__ import annotations

import json
import os
import platform
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
import requests
from git import Repo
from git.exc import GitCommandError

os.environ.pop("PYTHONPATH", None)

REPO_URL = "https://github.com/visvantha-testable/typescript-tool-testing-vitest-coverage-v8.git"
REPO_SLUG = "visvantha-testable/typescript-tool-testing-vitest-coverage-v8"
CODECOV_SERVICE = "github"
PROGRAMMING_LANGUAGE = "TypeScript"
TOOL_NAME = "Codecov"
TEST_FRAMEWORK = "Vitest"
COVERAGE_PROVIDER = "@vitest/coverage-v8"
ANALYSIS_TYPE = "Differential Coverage Analysis"
CODECOV_API_BASE = "https://api.codecov.io/api/v2"
CODECOV_CLI_RELEASE = "https://api.github.com/repos/codecov/codecov-cli/releases/latest"

METRIC_DEFINITIONS: list[dict[str, Any]] = [
    {
        "tool": "Codecov",
        "metric": "Coverage Delta %",
        "classification": "Coverage Analysis",
        "technique": "Differential Coverage Analysis",
    },
    {
        "tool": "Codecov",
        "metric": "Fresh Logic Proofing",
        "classification": "Code Change Validation",
        "technique": "Differential Coverage Analysis",
    },
]

FINDINGS_COLUMNS = [
    "File Name",
    "File Path",
    "Total Lines",
    "Covered Lines",
    "Missed Lines",
    "Coverage Percentage",
    "New Lines",
    "Changed Lines",
    "Differential Coverage",
    "Commit SHA",
    "Branch Name",
    "Coverage Delta",
    "Patch Coverage",
    "Project Coverage",
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
        if (current / "tool" / "_codecov_differential_coverage_utils.py").exists():
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
        "codecov_cli": metric_root / "output" / "codecov-cli",
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
        env=env or os.environ.copy(),
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
    skip = {".git", "node_modules", "vitest", "knip", "coverage", "dist"}
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
    add("requests", [sys.executable, "-c", "import requests; print(requests.__version__)"])
    add("tabulate", [sys.executable, "-c", "import tabulate; print(tabulate.__version__)"])
    return pd.DataFrame(rows)


def verify_required_packages(repo_path: Path) -> pd.DataFrame:
    package_json = json.loads(read_text(repo_path / "package.json") or "{}")
    dev_deps = package_json.get("devDependencies") or {}
    deps = package_json.get("dependencies") or {}
    all_deps = {**deps, **dev_deps}
    rows = []
    for package in ("vitest", "@vitest/coverage-v8", "typescript"):
        rows.append(
            {
                "Package": package,
                "Installed": "Yes" if package in all_deps else "No",
                "Version": str(all_deps.get(package, "")),
            }
        )
    return pd.DataFrame(rows)


def run_coverage_tests(repo_path: Path) -> dict[str, Any]:
    command = [
        "npx",
        "vitest",
        "run",
        "--coverage",
        "--coverage.reporter=lcov",
        "--coverage.reporter=json-summary",
        "--coverage.reporter=json",
    ]
    result = run_command(command, repo_path, "vitest run --coverage")
    return result


def locate_coverage_artifacts(repo_path: Path) -> dict[str, Path | None]:
    roots = [
        repo_path / "artifacts" / "training" / "coverage",
        repo_path / "coverage",
    ]
    names = {
        "lcov.info": "lcov.info",
        "coverage-final.json": "coverage-final.json",
        "coverage-summary.json": "coverage-summary.json",
    }
    found: dict[str, Path | None] = {key: None for key in names}
    html_dir: Path | None = None
    for root in roots:
        if not root.exists():
            continue
        for key, filename in names.items():
            candidate = root / filename
            if candidate.exists() and found[key] is None:
                found[key] = candidate.resolve()
        for html_name in ("lcov-report", "index.html"):
            candidate = root / html_name
            if candidate.exists():
                html_dir = candidate.resolve()
                break
    found["html_report"] = html_dir
    return found


def describe_coverage_tree(artifacts: dict[str, Path | None]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for name, path in artifacts.items():
        if path is None:
            rows.append({"Artifact": name, "Path": "", "Exists": "No", "Size Bytes": ""})
            continue
        if path.is_dir():
            for child in sorted(path.rglob("*"))[:40]:
                if child.is_file():
                    rel = child.relative_to(path)
                    rows.append(
                        {
                            "Artifact": name,
                            "Path": str(rel),
                            "Exists": "Yes",
                            "Size Bytes": str(child.stat().st_size),
                        }
                    )
        else:
            rows.append(
                {
                    "Artifact": name,
                    "Path": str(path),
                    "Exists": "Yes",
                    "Size Bytes": str(path.stat().st_size),
                }
            )
    return pd.DataFrame(rows)


def parse_local_coverage_summary(summary_path: Path | None) -> dict[str, Any]:
    if summary_path is None or not summary_path.exists():
        return {}
    payload = json.loads(read_text(summary_path))
    total = payload.get("total") or {}
    return {
        "project_coverage": total.get("lines", {}).get("pct"),
        "statements_pct": total.get("statements", {}).get("pct"),
        "branches_pct": total.get("branches", {}).get("pct"),
    }


def get_git_metadata(repo_path: Path) -> dict[str, str]:
    def git(args: list[str]) -> str:
        result = run_command(["git", *args], repo_path, "git metadata")
        return (result["stdout"] or result["stderr"]).strip()

    branch = git(["rev-parse", "--abbrev-ref", "HEAD"])
    sha = git(["rev-parse", "HEAD"])
    parent = git(["rev-parse", "HEAD^"])
    if "fatal" in parent.lower():
        parent = ""
    return {"branch": branch, "commit_sha": sha, "parent_sha": parent}


def _codecov_cli_asset() -> str:
    if platform.system().lower() == "windows":
        return "codecov.exe"
    if platform.system().lower() == "darwin":
        return "codecov"
    return "codecov"


def download_codecov_cli(cli_dir: Path, logger: NotebookLogger) -> Path:
    asset_name = _codecov_cli_asset()
    cli_path = cli_dir / asset_name
    if cli_path.exists():
        return cli_path
    with urllib.request.urlopen(CODECOV_CLI_RELEASE, timeout=60) as response:
        release = json.loads(response.read().decode("utf-8"))
    asset_url = next((asset["browser_download_url"] for asset in release.get("assets", []) if asset["name"] == asset_name), "")
    if not asset_url:
        alt = f"https://cli.codecov.io/latest/{platform.system().lower()}/{asset_name}"
        asset_url = alt
    logger.info("Downloading Codecov CLI", asset=asset_name)
    urllib.request.urlretrieve(asset_url, cli_path)
    if platform.system().lower() != "windows":
        cli_path.chmod(cli_path.stat().st_mode | 0o111)
    return cli_path


def upload_coverage_to_codecov(
    cli_path: Path,
    repo_path: Path,
    lcov_path: Path,
    git_meta: dict[str, str],
    logger: NotebookLogger,
) -> dict[str, Any]:
    token = os.environ.get("CODECOV_TOKEN", "").strip()
    env = os.environ.copy()
    if token:
        env["CODECOV_TOKEN"] = token
    command = [
        str(cli_path),
        "upload-coverage",
        "--disable-search",
        "-f",
        str(lcov_path),
        "--git-service",
        CODECOV_SERVICE,
        "-r",
        REPO_SLUG,
        "-B",
        git_meta.get("branch", "main"),
        "-C",
        git_meta.get("commit_sha", ""),
    ]
    if token:
        command.extend(["-t", token])
    result = run_command(command, repo_path, "codecov upload-coverage", env=env)
    if not token:
        logger.error("CODECOV_TOKEN not set; upload may be rejected by Codecov")
    upload_ok = result["success"] and "failed:" not in result["stderr"].lower()
    return {**result, "token_present": bool(token), "success": upload_ok}


def _codecov_headers() -> dict[str, str]:
    token = os.environ.get("CODECOV_TOKEN", "").strip()
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"bearer {token}"
    return headers


def _save_json_response(path: Path, payload: Any, status_code: int, url: str) -> None:
    envelope = {"url": url, "status_code": status_code, "body": payload}
    path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")


def fetch_codecov_results(
    git_meta: dict[str, str],
    raw_dir: Path,
    logger: NotebookLogger,
) -> dict[str, Any]:
    owner, repo = REPO_SLUG.split("/", 1)
    sha = git_meta.get("commit_sha", "")
    branch = git_meta.get("branch", "")
    parent = git_meta.get("parent_sha", "")
    headers = _codecov_headers()
    responses: dict[str, Any] = {}

    endpoints = {
        "commit_report.json": f"{CODECOV_API_BASE}/{CODECOV_SERVICE}/{owner}/repos/{repo}/commits/{sha}/report",
        "commit_detail.json": f"{CODECOV_API_BASE}/{CODECOV_SERVICE}/{owner}/repos/{repo}/commits/{sha}",
        "branch_detail.json": f"{CODECOV_API_BASE}/{CODECOV_SERVICE}/{owner}/repos/{repo}/branches/{branch}",
    }
    if parent:
        endpoints["compare.json"] = (
            f"{CODECOV_API_BASE}/{CODECOV_SERVICE}/{owner}/repos/{repo}/compare/?base={parent}&head={sha}"
        )

    for filename, url in endpoints.items():
        try:
            response = requests.get(url, headers=headers, timeout=60)
            try:
                body = response.json()
            except ValueError:
                body = {"raw_text": response.text}
            _save_json_response(raw_dir / filename, body, response.status_code, url)
            responses[filename] = {
                "url": url,
                "status_code": response.status_code,
                "body": body,
                "success": response.ok,
            }
        except requests.RequestException as exc:
            logger.error("Codecov API request failed", endpoint=filename, error=str(exc))
            responses[filename] = {"url": url, "status_code": 0, "body": {"error": str(exc)}, "success": False}

    return responses


def _coverage_pct(totals: dict[str, Any] | None) -> float | None:
    if not isinstance(totals, dict):
        return None
    if totals.get("coverage") is not None:
        return float(totals["coverage"])
    lines = totals.get("lines")
    if isinstance(lines, dict) and lines.get("coverage") is not None:
        return float(lines["coverage"])
    return None


def _extract_files_from_report(report_body: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    report = report_body
    if "body" in report_body and isinstance(report_body["body"], dict):
        report = report_body["body"]
    results = report.get("results") or report.get("report") or report
    files = {}
    if isinstance(results, list) and results:
        first = results[0]
        if isinstance(first, dict):
            files = ((first.get("report") or {}).get("files") or first.get("files") or {})
    elif isinstance(results, dict):
        files = results.get("files") or {}
    if not isinstance(files, dict):
        return rows
    for file_path, payload in files.items():
        if not isinstance(payload, dict):
            continue
        totals = payload.get("totals") or {}
        rows.append(
            {
                "File Name": Path(file_path).name,
                "File Path": file_path,
                "Total Lines": totals.get("lines", totals.get("count", "")),
                "Covered Lines": totals.get("hits", ""),
                "Missed Lines": totals.get("misses", ""),
                "Coverage Percentage": _coverage_pct(totals),
                "New Lines": "",
                "Changed Lines": "",
                "Differential Coverage": "",
                "Commit SHA": "",
                "Branch Name": "",
                "Coverage Delta": "",
                "Patch Coverage": "",
                "Project Coverage": _coverage_pct(totals),
            }
        )
    return rows


def _extract_impacted_files(compare_body: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    body = compare_body.get("body") if isinstance(compare_body.get("body"), dict) else compare_body
    impacted = body.get("impacted_files") or body.get("files") or []
    if isinstance(impacted, dict):
        impacted = [{"name": key, **value} for key, value in impacted.items() if isinstance(value, dict)]
    if not isinstance(impacted, list):
        return rows
    for item in impacted:
        if not isinstance(item, dict):
            continue
        head = item.get("head") or {}
        base = item.get("base") or {}
        patch = item.get("patch") or {}
        rows.append(
            {
                "File Name": Path(str(item.get("name", item.get("file", "")))).name,
                "File Path": item.get("name", item.get("file", "")),
                "Total Lines": (head.get("totals") or {}).get("lines", ""),
                "Covered Lines": (head.get("totals") or {}).get("hits", ""),
                "Missed Lines": (head.get("totals") or {}).get("misses", ""),
                "Coverage Percentage": _coverage_pct(head.get("totals")),
                "New Lines": patch.get("lines", ""),
                "Changed Lines": patch.get("lines", ""),
                "Differential Coverage": _coverage_pct(patch.get("totals") or patch),
                "Commit SHA": "",
                "Branch Name": "",
                "Coverage Delta": "",
                "Patch Coverage": _coverage_pct(patch.get("totals") or patch),
                "Project Coverage": _coverage_pct(head.get("totals")),
            }
        )
    return rows


def parse_codecov_findings(responses: dict[str, Any], git_meta: dict[str, str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    commit_report = responses.get("commit_report.json", {})
    compare = responses.get("compare.json", {})
    rows.extend(_extract_files_from_report(commit_report))
    impacted_rows = _extract_impacted_files(compare)
    if impacted_rows:
        rows = impacted_rows
    compare_body = compare.get("body") if isinstance(compare.get("body"), dict) else {}
    totals = compare_body.get("totals") or {}
    base_cov = _coverage_pct((totals.get("base") or {}))
    head_cov = _coverage_pct((totals.get("head") or {}))
    patch_cov = _coverage_pct((totals.get("patch") or {}))
    delta = None
    if base_cov is not None and head_cov is not None:
        delta = round(head_cov - base_cov, 4)
    summary_row = {
        "File Name": "__project__",
        "File Path": REPO_SLUG,
        "Total Lines": (totals.get("head") or {}).get("lines", ""),
        "Covered Lines": (totals.get("head") or {}).get("hits", ""),
        "Missed Lines": (totals.get("head") or {}).get("misses", ""),
        "Coverage Percentage": head_cov,
        "New Lines": (totals.get("patch") or {}).get("lines", ""),
        "Changed Lines": (totals.get("patch") or {}).get("lines", ""),
        "Differential Coverage": patch_cov,
        "Commit SHA": git_meta.get("commit_sha", ""),
        "Branch Name": git_meta.get("branch", ""),
        "Coverage Delta": delta,
        "Patch Coverage": patch_cov,
        "Project Coverage": head_cov,
    }
    if any(value not in ("", None) for key, value in summary_row.items() if key not in {"File Name", "File Path"}):
        rows.insert(0, summary_row)
    for row in rows:
        if not row.get("Commit SHA"):
            row["Commit SHA"] = git_meta.get("commit_sha", "")
        if not row.get("Branch Name"):
            row["Branch Name"] = git_meta.get("branch", "")
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def build_metric_mappings(findings_df: pd.DataFrame, responses: dict[str, Any]) -> list[dict[str, Any]]:
    compare = responses.get("compare.json", {})
    compare_body = compare.get("body") if isinstance(compare.get("body"), dict) else {}
    totals = compare_body.get("totals") or {}
    base_cov = _coverage_pct((totals.get("base") or {}))
    head_cov = _coverage_pct((totals.get("head") or {}))
    patch_cov = _coverage_pct((totals.get("patch") or {}))
    delta = None
    if base_cov is not None and head_cov is not None:
        delta = round(head_cov - base_cov, 4)

    project_rows = findings_df[findings_df["File Name"] == "__project__"] if not findings_df.empty else pd.DataFrame()
    if not project_rows.empty:
        row = project_rows.iloc[0]
        if row.get("Coverage Delta") not in ("", None):
            delta = row.get("Coverage Delta")
        if row.get("Project Coverage") not in ("", None):
            head_cov = row.get("Project Coverage")
        if row.get("Patch Coverage") not in ("", None):
            patch_cov = row.get("Patch Coverage")

    mappings: list[dict[str, Any]] = []

    delta_metric = METRIC_DEFINITIONS[0].copy()
    if delta is None and base_cov is None and head_cov is None:
        delta_metric.update(
            {
                "previous_coverage": None,
                "current_coverage": None,
                "coverage_delta": None,
                "affected_files": [],
                "evidence_status": "No evidence found in the current Codecov analysis.",
                "rationale": "Codecov compare/commit API did not return project coverage totals.",
                "evidence_rows": [],
            }
        )
    else:
        affected = findings_df[findings_df["File Name"] != "__project__"]["File Path"].dropna().astype(str).tolist()
        delta_metric.update(
            {
                "previous_coverage": base_cov,
                "current_coverage": head_cov,
                "coverage_delta": delta,
                "affected_files": affected,
                "evidence_status": "Evidence found in Codecov API response.",
                "rationale": (
                    f"Codecov compare totals report base={base_cov}, head={head_cov}, delta={delta}."
                ),
                "evidence_rows": project_rows.to_dict(orient="records"),
            }
        )
    mappings.append(delta_metric)

    fresh_metric = METRIC_DEFINITIONS[1].copy()
    changed_rows = findings_df[(findings_df["File Name"] != "__project__") & findings_df["Patch Coverage"].notna()]
    if changed_rows.empty and patch_cov is None:
        fresh_metric.update(
            {
                "patch_coverage": None,
                "uncovered_new_lines": [],
                "changed_files": [],
                "evidence_status": "No evidence found in the current Codecov analysis.",
                "rationale": "Codecov did not return patch or impacted-file differential coverage.",
                "evidence_rows": [],
            }
        )
    else:
        uncovered = changed_rows[changed_rows["Missed Lines"].astype(str).replace("", "0").astype(float) > 0]
        fresh_metric.update(
            {
                "patch_coverage": patch_cov,
                "uncovered_new_lines": uncovered[["File Path", "Missed Lines", "Patch Coverage"]].to_dict(orient="records"),
                "changed_files": changed_rows["File Path"].dropna().astype(str).tolist(),
                "evidence_status": "Evidence found in Codecov API response.",
                "rationale": (
                    f"Codecov patch coverage={patch_cov} across {len(changed_rows)} impacted file(s)."
                ),
                "evidence_rows": changed_rows.to_dict(orient="records"),
            }
        )
    mappings.append(fresh_metric)
    return mappings


def build_evidence_table(metric_mappings: list[dict[str, Any]], findings_df: pd.DataFrame) -> pd.DataFrame:
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
                    "File": "",
                    "Branch": findings_df["Branch Name"].iloc[0] if not findings_df.empty else "",
                    "Commit": findings_df["Commit SHA"].iloc[0] if not findings_df.empty else "",
                    "Previous Coverage": mapping.get("previous_coverage", ""),
                    "Current Coverage": mapping.get("current_coverage", mapping.get("patch_coverage", "")),
                    "Coverage Delta": mapping.get("coverage_delta", ""),
                    "Patch Coverage": mapping.get("patch_coverage", ""),
                    "Evidence": mapping["evidence_status"],
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
                    "File": item.get("File Path", item.get("file", "")),
                    "Branch": item.get("Branch Name", ""),
                    "Commit": item.get("Commit SHA", ""),
                    "Previous Coverage": mapping.get("previous_coverage", ""),
                    "Current Coverage": item.get("Project Coverage", item.get("Coverage Percentage", mapping.get("current_coverage", ""))),
                    "Coverage Delta": item.get("Coverage Delta", mapping.get("coverage_delta", "")),
                    "Patch Coverage": item.get("Patch Coverage", mapping.get("patch_coverage", "")),
                    "Evidence": mapping["rationale"],
                }
            )
    return pd.DataFrame(rows)


def build_final_summary(
    repo_path: Path,
    findings_df: pd.DataFrame,
    metric_mappings: list[dict[str, Any]],
    local_summary: dict[str, Any],
) -> dict[str, Any]:
    file_rows = findings_df[findings_df["File Name"] != "__project__"] if not findings_df.empty else pd.DataFrame()
    project_row = findings_df[findings_df["File Name"] == "__project__"].iloc[0] if (not findings_df.empty and (findings_df["File Name"] == "__project__").any()) else None
    covered_files = 0
    uncovered_files = 0
    if not file_rows.empty and "Coverage Percentage" in file_rows.columns:
        for value in file_rows["Coverage Percentage"]:
            try:
                if float(value) >= 100:
                    covered_files += 1
                else:
                    uncovered_files += 1
            except (TypeError, ValueError):
                uncovered_files += 1
    with_evidence = [m["metric"] for m in metric_mappings if m.get("evidence_status", "").startswith("Evidence found")]
    without_evidence = [m["metric"] for m in metric_mappings if not m.get("evidence_status", "").startswith("Evidence found")]
    return {
        "repository_name": repo_path.name,
        "programming_language": PROGRAMMING_LANGUAGE,
        "tool_used": TOOL_NAME,
        "total_files_analysed": int(len(file_rows)),
        "total_covered_files": covered_files,
        "total_uncovered_files": uncovered_files,
        "project_coverage": (project_row["Project Coverage"] if project_row is not None else local_summary.get("project_coverage")),
        "patch_coverage": (project_row["Patch Coverage"] if project_row is not None else None),
        "coverage_delta": (project_row["Coverage Delta"] if project_row is not None else None),
        "metrics_evaluated": [m["metric"] for m in METRIC_DEFINITIONS],
        "metrics_with_supporting_evidence": with_evidence,
        "metrics_without_supporting_evidence": without_evidence,
    }


def export_results(
    output_dir: Path,
    raw_dir: Path,
    findings_df: pd.DataFrame,
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
        "raw_responses_dir": raw_dir,
    }
    findings_df.to_csv(paths["parsed_findings_csv"], index=False)
    paths["parsed_findings_json"].write_text(findings_df.to_json(orient="records", indent=2), encoding="utf-8")
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

    packages_df = verify_required_packages(repo_path)
    coverage_result = run_coverage_tests(repo_path)
    (dirs["raw"] / "vitest_coverage.log").write_text(
        f"--- stdout ---\n{coverage_result['stdout']}\n\n--- stderr ---\n{coverage_result['stderr']}",
        encoding="utf-8",
    )

    artifacts = locate_coverage_artifacts(repo_path)
    artifacts_df = describe_coverage_tree(artifacts)
    for key in ("lcov.info", "coverage-final.json", "coverage-summary.json"):
        if artifacts.get(key):
            copy_file_verbatim(artifacts[key], dirs["raw"] / Path(str(artifacts[key])).name)

    local_summary = parse_local_coverage_summary(artifacts.get("coverage-summary.json"))
    git_meta = get_git_metadata(repo_path)

    cli_path = download_codecov_cli(dirs["codecov_cli"], logger)
    upload_result = {"success": False, "token_present": bool(os.environ.get("CODECOV_TOKEN", "").strip()), "stdout": "", "stderr": ""}
    if artifacts.get("lcov.info"):
        upload_result = upload_coverage_to_codecov(cli_path, repo_path, artifacts["lcov.info"], git_meta, logger)
    (dirs["raw"] / "codecov_upload.log").write_text(
        f"--- stdout ---\n{upload_result.get('stdout', '')}\n\n--- stderr ---\n{upload_result.get('stderr', '')}",
        encoding="utf-8",
    )

    codecov_responses = fetch_codecov_results(git_meta, dirs["raw"], logger)
    findings_df = parse_codecov_findings(codecov_responses, git_meta)
    metric_mappings = build_metric_mappings(findings_df, codecov_responses)
    evidence_df = build_evidence_table(metric_mappings, findings_df)
    summary = build_final_summary(repo_path, findings_df, metric_mappings, local_summary)
    exported = export_results(dirs["output"], dirs["raw"], findings_df, evidence_df, metric_mappings, summary)

    logger.write_errors()
    pipeline_success = coverage_result["success"] and artifacts.get("lcov.info") is not None
    return {
        "pipeline_success": pipeline_success,
        "install_result": install_result,
        "packages_df": packages_df,
        "coverage_result": coverage_result,
        "artifacts": artifacts,
        "artifacts_df": artifacts_df,
        "local_summary": local_summary,
        "git_meta": git_meta,
        "upload_result": upload_result,
        "codecov_responses": codecov_responses,
        "findings_df": findings_df,
        "metric_mappings": metric_mappings,
        "evidence_df": evidence_df,
        "summary": summary,
        "exported_paths": exported,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    }
