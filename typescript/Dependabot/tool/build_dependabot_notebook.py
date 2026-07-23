"""Generate dependabot_extraction.ipynb for TypeScript Dependabot validation."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "dependabot_extraction.ipynb"
UTILS_PATH = ROOT / "_dependabot_notebook_utils.py"

UTILS = UTILS_PATH.read_text(encoding="utf-8")


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "outputs": [], "source": source.splitlines(keepends=True)}


cells = [
    md(
        "# Extract Raw Dependabot Tool Output for a TypeScript Repository\n\n"
        "| Property | Value |\n"
        "| --- | --- |\n"
        "| Testing Type | Security White-box Testing |\n"
        "| Classification | Dependency Risk (SCA) |\n"
        "| Metric | Continuous Dependency Monitoring |\n"
        "| Capability | Real-Time Alerting |\n\n"
        "**Scope:** TypeScript · npm · GitHub Dependabot Alerts API only  \n"
        "**Cross-platform:** Windows · Linux · Google Colab  \n"
        "**Excluded tools:** npm audit · Snyk · CodeQL · OWASP Dependency Check · Trivy"
    ),
    md("## Step 1 — Clone Repository"),
    code(
        "USE_GIT_REPO = True\n"
        'REPO_URL = "https://github.com/visvantha-testable/typescript-tool-testing-dependabot.git"\n'
        'LOCAL_REPO = "/content/typescript-tool-testing-dependabot"\n'
        'GITHUB_TOKEN = "YOUR_GITHUB_PERSONAL_ACCESS_TOKEN"\n'
        'OWNER = "visvantha-testable"\n'
        'REPOSITORY = "typescript-tool-testing-dependabot"\n'
        'IF_CLONE_EXISTS = "reuse"\n'
    ),
    code(
        UTILS
        + "\n\n"
        "from pathlib import Path\n"
        "from IPython.display import display\n\n"
        "import sys, subprocess\n"
        "METRIC_ROOT = resolve_metric_root(Path('.').resolve())\n"
        "WORKSPACE_DIR = METRIC_ROOT / 'workspace'\n"
        "OUTPUT_PATH = METRIC_ROOT / 'outputs'\n"
        "ERROR_LOG_PATH = OUTPUT_PATH / 'error_log.txt'\n\n"
        "ensure_output_dir(OUTPUT_PATH)\n"
        "logger = NotebookLogger(ERROR_LOG_PATH)\n\n"
        "REQ = METRIC_ROOT / 'requirements.txt'\n"
        "if REQ.exists():\n"
        "    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', '-r', str(REQ)])\n\n"
        "LOCAL_REPO_PATH = Path(LOCAL_REPO)\n"
        "if USE_GIT_REPO:\n"
        "    REPO_PATH = resolve_repository_path(True, REPO_URL, LOCAL_REPO_PATH, WORKSPACE_DIR, IF_CLONE_EXISTS, logger)\n"
        "else:\n"
        "    REPO_PATH = resolve_repository_path(False, REPO_URL, LOCAL_REPO_PATH, WORKSPACE_DIR, IF_CLONE_EXISTS, logger)\n\n"
        "TS_VALIDATION = validate_typescript_project(REPO_PATH, logger)\n"
        "display(pd.DataFrame([TS_VALIDATION]))"
    ),
    md("## Step 2 — Install Dependencies"),
    code(
        "INSTALL_RESULT = install_npm_dependencies(REPO_PATH, logger)\n"
        "print(f\"Command: {INSTALL_RESULT['command']}\")\n"
        "print(f\"Return code: {INSTALL_RESULT['returncode']}\")\n"
        "print(f\"Elapsed ms: {INSTALL_RESULT['elapsed_ms']:.2f}\")\n"
        "print('--- stdout ---')\n"
        "print(INSTALL_RESULT['stdout'])\n"
        "print('--- stderr ---')\n"
        "print(INSTALL_RESULT['stderr'])"
    ),
    md("## Step 3 — Validate Dependabot Configuration"),
    code(
        "CONFIG_PATH = find_dependabot_config(REPO_PATH)\n"
        "DEPENDABOT_CONFIG_PRESENT = CONFIG_PATH is not None\n"
        "if not DEPENDABOT_CONFIG_PRESENT:\n"
        "    logger.error('Missing .github/dependabot.yml', file=str(REPO_PATH / '.github/dependabot.yml'))\n"
        "CONFIG_DF = parse_dependabot_configuration(CONFIG_PATH)\n"
        "CONFIG_CSV = OUTPUT_PATH / 'dependabot_configuration.csv'\n"
        "CONFIG_DF.to_csv(CONFIG_CSV, index=False)\n"
        "display(CONFIG_DF)"
    ),
    md("## Step 4 — Authenticate with GitHub"),
    code(
        "import os\n"
        "EFFECTIVE_TOKEN = GITHUB_TOKEN or os.environ.get('GITHUB_TOKEN', '')\n"
        "TOKEN_VALIDATION = validate_github_token(OWNER, REPOSITORY, EFFECTIVE_TOKEN, logger)\n"
        "display(pd.DataFrame([TOKEN_VALIDATION]))\n\n"
        "AUTH_OK = github_authentication_ok(TOKEN_VALIDATION)\n"
        "RAW_PAYLOAD = empty_raw_payload(OWNER, REPOSITORY)\n"
        "API_FETCH_OK = False\n"
        "if AUTH_OK:\n"
        "    print('GitHub authentication successful.')\n"
        "else:\n"
        "    try:\n"
        "        require_github_authentication(TOKEN_VALIDATION, logger)\n"
        "    except AuthenticationFailedError as exc:\n"
        "        print(f'AUTHENTICATION FAILED: {exc}')\n"
        "        print('Stopping Dependabot API execution. Remaining steps will record FAIL status.')"
    ),
    md(
        "## Step 5 — Execute Dependabot\n\n"
        "`GET /repos/visvantha-testable/typescript-tool-testing-dependabot/dependabot/alerts`"
    ),
    code(
        "if AUTH_OK:\n"
        "    RAW_PAYLOAD = fetch_dependabot_alerts_raw(OWNER, REPOSITORY, EFFECTIVE_TOKEN, logger)\n"
        "    API_FETCH_OK = bool(RAW_PAYLOAD.get('api_success'))\n"
        "    print(f'API success: {API_FETCH_OK}')\n"
        "    print(f\"Pages retrieved: {RAW_PAYLOAD.get('page_count', 0)}\")\n"
        "else:\n"
        "    print('Skipped: authentication failed.')"
    ),
    md("## Step 6 — Preserve Raw Tool Output"),
    code(
        "RAW_JSON_PATH = OUTPUT_PATH / 'dependabot_alerts_raw.json'\n"
        "save_dependabot_alerts_raw(RAW_PAYLOAD, RAW_JSON_PATH)\n"
        "print(f'Saved raw Dependabot output: {RAW_JSON_PATH}')"
    ),
    md("## Step 7 — Extract Alert Information"),
    code(
        "ALERTS = load_alerts_from_raw(RAW_PAYLOAD) if API_FETCH_OK else []\n"
        "if API_FETCH_OK and not ALERTS:\n"
        "    logger.error('Dependabot Alerts API returned an empty alert response.', file='dependabot_alerts')\n"
        "ALERTS_DF = parse_dependabot_alerts(ALERTS)\n"
        "ALERTS_CSV = OUTPUT_PATH / 'dependabot_alerts.csv'\n"
        "ALERTS_DF.to_csv(ALERTS_CSV, index=False)\n"
        "display(ALERTS_DF)"
    ),
    md("## Step 8 — Validate White-box Metric"),
    code(
        "ALERT_SUMMARY = summarize_alerts(ALERTS_DF)\n"
        "LIVE_ALERTS_RECEIVED = API_FETCH_OK and ALERT_SUMMARY['total_alerts'] > 0\n"
        "METRIC_VALIDATION_DF = build_security_metric_validation(\n"
        "    dependabot_config_present=DEPENDABOT_CONFIG_PRESENT,\n"
        "    api_fetch_ok=API_FETCH_OK,\n"
        "    live_alerts_received=LIVE_ALERTS_RECEIVED,\n"
        "    alert_summary=ALERT_SUMMARY,\n"
        ")\n"
        "METRIC_CSV = OUTPUT_PATH / 'security_metric_validation.csv'\n"
        "METRIC_VALIDATION_DF.to_csv(METRIC_CSV, index=False)\n"
        "display(METRIC_VALIDATION_DF)"
    ),
    md("## Step 9 — Repository Dashboard"),
    code(
        "TOTAL_DEPENDENCIES = count_npm_dependencies(REPO_PATH)\n"
        "DASHBOARD_DF = build_dashboard_summary(\n"
        "    repository_name=REPO_PATH.name,\n"
        "    package_manager='npm',\n"
        "    total_dependencies=TOTAL_DEPENDENCIES,\n"
        "    alert_summary=ALERT_SUMMARY,\n"
        "    live_alerts_received=LIVE_ALERTS_RECEIVED,\n"
        ")\n"
        "DASHBOARD_CSV = OUTPUT_PATH / 'dashboard_summary.csv'\n"
        "DASHBOARD_DF.to_csv(DASHBOARD_CSV, index=False)\n"
        "display(DASHBOARD_DF)"
    ),
    md("## Step 10 — Error Handling and Deliverables"),
    code(
        "logger.write_errors()\n"
        "deliverables = [RAW_JSON_PATH, ALERTS_CSV, CONFIG_CSV, METRIC_CSV, DASHBOARD_CSV, ERROR_LOG_PATH]\n"
        "print('Deliverables:')\n"
        "for path in deliverables:\n"
        "    print(f\"  [{'OK' if path.exists() else 'MISSING'}] {path}\")\n"
        "if ERROR_LOG_PATH.exists() and ERROR_LOG_PATH.stat().st_size > 0:\n"
        "    print('\\n--- error_log.txt ---')\n"
        "    print(ERROR_LOG_PATH.read_text(encoding='utf-8'))"
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

print(f"Wrote {NOTEBOOK}")
