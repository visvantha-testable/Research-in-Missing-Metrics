"""OpenTelemetry (.NET) raw execution trace extraction helpers."""
from __future__ import annotations

import csv
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

REPO_URL = "https://github.com/visvantha-testable/csharp-testing-opentelemetry.git"
PROGRAMMING_LANGUAGE = "C#"
TOOL_NAME = "OpenTelemetry (.NET) + OTLP/Jaeger/Zipkin Exporter"
ANALYSIS_TYPE = "White Box Execution Trace Extraction"
DOTNET_CHANNEL = "9.0"

EXCLUDE_DIRS = {".git", "bin", "obj", "packages", ".vs", "node_modules"}
OTEL_PACKAGE_PATTERN = re.compile(r"OpenTelemetry", re.IGNORECASE)
EXECUTABLE_OUTPUT_PATTERN = re.compile(r"<OutputType>\s*Exe\s*</OutputType>", re.IGNORECASE)
OPENTELEMETRY_PACKAGE_PATTERN = re.compile(
    r"PackageReference\s+Include=\"(OpenTelemetry[^\"]*)\"",
    re.IGNORECASE,
)

EXPORTER_FILES = {
    "otlp": ["otlp_export.json", "otlp.json", "traces.otlp.json"],
    "jaeger": ["jaeger_export.json", "jaeger.json"],
    "zipkin": ["zipkin_export.json", "zipkin.json"],
}

INVENTORY_COLUMNS = ["file_path", "file_name", "directory"]
SPAN_COLUMNS = [
    "trace_id",
    "span_id",
    "parent_span_id",
    "span_name",
    "operation_name",
    "kind",
    "status",
    "duration_ms",
    "start_time",
    "end_time",
]
EVENT_COLUMNS = ["trace_id", "span_id", "event_name", "timestamp", "attributes"]
ATTRIBUTE_COLUMNS = ["trace_id", "span_id", "attribute_name", "attribute_value"]


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
        if (current / "tool" / "_opentelemetry_utils.py").exists():
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
    repo_path = validate_local_repo_path(Path(local_repo_path), logger)
    return repo_path, f"Using local repository at {repo_path}"


def should_skip_path(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)


def discover_csharp_inventory(repo_path: Path) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    patterns = ("*.cs", "*.csproj", "*.sln")
    for pattern in patterns:
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


def discover_solution(repo_path: Path) -> Path | None:
    solutions = sorted(path for path in repo_path.glob("*.sln") if not should_skip_path(path))
    return solutions[0].resolve() if solutions else None


def discover_projects(repo_path: Path) -> list[Path]:
    return [
        path.resolve()
        for path in sorted(repo_path.rglob("*.csproj"))
        if not should_skip_path(path)
    ]


def discover_executable_project(repo_path: Path, logger: NotebookLogger) -> Path | None:
    platform_project = repo_path / "src" / "OpenTelemetryPlatform" / "OpenTelemetryPlatform.csproj"
    if platform_project.exists():
        return platform_project.resolve()

    executables: list[Path] = []
    for project in discover_projects(repo_path):
        content = project.read_text(encoding="utf-8", errors="replace")
        if EXECUTABLE_OUTPUT_PATTERN.search(content) or "Program.cs" in {
            source.name for source in project.parent.rglob("Program.cs") if not should_skip_path(source)
        }:
            executables.append(project)

    if not executables:
        logger.error("No executable .csproj discovered.", file=str(repo_path))
        return None
    if len(executables) > 1:
        preferred = next((p for p in executables if "Platform" in p.name or "App" in p.name), executables[0])
        logger.info(f"Multiple executable projects found; selected {preferred.name}")
        return preferred
    return executables[0]


def get_repository_commit(repo_path: Path) -> str:
    try:
        return Repo(repo_path).head.commit.hexsha
    except (InvalidGitRepositoryError, ValueError, TypeError):
        return "unknown"


def compute_repository_stats(repo_path: Path, inventory_df: pd.DataFrame) -> dict[str, Any]:
    cs_files = inventory_df[inventory_df["file_name"].str.endswith(".cs", na=False)]
    total_size = sum((repo_path / row["file_path"]).stat().st_size for _, row in cs_files.iterrows() if (repo_path / row["file_path"]).exists())
    solutions = inventory_df[inventory_df["file_name"].str.endswith(".sln", na=False)]["file_path"].tolist()
    projects = inventory_df[inventory_df["file_name"].str.endswith(".csproj", na=False)]["file_path"].tolist()
    return {
        "repository_name": repo_path.name,
        "repository_size_bytes": total_size,
        "csharp_file_count": len(cs_files),
        "solution_files": solutions,
        "project_files": projects,
        "commit_hash": get_repository_commit(repo_path),
    }


def dotnet_executable(dotnet_root: Path) -> Path:
    return dotnet_root / ("dotnet.exe" if sys.platform.startswith("win") else "dotnet")


def download_dotnet_sdk(install_dir: Path, channel: str = DOTNET_CHANNEL, tmp_dir: Path | None = None) -> Path:
    install_dir = install_dir.resolve()
    install_dir.mkdir(parents=True, exist_ok=True)
    dotnet = dotnet_executable(install_dir)
    if dotnet.exists():
        return install_dir

    shared_roots = [
        install_dir.parents[2] / "runtimes" / "dotnet-sdk-9",
        Path(__file__).resolve().parents[2] / "dotnet" / "runtimes" / "dotnet-sdk-9",
        Path(__file__).resolve().parents[2] / "runtimes" / "dotnet-sdk-9",
    ]
    for shared_root in shared_roots:
        shared_dotnet = dotnet_executable(shared_root)
        if shared_dotnet.exists():
            return shared_root.resolve()

    program_files = Path(r"C:\Program Files\dotnet\dotnet.exe")
    if program_files.exists():
        return program_files.parent

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
    if dotnet_root.name == "dotnet.exe":
        dotnet_root = dotnet_root.parent
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
    elapsed_ms = round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 2)
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    return {
        "command": " ".join(command),
        "stdout": stdout,
        "stderr": stderr,
        "returncode": completed.returncode,
        "success": completed.returncode == 0,
        "elapsed_ms": elapsed_ms,
    }


def dotnet_command(dotnet_root: Path, *args: str) -> list[str]:
    return [str(dotnet_executable(dotnet_root)), *args]


def collect_prerequisite_versions(dotnet_root: Path, env: dict[str, str], repo_path: Path | None = None) -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    def add(name: str, command: list[str], cwd: Path | None = None) -> None:
        result = run_command(command, cwd or Path.cwd(), env if command[0] == str(dotnet_executable(dotnet_root)) else os.environ.copy())
        output = (result["stdout"] or result["stderr"]).strip()
        version = output.splitlines()[0] if output else ""
        rows.append({"component": name, "version": version, "status": "ok" if result["success"] else "error"})

    add(".NET SDK", dotnet_command(dotnet_root, "--version"))
    add("dotnet tool list", dotnet_command(dotnet_root, "tool", "list"))

    otel_packages: list[str] = []
    if repo_path is not None:
        for project in discover_projects(repo_path):
            content = project.read_text(encoding="utf-8", errors="replace")
            otel_packages.extend(OPENTELEMETRY_PACKAGE_PATTERN.findall(content))
    otel_packages = sorted(set(otel_packages))
    rows.append(
        {
            "component": "OpenTelemetry packages",
            "version": ", ".join(otel_packages) if otel_packages else "none detected",
            "status": "ok" if otel_packages else "warning",
        }
    )

    for module_name in ("pandas", "gitpython", "jupyter"):
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


def run_dotnet_restore(repo_path: Path, solution_path: Path | None, dotnet_root: Path, env: dict[str, str]) -> dict[str, Any]:
    target = solution_path if solution_path and solution_path.exists() else discover_projects(repo_path)[0]
    result = run_command(dotnet_command(dotnet_root, "restore", str(target.relative_to(repo_path))), repo_path, env)
    result["target"] = str(target)
    return result


def run_dotnet_build(repo_path: Path, solution_path: Path | None, dotnet_root: Path, env: dict[str, str]) -> dict[str, Any]:
    target = solution_path if solution_path and solution_path.exists() else discover_projects(repo_path)[0]
    result = run_command(dotnet_command(dotnet_root, "build", str(target.relative_to(repo_path)), "--no-restore"), repo_path, env)
    result["target"] = str(target)
    result["project_count"] = len(discover_projects(repo_path))
    return result


def run_dotnet_execute(repo_path: Path, project_path: Path, dotnet_root: Path, env: dict[str, str]) -> dict[str, Any]:
    relative = project_path.relative_to(repo_path)
    platform_trigger = project_path.name == "OpenTelemetryPlatform.csproj"
    if platform_trigger:
        command = dotnet_command(dotnet_root, "run", "--project", str(relative), "--", "trigger", "--skip-verify")
    else:
        command = dotnet_command(dotnet_root, "run", "--project", str(relative), "--no-build")
    result = run_command(command, repo_path, env)
    result["project"] = str(relative)
    result["trigger_mode"] = platform_trigger
    return result


def find_exporter_file(repo_path: Path, exporter: str) -> Path | None:
    candidates = EXPORTER_FILES.get(exporter.lower(), [])
    search_roots = [
        repo_path / "artifacts" / "training",
        repo_path / "artifacts",
        repo_path / "outputs",
        repo_path,
    ]
    for root in search_roots:
        if not root.exists():
            continue
        for name in candidates:
            candidate = root / name
            if candidate.exists():
                return candidate.resolve()
        for candidate in root.rglob("*.json"):
            if should_skip_path(candidate):
                continue
            if candidate.name.lower() in {name.lower() for name in candidates}:
                return candidate.resolve()
    return None


def preserve_raw_trace_output(source_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, output_path)


def _parse_timestamp(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _duration_ms(start: Any, end: Any) -> str:
    if not start or not end:
        return ""
    try:
        start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
        return str(round((end_dt - start_dt).total_seconds() * 1000, 3))
    except ValueError:
        return ""


def _normalize_tags(tags: Any) -> dict[str, Any]:
    if isinstance(tags, dict):
        return tags
    if isinstance(tags, list):
        normalized: dict[str, Any] = {}
        for item in tags:
            if isinstance(item, dict) and "key" in item:
                normalized[str(item["key"])] = item.get("value", "")
        return normalized
    return {}


def _otlp_attribute_list_to_dict(attributes: Any) -> dict[str, Any]:
    if isinstance(attributes, dict):
        return attributes
    if not isinstance(attributes, list):
        return {}
    result: dict[str, Any] = {}
    for item in attributes:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if key is None:
            continue
        value_obj = item.get("value")
        if isinstance(value_obj, dict):
            value = next((value_obj[k] for k in ("stringValue", "intValue", "boolValue", "doubleValue") if k in value_obj), "")
        else:
            value = value_obj
        result[str(key)] = value
    return result


def _flatten_otlp_resource_spans(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten OTLP JSON (flat benchmark export or standard nested resourceSpans)."""
    records: list[dict[str, Any]] = []
    for resource_span in payload.get("resourceSpans") or []:
        if not isinstance(resource_span, dict):
            continue

        resource_attrs = _otlp_attribute_list_to_dict(resource_span.get("resource", {}).get("attributes"))
        if resource_span.get("tags"):
            resource_attrs = {**resource_attrs, **_normalize_tags(resource_span.get("tags"))}

        # Benchmark repo writes span fields directly under resourceSpans entries.
        if resource_span.get("traceId") or resource_span.get("spanId") or resource_span.get("name"):
            merged = dict(resource_span)
            if resource_attrs:
                merged.setdefault("resourceAttributes", resource_attrs)
            records.append(_normalize_span_record(merged, exporter_hint="otlp"))
            continue

        for scope_span in resource_span.get("scopeSpans") or []:
            if not isinstance(scope_span, dict):
                continue
            scope = scope_span.get("scope") or scope_span.get("instrumentationScope") or {}
            for span in scope_span.get("spans") or []:
                if not isinstance(span, dict):
                    continue
                merged = dict(span)
                if resource_attrs:
                    merged.setdefault("resourceAttributes", resource_attrs)
                if scope:
                    merged.setdefault("instrumentationScope", scope)
                if isinstance(span.get("attributes"), list):
                    merged["attributes"] = _otlp_attribute_list_to_dict(span["attributes"])
                records.append(_normalize_span_record(merged, exporter_hint="otlp"))
    return records


def extract_spans_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []

    if isinstance(payload.get("spans"), list):
        for span in payload["spans"]:
            if isinstance(span, dict):
                spans.append(_normalize_span_record(span, exporter_hint="zipkin" if "id" in span else "generic"))
        return spans

    if isinstance(payload.get("resourceSpans"), list):
        return _flatten_otlp_resource_spans(payload)

    if isinstance(payload.get("data"), list):
        for span in payload["data"]:
            if isinstance(span, dict):
                spans.append(_normalize_span_record(span, exporter_hint="jaeger"))
        return spans

    # Jaeger API v2 trace wrapper: {"result": [...]} or single trace object.
    if isinstance(payload.get("result"), list):
        for span in payload["result"]:
            if isinstance(span, dict):
                spans.append(_normalize_span_record(span, exporter_hint="jaeger"))
        return spans

    return spans


def _normalize_span_record(span: dict[str, Any], exporter_hint: str) -> dict[str, Any]:
    trace_id = span.get("traceId") or span.get("traceID") or span.get("trace_id") or ""
    span_id = span.get("spanId") or span.get("spanID") or span.get("id") or span.get("span_id") or ""
    parent_span_id = span.get("parentSpanId") or span.get("parentSpanID") or span.get("parentId") or ""
    references = span.get("references")
    if not parent_span_id and isinstance(references, list):
        for ref in references:
            if isinstance(ref, dict) and ref.get("refType") in {"CHILD_OF", "child_of", None}:
                parent_span_id = ref.get("spanID") or ref.get("spanId") or ""
                if parent_span_id:
                    break
    span_name = span.get("name") or span.get("spanName") or ""
    operation_name = span.get("operationName") or span.get("operation_name") or span_name
    kind = str(span.get("kind") or span.get("spanKind") or "")
    status_obj = span.get("status")
    if isinstance(status_obj, dict):
        status = str(status_obj.get("code") or status_obj.get("message") or "")
    else:
        status = str(status_obj or "")
    start_time = _parse_timestamp(span.get("startTime") or span.get("startTimeUnixNano") or span.get("timestamp"))
    end_time = _parse_timestamp(span.get("endTime") or span.get("endTimeUnixNano"))
    duration = span.get("duration") or _duration_ms(start_time, end_time)
    tags = _normalize_tags(span.get("tags") or span.get("attributes"))
    events = span.get("events") or []
    links = span.get("links") or []
    resource = span.get("resource") or span.get("resourceAttributes") or {}
    scope = span.get("instrumentationScope") or span.get("instrumentationLibrary") or {}

    return {
        "trace_id": str(trace_id),
        "span_id": str(span_id),
        "parent_span_id": str(parent_span_id),
        "span_name": str(span_name),
        "operation_name": str(operation_name),
        "kind": kind,
        "status": status,
        "duration_ms": str(duration),
        "start_time": start_time,
        "end_time": end_time,
        "events": events,
        "links": links,
        "attributes": tags,
        "resource_attributes": resource if isinstance(resource, dict) else {},
        "instrumentation_scope": scope if isinstance(scope, dict) else {},
        "exception_events": [event for event in events if isinstance(event, dict) and "exception" in str(event.get("name", "")).lower()],
        "exporter_hint": exporter_hint,
    }


def build_spans_dataframe(spans: list[dict[str, Any]]) -> pd.DataFrame:
    rows = [{column: span.get(column, "") for column in SPAN_COLUMNS} for span in spans]
    return pd.DataFrame(rows, columns=SPAN_COLUMNS)


def build_events_dataframe(spans: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for span in spans:
        for event in span.get("events") or []:
            if not isinstance(event, dict):
                continue
            rows.append(
                {
                    "trace_id": span.get("trace_id", ""),
                    "span_id": span.get("span_id", ""),
                    "event_name": str(event.get("name", "")),
                    "timestamp": _parse_timestamp(event.get("time") or event.get("timestamp")),
                    "attributes": json.dumps(event.get("attributes") or {}, sort_keys=True),
                }
            )
    return pd.DataFrame(rows, columns=EVENT_COLUMNS)


def build_attributes_dataframe(spans: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for span in spans:
        for name, value in (span.get("attributes") or {}).items():
            rows.append(
                {
                    "trace_id": span.get("trace_id", ""),
                    "span_id": span.get("span_id", ""),
                    "attribute_name": str(name),
                    "attribute_value": str(value),
                }
            )
    return pd.DataFrame(rows, columns=ATTRIBUTE_COLUMNS)


def build_execution_summary(spans: list[dict[str, Any]], execution_status: str) -> dict[str, Any]:
    trace_ids = {span.get("trace_id") for span in spans if span.get("trace_id")}
    parent_ids = {span.get("parent_span_id") for span in spans if span.get("parent_span_id")}
    root_spans = sum(1 for span in spans if span.get("span_id") and span.get("span_id") not in parent_ids)
    child_spans = max(len(spans) - root_spans, 0)
    exception_events = sum(len(span.get("exception_events") or []) for span in spans)
    return {
        "total_traces": len(trace_ids),
        "total_spans": len(spans),
        "root_spans": root_spans,
        "child_spans": child_spans,
        "exception_events": exception_events,
        "execution_status": execution_status,
    }


def collect_environment_json(dotnet_root: Path, env: dict[str, str], exporter: str) -> dict[str, Any]:
    dotnet_version = run_command(dotnet_command(dotnet_root, "--version"), Path.cwd(), env)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "dotnet_version": (dotnet_version["stdout"] or dotnet_version["stderr"]).strip(),
        "platform": sys.platform,
        "exporter": exporter,
        "otel_exporter_otlp_endpoint": env.get("OTEL_EXPORTER_OTLP_ENDPOINT", ""),
        "otel_exporter_otlp_traces_endpoint": env.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", ""),
        "otel_exporter_jaeger_endpoint": env.get("OTEL_EXPORTER_JAEGER_ENDPOINT", ""),
        "otel_exporter_zipkin_endpoint": env.get("OTEL_EXPORTER_ZIPKIN_ENDPOINT", ""),
    }


def export_deliverables(
    output_dir: Path,
    inventory_df: pd.DataFrame,
    raw_source: Path,
    spans_df: pd.DataFrame,
    events_df: pd.DataFrame,
    attributes_df: pd.DataFrame,
    execution_metadata: dict[str, Any],
    environment: dict[str, Any],
    restore_result: dict[str, Any],
    build_result: dict[str, Any],
    run_result: dict[str, Any],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "raw_output": output_dir / "opentelemetry_raw_output.json",
        "spans_csv": output_dir / "spans.csv",
        "events_csv": output_dir / "events.csv",
        "attributes_csv": output_dir / "attributes.csv",
        "inventory_csv": output_dir / "csharp_inventory.csv",
        "execution_metadata": output_dir / "execution_metadata.json",
        "environment": output_dir / "environment.json",
        "build_stdout": output_dir / "build_stdout.txt",
        "build_stderr": output_dir / "build_stderr.txt",
        "run_stdout": output_dir / "run_stdout.txt",
        "run_stderr": output_dir / "run_stderr.txt",
    }
    preserve_raw_trace_output(raw_source, paths["raw_output"])
    inventory_df.to_csv(paths["inventory_csv"], index=False)
    spans_df.to_csv(paths["spans_csv"], index=False)
    events_df.to_csv(paths["events_csv"], index=False)
    attributes_df.to_csv(paths["attributes_csv"], index=False)
    paths["execution_metadata"].write_text(json.dumps(execution_metadata, indent=2), encoding="utf-8")
    paths["environment"].write_text(json.dumps(environment, indent=2), encoding="utf-8")
    paths["build_stdout"].write_text(build_result.get("stdout", ""), encoding="utf-8")
    paths["build_stderr"].write_text(build_result.get("stderr", ""), encoding="utf-8")
    paths["run_stdout"].write_text(run_result.get("stdout", ""), encoding="utf-8")
    paths["run_stderr"].write_text(run_result.get("stderr", ""), encoding="utf-8")
    return paths


def run_pipeline(
    metric_root: Path,
    *,
    use_git_url: bool,
    repo_url: str,
    local_repo_path: str,
    workspace_dir: Path,
    output_dir: Path,
    exporter: str,
    if_clone_exists: str,
    logger: NotebookLogger,
) -> dict[str, Any]:
    dirs = ensure_output_dirs(metric_root)
    dotnet_root = download_dotnet_sdk(dirs["runtimes"], tmp_dir=dirs["tmp"])
    env = dotnet_env(dotnet_root, tmp_dir=dirs["tmp"])

    repo_path, clone_status = resolve_repository_path(
        use_git_url, repo_url, local_repo_path, workspace_dir, if_clone_exists, logger
    )
    inventory_df = discover_csharp_inventory(repo_path)
    repo_stats = compute_repository_stats(repo_path, inventory_df)
    solution_path = discover_solution(repo_path)

    restore_result = run_dotnet_restore(repo_path, solution_path, dotnet_root, env)
    if not restore_result["success"]:
        logger.error("dotnet restore failed.", file=restore_result.get("target", "restore"))
    build_result = {"stdout": "", "stderr": "", "success": False, "elapsed_ms": 0, "returncode": 1}
    run_result = {"stdout": "", "stderr": "", "success": False, "elapsed_ms": 0, "returncode": 1}
    if restore_result["success"]:
        build_result = run_dotnet_build(repo_path, solution_path, dotnet_root, env)
        if not build_result["success"]:
            logger.error("dotnet build failed.", file=build_result.get("target", "build"))

    execution_status = "FAILED"
    raw_source: Path | None = None
    spans: list[dict[str, Any]] = []

    if build_result.get("success"):
        executable = discover_executable_project(repo_path, logger)
        if executable is None:
            logger.error("Unable to determine executable project.", file=str(repo_path))
        else:
            run_result = run_dotnet_execute(repo_path, executable, dotnet_root, env)
            if not run_result["success"]:
                logger.error("dotnet run failed.", file=run_result.get("project", "run"))
            raw_source = find_exporter_file(repo_path, exporter)
            if raw_source is None:
                logger.error(
                    f"No {exporter} telemetry export file detected after execution.",
                    file=str(repo_path / "artifacts" / "training"),
                )
            else:
                try:
                    payload = json.loads(raw_source.read_text(encoding="utf-8"))
                    spans = extract_spans_from_payload(payload)
                    execution_status = "SUCCESS" if run_result["success"] and spans else "PARTIAL"
                except json.JSONDecodeError as exc:
                    logger.error(f"Malformed telemetry JSON: {exc}", file=str(raw_source))

    if raw_source is None:
        raw_source = output_dir / "opentelemetry_raw_output.json"
        raw_source.write_text("{}", encoding="utf-8")

    summary = build_execution_summary(spans, execution_status)
    environment = collect_environment_json(dotnet_root, env, exporter)
    execution_metadata = {
        "clone_status": clone_status,
        "repository_stats": repo_stats,
        "restore": {
            "success": restore_result["success"],
            "returncode": restore_result["returncode"],
            "elapsed_ms": restore_result["elapsed_ms"],
            "target": restore_result.get("target", ""),
        },
        "build": {
            "success": build_result.get("success", False),
            "returncode": build_result.get("returncode", 1),
            "elapsed_ms": build_result.get("elapsed_ms", 0),
            "target": build_result.get("target", ""),
        },
        "run": {
            "success": run_result.get("success", False),
            "returncode": run_result.get("returncode", 1),
            "elapsed_ms": run_result.get("elapsed_ms", 0),
            "project": run_result.get("project", ""),
            "trigger_mode": run_result.get("trigger_mode", False),
        },
        "telemetry_source": str(raw_source),
        "exporter": exporter,
        "summary": summary,
    }

    spans_df = build_spans_dataframe(spans)
    events_df = build_events_dataframe(spans)
    attributes_df = build_attributes_dataframe(spans)
    exported_paths = export_deliverables(
        output_dir,
        inventory_df,
        raw_source,
        spans_df,
        events_df,
        attributes_df,
        execution_metadata,
        environment,
        restore_result,
        build_result,
        run_result,
    )
    logger.write_errors()

    return {
        "repo_path": repo_path,
        "clone_status": clone_status,
        "repo_stats": repo_stats,
        "inventory_df": inventory_df,
        "restore_result": restore_result,
        "build_result": build_result,
        "run_result": run_result,
        "raw_source": raw_source,
        "spans": spans,
        "summary": summary,
        "exported_paths": exported_paths,
        "execution_status": execution_status,
        "pipeline_success": execution_status in {"SUCCESS", "PARTIAL"},
    }
