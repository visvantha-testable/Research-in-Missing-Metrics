"""Generate jacoco_path_analysis_validation.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
JACOCO_UTILS_ROOT = METRIC_ROOT.parent / "JaCoCo Coverage" / "tool"
NOTEBOOK = METRIC_ROOT / "jacoco_path_analysis_validation.ipynb"

BASE_UTILS = (JACOCO_UTILS_ROOT / "_jacoco_notebook_utils.py").read_text(encoding="utf-8")
PATH_UTILS = (ROOT / "_jacoco_path_analysis_utils.py").read_text(encoding="utf-8")


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
        "# JaCoCo Path Analysis Validation (Java)\n\n"
        "This notebook executes **JaCoCo** against a Java repository and validates whether JaCoCo "
        "**explicitly emits any Path Coverage-related metrics or evidence**.\n\n"
        "**Default repository:** "
        "[visvantha-testable/java-tool-testing-jacoco]"
        "(https://github.com/visvantha-testable/java-tool-testing-jacoco)\n\n"
        "> **Important:** This notebook does **not** derive or estimate Path Coverage. "
        "It only reports whether Path Coverage evidence is explicitly present in JaCoCo outputs."
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
        "    !apt-get install -y openjdk-17-jdk maven\n\n"
        "!pip install -q pandas gitpython notebook jupyter\n\n"
        "subprocess.run(['java', '-version'], check=False)\n"
        "if shutil.which('mvn'):\n"
        "    subprocess.run(['mvn', '-version'], check=False)"
    ),
    md("## Section 2 — Configuration"),
    code(
        "USE_GIT_REPO = True\n\n"
        "REPO_URL = 'https://github.com/visvantha-testable/java-tool-testing-jacoco.git'\n\n"
        "LOCAL_REPO = './workspace/java-tool-testing-jacoco'\n\n"
        "WORKSPACE_DIR = './workspace'\n"
        "OUTPUT_DIR = './outputs'\n"
        "IF_CLONE_EXISTS = 'reuse'\n"
        "CLONE_DEPTH = 1\n"
        "RAW_OUTPUT_PREVIEW_LINES = 150"
    ),
    md("## Section 3 — Imports and Utility Functions"),
    code(
        "import sys\n"
        "import time\n"
        "from pathlib import Path\n\n"
        "from IPython.display import display\n\n"
        "JACOCO_UTILS_ROOT = Path('..') / 'JaCoCo Coverage' / 'tool'\n"
        "sys.path.insert(0, str(JACOCO_UTILS_ROOT.resolve()))\n"
        "sys.path.insert(0, str(Path('tool').resolve()))\n\n"
        + BASE_UTILS
        + "\n\n"
        + PATH_UTILS
    ),
    md("## Section 4 — Repository Information"),
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
        "REPO_STATS = compute_repository_stats(REPO_PATH, JAVA_FILES, BUILD_TOOL, JAVA_VERSION)\n"
        "REPOSITORY_SUMMARY_CSV = OUTPUT_PATH / 'repository_summary.csv'\n"
        "pd.DataFrame([REPO_STATS]).to_csv(REPOSITORY_SUMMARY_CSV, index=False)\n\n"
        "print(f\"Repository Name: {REPO_STATS['repository_name']}\")\n"
        "print(f\"Repository Path: {REPO_STATS['repository_location']}\")\n"
        "print(f\"Build Tool: {REPO_STATS['build_tool']}\")\n"
        "print(f\"Java Version: {REPO_STATS['java_version']}\")\n"
        "print(f\"Total Java Files: {REPO_STATS['total_java_files']}\")"
    ),
    md("## Section 5 — Discover Java Files"),
    code(
        "INVENTORY_CSV = OUTPUT_PATH / 'java_files_inventory.csv'\n"
        "save_java_inventory(JAVA_FILES, INVENTORY_CSV)\n"
        "display(pd.read_csv(INVENTORY_CSV).head())"
    ),
    md("## Section 6 — Detect Build Tool"),
    code("print('Detected Build Tool:')\nprint(BUILD_TOOL)"),
    md("## Section 7 — Build Project"),
    code(
        "PIPELINE_STARTED = time.perf_counter()\n"
        "BUILD_STATUS, RAW_CONSOLE_OUTPUT = execute_build_and_jacoco(\n"
        "    REPO_PATH, BUILD_TOOL, JAVA_ENV, logger\n"
        ")\n"
        "print(f'Build success: {BUILD_STATUS.build_success}')\n"
        "print(f'Test success: {BUILD_STATUS.test_success}')\n"
        "print(f'Report generated: {BUILD_STATUS.report_generated}')"
    ),
    md("## Section 8 — Execute JaCoCo / Verify Reports"),
    code(
        "if BUILD_STATUS.report_dir:\n"
        "    for label, path in [\n"
        "        ('jacoco.exec', BUILD_STATUS.jacoco_exec),\n"
        "        ('jacoco.xml', BUILD_STATUS.jacoco_xml),\n"
        "        ('jacoco.csv', BUILD_STATUS.jacoco_csv),\n"
        "        ('index.html', BUILD_STATUS.index_html),\n"
        "    ]:\n"
        "        print(f\"{label}: {'OK' if path and path.exists() else 'MISSING'}\")\n"
        "else:\n"
        "    logger.error('JaCoCo report directory not found.', step='jacoco')"
    ),
    md("## Section 9 — Preserve Raw Outputs"),
    code(
        "CONSOLE_PATH = OUTPUT_PATH / 'jacoco_console_output.txt'\n"
        "CONSOLE_PATH.write_text(RAW_CONSOLE_OUTPUT, encoding='utf-8')\n"
        "COPIED = copy_raw_jacoco_artifacts(BUILD_STATUS, OUTPUT_PATH)\n"
        "print('Copied artifacts:', COPIED)\n"
        "preview_raw_output(RAW_CONSOLE_OUTPUT, RAW_OUTPUT_PREVIEW_LINES, CONSOLE_PATH)"
    ),
    md("## Section 10 — Parse JaCoCo XML"),
    code(
        "XML_DUMP_CSV = OUTPUT_PATH / 'jacoco_xml_dump.csv'\n"
        "if (OUTPUT_PATH / 'jacoco.xml').exists():\n"
        "    XML_DUMP_DF = dump_jacoco_xml_nodes(OUTPUT_PATH / 'jacoco.xml', XML_DUMP_CSV)\n"
        "    print(f'XML nodes dumped: {len(XML_DUMP_DF)}')\n"
        "    display(XML_DUMP_DF.head(20))\n"
        "else:\n"
        "    logger.error('jacoco.xml missing; cannot dump XML nodes.', step='xml_parse')"
    ),
    md("## Section 11 — Search for Path Coverage Evidence"),
    code(
        "ARTIFACTS = {\n"
        "    'jacoco_console_output.txt': CONSOLE_PATH,\n"
        "    'jacoco.xml': OUTPUT_PATH / 'jacoco.xml',\n"
        "    'jacoco.csv': OUTPUT_PATH / 'jacoco.csv',\n"
        "    'index.html': OUTPUT_PATH / 'index.html',\n"
        "    'jacoco.exec': OUTPUT_PATH / 'jacoco.exec',\n"
        "}\n"
        "KEYWORD_DF = search_path_keywords(ARTIFACTS)\n"
        "KEYWORD_CSV = OUTPUT_PATH / 'path_keyword_search.csv'\n"
        "KEYWORD_DF.to_csv(KEYWORD_CSV, index=False)\n"
        "display(KEYWORD_DF[KEYWORD_DF['Found (Yes/No)'] == 'Yes'])"
    ),
    md("## Section 12 — Path Metric Validation"),
    code(
        "VALIDATION_DF = validate_path_metrics(\n"
        "    KEYWORD_DF,\n"
        "    ARTIFACTS,\n"
        "    OUTPUT_PATH / 'jacoco.xml',\n"
        ")\n"
        "VALIDATION_CSV = OUTPUT_PATH / 'path_metric_validation.csv'\n"
        "VALIDATION_DF.to_csv(VALIDATION_CSV, index=False)\n"
        "display(VALIDATION_DF)"
    ),
    md("## Section 13 — Dashboard"),
    code(
        "TOTAL_EXECUTION_TIME = round(time.perf_counter() - PIPELINE_STARTED, 5)\n"
        "dashboard_df = pd.DataFrame([\n"
        "    {'Metric': metric, 'Supported': row['Supported']}\n"
        "    for metric, row in VALIDATION_DF.set_index('Metric').iterrows()\n"
        "])\n"
        "display(dashboard_df)\n\n"
        "deliverables = [\n"
        "    REPOSITORY_SUMMARY_CSV,\n"
        "    INVENTORY_CSV,\n"
        "    CONSOLE_PATH,\n"
        "    OUTPUT_PATH / 'jacoco.exec',\n"
        "    OUTPUT_PATH / 'jacoco.xml',\n"
        "    OUTPUT_PATH / 'jacoco.csv',\n"
        "    OUTPUT_PATH / 'index.html',\n"
        "    XML_DUMP_CSV,\n"
        "    KEYWORD_CSV,\n"
        "    VALIDATION_CSV,\n"
        "    ERROR_LOG_PATH,\n"
        "]\n"
        "print('\\nDeliverables:')\n"
        "for path in deliverables:\n"
        "    print(f\"  [{'OK' if path.exists() else 'MISSING'}] {path}\")\n"
        "print(f'\\nTotal execution time: {TOTAL_EXECUTION_TIME}s')"
    ),
    md("## Section 14 — Error Handling"),
    code(
        "if ERROR_LOG_PATH.exists() and ERROR_LOG_PATH.stat().st_size > 0:\n"
        "    print(ERROR_LOG_PATH.read_text(encoding='utf-8'))\n"
        "else:\n"
        "    print('No errors logged.')"
    ),
    md(
        "## Deliverables\n\n"
        "```text\n"
        "outputs/\n"
        "├── repository_summary.csv\n"
        "├── java_files_inventory.csv\n"
        "├── jacoco_console_output.txt\n"
        "├── jacoco.exec\n"
        "├── jacoco.xml\n"
        "├── jacoco.csv\n"
        "├── index.html\n"
        "├── jacoco_xml_dump.csv\n"
        "├── path_keyword_search.csv\n"
        "├── path_metric_validation.csv\n"
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
