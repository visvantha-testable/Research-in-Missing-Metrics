"""Generate eslint_path_coverage_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "eslint_path_coverage_extraction.ipynb"
UTILS_PATH = ROOT / "_eslint_path_coverage_utils.py"
UTILS = UTILS_PATH.read_text(encoding="utf-8")


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "outputs": [], "source": source.splitlines(keepends=True)}


cells = [
    md(
        "# ESLint + eslint-plugin-sonarjs — Path Coverage Raw Output Extraction (TypeScript)\n\n"
        "| Property | Value |\n"
        "| --- | --- |\n"
        "| Testing Type | Control Flow Testing |\n"
        "| Classification | Path Coverage |\n"
        "| Metric | Path Detection Testing |\n"
        "| KPI | Path Coverage % |\n\n"
        "**Scope:** TypeScript only · npm · ESLint + eslint-plugin-sonarjs only  \n"
        "**Default repository:** "
        "[visvantha-testable/typescript-tool-testing-eslint-eslint-plugin-sonarjs]"
        "(https://github.com/visvantha-testable/typescript-tool-testing-eslint-eslint-plugin-sonarjs)\n\n"
        "> This notebook preserves the **raw ESLint JSON output** exactly as emitted by the tool "
        "and validates whether Path Coverage evidence is present in that output."
    ),
    md("## Step 1 — Clone Repository"),
    code(
        "USE_GIT_REPO = True\n"
        'REPO_URL = "https://github.com/visvantha-testable/typescript-tool-testing-eslint-eslint-plugin-sonarjs.git"\n'
        'LOCAL_REPO = "./workspace/typescript-tool-testing-eslint-eslint-plugin-sonarjs"\n'
        'IF_CLONE_EXISTS = "reuse"\n'
        "CLONE_DEPTH = 1\n"
    ),
    md("## Step 2 — Install Dependencies"),
    code(
        "import shutil\n"
        "import subprocess\n"
        "import sys\n\n"
        "for cmd in [[sys.executable, '-m', 'pip', 'install', '-q', '-r', 'requirements.txt'], "
        "['node', '--version'], ['npm', '--version']]:\n"
        "    subprocess.run(cmd, check=False)\n"
    ),
    md("## Step 3 — Validate ESLint Configuration"),
    code(
        UTILS
        + "\n\n"
        "import time\n"
        "from pathlib import Path\n"
        "from IPython.display import display\n\n"
        "METRIC_ROOT = resolve_metric_root(Path('.').resolve())\n"
        "WORKSPACE_DIR = METRIC_ROOT / 'workspace'\n"
        "OUTPUT_PATH = METRIC_ROOT / 'outputs'\n"
        "ERROR_LOG_PATH = OUTPUT_PATH / 'error_log.txt'\n\n"
        "ensure_output_dir(OUTPUT_PATH)\n"
        "logger = NotebookLogger(ERROR_LOG_PATH)\n"
        "PIPELINE_STARTED = time.perf_counter()\n\n"
        "REPO_PATH = resolve_repository_path(\n"
        "    USE_GIT_REPO,\n"
        "    REPO_URL,\n"
        "    Path(LOCAL_REPO),\n"
        "    WORKSPACE_DIR,\n"
        "    IF_CLONE_EXISTS,\n"
        "    logger,\n"
        "    CLONE_DEPTH,\n"
        ")\n\n"
        "PROJECT_VALIDATION = validate_typescript_eslint_project(REPO_PATH, logger)\n"
        "display(pd.DataFrame([PROJECT_VALIDATION]))\n"
        "if not PROJECT_VALIDATION['project_valid']:\n"
        "    raise RuntimeError('Mandatory project files are missing; stopping execution.')\n"
    ),
    code(
        "INSTALL_RESULT = install_npm_dependencies(REPO_PATH, logger)\n"
        "print(f\"Command: {INSTALL_RESULT['command']}\")\n"
        "print(f\"Return code: {INSTALL_RESULT['returncode']}\")\n"
        "print(f\"Elapsed ms: {INSTALL_RESULT['elapsed_ms']:.2f}\")\n"
        "print('--- stdout ---')\n"
        "print(INSTALL_RESULT['stdout'])\n"
        "print('--- stderr ---')\n"
        "print(INSTALL_RESULT['stderr'])\n\n"
        "PACKAGE_DF = verify_runtime_packages(REPO_PATH, logger)\n"
        "display(PACKAGE_DF)\n"
        "if INSTALL_RESULT['returncode'] != 0:\n"
        "    raise RuntimeError('npm install failed.')\n"
    ),
    code(
        "CONFIG_DF = validate_eslint_configuration(REPO_PATH, logger)\n"
        "CONFIG_CSV = OUTPUT_PATH / 'eslint_configuration.csv'\n"
        "CONFIG_DF.to_csv(CONFIG_CSV, index=False)\n"
        "display(CONFIG_DF)"
    ),
    md("## Step 4 — Execute ESLint + SonarJS"),
    code(
        "RAW_JSON_PATH = OUTPUT_PATH / 'eslint_raw_output.json'\n"
        "ESLINT_RESULT = execute_eslint(REPO_PATH, RAW_JSON_PATH, logger)\n"
        "print(f\"Command: {ESLINT_RESULT['command']}\")\n"
        "print(f\"Return code: {ESLINT_RESULT['returncode']}\")\n"
        "print(f\"Elapsed ms: {ESLINT_RESULT['elapsed_ms']:.2f}\")\n"
        "print('--- stdout ---')\n"
        "print(ESLINT_RESULT['stdout'])\n"
        "print('--- stderr ---')\n"
        "print(ESLINT_RESULT['stderr'])"
    ),
    md("## Step 5 — Preserve Raw Tool Output"),
    code(
        "if RAW_JSON_PATH.exists():\n"
        "    print(f'Raw ESLint JSON preserved at: {RAW_JSON_PATH}')\n"
        "    print(f'File size (bytes): {RAW_JSON_PATH.stat().st_size}')\n"
        "else:\n"
        "    logger.error('eslint_raw_output.json missing after ESLint execution.', file=str(RAW_JSON_PATH))\n"
        "    raise FileNotFoundError('eslint_raw_output.json was not created.')"
    ),
    md("## Step 6 — Extract Rule Violations"),
    code(
        "RECORDS = load_eslint_records(RAW_JSON_PATH, logger)\n"
        "FINDINGS_DF = parse_eslint_findings(RECORDS)\n"
        "FINDINGS_CSV = OUTPUT_PATH / 'eslint_findings.csv'\n"
        "FINDINGS_DF.to_csv(FINDINGS_CSV, index=False)\n"
        "print(f'Total findings extracted: {len(FINDINGS_DF)}')\n"
        "display(FINDINGS_DF.head(20))"
    ),
    md("## Step 7 — Repository Summary"),
    code(
        "SUMMARY = summarize_eslint_results(RECORDS, FINDINGS_DF)\n"
        "VERSIONS = get_tool_versions(REPO_PATH, logger)\n"
        "REPO_SUMMARY_DF = build_repository_summary(\n"
        "    PROJECT_VALIDATION['repository_name'],\n"
        "    PROJECT_VALIDATION['typescript_file_count'],\n"
        "    SUMMARY,\n"
        "    VERSIONS,\n"
        ")\n"
        "REPO_SUMMARY_CSV = OUTPUT_PATH / 'repository_summary.csv'\n"
        "REPO_SUMMARY_DF.to_csv(REPO_SUMMARY_CSV, index=False)\n"
        "display(REPO_SUMMARY_DF)"
    ),
    md("## Step 8 — Validate White-box Metric"),
    code(
        "VALIDATION_DF = build_path_coverage_validation(FINDINGS_DF, RAW_JSON_PATH)\n"
        "VALIDATION_CSV = OUTPUT_PATH / 'path_coverage_validation.csv'\n"
        "VALIDATION_DF.to_csv(VALIDATION_CSV, index=False)\n"
        "display(VALIDATION_DF)"
    ),
    md("## Step 9 — Dashboard Summary"),
    code(
        "ESLINT_EXECUTION_OK = (\n"
        "    INSTALL_RESULT['returncode'] == 0\n"
        "    and ESLINT_RESULT['returncode'] in ESLINT_SUCCESS_CODES\n"
        "    and ESLINT_RESULT['json_valid']\n"
        "    and RAW_JSON_PATH.exists()\n"
        ")\n"
        "DASHBOARD_DF = build_dashboard_summary(\n"
        "    PROJECT_VALIDATION['repository_name'],\n"
        "    VERSIONS,\n"
        "    SUMMARY,\n"
        "    VALIDATION_DF,\n"
        "    ESLINT_EXECUTION_OK,\n"
        ")\n"
        "DASHBOARD_CSV = OUTPUT_PATH / 'dashboard_summary.csv'\n"
        "DASHBOARD_DF.to_csv(DASHBOARD_CSV, index=False)\n"
        "display(DASHBOARD_DF)\n\n"
        "TOTAL_EXECUTION_TIME = round(time.perf_counter() - PIPELINE_STARTED, 2)\n"
        "print(f'Total notebook execution time (seconds): {TOTAL_EXECUTION_TIME}')"
    ),
    md("## Step 10 — Error Handling"),
    code(
        "logger.write_errors()\n"
        "deliverables = [\n"
        "    RAW_JSON_PATH,\n"
        "    FINDINGS_CSV,\n"
        "    CONFIG_CSV,\n"
        "    REPO_SUMMARY_CSV,\n"
        "    VALIDATION_CSV,\n"
        "    DASHBOARD_CSV,\n"
        "    ERROR_LOG_PATH,\n"
        "]\n"
        "print('\\nDeliverables:')\n"
        "for path in deliverables:\n"
        "    print(f\"  [{'OK' if path.exists() else 'MISSING'}] {path}\")\n\n"
        "if ERROR_LOG_PATH.exists() and ERROR_LOG_PATH.stat().st_size > 0:\n"
        "    print('\\n===== error_log.txt =====\\n')\n"
        "    print(ERROR_LOG_PATH.read_text(encoding='utf-8'))\n"
        "else:\n"
        "    print('\\nNo errors logged.')"
    ),
    md(
        "## Deliverables\n\n"
        "```text\n"
        "outputs/\n"
        "├── eslint_raw_output.json\n"
        "├── eslint_findings.csv\n"
        "├── eslint_configuration.csv\n"
        "├── repository_summary.csv\n"
        "├── path_coverage_validation.csv\n"
        "├── dashboard_summary.csv\n"
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
