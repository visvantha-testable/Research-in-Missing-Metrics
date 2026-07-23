"""Generate vitest_path_coverage_validation.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "vitest_path_coverage_validation.ipynb"
UTILS = (ROOT / "_vitest_path_coverage_utils.py").read_text(encoding="utf-8")


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "outputs": [], "source": source.splitlines(keepends=True)}


cells = [
    md(
        "# Vitest + @vitest/coverage-v8 — Path Coverage Validation (TypeScript)\n\n"
        "| Property | Value |\n"
        "| --- | --- |\n"
        "| Testing Technique | Control Flow Testing |\n"
        "| Classification | Path Coverage |\n"
        "| Metric | Path Detection Testing |\n"
        "| KPI | Path Coverage % |\n\n"
        "**Repository:** "
        "[visvantha-testable/typescript-tool-testing-eslint-eslint-plugin-sonarjs]"
        "(https://github.com/visvantha-testable/typescript-tool-testing-eslint-eslint-plugin-sonarjs)\n\n"
        "**Tool:** Vitest + `@vitest/coverage-v8` only\n\n"
        "> Raw Vitest coverage artifacts are preserved verbatim under `artifacts/raw/`. "
        "Metric extraction reads only from generated coverage JSON."
    ),
    md("## 1. Clone Repository"),
    code(
        "USE_GIT_REPO = True\n"
        'REPO_URL = "https://github.com/visvantha-testable/typescript-tool-testing-eslint-eslint-plugin-sonarjs.git"\n'
        'LOCAL_REPO = "./workspace/typescript-tool-testing-eslint-eslint-plugin-sonarjs"\n'
        'IF_CLONE_EXISTS = "reuse"\n'
        "CLONE_DEPTH = 1\n"
    ),
    md("## 2. Environment Information"),
    code(
        "import subprocess\n"
        "import sys\n\n"
        "subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', '-r', 'requirements.txt'])\n"
    ),
    md("## 3. Install Dependencies"),
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
        "ENVIRONMENT = collect_environment_info(REPO_PATH, logger)\n"
        "ENV_DF = pd.DataFrame([ENVIRONMENT])\n"
        "ENV_DF.to_csv(PARSED_DIR / 'environment_info.csv', index=False)\n"
        "(PARSED_DIR / 'environment_info.json').write_text(json.dumps(ENVIRONMENT, indent=2), encoding='utf-8')\n"
        "display(ENV_DF)"
    ),
    md("## 4. Install Vitest Coverage"),
    code(
        "INSTALL_RESULT = install_project_dependencies(REPO_PATH, logger)\n"
        "print(f\"Command: {INSTALL_RESULT['command']}\")\n"
        "print(f\"Return code: {INSTALL_RESULT['returncode']}\")\n"
        "print(f\"Elapsed ms: {INSTALL_RESULT['elapsed_ms']:.2f}\")\n"
        "print('--- stdout ---')\n"
        "print(INSTALL_RESULT['stdout'])\n"
        "print('--- stderr ---')\n"
        "print(INSTALL_RESULT['stderr'])\n"
        "if INSTALL_RESULT['returncode'] != 0:\n"
        "    raise RuntimeError('npm install failed.')\n\n"
        "VITEST_PACKAGES_DF = install_vitest_packages(REPO_PATH, logger)\n"
        "VITEST_PACKAGES_DF.to_csv(PARSED_DIR / 'vitest_packages.csv', index=False)\n"
        "display(VITEST_PACKAGES_DF)\n"
        "if (VITEST_PACKAGES_DF['status'] != 'OK').any():\n"
        "    raise RuntimeError('Required Vitest packages are not installed.')"
    ),
    md("## 5. Execute Tests"),
    code(
        "REPO_CONFIG = detect_vitest_config(REPO_PATH)\n"
        "TEMP_CONFIG = None\n"
        "if REPO_CONFIG is None:\n"
        "    TEMP_CONFIG = create_temp_vitest_config(ARTIFACT_DIRS['temp'], RAW_DIR / 'coverage')\n"
        "    CONFIG_USED = TEMP_CONFIG\n"
        "    CONFIG_SOURCE = 'temporary notebook config'\n"
        "else:\n"
        "    CONFIG_USED = REPO_CONFIG\n"
        "    CONFIG_SOURCE = 'repository config'\n\n"
        "CONFIG_INFO = {\n"
        "    'repository_config': str(REPO_CONFIG) if REPO_CONFIG else '',\n"
        "    'config_used': str(CONFIG_USED),\n"
        "    'config_source': CONFIG_SOURCE,\n"
        "}\n"
        "(PARSED_DIR / 'vitest_configuration.json').write_text(json.dumps(CONFIG_INFO, indent=2), encoding='utf-8')\n"
        "print(json.dumps(CONFIG_INFO, indent=2))\n\n"
        "EXECUTION = execute_vitest_coverage(REPO_PATH, None if REPO_CONFIG else TEMP_CONFIG, logger)\n"
        "print(f\"Command: {EXECUTION['command']}\")\n"
        "print(f\"Return code: {EXECUTION['returncode']}\")\n"
        "print(f\"Elapsed ms: {EXECUTION['elapsed_ms']:.2f}\")\n"
        "if EXECUTION['returncode'] != 0:\n"
        "    raise RuntimeError('Vitest test execution failed.')"
    ),
    md("## 6. Save Raw Tool Output"),
    code(
        "COVERAGE_DIR = locate_coverage_output_dir(REPO_PATH, CONFIG_USED, RAW_DIR)\n"
        "SAVED = preserve_raw_artifacts(COVERAGE_DIR, RAW_DIR, EXECUTION, ENVIRONMENT)\n"
        "ARTIFACT_PATHS = require_coverage_artifacts(RAW_DIR, logger)\n\n"
        "print('Saved raw artifacts:')\n"
        "for path in sorted(set(SAVED['files'])):\n"
        "    print(f'  {path}')"
    ),
    md("## 7. Display Raw JSON"),
    code(
        "SUMMARY_RAW_TEXT = read_raw_json_text(ARTIFACT_PATHS['coverage-summary.json'])\n"
        "FINAL_RAW_TEXT = read_raw_json_text(ARTIFACT_PATHS['coverage-final.json'])\n\n"
        "print('===== coverage-summary.json (verbatim) =====')\n"
        "print(SUMMARY_RAW_TEXT)\n"
        "print('\\n===== coverage-final.json (first 2000 chars, full file saved verbatim) =====')\n"
        "print(FINAL_RAW_TEXT[:2000])\n"
        "if len(FINAL_RAW_TEXT) > 2000:\n"
        "    print(f'\\n... ({len(FINAL_RAW_TEXT) - 2000} more characters saved to {ARTIFACT_PATHS[\"coverage-final.json\"]})')"
    ),
    md("## 8. Extract Coverage Metrics"),
    code(
        "METRICS_DF = extract_coverage_metrics(ARTIFACT_PATHS['coverage-summary.json'])\n"
        "METRICS_DF.to_csv(PARSED_DIR / 'coverage_metrics.csv', index=False)\n"
        "METRICS_PAYLOAD = {\n"
        "    row['Metric']: {'json_field': row['JSON Field'], 'value': row['Value']}\n"
        "    for _, row in METRICS_DF.iterrows()\n"
        "}\n"
        "(PARSED_DIR / 'coverage_metrics.json').write_text(json.dumps(METRICS_PAYLOAD, indent=2), encoding='utf-8')\n"
        "display(METRICS_DF)"
    ),
    md("## 9. Validate Path Coverage Metric"),
    code(
        "PATH_VALIDATION = validate_path_coverage_metric(ARTIFACT_PATHS['coverage-summary.json'])\n"
        "(PARSED_DIR / 'path_coverage_validation.json').write_text(json.dumps(PATH_VALIDATION, indent=2), encoding='utf-8')\n"
        "display(pd.DataFrame([PATH_VALIDATION]))\n"
        "print(PATH_VALIDATION['path_coverage_statement'])\n"
        "print(PATH_VALIDATION['branch_coverage_note'])"
    ),
    md("## 10. Final Summary"),
    code(
        "REPORT_DF = build_final_report_table(PATH_VALIDATION)\n"
        "REPORT_DF.to_csv(REPORTS_DIR / 'final_metric_report.csv', index=False)\n"
        "REPORT_MARKDOWN = render_final_report_markdown(REPORT_DF, PATH_VALIDATION)\n"
        "(REPORTS_DIR / 'final_metric_report.md').write_text(REPORT_MARKDOWN, encoding='utf-8')\n\n"
        "OUTPUT_JSON_PATH = REPORTS_DIR / 'output.json'\n"
        "OUTPUT_PAYLOAD = build_output_json(\n"
        "    repo_path=REPO_PATH,\n"
        "    repo_validation=REPO_VALIDATION,\n"
        "    environment=ENVIRONMENT,\n"
        "    install_result=INSTALL_RESULT,\n"
        "    config_info=CONFIG_INFO,\n"
        "    execution=EXECUTION,\n"
        "    metrics_payload=METRICS_PAYLOAD,\n"
        "    path_validation=PATH_VALIDATION,\n"
        "    report_df=REPORT_DF,\n"
        "    artifact_paths=ARTIFACT_PATHS,\n"
        "    raw_dir=RAW_DIR,\n"
        "    elapsed_ms=(time.perf_counter() - PIPELINE_STARTED) * 1000,\n"
        ")\n"
        "save_output_json(OUTPUT_JSON_PATH, OUTPUT_PAYLOAD)\n"
        "print(f'Saved consolidated output JSON: {OUTPUT_JSON_PATH}')\n"
        "print(json.dumps(OUTPUT_PAYLOAD, indent=2))\n\n"
        "display(Markdown(REPORT_MARKDOWN))\n\n"
        "TOTAL_EXECUTION_TIME = round(time.perf_counter() - PIPELINE_STARTED, 2)\n"
        "print(f'Total notebook execution time (seconds): {TOTAL_EXECUTION_TIME}')\n\n"
        "deliverables = [\n"
        "    RAW_DIR / 'coverage-summary.json',\n"
        "    RAW_DIR / 'coverage-final.json',\n"
        "    RAW_DIR / 'vitest-console.log',\n"
        "    RAW_DIR / 'vitest-stdout.txt',\n"
        "    RAW_DIR / 'vitest-stderr.txt',\n"
        "    RAW_DIR / 'execution-metadata.json',\n"
        "    PARSED_DIR / 'coverage_metrics.csv',\n"
        "    REPORTS_DIR / 'output.json',\n"
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
        "│   ├── coverage-summary.json\n"
        "│   ├── coverage-final.json\n"
        "│   ├── coverage/\n"
        "│   ├── vitest-console.log\n"
        "│   ├── vitest-stdout.txt\n"
        "│   ├── vitest-stderr.txt\n"
        "│   └── execution-metadata.json\n"
        "├── parsed/\n"
        "│   ├── coverage_metrics.csv\n"
        "│   └── path_coverage_validation.json\n"
        "└── reports/\n"
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
