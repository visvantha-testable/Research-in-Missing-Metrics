"""Generate jpf_path_analysis_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
JACOCO_UTILS_ROOT = METRIC_ROOT.parent / "JaCoCo Coverage" / "tool"
NOTEBOOK = METRIC_ROOT / "jpf_path_analysis_extraction.ipynb"

BASE_UTILS = (JACOCO_UTILS_ROOT / "_jacoco_notebook_utils.py").read_text(encoding="utf-8")
JPF_UTILS = (ROOT / "_jpf_notebook_utils.py").read_text(encoding="utf-8")


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
        "# Java PathFinder (JPF) — Raw Output Extraction (Java)\n\n"
        "This notebook performs **end-to-end execution of Java PathFinder (JPF)** against a Java repository "
        "and captures the **complete raw tool output** without modifying or filtering the results.\n\n"
        "**Default repository:** "
        "[visvantha-testable/java-tool-testing-jacoco]"
        "(https://github.com/visvantha-testable/java-tool-testing-jacoco)\n\n"
        "> **Important:** Metrics are parsed only from explicit JPF console output. "
        "No Path Coverage values are inferred beyond what JPF emits."
    ),
    md(
        "## Section 1 — Install Dependencies\n\n"
        "Install Java, Maven, Python packages, and build Java PathFinder (`jpf-core`, `java-17` branch)."
    ),
    code(
        "import platform\n"
        "import shutil\n"
        "import subprocess\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        "IS_COLAB = 'google.colab' in sys.modules\n"
        "IS_LINUX = platform.system() == 'Linux'\n\n"
        "if IS_COLAB or IS_LINUX:\n"
        "    !apt-get update -qq\n"
        "    !apt-get install -y openjdk-17-jdk maven git\n\n"
        "!pip install -q pandas gitpython notebook jupyter\n\n"
        "print('Java:')\n"
        "subprocess.run(['java', '-version'], check=False)\n"
        "if shutil.which('mvn'):\n"
        "    print('\\nMaven:')\n"
        "    subprocess.run(['mvn', '-version'], check=False)\n"
        "if shutil.which('gradle'):\n"
        "    print('\\nGradle:')\n"
        "    subprocess.run(['gradle', '-version'], check=False)"
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
        "RAW_OUTPUT_PREVIEW_LINES = 150\n"
        "JPF_REPO_URL = 'https://github.com/javapathfinder/jpf-core.git'\n"
        "JPF_BRANCH = 'java-17'\n\n"
        "# Local mode example:\n"
        "# USE_GIT_REPO = False\n"
        "# LOCAL_REPO = './workspace/java-tool-testing-jacoco'\n\n"
        "# Colab example:\n"
        "# USE_GIT_REPO = False\n"
        "# LOCAL_REPO = '/content/java-tool-testing-jacoco'"
    ),
    md("## Section 3 — Imports and Utility Functions"),
    code(
        "import sys\n"
        "import time\n"
        "from pathlib import Path\n\n"
        "import pandas as pd\n"
        "from IPython.display import display\n\n"
        "JACOCO_UTILS_ROOT = Path('..') / 'JaCoCo Coverage' / 'tool'\n"
        "sys.path.insert(0, str(JACOCO_UTILS_ROOT.resolve()))\n"
        "sys.path.insert(0, str(Path('tool').resolve()))\n\n"
        + BASE_UTILS
        + "\n\n"
        + JPF_UTILS
    ),
    md("## Section 4 — Repository Information"),
    code(
        "OUTPUT_PATH = Path(OUTPUT_DIR).resolve()\n"
        "WORKSPACE_PATH = Path(WORKSPACE_DIR).resolve()\n"
        "ERROR_LOG_PATH = OUTPUT_PATH / 'error_log.txt'\n\n"
        "ensure_output_dir(OUTPUT_PATH)\n"
        "logger = JpfNotebookLogger(ERROR_LOG_PATH)\n"
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
        "JAVA_CLASSES = build_java_inventory(JAVA_FILES)\n"
        "REPO_STATS = compute_repository_summary(REPO_PATH, JAVA_CLASSES, BUILD_TOOL, JAVA_VERSION)\n"
        "REPOSITORY_SUMMARY_CSV = OUTPUT_PATH / 'repository_summary.csv'\n"
        "pd.DataFrame([REPO_STATS]).to_csv(REPOSITORY_SUMMARY_CSV, index=False)\n\n"
        "print(f\"Repository Name: {REPO_STATS['repository_name']}\")\n"
        "print(f\"Repository Path: {REPO_STATS['repository_path']}\")\n"
        "print(f\"Java Version: {REPO_STATS['java_version']}\")\n"
        "print(f\"Build Tool: {REPO_STATS['build_tool']}\")\n"
        "print(f\"Total Packages: {REPO_STATS['total_packages']}\")\n"
        "print(f\"Total Classes: {REPO_STATS['total_classes']}\")\n"
        "print(f\"Repository Size (bytes): {REPO_STATS['repository_size_bytes']}\")"
    ),
    md("## Section 5 — Discover Java Files"),
    code(
        "INVENTORY_CSV = OUTPUT_PATH / 'java_files_inventory.csv'\n"
        "save_java_inventory(JAVA_CLASSES, INVENTORY_CSV)\n"
        "display(pd.read_csv(INVENTORY_CSV).head(20))"
    ),
    md("## Section 6 — Detect Build Tool"),
    code("print('Detected Build Tool:')\nprint(BUILD_TOOL)"),
    md("## Section 7 — Build Repository"),
    code(
        "PIPELINE_STARTED = time.perf_counter()\n"
        "BUILD_RESULT, BUILD_CONSOLE_OUTPUT = execute_compile_only(\n"
        "    REPO_PATH, BUILD_TOOL, JAVA_ENV, logger\n"
        ")\n"
        "print(f'Build success: {BUILD_RESULT.exit_code == 0}')\n"
        "print(f'Build execution time (s): {BUILD_RESULT.execution_time_seconds}')"
    ),
    md("## Section 8 — Configure Java PathFinder"),
    code(
        "JPF_INSTALL = ensure_jpf_installed(\n"
        "    JAVA_ENV,\n"
        "    logger,\n"
        "    WORKSPACE_PATH,\n"
        "    jpf_repo_url=JPF_REPO_URL,\n"
        "    jpf_branch=JPF_BRANCH,\n"
        ")\n"
        "CLASSPATH_DIRS = discover_compiled_classpath_dirs(REPO_PATH)\n"
        "SOURCEPATH_DIRS = discover_sourcepath_dirs(REPO_PATH)\n"
        "PROJECT_JPF_PROPERTIES = write_project_jpf_properties(REPO_PATH, CLASSPATH_DIRS, SOURCEPATH_DIRS)\n"
        "JPF_CONFIG_DIR = OUTPUT_PATH / 'jpf_configs'\n"
        "JPF_CONFIG_DIR.mkdir(parents=True, exist_ok=True)\n\n"
        "print('JPF Home:', JPF_INSTALL.jpf_home)\n"
        "print('RunJPF.jar:', JPF_INSTALL.run_jpf_jar)\n"
        "print('site.properties:', JPF_INSTALL.site_properties)\n"
        "print('Project jpf.properties:', PROJECT_JPF_PROPERTIES)\n"
        "print('Classpath dirs:', [str(path) for path in CLASSPATH_DIRS])\n"
        "print('Sourcepath dirs:', [str(path) for path in SOURCEPATH_DIRS])\n"
        "print('\\nGenerated jpf.properties:')\n"
        "print(PROJECT_JPF_PROPERTIES.read_text(encoding='utf-8'))"
    ),
    md("## Section 9 — Execute Java PathFinder"),
    code(
        "if not JPF_INSTALL.build_success:\n"
        "    logger.error('JPF installation/build failed. Cannot execute JPF.', step='jpf_install')\n"
        "    JPF_RUNS, JPF_CONSOLE_OUTPUT = [], BUILD_CONSOLE_OUTPUT\n"
        "else:\n"
        "    JPF_RUNS, JPF_CONSOLE_OUTPUT = execute_jpf_for_classes(\n"
        "        JPF_INSTALL,\n"
        "        JAVA_CLASSES,\n"
        "        CLASSPATH_DIRS,\n"
        "        SOURCEPATH_DIRS,\n"
        "        JAVA_ENV,\n"
        "        logger,\n"
        "        JPF_CONFIG_DIR,\n"
        "    )\n"
        "    JPF_CONSOLE_OUTPUT = BUILD_CONSOLE_OUTPUT + '\\n' + JPF_CONSOLE_OUTPUT\n"
        "print(f'Classes executed by JPF: {len(JPF_RUNS)}')\n"
        "print(f'Classes with main method: {sum(1 for item in JAVA_CLASSES if item.has_main)}')"
    ),
    md("## Section 10 — Raw Output Collection"),
    code(
        "CONSOLE_PATH = OUTPUT_PATH / 'jpf_console_output.txt'\n"
        "CONSOLE_PATH.write_text(JPF_CONSOLE_OUTPUT, encoding='utf-8')\n"
        "SECTION_ARTIFACTS = extract_verbatim_sections(JPF_CONSOLE_OUTPUT, OUTPUT_PATH)\n"
        "COPIED_ARTIFACTS = copy_generated_jpf_artifacts([JPF_CONFIG_DIR, REPO_PATH], OUTPUT_PATH)\n"
        "print('Saved:', CONSOLE_PATH)\n"
        "print('Section artifacts:', SECTION_ARTIFACTS)\n"
        "print('Copied artifacts:', COPIED_ARTIFACTS)\n"
        "preview_raw_output(JPF_CONSOLE_OUTPUT, RAW_OUTPUT_PREVIEW_LINES, CONSOLE_PATH)"
    ),
    md("## Section 11 — Extract JPF Results"),
    code(
        "METRIC_ROWS = []\n"
        "for run in JPF_RUNS:\n"
        "    METRIC_ROWS.extend(run.metrics)\n"
        "JPF_METRICS_DF = pd.DataFrame(METRIC_ROWS)\n"
        "if JPF_METRICS_DF.empty:\n"
        "    JPF_METRICS_DF = pd.DataFrame(columns=['metric_name', 'metric_value', 'source_class', 'method'])\n"
        "JPF_METRICS_DF.to_csv(OUTPUT_PATH / 'jpf_metrics.csv', index=False)\n"
        "display(JPF_METRICS_DF.head(30))"
    ),
    md("## Section 12 — Path Analysis"),
    code(
        "PATH_VALIDATION_DF = validate_path_metrics(JPF_CONSOLE_OUTPUT, 'jpf_console_output.txt')\n"
        "PATH_VALIDATION_DF.to_csv(OUTPUT_PATH / 'path_validation.csv', index=False)\n"
        "display(PATH_VALIDATION_DF)"
    ),
    md("## Section 13 — Class Summary"),
    code(
        "CLASS_SUMMARY_DF = build_class_summary(JPF_RUNS)\n"
        "CLASS_SUMMARY_DF.to_csv(OUTPUT_PATH / 'class_summary.csv', index=False)\n"
        "display(CLASS_SUMMARY_DF)"
    ),
    md("## Section 14 — Repository Summary"),
    code(
        "TOTAL_EXECUTION_TIME = round(time.perf_counter() - PIPELINE_STARTED, 5)\n"
        "REPOSITORY_METRICS_DF = build_repository_metrics(JAVA_CLASSES, JPF_RUNS, TOTAL_EXECUTION_TIME)\n"
        "REPOSITORY_METRICS_DF.to_csv(OUTPUT_PATH / 'repository_metrics.csv', index=False)\n"
        "display(REPOSITORY_METRICS_DF)"
    ),
    md("## Section 15 — Dashboard"),
    code(
        "DASHBOARD_DF = build_dashboard_table(REPO_STATS, CLASS_SUMMARY_DF, REPOSITORY_METRICS_DF)\n"
        "display(DASHBOARD_DF)"
    ),
    md("## Section 16 — Error Handling"),
    code(
        "logger.write_errors()\n"
        "if ERROR_LOG_PATH.exists():\n"
        "    display(pd.read_csv(ERROR_LOG_PATH))\n"
        "else:\n"
        "    print('No errors logged.')"
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "pygments_lexer": "ipython3",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

NOTEBOOK.write_text(json.dumps(notebook, indent=2), encoding="utf-8")
print(f"Wrote {NOTEBOOK}")
