"""Generate jacoco_static_du_validation.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
JACOCO_UTILS_ROOT = METRIC_ROOT.parent / "JaCoCo Coverage" / "tool"
JACOCO_PATH_UTILS_ROOT = METRIC_ROOT.parent / "JaCoCo Path Analysis" / "tool"
STATIC_DU_UTILS_ROOT = METRIC_ROOT.parent / "Static DU Analysis" / "tool"
NOTEBOOK = METRIC_ROOT / "jacoco_static_du_validation.ipynb"

UTILS = (ROOT / "_jacoco_static_du_validation_utils.py").read_text(encoding="utf-8")
BASE_UTILS = (JACOCO_UTILS_ROOT / "_jacoco_notebook_utils.py").read_text(encoding="utf-8")
PATH_UTILS = (JACOCO_PATH_UTILS_ROOT / "_jacoco_path_analysis_utils.py").read_text(encoding="utf-8")
STATIC_DU_UTILS = (STATIC_DU_UTILS_ROOT / "_static_du_notebook_utils.py").read_text(encoding="utf-8")


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
        "# JaCoCo + Static DU — White Box Validation Notebook\n\n"
        "End-to-end execution of **JaCoCo** and **Static DU** against a Java repository. "
        "Preserves every raw tool output exactly as emitted and validates **31+ White Box metrics** across:\n\n"
        "- Control Flow Testing\n"
        "- Test Regression / Coverage Analysis\n"
        "- Data Flow Testing\n\n"
        "**Default repository:** [java-tool-testing-def-use]"
        "(https://github.com/visvantha-testable/java-tool-testing-def-use)\n\n"
        "Each metric is classified as **Directly Emitted**, **Derived**, or **Not Supported** — never fabricated."
    ),
    md("## Section 1 — Install Dependencies"),
    code(
        "import platform\n"
        "import shutil\n"
        "import subprocess\n"
        "import sys\n\n"
        "IS_COLAB = 'google.colab' in sys.modules\n"
        "IS_LINUX = platform.system() == 'Linux'\n\n"
        "if IS_COLAB or IS_LINUX:\n"
        "    !apt-get update -qq\n"
        "    !apt-get install -y openjdk-17-jdk maven git\n\n"
        "!pip install -q pandas gitpython lxml notebook jupyter\n\n"
        "print('Java:')\n"
        "subprocess.run(['java', '-version'], check=False)\n"
        "if shutil.which('mvn'):\n"
        "    print('\\nMaven:')\n"
        "    subprocess.run(['mvn', '-version'], check=False)"
    ),
    md("## Section 2 — Configuration"),
    code(
        "# Mode 1: Git clone\n"
        "USE_GIT_REPO = True\n"
        "USE_GIT = USE_GIT_REPO  # alias\n\n"
        "REPO_URL = 'https://github.com/visvantha-testable/java-tool-testing-def-use.git'\n\n"
        "# Mode 2: Local path\n"
        "LOCAL_REPO = './workspace/java-tool-testing-def-use'\n\n"
        "WORKSPACE_DIR = './workspace'\n"
        "OUTPUT_DIR = './outputs'\n"
        "IF_CLONE_EXISTS = 'reuse'\n"
        "CLONE_DEPTH = 1\n"
        "SKIP_VERIFY = True\n"
        "BASELINE_JACOCO_XML = ''\n\n"
        "# Colab example:\n"
        "# USE_GIT_REPO = False\n"
        "# LOCAL_REPO = '/content/java-tool-testing-def-use'"
    ),
    md("## Section 3 — Imports and Utility Functions"),
    code(
        "import json\n"
        "import sys\n"
        "import time\n"
        "from pathlib import Path\n\n"
        "import pandas as pd\n"
        "from IPython.display import display\n\n"
        "JACOCO_UTILS_ROOT = Path('..') / 'JaCoCo Coverage' / 'tool'\n"
        "JACOCO_PATH_UTILS_ROOT = Path('..') / 'JaCoCo Path Analysis' / 'tool'\n"
        "STATIC_DU_UTILS_ROOT = Path('..') / 'Static DU Analysis' / 'tool'\n"
        "for path in (JACOCO_UTILS_ROOT, JACOCO_PATH_UTILS_ROOT, STATIC_DU_UTILS_ROOT, Path('tool')):\n"
        "    sys.path.insert(0, str(path.resolve()))\n\n"
        + BASE_UTILS
        + "\n\n"
        + PATH_UTILS
        + "\n\n"
        + STATIC_DU_UTILS
        + "\n\n"
        + UTILS
    ),
    md("## Section 4 — Repository Setup"),
    code(
        "OUTPUT_PATH = Path(OUTPUT_DIR).resolve()\n"
        "WORKSPACE_PATH = Path(WORKSPACE_DIR).resolve()\n"
        "ERROR_LOG_PATH = OUTPUT_PATH / 'error_log.txt'\n\n"
        "ensure_output_dir(OUTPUT_PATH)\n"
        "logger = NotebookLogger(ERROR_LOG_PATH)\n"
        "JAVA_ENV = configure_java_runtime(logger)\n"
        "JAVA_VERSION = java_version_text(JAVA_ENV)\n\n"
        "REPO_PATH = resolve_repository_path(\n"
        "    use_git_repo=USE_GIT_REPO,\n"
        "    repo_url=REPO_URL,\n"
        "    local_repo=LOCAL_REPO,\n"
        "    workspace_dir=WORKSPACE_PATH,\n"
        "    if_clone_exists=IF_CLONE_EXISTS,\n"
        "    logger=logger,\n"
        "    clone_depth=CLONE_DEPTH,\n"
        ")\n\n"
        "BUILD_TOOL = detect_build_tool(REPO_PATH)\n"
        "JAVA_FILES = discover_java_files(REPO_PATH)\n"
        "if not JAVA_FILES:\n"
        "    raise FileNotFoundError('No Java source files found.')\n\n"
        "save_java_inventory(JAVA_FILES, OUTPUT_PATH / 'java_files_inventory.csv')\n"
        "print(f'Repository: {REPO_PATH.name}')\n"
        "print(f'Build Tool: {BUILD_TOOL}')\n"
        "print(f'Java Files: {len(JAVA_FILES)}')"
    ),
    md("## Section 5 — Detect Build Tool"),
    code("print('Detected Build Tool:', BUILD_TOOL)"),
    md("## Section 6 — Build Project, Execute JaCoCo + Static DU (Unified DefUseTrigger)"),
    code(
        "PIPELINE_STARTED = time.perf_counter()\n"
        "COMBINED_STATUS, JACOCO_BUILD_CONSOLE, JACOCO_TRIGGER_CONSOLE, STATIC_DU_CONSOLE = execute_platform_triggers(\n"
        "    REPO_PATH, JAVA_ENV, logger, skip_verify=SKIP_VERIFY\n"
        ")\n"
        "print('Unified trigger:', COMBINED_STATUS.unified_trigger)\n"
        "print('Build success:', COMBINED_STATUS.build_status.build_success)\n"
        "print('JaCoCo report:', COMBINED_STATUS.build_status.report_generated)\n"
        "print('JaCoCo trigger:', COMBINED_STATUS.jacoco_trigger_success)\n"
        "print('Static DU trigger:', COMBINED_STATUS.static_du_trigger_success)"
    ),
    md("## Section 7 — Preserve Raw Outputs"),
    code(
        "BASELINE_PATH = Path(BASELINE_JACOCO_XML).resolve() if BASELINE_JACOCO_XML else None\n"
        "TOTAL_EXECUTION_TIME = round(time.perf_counter() - PIPELINE_STARTED, 5)\n"
        "PARSED = collect_all_outputs(\n"
        "    COMBINED_STATUS, REPO_PATH, JAVA_FILES, BUILD_TOOL, OUTPUT_PATH,\n"
        "    BASELINE_PATH, JACOCO_BUILD_CONSOLE, JACOCO_TRIGGER_CONSOLE, STATIC_DU_CONSOLE,\n"
        ")\n"
        "print('JaCoCo artifacts:', PARSED['copied'])\n"
        "print('Platform JSON:', PARSED['platform_json_copied'])\n"
        "print('Validation JSON:', PARSED['validation_results_json'])"
    ),
    md("## Section 8 — Parse JaCoCo"),
    code("display(PARSED['jacoco_metrics_df'])"),
    md("## Section 9 — Parse Static DU"),
    code("display(PARSED['static_du_metrics_df'].head(25))"),
    md("## Section 10 — Validate Control Flow Testing"),
    code(
        "CONTROL_FLOW_DF = PARSED['control_flow_df']\n"
        "display(CONTROL_FLOW_DF)"
    ),
    md("## Section 11 — Validate Test Regression / Coverage Analysis"),
    code(
        "COVERAGE_DELTA_DF = PARSED['coverage_delta_df']\n"
        "display(COVERAGE_DELTA_DF)"
    ),
    md("## Section 12 — Validate Data Flow Testing"),
    code(
        "DATA_FLOW_DF = PARSED['data_flow_df']\n"
        "display(DATA_FLOW_DF)"
    ),
    md("## Section 13 — Cross Validation"),
    code(
        "CROSS_VALIDATION_DF = PARSED['cross_validation_df']\n"
        "display(CROSS_VALIDATION_DF.head(20))"
    ),
    md("## Section 14 — Taxonomy Truth Table"),
    code(
        "display(PARSED['taxonomy_truth_df'].head(15))\n"
        "print(PARSED['taxonomy_truth_df']['Coverage_Tier'].value_counts())"
    ),
    md("## Section 15 — Repository Summary"),
    code("display(PARSED['repository_summary_df'])"),
    md("## Section 16 — Dashboard"),
    code(
        "display(PARSED['dashboard_summary_df'])\n"
        "display(PARSED['dashboard_df'])\n"
        "print(f'Total execution time (s): {TOTAL_EXECUTION_TIME}')"
    ),
    md("## Section 17 — JSON Exports"),
    code(
        "import json\n"
        "for name in ['jacoco.json', 'static_du.json', 'def_use.json', 'metrics.json', 'platform_metrics.json', 'dashboard_metrics.json', 'validation_results.json']:\n"
        "    path = OUTPUT_PATH / name\n"
        "    print(f'{name}:', 'OK' if path.exists() else 'MISSING')\n"
        "with open(OUTPUT_PATH / 'validation_results.json', encoding='utf-8') as fh:\n"
        "    preview = json.load(fh)\n"
        "print('validation_results.json keys:', list(preview.keys()))"
    ),
    md("## Section 18 — Error Handling"),
    code(
        "logger.write_errors()\n"
        "if ERROR_LOG_PATH.exists() and ERROR_LOG_PATH.stat().st_size:\n"
        "    display(pd.read_csv(ERROR_LOG_PATH))\n"
        "else:\n"
        "    print('No errors logged.')"
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "pygments_lexer": "ipython3"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

NOTEBOOK.write_text(json.dumps(notebook, indent=2), encoding="utf-8")
print(f"Wrote {NOTEBOOK}")
