"""Dependabot raw output extraction and SCA metric validation helpers."""
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
import requests
import yaml
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

os.environ.pop("PYTHONPATH", None)

DEFAULT_REPO_URL = "https://github.com/visvantha-testable/typescript-tool-testing-dependabot.git"
DEFAULT_OWNER = "visvantha-testable"
DEFAULT_REPOSITORY = "typescript-tool-testing-dependabot"
GITHUB_API_VERSION = "2022-11-28"
PACKAGE_MANAGER = "npm"
DEPENDABOT_ALERTS_COLUMNS = [
    "Alert ID",
    "Dependency Name",
    "Package Ecosystem",
    "Manifest Path",
    "Severity",
    "CVE",
    "GHSA ID",
    "Vulnerable Version",
    "First Patched Version",
    "Alert State",
    "Advisory Summary",
    "Created Date",
    "Updated Date",
    "Fixed Version",
]
CONFIG_COLUMNS = [
    "ecosystem",
    "directory",
    "schedule",
    "open_pull_requests_limit",
    "reviewers",
    "labels",
    "assignees",
    "config_file",
]
SECURITY_VALIDATION_COLUMNS = [
    "Testing Type",
    "Classification",
    "Metric",
    "Capability",
    "Supported",
    "Directly Emitted",
    "Derived",
    "Evidence",
    "Comments",
]
DASHBOARD_COLUMNS = [
    "Repository Name",
    "Package Manager",
    "Total Dependencies",
    "Total Dependabot Alerts",
    "Open Alerts",
    "Fixed Alerts",
    "Critical Alerts",
    "High Alerts",
    "Moderate Alerts",
    "Low Alerts",
    "Continuous Dependency Monitoring Status",
    "Real-Time Alerting Status",
]
TYPESCRIPT_REQUIRED_PATHS = (
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    ".github/dependabot.yml",
)


class AuthenticationFailedError(RuntimeError):
    """Raised when GitHub authentication for Dependabot alerts is invalid."""


class NotebookLogger:
    def __init__(self, error_log_path: Path) -> None:
        self.error_log_path = error_log_path
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._errors: list[dict[str, str]] = []
        self.command_log: list[dict[str, Any]] = []
        self.api_log: list[dict[str, Any]] = []
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

    def log_api(self, method: str, url: str, status_code: int | None, elapsed_ms: float, detail: str = "") -> None:
        self.api_log.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "method": method,
                "url": url,
                "status_code": status_code,
                "elapsed_ms": round(elapsed_ms, 2),
                "detail": detail,
            }
        )

    def write_errors(self) -> None:
        with self.error_log_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timestamp", "file", "error_message"])
            writer.writeheader()
            writer.writerows(self._errors)
        if self.command_log or self.api_log:
            with self.error_log_path.open("a", encoding="utf-8") as handle:
                handle.write("\n===== COMMAND LOG =====\n")
                for entry in self.command_log:
                    handle.write(json.dumps(entry) + "\n")
                handle.write("\n===== API LOG =====\n")
                for entry in self.api_log:
                    handle.write(json.dumps(entry) + "\n")


def ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


def resolve_metric_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__).resolve().parent).resolve()
    for _ in range(8):
        if (current / "tool" / "_dependabot_notebook_utils.py").exists():
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
) -> Path:
    if use_git_repo:
        return clone_or_reuse_repository(repo_url, workspace_dir, if_clone_exists, logger)
    return validate_local_repo_path(local_repo, logger)


def validate_typescript_project(repo_path: Path, logger: NotebookLogger) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    for item in TYPESCRIPT_REQUIRED_PATHS:
        target = repo_path / item
        checks[item] = target.is_file()
        if not checks[item]:
            logger.error(f"Missing required TypeScript project file: {item}", file=str(target))
    return {
        "repository_name": repo_path.name,
        **checks,
        "typescript_project_valid": all(checks.values()),
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


def install_npm_dependencies(repo_path: Path, logger: NotebookLogger) -> dict[str, Any]:
    npm = shutil.which("npm")
    if not npm:
        npm = shutil.which("npm.cmd")
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


def verify_runtime_tools(logger: NotebookLogger) -> dict[str, str]:
    versions: dict[str, str] = {}
    for tool, args in (("git", ["--version"]), ("node", ["--version"]), ("npm", ["--version"]), ("python", ["--version"])):
        executable = shutil.which(tool)
        if not executable:
            logger.error(f"{tool} not found on PATH.", file=tool)
            versions[tool] = "NOT FOUND"
            continue
        stdout, stderr, returncode, _ = run_command([executable, *args], logger)
        versions[tool] = (stdout or stderr).strip() if returncode == 0 else f"ERROR ({returncode})"
    return versions


def find_dependabot_config(repo_path: Path) -> Path | None:
    for name in (".github/dependabot.yml", ".github/dependabot.yaml"):
        candidate = repo_path / name
        if candidate.exists():
            return candidate
    return None


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def parse_dependabot_configuration(config_path: Path | None) -> pd.DataFrame:
    if config_path is None:
        return pd.DataFrame(columns=CONFIG_COLUMNS)
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    rows: list[dict[str, str]] = []
    for update in payload.get("updates", []) or []:
        schedule = update.get("schedule") or {}
        rows.append(
            {
                "ecosystem": _stringify(update.get("package-ecosystem")),
                "directory": _stringify(update.get("directory")),
                "schedule": _stringify(schedule.get("interval") or schedule),
                "open_pull_requests_limit": _stringify(update.get("open-pull-requests-limit")),
                "reviewers": _stringify(update.get("reviewers")),
                "labels": _stringify(update.get("labels")),
                "assignees": _stringify(update.get("assignees")),
                "config_file": str(config_path),
            }
        )
    return pd.DataFrame(rows, columns=CONFIG_COLUMNS)


def build_github_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }


def validate_github_token(owner: str, repository: str, token: str, logger: NotebookLogger) -> dict[str, Any]:
    repo_url = f"https://api.github.com/repos/{owner}/{repository}"
    alerts_url = f"{repo_url}/dependabot/alerts?per_page=1"
    result: dict[str, Any] = {
        "token_present": bool(token and token != "YOUR_GITHUB_PERSONAL_ACCESS_TOKEN"),
        "repo_access_ok": False,
        "dependabot_alerts_access_ok": False,
        "rate_limit_remaining": None,
    }
    if not result["token_present"]:
        logger.error(
            "GITHUB_TOKEN is missing or still set to placeholder. Dependabot Alerts API requires a valid token.",
            file="GITHUB_TOKEN",
        )
        return result

    for label, url in (("repo", repo_url), ("dependabot_alerts", alerts_url)):
        start = time.perf_counter()
        try:
            response = requests.get(url, headers=build_github_headers(token), timeout=60)
        except requests.RequestException as exc:
            logger.error(f"Network failure during GitHub API request ({label}): {exc}", file=url)
            logger.log_api("GET", url, None, (time.perf_counter() - start) * 1000, str(exc))
            continue
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.log_api("GET", url, response.status_code, elapsed_ms)
        result["rate_limit_remaining"] = response.headers.get("X-RateLimit-Remaining")
        if label == "repo" and response.status_code == 200:
            result["repo_access_ok"] = True
        if label == "dependabot_alerts" and response.status_code == 200:
            result["dependabot_alerts_access_ok"] = True
        elif label == "dependabot_alerts" and response.status_code == 403:
            logger.error(
                "Unauthorized API access: token lacks permission to read Dependabot alerts "
                "(requires security_events or dependabot_alerts scope).",
                file=url,
            )
        elif label == "dependabot_alerts" and response.status_code == 401:
            logger.error("Invalid GitHub token (401 Unauthorized).", file=url)
        elif label == "dependabot_alerts" and response.status_code == 429:
            logger.error("GitHub API rate limiting encountered (429).", file=url)
        elif label == "dependabot_alerts" and response.status_code not in {200, 404}:
            logger.error(
                f"Dependabot alerts probe failed with HTTP {response.status_code}: {response.text[:300]}",
                file=url,
            )
    return result


def github_authentication_ok(token_validation: dict[str, Any]) -> bool:
    return bool(
        token_validation.get("token_present")
        and token_validation.get("repo_access_ok")
        and token_validation.get("dependabot_alerts_access_ok")
    )


def require_github_authentication(token_validation: dict[str, Any], logger: NotebookLogger) -> None:
    if github_authentication_ok(token_validation):
        return
    if not token_validation.get("token_present"):
        message = (
            "GitHub authentication failed: GITHUB_TOKEN is missing or still set to the placeholder value. "
            "Provide a Personal Access Token with Dependabot alerts read permission."
        )
    elif not token_validation.get("repo_access_ok"):
        message = (
            "GitHub authentication failed: token cannot access repository "
            f"{DEFAULT_OWNER}/{DEFAULT_REPOSITORY}."
        )
    else:
        message = (
            "GitHub authentication failed: token lacks permission to read Dependabot alerts. "
            "Grant security_events or dependabot_alerts scope."
        )
    logger.error(message, file="GITHUB_TOKEN")
    raise AuthenticationFailedError(message)


def empty_raw_payload(owner: str, repository: str) -> dict[str, Any]:
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "owner": owner,
        "repository": repository,
        "api_endpoint": f"GET /repos/{owner}/{repository}/dependabot/alerts",
        "page_count": 0,
        "api_success": False,
        "request_records": [],
        "raw_pages": [],
    }


def _parse_link_header(link_header: str | None) -> dict[str, str]:
    if not link_header:
        return {}
    links: dict[str, str] = {}
    for part in link_header.split(","):
        section = part.strip().split(";")
        if len(section) < 2:
            continue
        url = section[0].strip()[1:-1]
        rel_match = re.search(r'rel="([^"]+)"', section[1])
        if rel_match:
            links[rel_match.group(1)] = url
    return links


def fetch_dependabot_alerts_raw(
    owner: str,
    repository: str,
    token: str,
    logger: NotebookLogger,
) -> dict[str, Any]:
    base_url = f"https://api.github.com/repos/{owner}/{repository}/dependabot/alerts"
    raw_pages: list[str] = []
    request_records: list[dict[str, Any]] = []
    api_success = False
    next_url: str | None = f"{base_url}?per_page=100"

    if not token or token == "YOUR_GITHUB_PERSONAL_ACCESS_TOKEN":
        logger.error("Cannot call Dependabot Alerts API without a valid GITHUB_TOKEN.", file="dependabot_alerts")
        return {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "owner": owner,
            "repository": repository,
            "api_endpoint": f"GET /repos/{owner}/{repository}/dependabot/alerts",
            "page_count": 0,
            "api_success": False,
            "request_records": [],
            "raw_pages": [],
        }

    while next_url:
        start = time.perf_counter()
        try:
            response = requests.get(next_url, headers=build_github_headers(token), timeout=120)
        except requests.RequestException as exc:
            logger.error(f"Dependabot alerts API network failure: {exc}", file=next_url)
            logger.log_api("GET", next_url, None, (time.perf_counter() - start) * 1000, str(exc))
            break
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.log_api("GET", next_url, response.status_code, elapsed_ms)
        request_records.append(
            {
                "url": next_url,
                "status_code": response.status_code,
                "elapsed_ms": round(elapsed_ms, 2),
                "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining"),
            }
        )
        if response.status_code == 429:
            logger.error("GitHub API rate limiting encountered while fetching Dependabot alerts.", file=next_url)
            break
        if response.status_code != 200:
            logger.error(
                f"Dependabot alerts API returned HTTP {response.status_code}: {response.text[:500]}",
                file=next_url,
            )
            break
        api_success = True
        raw_pages.append(response.text)
        links = _parse_link_header(response.headers.get("Link"))
        next_url = links.get("next")

    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "owner": owner,
        "repository": repository,
        "api_endpoint": f"GET /repos/{owner}/{repository}/dependabot/alerts",
        "page_count": len(raw_pages),
        "api_success": api_success,
        "request_records": request_records,
        "raw_pages": raw_pages,
    }


def save_dependabot_alerts_raw(raw_payload: dict[str, Any], output_path: Path) -> None:
    raw_pages = raw_payload.get("raw_pages") or []
    if len(raw_pages) == 1:
        output_path.write_text(raw_pages[0], encoding="utf-8")
        return
    envelope = {
        "preservation_note": "GitHub API responses preserved verbatim in raw_pages.",
        "fetched_at": raw_payload.get("fetched_at"),
        "owner": raw_payload.get("owner"),
        "repository": raw_payload.get("repository"),
        "api_endpoint": raw_payload.get("api_endpoint"),
        "page_count": raw_payload.get("page_count"),
        "request_records": raw_payload.get("request_records"),
        "raw_pages": raw_pages,
    }
    output_path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")


def load_alerts_from_raw(raw_payload: dict[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for page_text in raw_payload.get("raw_pages") or []:
        if not page_text.strip():
            continue
        parsed = json.loads(page_text)
        if isinstance(parsed, list):
            alerts.extend(parsed)
    return alerts


def _extract_identifier(advisory: dict[str, Any], id_type: str) -> str:
    identifiers = advisory.get("identifiers") or []
    for item in identifiers:
        if isinstance(item, dict) and item.get("type") == id_type:
            return _stringify(item.get("value"))
    if id_type == "GHSA":
        return _stringify(advisory.get("ghsa_id"))
    if id_type == "CVE":
        return _stringify(advisory.get("cve_id"))
    return ""


def parse_dependabot_alerts(alerts: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for alert in alerts:
        dependency = alert.get("dependency") or {}
        package = dependency.get("package") or {}
        advisory = alert.get("security_advisory") or {}
        vulnerability = alert.get("security_vulnerability") or {}
        first_patched = vulnerability.get("first_patched_version") or {}
        patched_version = _stringify(first_patched.get("identifier") or first_patched.get("name"))
        rows.append(
            {
                "Alert ID": _stringify(alert.get("number")),
                "Dependency Name": _stringify(package.get("name")),
                "Package Ecosystem": _stringify(package.get("ecosystem")),
                "Manifest Path": _stringify(dependency.get("manifest_path")),
                "Severity": _stringify(advisory.get("severity") or vulnerability.get("severity")),
                "CVE": _extract_identifier(advisory, "CVE"),
                "GHSA ID": _extract_identifier(advisory, "GHSA"),
                "Vulnerable Version": _stringify(
                    dependency.get("version")
                    or dependency.get("requirements")
                    or vulnerability.get("vulnerable_version_range")
                ),
                "First Patched Version": patched_version,
                "Alert State": _stringify(alert.get("state")),
                "Advisory Summary": _stringify(advisory.get("summary")),
                "Created Date": _stringify(alert.get("created_at")),
                "Updated Date": _stringify(alert.get("updated_at")),
                "Fixed Version": patched_version or _stringify(alert.get("fixed_at")),
            }
        )
    return pd.DataFrame(rows, columns=DEPENDABOT_ALERTS_COLUMNS)


def count_npm_dependencies(repo_path: Path) -> int:
    lock_path = repo_path / "package-lock.json"
    if lock_path.exists():
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            packages = lock.get("packages") or {}
            return sum(1 for key in packages if key)
        except json.JSONDecodeError:
            pass
    package_json = repo_path / "package.json"
    if package_json.exists():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
            deps = payload.get("dependencies") or {}
            dev_deps = payload.get("devDependencies") or {}
            return len(deps) + len(dev_deps)
        except json.JSONDecodeError:
            return 0
    return 0


def summarize_alerts(alerts_df: pd.DataFrame) -> dict[str, int]:
    if alerts_df.empty:
        return {
            "total_alerts": 0,
            "open_alerts": 0,
            "fixed_alerts": 0,
            "critical_alerts": 0,
            "high_alerts": 0,
            "moderate_alerts": 0,
            "low_alerts": 0,
        }
    state = alerts_df["Alert State"].str.lower()
    severity = alerts_df["Severity"].str.lower()
    return {
        "total_alerts": len(alerts_df),
        "open_alerts": int((state == "open").sum()),
        "fixed_alerts": int((state == "fixed").sum()),
        "critical_alerts": int((severity == "critical").sum()),
        "high_alerts": int((severity == "high").sum()),
        "moderate_alerts": int((severity == "medium").sum() + (severity == "moderate").sum()),
        "low_alerts": int((severity == "low").sum()),
    }


def build_security_metric_validation(
    dependabot_config_present: bool,
    api_fetch_ok: bool,
    live_alerts_received: bool,
    alert_summary: dict[str, int],
) -> pd.DataFrame:
    if live_alerts_received:
        supported = "Supported"
        directly_emitted = "Yes"
        derived = "No"
        evidence = (
            f"GitHub Dependabot Alerts API returned {alert_summary['total_alerts']} live alert(s); "
            f"open={alert_summary['open_alerts']}; fixed={alert_summary['fixed_alerts']}"
        )
        comments = (
            "Continuous Dependency Monitoring and Real-Time Alerting are directly emitted from "
            "live GitHub Dependabot security alerts for the TypeScript repository."
        )
    elif api_fetch_ok and alert_summary["total_alerts"] == 0:
        supported = "Not Supported"
        directly_emitted = "No"
        derived = "No"
        evidence = "Dependabot Alerts API call succeeded but returned zero live security alerts."
        comments = (
            "Expected validation requires live security alerts from the GitHub Dependabot Alerts API."
        )
    else:
        supported = "Not Supported"
        directly_emitted = "No"
        derived = "No"
        if dependabot_config_present:
            evidence = "dependabot.yml detected, but live Dependabot alerts were not retrieved successfully."
        else:
            evidence = "No dependabot.yml and no live Dependabot alerts from the GitHub API."
        comments = (
            "Metric must be evaluated solely from live GitHub Dependabot alert data."
        )

    row = {
        "Testing Type": "Security White-box Testing",
        "Classification": "Dependency Risk (SCA)",
        "Metric": "Continuous Dependency Monitoring",
        "Capability": "Real-Time Alerting",
        "Supported": supported,
        "Directly Emitted": directly_emitted,
        "Derived": derived,
        "Evidence": evidence,
        "Comments": comments,
    }
    return pd.DataFrame([row], columns=SECURITY_VALIDATION_COLUMNS)


def build_dashboard_summary(
    repository_name: str,
    package_manager: str,
    total_dependencies: int,
    alert_summary: dict[str, int],
    live_alerts_received: bool,
) -> pd.DataFrame:
    status = "PASS" if live_alerts_received else "FAIL"
    row = {
        "Repository Name": repository_name,
        "Package Manager": package_manager,
        "Total Dependencies": total_dependencies,
        "Total Dependabot Alerts": alert_summary["total_alerts"],
        "Open Alerts": alert_summary["open_alerts"],
        "Fixed Alerts": alert_summary["fixed_alerts"],
        "Critical Alerts": alert_summary["critical_alerts"],
        "High Alerts": alert_summary["high_alerts"],
        "Moderate Alerts": alert_summary["moderate_alerts"],
        "Low Alerts": alert_summary["low_alerts"],
        "Continuous Dependency Monitoring Status": status,
        "Real-Time Alerting Status": status,
    }
    return pd.DataFrame([row], columns=DASHBOARD_COLUMNS)


def run_pipeline(
    repo_path: Path,
    output_dir: Path,
    owner: str,
    repository: str,
    github_token: str,
    logger: NotebookLogger | None = None,
) -> dict[str, Any]:
    logger = logger or NotebookLogger(output_dir / "error_log.txt")
    ensure_output_dir(output_dir)
    started = time.perf_counter()

    ts_validation = validate_typescript_project(repo_path, logger)
    install_result = install_npm_dependencies(repo_path, logger)

    config_path = find_dependabot_config(repo_path)
    dependabot_config_present = config_path is not None
    config_df = parse_dependabot_configuration(config_path)
    if not dependabot_config_present:
        logger.error("Missing Dependabot configuration (.github/dependabot.yml).", file=str(repo_path / ".github"))

    config_csv = output_dir / "dependabot_configuration.csv"
    config_df.to_csv(config_csv, index=False)

    token_validation = validate_github_token(owner, repository, github_token, logger)
    raw_payload = empty_raw_payload(owner, repository)
    api_fetch_ok = False
    try:
        require_github_authentication(token_validation, logger)
        raw_payload = fetch_dependabot_alerts_raw(owner, repository, github_token, logger)
        api_fetch_ok = bool(raw_payload.get("api_success"))
    except AuthenticationFailedError:
        pass

    raw_json_path = output_dir / "dependabot_alerts_raw.json"
    save_dependabot_alerts_raw(raw_payload, raw_json_path)

    alerts: list[dict[str, Any]] = []
    if api_fetch_ok:
        try:
            alerts = load_alerts_from_raw(raw_payload)
            if not alerts:
                logger.error("Dependabot Alerts API returned an empty alert response.", file="dependabot_alerts")
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse Dependabot alerts JSON: {exc}", file=str(raw_json_path))

    alerts_df = parse_dependabot_alerts(alerts)
    alerts_csv = output_dir / "dependabot_alerts.csv"
    alerts_df.to_csv(alerts_csv, index=False)

    alert_summary = summarize_alerts(alerts_df)
    total_dependencies = count_npm_dependencies(repo_path)
    live_alerts_received = api_fetch_ok and alert_summary["total_alerts"] > 0

    metric_validation = build_security_metric_validation(
        dependabot_config_present=dependabot_config_present,
        api_fetch_ok=api_fetch_ok,
        live_alerts_received=live_alerts_received,
        alert_summary=alert_summary,
    )
    metric_csv = output_dir / "security_metric_validation.csv"
    metric_validation.to_csv(metric_csv, index=False)

    dashboard = build_dashboard_summary(
        repository_name=ts_validation["repository_name"],
        package_manager=PACKAGE_MANAGER,
        total_dependencies=total_dependencies,
        alert_summary=alert_summary,
        live_alerts_received=live_alerts_received,
    )
    dashboard_csv = output_dir / "dashboard_summary.csv"
    dashboard.to_csv(dashboard_csv, index=False)

    logger.write_errors()
    elapsed_ms = (time.perf_counter() - started) * 1000
    pipeline_success = (
        ts_validation["typescript_project_valid"]
        and dependabot_config_present
        and install_result["returncode"] == 0
        and live_alerts_received
    )

    return {
        "benchmark_ready": pipeline_success,
        "pipeline_success": pipeline_success,
        "repository": str(repo_path),
        "package_manager": PACKAGE_MANAGER,
        "typescript_project_valid": ts_validation["typescript_project_valid"],
        "dependabot_config_present": dependabot_config_present,
        "api_fetch_ok": api_fetch_ok,
        "live_alerts_received": live_alerts_received,
        "total_alerts": alert_summary["total_alerts"],
        "install_returncode": install_result["returncode"],
        "elapsed_ms": round(elapsed_ms, 2),
        "outputs": {
            "dependabot_alerts_raw.json": raw_json_path.exists(),
            "dependabot_alerts.csv": alerts_csv.exists(),
            "dependabot_configuration.csv": config_csv.exists(),
            "security_metric_validation.csv": metric_csv.exists(),
            "dashboard_summary.csv": dashboard_csv.exists(),
            "error_log.txt": (output_dir / "error_log.txt").exists(),
        },
    }
