"""Generate vitest_exception_path_validation.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "vitest_exception_path_validation.ipynb"
UTILS = (ROOT / "_vitest_exception_path_utils.py").read_text(encoding="utf-8")


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "outputs": [], "source": source.splitlines(keepends=True)}


cells = [
    md(
        "# Vitest + @vitest/coverage-v8 — Exception Path Handling Validation\n\n"
        "| Property | Value |\n"
        "| --- | --- |\n"
        "| Repository | [typescript-tool-testing-knip](https://github.com/visvantha-testable/typescript-tool-testing-knip) |\n"
        "| Language | TypeScript |\n"
        "| Tool | Vitest + `@vitest/coverage-v8` |\n"
        "| Technique | Control Flow Testing |\n"
        "| Classification | Path Coverage |\n"
        "| Metric | Exception Path Handling |\n"
        "| KPI | Error Flow Verification |\n\n"
        "**Definition:** Measures the code's ability to gracefully handle and recover from unexpected "
        "errors or try-catch blocks, ensuring the system does not crash when forced into a failure state.\n\n"
        "> Raw runtime output is preserved verbatim. Metrics are extracted only from values present in "
        "coverage-summary.json, coverage-final.json, Vitest stdout, and Vitest stderr."
    ),
    md("## Step 1 — Clone Repository"),
    code(
        "USE_GIT_REPO = True\n"
        'REPO_URL = "https://github.com/visvantha-testable/typescript-tool-testing-knip.git"\n'
        'LOCAL_REPO = "./workspace/typescript-tool-testing-knip"\n'
        'IF_CLONE_EXISTS = "reuse"\n'
        "CLONE_DEPTH = 1\n"
    ),
    md("## Step 2 — Collect Environment Information"),
    code(
        "import subprocess\n"
        "import sys\n\n"
        "subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', '-r', 'requirements.txt'])"
    ),
    md("## Step 3 — Install Dependencies"),
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
        "REPO_INFO = display_repository_info(REPO_PATH)\n"
        "print('Current directory:', REPO_INFO['current_directory'])\n"
        "print('Repository name:', REPO_INFO['repository_name'])\n"
        "print('Current Git commit hash:', REPO_INFO['commit_hash'])\n\n"
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
        "INSTALL_RESULT = install_project_dependencies(REPO_PATH, PACKAGE_MANAGER, logger)\n"
        "print(f\"Command: {INSTALL_RESULT['command']}\")\n"
        "print(f\"Return code: {INSTALL_RESULT['returncode']}\")\n"
        "print(f\"Elapsed ms: {INSTALL_RESULT['elapsed_ms']:.2f}\")\n"
        "if INSTALL_RESULT['returncode'] != 0:\n"
        "    raise RuntimeError(f'{PACKAGE_MANAGER} install failed.')"
    ),
    md("## Step 4 — Verify Tool Installation"),
    code(
        "VITEST_PACKAGES_DF = install_vitest_packages(REPO_PATH, PACKAGE_MANAGER, logger)\n"
        "display(VITEST_PACKAGES_DF)\n"
        "if (VITEST_PACKAGES_DF['status'] != 'OK').any():\n"
        "    raise RuntimeError('Required Vitest packages are not installed.')\n\n"
        "ENVIRONMENT = collect_environment_details(REPO_PATH, PACKAGE_MANAGER, logger)\n"
        "ENVIRONMENT_PATH = REPORTS_DIR / 'environment.json'\n"
        "ENVIRONMENT_PATH.write_text(json.dumps(ENVIRONMENT, indent=2), encoding='utf-8')\n"
        "display(pd.DataFrame([ENVIRONMENT]))"
    ),
    md("## Step 5 — Execute Tests"),
    code(
        "CONFIG_PATH = detect_vitest_config(REPO_PATH)\n"
        "print('Repository Vitest config:', CONFIG_PATH if CONFIG_PATH else 'not found')\n\n"
        "EXECUTION = execute_vitest_coverage(REPO_PATH, PACKAGE_MANAGER, logger)\n"
        "print(f\"Command: {EXECUTION['command']}\")\n"
        "print(f\"Return code: {EXECUTION['returncode']}\")\n"
        "print(f\"Elapsed ms: {EXECUTION['elapsed_ms']:.2f}\")\n"
        "print('--- stdout ---')\n"
        "print(EXECUTION['stdout'])\n"
        "print('--- stderr ---')\n"
        "print(EXECUTION['stderr'])\n"
        "if EXECUTION['returncode'] != 0:\n"
        "    raise RuntimeError('Vitest test execution failed.')"
    ),
    md("## Step 6 — Collect Raw Coverage Artifacts"),
    code(
        "write_text_verbatim(RAW_DIR / 'vitest_stdout.txt', EXECUTION['stdout'])\n"
        "write_text_verbatim(RAW_DIR / 'vitest_stderr.txt', EXECUTION['stderr'])\n"
        "EXECUTION_PATH = save_execution_report(REPORTS_DIR, EXECUTION, ENVIRONMENT)\n\n"
        "COVERAGE_DIR = locate_coverage_output_dir(REPO_PATH, CONFIG_PATH)\n"
        "SAVED = preserve_raw_coverage_artifacts(COVERAGE_DIR, RAW_DIR)\n"
        "ARTIFACT_PATHS = require_coverage_artifacts(RAW_DIR, logger)\n\n"
        "print(f'Saved execution metadata: {EXECUTION_PATH}')\n"
        "print('Saved raw artifacts:')\n"
        "for path in sorted(set(SAVED['files'])):\n"
        "    print(f'  {path}')\n"
        "if SAVED['missing_optional']:\n"
        "    print('Optional artifacts not generated by repository configuration:')\n"
        "    for name in SAVED['missing_optional']:\n"
        "        print(f'  - {name}')"
    ),
    md("## Step 7 — Display Raw Output"),
    code(
        "SUMMARY_RAW_TEXT = read_raw_json_text(ARTIFACT_PATHS['coverage-summary.json'])\n"
        "FINAL_RAW_TEXT = read_raw_json_text(ARTIFACT_PATHS['coverage-final.json'])\n"
        "TAXONOMY_METRICS_PATH = RAW_DIR / 'taxonomy_metrics.json'\n"
        "TAXONOMY_METRICS = load_taxonomy_metrics(TAXONOMY_METRICS_PATH)\n"
        "TAXONOMY_RAW_TEXT = read_raw_json_text(TAXONOMY_METRICS_PATH) if TAXONOMY_METRICS_PATH.exists() else ''\n\n"
        "print('===== coverage-summary.json (verbatim) =====')\n"
        "print(SUMMARY_RAW_TEXT)\n"
        "print('\\n===== coverage-final.json (verbatim) =====')\n"
        "print(FINAL_RAW_TEXT)\n"
        "print('\\n===== taxonomy_metrics.json (verbatim) =====')\n"
        "print(TAXONOMY_RAW_TEXT or 'taxonomy_metrics.json was not generated. Re-run npm run coverage in the repository.')"
    ),
    md("## Step 8 — Extract Runtime Coverage Metrics"),
    code(
        "RUNTIME_METRICS = build_runtime_metrics_json(ARTIFACT_PATHS['coverage-summary.json'])\n"
        "RUNTIME_METRICS_PATH = REPORTS_DIR / 'runtime_metrics.json'\n"
        "RUNTIME_METRICS_PATH.write_text(json.dumps(RUNTIME_METRICS, indent=2), encoding='utf-8')\n"
        "display(pd.DataFrame([\n"
        "    {'Metric': key, 'JSON Field': value['json_field'], 'Value': value['value']}\n"
        "    for key, value in RUNTIME_METRICS.items()\n"
        "]))\n"
        "print(f'Saved runtime metrics: {RUNTIME_METRICS_PATH}')"
    ),
    md("## Step 9 — Exception Path Evidence Extraction"),
    code(
        "RUNTIME_CONTEXT = build_runtime_context(\n"
        "    EXECUTION['stdout'],\n"
        "    EXECUTION['stderr'],\n"
        "    ARTIFACT_PATHS['coverage-summary.json'],\n"
        "    ARTIFACT_PATHS['coverage-final.json'],\n"
        "    TAXONOMY_METRICS,\n"
        ")\n"
        "EVIDENCE_DF = extract_exception_path_evidence(RUNTIME_CONTEXT)\n"
        "display(EVIDENCE_DF)"
    ),
    md("## Step 10 — Taxonomy Validation"),
    code(
        "TAXONOMY_DF = validate_taxonomy_levels(RUNTIME_CONTEXT)\n"
        "TAXONOMY_PATH = REPORTS_DIR / 'taxonomy_validation.json'\n"
        "TAXONOMY_PATH.write_text(json.dumps(TAXONOMY_DF.to_dict(orient='records'), indent=2), encoding='utf-8')\n"
        "display(TAXONOMY_DF)\n"
        "print(f'Saved taxonomy validation: {TAXONOMY_PATH}')"
    ),
    md("## Step 11 — Generate Final Validation Table"),
    code(
        "TAXONOMY_MARKDOWN = render_taxonomy_markdown_table(TAXONOMY_DF)\n"
        "display(Markdown(TAXONOMY_MARKDOWN))"
    ),
    md("## Step 12 — Generate Final Assessment"),
    code(
        "FINAL_ASSESSMENT = render_final_assessment(\n"
        "    EXECUTION,\n"
        "    RUNTIME_METRICS,\n"
        "    EVIDENCE_DF,\n"
        "    TAXONOMY_DF,\n"
        "    SAVED,\n"
        "    TAXONOMY_METRICS,\n"
        ")\n"
        "(REPORTS_DIR / 'final_assessment.md').write_text(FINAL_ASSESSMENT, encoding='utf-8')\n"
        "display(Markdown(FINAL_ASSESSMENT))\n\n"
        "TOTAL_EXECUTION_TIME = round(time.perf_counter() - PIPELINE_STARTED, 2)\n"
        "print(f'Total notebook execution time (seconds): {TOTAL_EXECUTION_TIME}')\n\n"
        "deliverables = [\n"
        "    ARTIFACT_PATHS['coverage-summary.json'],\n"
        "    ARTIFACT_PATHS['coverage-final.json'],\n"
        "    RAW_DIR / 'vitest_stdout.txt',\n"
        "    RAW_DIR / 'vitest_stderr.txt',\n"
        "    ENVIRONMENT_PATH,\n"
        "    EXECUTION_PATH,\n"
        "    RUNTIME_METRICS_PATH,\n"
        "    TAXONOMY_PATH,\n"
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
        "│   ├── taxonomy_metrics.json\n"
        "│   ├── coverage/\n"
        "│   ├── vitest_stdout.txt\n"
        "│   └── vitest_stderr.txt\n"
        "└── reports/\n"
        "    ├── environment.json\n"
        "    ├── execution.json\n"
        "    ├── runtime_metrics.json\n"
        "    └── taxonomy_validation.json\n"
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
