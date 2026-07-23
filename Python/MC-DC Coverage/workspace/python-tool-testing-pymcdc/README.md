# Python Tool Testing — pymcdc

Cyclomatic Complexity **Condition Coverage** metric validation using **pymcdc**, aligned with *Testable Strategy & Metrics Reference v3.0*.

## Tool + Metric

| Field | Value |
|-------|-------|
| **Tool** | [pymcdc](https://pypi.org/project/pymcdc/) |
| **Strategy** | Cyclomatic Complexity → Condition Coverage |
| **L5 Metric** | **Logical Sub-expression Validation** |
| **Training subject** | `sample_subject/logic.py` + `sample_subject/test_logic.py` (**100/100**) |
| **GitHub repo** | https://github.com/visvantha-testable/python-tool-testing-pymcdc |

## Metric definition

**Logical Sub-expression Validation** measures whether each individual component of a compound logical statement (e.g., in `if A and B`, checking `A` and `B` separately) has been evaluated as both **True** and **False** during MC/DC analysis.

## Platform trigger (REQUIRED — do not run static pymcdc alone)

**Run this command on Testable** (not `python -m pymcdc logic.py` without `--unittest`):

```bash
python pymcdc_trigger.py
```

Alternative:

```bash
python -m pymcdc_platform sample_subject/logic.py -o pymcdc.json
```

See **[TRIGGER.md](TRIGGER.md)** and `config/platform_trigger.json`.

## Primary output — single JSON file

**`pymcdc.json`** is the **one unified output file** the Testable platform should read. It contains:

| Section | What it includes |
|---------|------------------|
| `decisions[]` | MC/DC decision points with requirement tables |
| `summary` | 3 decisions, 11/11 requirements covered |
| `metrics[]` | Logical Sub-expression Validation with `"covered": "yes"` and `"score": 100` |
| `totals` | Platform-scaled ratio fields at 0-100 (prevents 1/100 FAIL) |
| `platform_scores` | Condition Coverage + Logical Sub-expression Validation = 100 |

Verify:

```powershell
python scripts/verify_pymcdc_json.py --pymcdc-json pymcdc.json
python -m pytest tests/ -q
```

Expected: **`PASS: pymcdc.json has Logical Sub-expression Validation covered=yes with 100/100 score`**

## Quick Start (100/100 certification)

```powershell
git clone https://github.com/visvantha-testable/python-tool-testing-pymcdc.git
cd python-tool-testing-pymcdc
python pymcdc_trigger.py
python validate_metric_coverage.py --metrics-json pymcdc_metrics.json
python scripts/verify_pymcdc_json.py
```

## Expected metrics (after pipeline)

| Metric | Expected value |
|--------|----------------|
| Decisions analyzed | 3 |
| MC/DC requirements | 11 |
| Requirements covered | 11 |
| Coverage percent | 100 |
| Logical Sub-expression Validation | **100/100 PASS** |

## Repository layout

```
python-tool-testing-pymcdc/
  sample_subject/logic.py          # Subject under test (compound logical decisions)
  sample_subject/test_logic.py     # Unittest suite achieving 100% MC/DC
  pymcdc_metrics.py                # Score derivation
  pymcdc_trigger.py                # One-shot platform trigger
  pymcdc_platform/                 # Testable wrapper CLI
  config/metric_coverage.json      # Machine-readable metric mapping
  pymcdc.json                      # PRIMARY platform output (root)
  TESTING_TEAM.md                  # QA verification guide
```

## Testing team

See **[TESTING_TEAM.md](TESTING_TEAM.md)** for step-by-step verification before platform submission.
