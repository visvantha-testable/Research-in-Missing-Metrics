"""Generate lizard_file_function_length_extraction.ipynb for C# repositories."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "lizard_file_function_length_extraction.ipynb"

UTILS = r'''
from __future__ import annotations

import csv
import io
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from IPython.display import display
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

EXCLUDED_DIR_NAMES = {
    ".git", "bin", "obj", "packages", "artifacts", "TestResults", "docs",
}
LIZARD_EXCLUDE_PATTERNS = [
    "*/.git/*", "*/bin/*", "*/obj/*", "*/packages/*",
    "*/artifacts/*", "*/TestResults/*", "*/docs/*",
]
LIZARD_RAW_COLUMNS = [
    "nloc", "ccn", "token_count", "parameter_count", "length", "location",
    "file", "function", "long_name", "start_line", "end_line",
]
LIZARD_OUTPUT_COLUMNS = [
    "NLOC", "CCN", "token", "PARAM", "length", "location", "file", "function",
]
LIZARD_METRICS_COLUMNS = [
    "file", "class", "method", "nloc", "cyclomatic_complexity", "token_count",
    "parameter_count", "function_length", "start_line", "end_line",
]
LONG_METHOD_COLUMNS = ["file", "class", "method", "function_length", "status"]
FILE_SUMMARY_RE = re.compile(r"^\s*(\d+)\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+\d+\s+(.+)$")
LONG_METHOD_THRESHOLD = 50
PY = sys.executable


class NotebookLogger:
    def __init__(self, error_log_path: Path) -> None:
        self.error_log_path = error_log_path
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._errors: list[dict[str, str]] = []
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

    def write_errors(self) -> None:
        with self.error_log_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timestamp", "file", "error_message"])
            writer.writeheader()
            writer.writerows(self._errors)


def ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


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
    repo_url: str, workspace_dir: Path, if_clone_exists: str, logger: NotebookLogger, clone_depth: int | None = None,
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
    use_git_url: bool, repo_url: str, local_repo_path: str | Path, workspace_dir: Path,
    if_clone_exists: str, logger: NotebookLogger, clone_depth: int | None = None,
) -> Path:
    if use_git_url:
        return clone_or_reuse_repository(repo_url, workspace_dir, if_clone_exists, logger, clone_depth)
    return validate_local_repo_path(Path(local_repo_path), logger)


def split_csharp_symbol(function_name: str) -> tuple[str, str]:
    name = str(function_name).strip('"')
    if "::" in name:
        class_name, method_name = name.split("::", 1)
        return class_name, method_name
    return "", name


def discover_csharp_files(repo_path: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo_path.rglob("*.cs"):
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def compute_repository_stats(repo_path: Path, csharp_files: list[Path]) -> dict[str, Any]:
    total_size = sum(path.stat().st_size for path in csharp_files)
    directories = {path.parent for path in csharp_files}
    return {
        "repository_name": repo_path.name,
        "repository_size_bytes": total_size,
        "directory_count": len(directories),
        "csharp_file_count": len(csharp_files),
    }


def save_csharp_inventory(csharp_files: list[Path], output_csv: Path) -> None:
    pd.DataFrame(
        [{"file_path": str(p), "file_name": p.name, "directory": str(p.parent)} for p in csharp_files]
    ).to_csv(output_csv, index=False)


def parse_file_nloc_summary(lizard_text: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    in_summary = False
    for line in lizard_text.splitlines():
        if "function_cnt" in line and line.strip().startswith("NLOC"):
            in_summary = True
            continue
        if not in_summary:
            continue
        if line.startswith("="):
            break
        if line.startswith("-") and not line.strip("-").strip():
            continue
        match = FILE_SUMMARY_RE.match(line)
        if match:
            rows.append({"file": match.group(2).strip(), "file_length": int(match.group(1))})
    return pd.DataFrame(rows, columns=["file", "file_length"])


def build_file_length_summary(lizard_text: str, metrics_df: pd.DataFrame) -> pd.DataFrame:
    summary_df = parse_file_nloc_summary(lizard_text)
    if not summary_df.empty:
        return summary_df
    if metrics_df.empty:
        return pd.DataFrame(columns=["file", "file_length"])
    grouped = metrics_df.groupby("file", as_index=False)["nloc"].sum()
    grouped.columns = ["file", "file_length"]
    grouped["file_length"] = grouped["file_length"].astype(int)
    return grouped


def build_lizard_command(repo_path: Path, *, csv_output: bool = False, ens: bool = False) -> list[str]:
    command = [PY, "-m", "lizard", "-l", "csharp"]
    for pattern in LIZARD_EXCLUDE_PATTERNS:
        command.extend(["-x", pattern])
    if csv_output:
        command.append("--csv")
    if ens:
        command.append("-ENS")
    command.append(str(repo_path))
    return command


def run_lizard_command(command: list[str], logger: NotebookLogger) -> tuple[str, str, int]:
    completed = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    return completed.stdout, completed.stderr, completed.returncode


def combine_raw_streams(stdout: str, stderr: str) -> str:
    raw = stdout
    if stderr:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += stderr
    return raw


def parse_lizard_csv(csv_text: str, *, with_ens: bool = False) -> pd.DataFrame:
    if not csv_text.strip():
        columns = LIZARD_RAW_COLUMNS + (["max_nested_structures"] if with_ens else [])
        return pd.DataFrame(columns=columns)
    columns = LIZARD_RAW_COLUMNS + (["max_nested_structures"] if with_ens else [])
    rows = list(csv.reader(io.StringIO(csv_text.strip())))
    if rows and rows[0] and rows[0][0].lower() in {"nloc", "ncss"}:
        rows = rows[1:]
    parsed = [dict(zip(columns, row + [""] * (len(columns) - len(row)))) for row in rows]
    frame = pd.DataFrame(parsed)
    numeric_cols = [
        "nloc", "ccn", "token_count", "parameter_count", "length", "start_line", "end_line",
    ]
    if with_ens:
        numeric_cols.append("max_nested_structures")
    for col in numeric_cols:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def to_lizard_output_csv(lizard_df: pd.DataFrame) -> pd.DataFrame:
    if lizard_df.empty:
        return pd.DataFrame(columns=LIZARD_OUTPUT_COLUMNS)
    return pd.DataFrame({
        "NLOC": lizard_df["nloc"],
        "CCN": lizard_df["ccn"],
        "token": lizard_df["token_count"],
        "PARAM": lizard_df["parameter_count"],
        "length": lizard_df["length"],
        "location": lizard_df["location"].astype(str).str.strip('"'),
        "file": lizard_df["file"].astype(str).str.strip('"'),
        "function": lizard_df["function"].astype(str).str.strip('"'),
    })


def to_lizard_metrics(lizard_df: pd.DataFrame) -> pd.DataFrame:
    if lizard_df.empty:
        return pd.DataFrame(columns=LIZARD_METRICS_COLUMNS)
    classes: list[str] = []
    methods: list[str] = []
    for function_name in lizard_df["function"].astype(str):
        class_name, method_name = split_csharp_symbol(function_name)
        classes.append(class_name)
        methods.append(method_name)
    return pd.DataFrame({
        "file": lizard_df["file"].astype(str).str.strip('"'),
        "class": classes,
        "method": methods,
        "nloc": lizard_df["nloc"],
        "cyclomatic_complexity": lizard_df["ccn"],
        "token_count": lizard_df["token_count"],
        "parameter_count": lizard_df["parameter_count"],
        "function_length": lizard_df["nloc"],
        "start_line": lizard_df["start_line"],
        "end_line": lizard_df["end_line"],
    })


def build_long_methods(metrics_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, record in metrics_df.iterrows():
        function_length = int(record.get("function_length", 0) or 0)
        status = "Long Method" if function_length > LONG_METHOD_THRESHOLD else "OK"
        rows.append({
            "file": record.get("file", ""),
            "class": record.get("class", ""),
            "method": record.get("method", ""),
            "function_length": function_length,
            "status": status,
        })
    return pd.DataFrame(rows, columns=LONG_METHOD_COLUMNS)


def compute_max_nesting_depth(ens_df: pd.DataFrame) -> int:
    if ens_df.empty or "max_nested_structures" not in ens_df.columns:
        return 0
    values = pd.to_numeric(ens_df["max_nested_structures"], errors="coerce").dropna()
    return int(values.max()) if not values.empty else 0


def compute_complexity_summary(metrics_df: pd.DataFrame, max_nesting_depth: int) -> pd.DataFrame:
    ccn_values = pd.to_numeric(metrics_df["cyclomatic_complexity"], errors="coerce").dropna()
    length_values = pd.to_numeric(metrics_df["function_length"], errors="coerce").dropna()
    token_values = pd.to_numeric(metrics_df["token_count"], errors="coerce").dropna()
    param_values = pd.to_numeric(metrics_df["parameter_count"], errors="coerce").dropna()
    return pd.DataFrame([
        {"metric_name": "Cyclomatic_Complexity", "metric_value": int(ccn_values.max()) if not ccn_values.empty else 0},
        {"metric_name": "Function_Length", "metric_value": int(length_values.max()) if not length_values.empty else 0},
        {"metric_name": "Maximum_Nesting_Depth", "metric_value": max_nesting_depth},
        {"metric_name": "Parameter_Count", "metric_value": int(param_values.max()) if not param_values.empty else 0},
        {"metric_name": "Token_Count", "metric_value": int(token_values.max()) if not token_values.empty else 0},
    ])


def preview_raw_output(raw_text: str, preview_lines: int, output_path: Path) -> None:
    lines = raw_text.splitlines()
    print(f"\n{'=' * 80}")
    print(f"RAW LIZARD OUTPUT PREVIEW (first {preview_lines} lines)")
    print(f"{'=' * 80}\n")
    if not lines:
        print("(empty raw output)")
        return
    print("\n".join(lines[:preview_lines]))
    remaining = len(lines) - preview_lines
    if remaining > 0:
        print(f"\n... ({remaining} more lines saved to {output_path})")
'''


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": [line + "\n" for line in source.split("\n")]}


def code(source: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [line + "\n" for line in source.split("\n")]}


cells = [
    md(
        "# Lizard File & Function Length — Raw Output Extraction (C#)\n\n"
        "This notebook analyzes **C# repositories** with **Lizard** and captures complete raw tool output "
        "for File Length, Function Length, Cyclomatic Complexity (CCN), NLOC, Token Count, Parameter Count, "
        "Maximum Nesting Depth, Class Name, and Method Name.\n\n"
        "**Default benchmark repository:** [dotnet/runtime](https://github.com/dotnet/runtime)\n\n"
        "> **Note:** **Function Length is directly emitted by Lizard** through the `NLOC` column in CSV output. "
        "**File Length is derived** from the file-level `NLOC` summary reported by Lizard in text output.\n\n"
        "**Metric mapping:**\n"
        "| White Box Metric | Lizard Field |\n"
        "|------------------|-------------|\n"
        "| Function Length | `NLOC` (CSV) → `function_length` |\n"
        "| File Length | File summary `NLOC` (text output) |\n"
        "| Cyclomatic Complexity | `CCN` |\n"
        "| Parameter Count | `PARAM` |\n"
        "| Token Count | `token` |\n"
        "| Maximum Nesting Depth | `-ENS` → `max_nested_structures` |\n"
        "| Class / Method | `function` (`ClassName::MethodName`)"
    ),
    md("## Section 1 — Install Dependencies\n\nInstall open-source Python packages and verify Lizard."),
    code(
        "!pip install -q lizard pandas gitpython jupyter\n\n"
        "import subprocess, sys\n"
        "subprocess.run([sys.executable, '-m', 'lizard', '--version'], check=False)"
    ),
    md("## Section 2 — Configuration\n\nSet repository source, workspace, and output directory."),
    code(
        "USE_GIT_URL = True\n\n"
        "REPO_URL = 'https://github.com/dotnet/runtime.git'\n\n"
        "LOCAL_REPO_PATH = '/content/runtime'\n\n"
        "WORKSPACE_DIR = './workspace'\n\n"
        "OUTPUT_DIR = './outputs'\n\n"
        "IF_CLONE_EXISTS = 'reuse'\n\n"
        "CLONE_DEPTH = 1\n\n"
        "RAW_OUTPUT_PREVIEW_LINES = 150\n\n"
        "# Fast validation benchmark:\n"
        "# USE_GIT_URL = False\n"
        "# LOCAL_REPO_PATH = './workspace/file_function_length_benchmark'"
    ),
    md("## Section 3 — Imports and Utility Functions"),
    code("from pathlib import Path\n\n" + UTILS.strip()),
    md("## Section 4 — Repository Setup"),
    code(
        "OUTPUT_PATH = Path(OUTPUT_DIR).resolve()\n"
        "WORKSPACE_PATH = Path(WORKSPACE_DIR).resolve()\n"
        "ERROR_LOG_PATH = OUTPUT_PATH / 'error_log.txt'\n\n"
        "ensure_output_dir(OUTPUT_PATH)\n"
        "logger = NotebookLogger(ERROR_LOG_PATH)\n\n"
        "try:\n"
        "    REPO_PATH = resolve_repository_path(\n"
        "        use_git_url=USE_GIT_URL,\n"
        "        repo_url=REPO_URL,\n"
        "        local_repo_path=LOCAL_REPO_PATH,\n"
        "        workspace_dir=WORKSPACE_PATH,\n"
        "        if_clone_exists=IF_CLONE_EXISTS,\n"
        "        logger=logger,\n"
        "        clone_depth=CLONE_DEPTH,\n"
        "    )\n"
        "except Exception as exc:\n"
        "    logger.error(f'Repository setup failed: {exc}')\n"
        "    raise\n\n"
        "CS_FILES = discover_csharp_files(REPO_PATH)\n"
        "if not CS_FILES:\n"
        "    logger.error('No C# source files found in repository.', file=str(REPO_PATH))\n"
        "    raise FileNotFoundError('No C# source files found.')\n\n"
        "REPO_STATS = compute_repository_stats(REPO_PATH, CS_FILES)\n"
        "logger.info(f'Repository ready at: {REPO_PATH}')\n"
        "print(f\"Repository: {REPO_STATS['repository_name']}\")\n"
        "print(f\"Size (C# files): {REPO_STATS['repository_size_bytes']:,} bytes\")\n"
        "print(f\"Directories: {REPO_STATS['directory_count']:,}\")\n"
        "print(f\"C# files: {REPO_STATS['csharp_file_count']:,}\")"
    ),
    md("## Section 5 — Discover C# Files"),
    code(
        "INVENTORY_CSV = OUTPUT_PATH / 'csharp_files_inventory.csv'\n"
        "save_csharp_inventory(CS_FILES, INVENTORY_CSV)\n\n"
        "print(f'Total C# Files Found: {len(CS_FILES)}')\n"
        "print(f'Saved inventory to: {INVENTORY_CSV}')"
    ),
    md(
        "## Section 6 — Execute Lizard\n\n"
        "Run Lizard in text, CSV, and `-ENS` modes. Preserve stdout and stderr exactly as emitted.\n\n"
        "Raw outputs preserved: `text`, `csv`, and `csv_ens`."
    ),
    code(
        "LIZARD_CONSOLE_CHUNKS: list[str] = []\n"
        "LIZARD_CSV = ''\n"
        "LIZARD_CSV_ENS = ''\n"
        "LIZARD_TEXT = ''\n\n"
        "for label, csv_output, ens in [\n"
        "    ('text', False, False),\n"
        "    ('csv', True, False),\n"
        "    ('csv_ens', True, True),\n"
        "]:\n"
        "    command = build_lizard_command(REPO_PATH, csv_output=csv_output, ens=ens)\n"
        "    stdout, stderr, code = run_lizard_command(command, logger)\n"
        "    LIZARD_CONSOLE_CHUNKS.append(f'===== lizard {label} =====\\n' + combine_raw_streams(stdout, stderr))\n"
        "    if label == 'text':\n"
        "        LIZARD_TEXT = stdout\n"
        "    elif csv_output and ens:\n"
        "        LIZARD_CSV_ENS = stdout\n"
        "    elif csv_output:\n"
        "        LIZARD_CSV = stdout\n"
        "    if code not in (0, 1):\n"
        "        logger.error(f'Lizard {label} run exited with code {code}', file=label)\n\n"
        "logger.info('Lizard execution complete.')"
    ),
    md("## Section 7 — Raw Output Extraction\n\nSave raw console output and structured CSV files without modification."),
    code(
        "CONSOLE_PATH = OUTPUT_PATH / 'lizard_raw_console_output.txt'\n"
        "LIZARD_OUTPUT_CSV = OUTPUT_PATH / 'lizard_output.csv'\n\n"
        "CONSOLE_PATH.write_text('\\n'.join(LIZARD_CONSOLE_CHUNKS), encoding='utf-8')\n\n"
        "BASE_DF = parse_lizard_csv(LIZARD_CSV, with_ens=False)\n"
        "ENS_DF = parse_lizard_csv(LIZARD_CSV_ENS, with_ens=True)\n"
        "OUTPUT_DF = to_lizard_output_csv(BASE_DF)\n"
        "OUTPUT_DF.to_csv(LIZARD_OUTPUT_CSV, index=False)\n\n"
        "logger.info(f'Saved raw console output and Lizard CSV ({len(OUTPUT_DF)} methods).')\n"
        "preview_raw_output(CONSOLE_PATH.read_text(encoding='utf-8'), RAW_OUTPUT_PREVIEW_LINES, CONSOLE_PATH)"
    ),
    md("## Section 8 — Parse Lizard Output\n\nGenerate per-method metrics from Lizard CSV."),
    code(
        "METRICS_DF = to_lizard_metrics(BASE_DF)\n"
        "METRICS_CSV = OUTPUT_PATH / 'lizard_metrics.csv'\n"
        "METRICS_DF.to_csv(METRICS_CSV, index=False)\n\n"
        "logger.info(f'Parsed Lizard metrics rows={len(METRICS_DF)}')\n"
        "display(METRICS_DF.head())"
    ),
    md(
        "## Section 9 — Function Length\n\n"
        "**Direct metric** (emitted by Lizard via the `NLOC` column):\n\n"
        "```text\n"
        "Function_Length = NLOC\n"
        "```"
    ),
    code(
        "NLOC_VALUES = pd.to_numeric(METRICS_DF['function_length'], errors='coerce').dropna()\n"
        "MAX_FUNCTION_LENGTH = int(NLOC_VALUES.max()) if not NLOC_VALUES.empty else 0\n"
        "AVG_FUNCTION_LENGTH = round(float(NLOC_VALUES.mean()), 4) if not NLOC_VALUES.empty else 0.0\n\n"
        "FUNCTION_LENGTH_SUMMARY_CSV = OUTPUT_PATH / 'function_length_summary.csv'\n"
        "pd.DataFrame([{'metric_name': 'Function_Length', 'metric_value': MAX_FUNCTION_LENGTH}]).to_csv(\n"
        "    FUNCTION_LENGTH_SUMMARY_CSV, index=False\n"
        ")\n\n"
        "logger.info(f'Function Length (max NLOC)={MAX_FUNCTION_LENGTH} (directly from Lizard)')\n"
        "display(pd.read_csv(FUNCTION_LENGTH_SUMMARY_CSV))"
    ),
    md(
        "## Section 10 — File Length\n\n"
        "**Derived metric** (file-level NLOC from Lizard text summary):\n\n"
        "```text\n"
        "File_Length = Total Logical Lines of Code (NLOC) reported in the file summary\n"
        "```"
    ),
    code(
        "FILE_LENGTH_DF = build_file_length_summary(LIZARD_TEXT, METRICS_DF)\n"
        "FILE_LENGTH_CSV = OUTPUT_PATH / 'file_length_summary.csv'\n"
        "FILE_LENGTH_DF.to_csv(FILE_LENGTH_CSV, index=False)\n\n"
        "AVG_FILE_LENGTH = round(float(FILE_LENGTH_DF['file_length'].mean()), 4) if not FILE_LENGTH_DF.empty else 0.0\n"
        "MAX_FILE_LENGTH = int(FILE_LENGTH_DF['file_length'].max()) if not FILE_LENGTH_DF.empty else 0\n\n"
        "logger.info(f'File Length computed for {len(FILE_LENGTH_DF)} files (from Lizard file summary)')\n"
        "display(FILE_LENGTH_DF)"
    ),
    md("## Section 11 — Long Method Detection\n\nFlag methods where `Function_Length > 50`."),
    code(
        "LONG_METHODS_DF = build_long_methods(METRICS_DF)\n"
        "LONG_METHODS_CSV = OUTPUT_PATH / 'long_methods.csv'\n"
        "LONG_METHODS_DF.to_csv(LONG_METHODS_CSV, index=False)\n\n"
        "LONG_METHOD_COUNT = int((LONG_METHODS_DF['status'] == 'Long Method').sum())\n"
        "logger.info(f'Long method count={LONG_METHOD_COUNT}')\n"
        "display(LONG_METHODS_DF)"
    ),
    md("## Section 12 — Complexity Summary"),
    code(
        "MAX_NESTING = compute_max_nesting_depth(ENS_DF)\n"
        "COMPLEXITY_DF = compute_complexity_summary(METRICS_DF, MAX_NESTING)\n"
        "COMPLEXITY_CSV = OUTPUT_PATH / 'complexity_summary.csv'\n"
        "COMPLEXITY_DF.to_csv(COMPLEXITY_CSV, index=False)\n\n"
        "CCN_VALUES = pd.to_numeric(METRICS_DF['cyclomatic_complexity'], errors='coerce').dropna()\n"
        "AVG_CCN = round(float(CCN_VALUES.mean()), 4) if not CCN_VALUES.empty else 0.0\n\n"
        "logger.info(f'Saved complexity summary: {COMPLEXITY_CSV}')\n"
        "display(COMPLEXITY_DF)"
    ),
    md("## Section 13 — Summary Dashboard"),
    code(
        "summary_df = pd.DataFrame([\n"
        "    {'Metric': 'Total C# Files', 'Value': len(CS_FILES)},\n"
        "    {'Metric': 'Total Methods', 'Value': len(METRICS_DF)},\n"
        "    {'Metric': 'Average Function Length', 'Value': AVG_FUNCTION_LENGTH},\n"
        "    {'Metric': 'Maximum Function Length', 'Value': MAX_FUNCTION_LENGTH},\n"
        "    {'Metric': 'Average File Length', 'Value': AVG_FILE_LENGTH},\n"
        "    {'Metric': 'Long Methods', 'Value': LONG_METHOD_COUNT},\n"
        "    {'Metric': 'Average Cyclomatic Complexity', 'Value': AVG_CCN},\n"
        "    {'Metric': 'Maximum Nesting Depth', 'Value': MAX_NESTING},\n"
        "])\n"
        "display(summary_df)\n\n"
        "deliverables = [\n"
        "    CONSOLE_PATH, LIZARD_OUTPUT_CSV, METRICS_CSV, FUNCTION_LENGTH_SUMMARY_CSV,\n"
        "    FILE_LENGTH_CSV, LONG_METHODS_CSV, COMPLEXITY_CSV, INVENTORY_CSV, ERROR_LOG_PATH,\n"
        "]\n"
        "print('\\nDeliverables:')\n"
        "for path in deliverables:\n"
        "    print(f\"  [{'OK' if path.exists() else 'MISSING'}] {path}\")"
    ),
    md("## Section 14 — Error Handling"),
    code(
        "if ERROR_LOG_PATH.exists() and ERROR_LOG_PATH.stat().st_size > 0:\n"
        "    print(ERROR_LOG_PATH.read_text(encoding='utf-8'))\n"
        "else:\n"
        "    print('No errors logged.')"
    ),
    md(
        "## Section 15 — Deliverables\n\n"
        "```text\n"
        "outputs/\n"
        "├── lizard_raw_console_output.txt\n"
        "├── lizard_output.csv\n"
        "├── lizard_metrics.csv\n"
        "├── function_length_summary.csv\n"
        "├── file_length_summary.csv\n"
        "├── long_methods.csv\n"
        "├── complexity_summary.csv\n"
        "├── csharp_files_inventory.csv\n"
        "└── error_log.txt\n"
        "```"
    ),
]

NOTEBOOK.write_text(
    json.dumps(
        {
            "cells": cells,
            "metadata": {
                "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                "language_info": {"name": "python", "version": "3.11.0"},
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        },
        indent=1,
    ),
    encoding="utf-8",
)
print(f"Wrote {NOTEBOOK}")
