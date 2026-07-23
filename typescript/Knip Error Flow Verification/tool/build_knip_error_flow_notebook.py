"""Generate knip_error_flow_validation.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "knip_error_flow_validation.ipynb"
UTILS = (ROOT / "_knip_error_flow_utils.py").read_text(encoding="utf-8")


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "outputs": [], "source": source.splitlines(keepends=True)}


cells = [
    md(
        "# Knip — Error Flow Verification (TypeScript)\n\n"
        "| Property | Value |\n"
        "| --- | --- |\n"
        "| Technique | Control Flow Testing |\n"
        "| Classification | Path Coverage |\n"
        "| Metric | Exception Path Handling |\n"
        "| KPI | Error Flow Verification |\n\n"
        "**Repository:** "
        "[visvantha-testable/typescript-tool-testing-knip]"
        "(https://github.com/visvantha-testable/typescript-tool-testing-knip)\n\n"
        "**Tool:** Knip (latest stable)\n\n"
        "> Raw Knip output is preserved verbatim. Metrics are extracted only from actual Knip reporter output."
    ),
    md("## Section 1 — Clone Repository"),
    code(
        "USE_GIT_REPO = True\n"
        'REPO_URL = "https://github.com/visvantha-testable/typescript-tool-testing-knip.git"\n'
        'LOCAL_REPO = "./workspace/typescript-tool-testing-knip"\n'
        'IF_CLONE_EXISTS = "reuse"\n'
        "CLONE_DEPTH = 1\n"
    ),
    md("## Section 2 — Environment Information"),
    code(
        "import subprocess\n"
        "import sys\n\n"
        "subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', '-r', 'requirements.txt'])"
    ),
    md("## Section 3 — Install Dependencies"),
    code(
        UTILS
        + "\n\n"
        "import time\n"
        "from pathlib import Path\n"
        "from IPython.display import Markdown, display\n\n"
        "METRIC_ROOT = resolve_metric_root(Path('.').resolve())\n"
        "WORKSPACE_DIR = METRIC_ROOT / 'workspace'\n"
        "ARTIFACT_DIRS = ensure_artifact_dirs(METRIC_ROOT)\n"
        "RAW_DIR = ARTIFACT_DIRS['raw']\n"
        "PARSED_DIR = ARTIFACT_DIRS['parsed']\n"
        "REPORTS_DIR = ARTIFACT_DIRS['reports']\n"
        "ERROR_LOG_PATH = REPORTS_DIR / 'error_log.txt'\n\n"
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
        "REPO_VALIDATION = validate_repository_layout(REPO_PATH, logger)\n"
        "display(pd.DataFrame([REPO_VALIDATION]))\n"
        "if not REPO_VALIDATION['repository_valid']:\n"
        "    raise RuntimeError('Repository validation failed.')"
    ),
    code(
        "PACKAGE_MANAGER = detect_package_manager(REPO_PATH)\n"
        "print(f'Detected package manager: {PACKAGE_MANAGER}')\n"
        "if PACKAGE_MANAGER == 'unknown':\n"
        "    raise RuntimeError('Unable to detect package manager.')\n\n"
        "ENVIRONMENT = collect_environment_details(REPO_PATH, PACKAGE_MANAGER, logger)\n"
        "ENVIRONMENT_PATH = REPORTS_DIR / 'environment.json'\n"
        "ENVIRONMENT_PATH.write_text(json.dumps(ENVIRONMENT, indent=2), encoding='utf-8')\n"
        "display(pd.DataFrame([ENVIRONMENT]))"
    ),
    md("## Section 4 — Install Knip"),
    code(
        "INSTALL_RESULT = install_project_dependencies(REPO_PATH, PACKAGE_MANAGER, logger)\n"
        "print(f\"Command: {INSTALL_RESULT['command']}\")\n"
        "print(f\"Return code: {INSTALL_RESULT['returncode']}\")\n"
        "print(f\"Elapsed ms: {INSTALL_RESULT['elapsed_ms']:.2f}\")\n"
        "if INSTALL_RESULT['returncode'] != 0:\n"
        "    raise RuntimeError(f'{PACKAGE_MANAGER} install failed.')\n\n"
        "KNIP_INSTALL = ensure_knip_installed(REPO_PATH, PACKAGE_MANAGER, logger)\n"
        "display(pd.DataFrame([KNIP_INSTALL]))\n"
        "if KNIP_INSTALL['status'] != 'OK':\n"
        "    raise RuntimeError('Knip is not installed and could not be installed.')"
    ),
    md("## Section 5 — Execute Knip"),
    code(
        "CONFIG_INFO = resolve_knip_config(REPO_PATH, ARTIFACT_DIRS['temp'], logger)\n"
        "CONFIG_PATH = Path(CONFIG_INFO['config_path'])\n"
        "if not CONFIG_PATH.exists():\n"
        "    raise FileNotFoundError(f'Knip config file not found: {CONFIG_PATH}')\n"
        "(PARSED_DIR / 'knip_configuration.json').write_text(json.dumps(CONFIG_INFO, indent=2), encoding='utf-8')\n"
        "print(json.dumps(CONFIG_INFO, indent=2))\n\n"
        "JSON_EXECUTION = execute_knip(REPO_PATH, CONFIG_PATH, logger, json_output=True)\n"
        "CONSOLE_EXECUTION = execute_knip(REPO_PATH, CONFIG_PATH, logger, json_output=False)\n\n"
        "print('JSON command:', JSON_EXECUTION['command'])\n"
        "print('JSON return code:', JSON_EXECUTION['returncode'])\n"
        "print('Console command:', CONSOLE_EXECUTION['command'])\n"
        "print('Console return code:', CONSOLE_EXECUTION['returncode'])"
    ),
    md("## Section 6 — Capture Raw Tool Output"),
    code(
        "write_text_verbatim(RAW_DIR / 'knip_stdout.txt', CONSOLE_EXECUTION['stdout'])\n"
        "write_text_verbatim(\n"
        "    RAW_DIR / 'knip_stderr.txt',\n"
        "    CONSOLE_EXECUTION['stderr'] + JSON_EXECUTION['stderr'],\n"
        ")\n"
        "write_text_verbatim(RAW_DIR / 'knip_json_stdout.txt', JSON_EXECUTION['stdout'])\n"
        "REPORT_PATH = require_knip_json_report(RAW_DIR, JSON_EXECUTION, logger)\n"
        "EXECUTION_PATH = save_execution_report(REPORTS_DIR, CONSOLE_EXECUTION, JSON_EXECUTION, ENVIRONMENT)\n\n"
        "print(f'Saved raw JSON report: {REPORT_PATH}')\n"
        "print(f'Saved execution metadata: {EXECUTION_PATH}')"
    ),
    md("## Section 7 — Display Raw Output"),
    code(
        "KNIP_RAW_JSON = REPORT_PATH.read_text(encoding='utf-8')\n"
        "print('===== knip-report.json (verbatim) =====')\n"
        "print(KNIP_RAW_JSON)\n"
        "print('\\n===== knip_stdout.txt (verbatim) =====')\n"
        "print(CONSOLE_EXECUTION['stdout'] or '(empty)')"
    ),
    md("## Section 8 — Extract Available Metrics"),
    code(
        "METRICS_DF = extract_knip_metrics(REPORT_PATH)\n"
        "METRICS_DF.to_csv(PARSED_DIR / 'knip_metrics.csv', index=False)\n"
        "METRICS_PAYLOAD = {\n"
        "    str(row['Metric']): {'json_field': row['JSON Field'], 'value': row['Value']}\n"
        "    for _, row in METRICS_DF.iterrows()\n"
        "}\n"
        "(PARSED_DIR / 'knip_metrics.json').write_text(json.dumps(METRICS_PAYLOAD, indent=2), encoding='utf-8')\n"
        "display(METRICS_DF)"
    ),
    md("## Section 9 — Validate Exception Path Handling Metric"),
    code(
        "TAXONOMY_DF = validate_taxonomy_levels(\n"
        "    REPORT_PATH,\n"
        "    CONSOLE_EXECUTION['stdout'],\n"
        "    CONSOLE_EXECUTION['stderr'],\n"
        ")\n"
        "TAXONOMY_DF.to_csv(PARSED_DIR / 'taxonomy_validation.csv', index=False)\n"
        "(PARSED_DIR / 'taxonomy_validation.json').write_text(\n"
        "    json.dumps(TAXONOMY_DF.to_dict(orient='records'), indent=2),\n"
        "    encoding='utf-8',\n"
        ")\n"
        "display(TAXONOMY_DF)\n"
        "print(EXCEPTION_PATH_STATEMENT)"
    ),
    md("## Section 10 — Generate Final Summary"),
    code(
        "REPORT_DF = build_final_report_table(\n"
        "    REPORT_PATH,\n"
        "    CONSOLE_EXECUTION['stdout'],\n"
        "    CONSOLE_EXECUTION['stderr'],\n"
        ")\n"
        "REPORT_DF.to_csv(REPORTS_DIR / 'final_metric_report.csv', index=False)\n"
        "REPORT_MARKDOWN = render_final_report_markdown(REPORT_DF, TAXONOMY_DF)\n"
        "(REPORTS_DIR / 'final_metric_report.md').write_text(REPORT_MARKDOWN, encoding='utf-8')\n\n"
        "ARTIFACT_PATHS = {\n"
        "    'knip_report_json': str(REPORT_PATH.resolve()),\n"
        "    'knip_stdout_txt': str((RAW_DIR / 'knip_stdout.txt').resolve()),\n"
        "    'knip_stderr_txt': str((RAW_DIR / 'knip_stderr.txt').resolve()),\n"
        "    'knip_json_stdout_txt': str((RAW_DIR / 'knip_json_stdout.txt').resolve()),\n"
        "    'execution_json': str(EXECUTION_PATH.resolve()),\n"
        "    'environment_json': str(ENVIRONMENT_PATH.resolve()),\n"
        "}\n"
        "OUTPUT_JSON_PATH = REPORTS_DIR / 'output.json'\n"
        "OUTPUT_PAYLOAD = build_output_json(\n"
        "    repo_path=REPO_PATH,\n"
        "    repo_validation=REPO_VALIDATION,\n"
        "    environment=ENVIRONMENT,\n"
        "    config_info=CONFIG_INFO,\n"
        "    install_result=INSTALL_RESULT,\n"
        "    knip_install=KNIP_INSTALL,\n"
        "    console_execution=CONSOLE_EXECUTION,\n"
        "    json_execution=JSON_EXECUTION,\n"
        "    metrics_payload=METRICS_PAYLOAD,\n"
        "    taxonomy_df=TAXONOMY_DF,\n"
        "    report_df=REPORT_DF,\n"
        "    artifact_paths=ARTIFACT_PATHS,\n"
        "    elapsed_ms=(time.perf_counter() - PIPELINE_STARTED) * 1000,\n"
        ")\n"
        "OUTPUT_JSON_PATH.write_text(json.dumps(OUTPUT_PAYLOAD, indent=2), encoding='utf-8')\n\n"
        "display(Markdown(REPORT_MARKDOWN))\n"
        "print(f'Saved consolidated output JSON: {OUTPUT_JSON_PATH}')\n\n"
        "TOTAL_EXECUTION_TIME = round(time.perf_counter() - PIPELINE_STARTED, 2)\n"
        "print(f'Total notebook execution time (seconds): {TOTAL_EXECUTION_TIME}')\n\n"
        "deliverables = [\n"
        "    REPORT_PATH,\n"
        "    RAW_DIR / 'knip_stdout.txt',\n"
        "    RAW_DIR / 'knip_stderr.txt',\n"
        "    EXECUTION_PATH,\n"
        "    ENVIRONMENT_PATH,\n"
        "    PARSED_DIR / 'knip_metrics.csv',\n"
        "    OUTPUT_JSON_PATH,\n"
        "    REPORTS_DIR / 'final_metric_report.md',\n"
        "    ERROR_LOG_PATH,\n"
        "]\n"
        "print('\\nDeliverables:')\n"
        "for path in deliverables:\n"
        "    print(f\"  [{'OK' if path.exists() else 'MISSING'}] {path}\")\n\n"
        "logger.write_errors()"
    ),
    md(
        "## Artifact Layout\n\n"
        "```text\n"
        "artifacts/\n"
        "├── raw/\n"
        "│   ├── knip-report.json\n"
        "│   ├── knip_stdout.txt\n"
        "│   ├── knip_stderr.txt\n"
        "│   └── knip_json_stdout.txt\n"
        "├── parsed/\n"
        "│   ├── knip_metrics.csv\n"
        "│   └── taxonomy_validation.csv\n"
        "└── reports/\n"
        "    ├── environment.json\n"
        "    ├── execution.json\n"
        "    ├── output.json\n"
        "    ├── final_metric_report.md\n"
        "    └── error_log.txt\n"
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
