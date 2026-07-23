"""Generate pymcdc_mcdc_coverage_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "pymcdc_mcdc_coverage_extraction.ipynb"
UTILS = (ROOT / "_pymcdc_notebook_utils.py").read_text(encoding="utf-8")


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": [line + "\n" for line in source.split("\n")]}


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in source.split("\n")],
    }


cells = [
    md(
        "# PyMCDC MC/DC Coverage — Raw Output Extraction (Python)\n\n"
        "This notebook performs **end-to-end execution of PyMCDC** against a Python repository and captures "
        "the **complete raw tool output** for MC/DC (Modified Condition/Decision Coverage) validation.\n\n"
        "**Default repository:** "
        "[visvantha-testable/python-tool-testing-pymcdc]"
        "(https://github.com/visvantha-testable/python-tool-testing-pymcdc)\n\n"
        "> **Note:** PyMCDC emits MC/DC metrics through console text output. JSON and XML deliverables in "
        "`outputs/` are structured exports parsed from that raw console output because PyMCDC does not "
        "provide native JSON or XML formats."
    ),
    md(
        "## Section 1 — Install Dependencies\n\n"
        "Install open-source packages and verify the PyMCDC CLI."
    ),
    code(
        "!pip install -q pymcdc pandas gitpython notebook jupyter\n\n"
        "import os\n"
        "import subprocess\n"
        "import sys\n\n"
        "os.environ['PYTHONIOENCODING'] = 'utf-8'\n"
        "subprocess.run([sys.executable, '-m', 'pymcdc', '--help'], check=False)"
    ),
    md(
        "## Section 2 — Configuration\n\n"
        "Choose Git clone mode or local repository mode."
    ),
    code(
        "USE_GIT_REPO = True\n\n"
        "REPO_URL = 'https://github.com/visvantha-testable/python-tool-testing-pymcdc.git'\n\n"
        "LOCAL_REPO = './workspace/python-tool-testing-pymcdc'\n\n"
        "WORKSPACE_DIR = './workspace'\n"
        "OUTPUT_DIR = './outputs'\n"
        "IF_CLONE_EXISTS = 'reuse'\n"
        "CLONE_DEPTH = 1\n"
        "RAW_OUTPUT_PREVIEW_LINES = 150\n\n"
        "# Local mode example:\n"
        "# USE_GIT_REPO = False\n"
        "# LOCAL_REPO = './workspace/python-tool-testing-pymcdc'\n\n"
        "# Colab example:\n"
        "# USE_GIT_REPO = False\n"
        "# LOCAL_REPO = '/content/python-tool-testing-pymcdc'"
    ),
    md("## Section 3 — Imports and Utility Functions"),
    code("from pathlib import Path\n\n" + UTILS.strip()),
    md(
        "## Section 4 — Repository Information\n\n"
        "Resolve the repository, discover Python files, and write `repository_summary.csv`."
    ),
    code(
        "OUTPUT_PATH = Path(OUTPUT_DIR).resolve()\n"
        "WORKSPACE_PATH = Path(WORKSPACE_DIR).resolve()\n"
        "ERROR_LOG_PATH = OUTPUT_PATH / 'error_log.txt'\n\n"
        "ensure_output_dir(OUTPUT_PATH)\n"
        "logger = NotebookLogger(ERROR_LOG_PATH)\n"
        "CLI_PREFIX = detect_pymcdc_cli(logger)\n\n"
        "try:\n"
        "    REPO_PATH = resolve_repository_path(\n"
        "        use_git_repo=USE_GIT_REPO,\n"
        "        repo_url=REPO_URL,\n"
        "        local_repo=LOCAL_REPO,\n"
        "        workspace_dir=WORKSPACE_PATH,\n"
        "        if_clone_exists=IF_CLONE_EXISTS,\n"
        "        logger=logger,\n"
        "        clone_depth=CLONE_DEPTH,\n"
        "    )\n"
        "except Exception as exc:\n"
        "    logger.error(f'Repository setup failed: {exc}')\n"
        "    raise\n\n"
        "PYTHON_FILES = discover_python_files(REPO_PATH)\n"
        "if not PYTHON_FILES:\n"
        "    logger.error('No Python source files found in repository.', file=str(REPO_PATH))\n"
        "    raise FileNotFoundError('No Python source files found.')\n\n"
        "REPO_STATS = compute_repository_stats(REPO_PATH, PYTHON_FILES)\n"
        "REPOSITORY_SUMMARY_CSV = OUTPUT_PATH / 'repository_summary.csv'\n"
        "save_repository_summary(REPO_STATS, REPOSITORY_SUMMARY_CSV)\n\n"
        "print(f\"Repository Name: {REPO_STATS['repository_name']}\")\n"
        "print(f\"Repository Location: {REPO_STATS['repository_location']}\")\n"
        "print(f\"Total Files: {REPO_STATS['total_files']:,}\")\n"
        "print(f\"Total Python Files: {REPO_STATS['total_python_files']:,}\")\n"
        "print(f\"Repository Size (Python files): {REPO_STATS['repository_size_bytes']:,} bytes\")\n"
        "print('\\nDirectory Structure:')\n"
        "print(REPO_STATS['directory_structure'])"
    ),
    md("## Section 5 — Discover Python Files"),
    code(
        "INVENTORY_CSV = OUTPUT_PATH / 'python_files_inventory.csv'\n"
        "save_python_inventory(PYTHON_FILES, INVENTORY_CSV)\n\n"
        "print(f'Total Python Files Found: {len(PYTHON_FILES)}')\n"
        "print(f'Saved inventory to: {INVENTORY_CSV}')\n"
        "display(pd.read_csv(INVENTORY_CSV).head())"
    ),
    md(
        "## Section 6 — Install Repository Requirements\n\n"
        "Detect `requirements.txt`, `pyproject.toml`, or `setup.py` and install dependencies."
    ),
    code("install_repository_requirements(REPO_PATH, logger)"),
    md(
        "## Section 7 — Execute PyMCDC\n\n"
        "Run PyMCDC against every Python source file. Continue on failure and preserve stdout/stderr."
    ),
    code(
        "FILE_RESULTS, RAW_CONSOLE_OUTPUT, TOTAL_EXECUTION_TIME = run_pymcdc_on_repository(\n"
        "    CLI_PREFIX,\n"
        "    PYTHON_FILES,\n"
        "    logger,\n"
        ")\n"
        "logger.info(f'PyMCDC execution complete for {len(FILE_RESULTS)} files in {TOTAL_EXECUTION_TIME}s.')"
    ),
    md("## Section 8 — Raw Output\n\nSave the exact console output emitted by PyMCDC."),
    code(
        "RAW_CONSOLE_PATH = OUTPUT_PATH / 'pymcdc_raw_console_output.txt'\n"
        "RAW_CONSOLE_PATH.write_text(RAW_CONSOLE_OUTPUT, encoding='utf-8')\n\n"
        "logger.info(f'Saved raw console output to: {RAW_CONSOLE_PATH}')\n"
        "preview_raw_output(RAW_CONSOLE_OUTPUT, RAW_OUTPUT_PREVIEW_LINES, RAW_CONSOLE_PATH)"
    ),
    md(
        "## Section 9 — Extract Metrics\n\n"
        "Parse metrics explicitly emitted by PyMCDC console output."
    ),
    code(
        "METRICS_ROWS = build_metrics_rows(FILE_RESULTS)\n"
        "METRICS_CSV = OUTPUT_PATH / 'pymcdc_metrics.csv'\n"
        "METRICS_DF = pd.DataFrame(METRICS_ROWS, columns=['metric_name', 'metric_value', 'file', 'function'])\n"
        "METRICS_DF.to_csv(METRICS_CSV, index=False)\n\n"
        "FILE_SUMMARY_CSV = OUTPUT_PATH / 'pymcdc_file_summary.csv'\n"
        "FILE_SUMMARY_DF = pd.DataFrame(build_file_summary_rows(FILE_RESULTS))\n"
        "FILE_SUMMARY_DF.to_csv(FILE_SUMMARY_CSV, index=False)\n\n"
        "REPO_SUMMARY_ROW = build_repository_summary_row(REPO_STATS, FILE_RESULTS, TOTAL_EXECUTION_TIME)\n"
        "REPO_SUMMARY_CSV = OUTPUT_PATH / 'pymcdc_repository_summary.csv'\n"
        "pd.DataFrame([REPO_SUMMARY_ROW]).to_csv(REPO_SUMMARY_CSV, index=False)\n\n"
        "JSON_PATH = OUTPUT_PATH / 'pymcdc_output.json'\n"
        "XML_PATH = OUTPUT_PATH / 'pymcdc_output.xml'\n"
        "export_parsed_json(FILE_RESULTS, REPO_SUMMARY_ROW, JSON_PATH)\n"
        "export_parsed_xml(FILE_RESULTS, REPO_SUMMARY_ROW, XML_PATH)\n\n"
        "logger.info(f'Saved metrics rows={len(METRICS_DF)}')\n"
        "display(METRICS_DF.head(20))"
    ),
    md("## Section 10 — Error Handling"),
    code(
        "if ERROR_LOG_PATH.exists() and ERROR_LOG_PATH.stat().st_size > 0:\n"
        "    print(ERROR_LOG_PATH.read_text(encoding='utf-8'))\n"
        "else:\n"
        "    print('No errors logged.')"
    ),
    md("## Section 11 — Dashboard"),
    code(
        "dashboard_df = pd.DataFrame([\n"
        "    {'Metric': 'Repository', 'Value': REPO_STATS['repository_name']},\n"
        "    {'Metric': 'Python Files', 'Value': REPO_STATS['total_python_files']},\n"
        "    {'Metric': 'Functions', 'Value': REPO_SUMMARY_ROW['Total Functions']},\n"
        "    {'Metric': 'Decisions', 'Value': REPO_SUMMARY_ROW['Total Decisions']},\n"
        "    {'Metric': 'Conditions', 'Value': REPO_SUMMARY_ROW['Total Conditions']},\n"
        "    {'Metric': 'Decision Coverage', 'Value': f\"{REPO_SUMMARY_ROW['Decision Coverage %']}%\"},\n"
        "    {'Metric': 'Condition Coverage', 'Value': f\"{REPO_SUMMARY_ROW['Condition Coverage %']}%\"},\n"
        "    {'Metric': 'MC/DC Coverage', 'Value': f\"{REPO_SUMMARY_ROW['MC/DC Coverage %']}%\"},\n"
        "    {'Metric': 'Execution Time', 'Value': f\"{TOTAL_EXECUTION_TIME}s\"},\n"
        "])\n"
        "display(dashboard_df)\n\n"
        "deliverables = [\n"
        "    REPOSITORY_SUMMARY_CSV,\n"
        "    INVENTORY_CSV,\n"
        "    RAW_CONSOLE_PATH,\n"
        "    JSON_PATH,\n"
        "    XML_PATH,\n"
        "    METRICS_CSV,\n"
        "    FILE_SUMMARY_CSV,\n"
        "    REPO_SUMMARY_CSV,\n"
        "    ERROR_LOG_PATH,\n"
        "]\n"
        "print('\\nDeliverables:')\n"
        "for path in deliverables:\n"
        "    print(f\"  [{'OK' if path.exists() else 'MISSING'}] {path}\")"
    ),
    md(
        "## Deliverables\n\n"
        "```text\n"
        "outputs/\n"
        "├── repository_summary.csv\n"
        "├── python_files_inventory.csv\n"
        "├── pymcdc_raw_console_output.txt\n"
        "├── pymcdc_output.json\n"
        "├── pymcdc_output.xml\n"
        "├── pymcdc_metrics.csv\n"
        "├── pymcdc_file_summary.csv\n"
        "├── pymcdc_repository_summary.csv\n"
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
