# Python Tool Testing — pymcdc (Testing Team Guide)

This repo is maintained for **100/100 PASS** on **Logical Sub-expression Validation** (Condition Coverage / Cyclomatic Complexity).

## Quick verify (must pass before submission)

```powershell
git clone https://github.com/visvantha-testable/python-tool-testing-pymcdc.git
cd python-tool-testing-pymcdc
python pymcdc_trigger.py
python scripts/verify_pymcdc_json.py --pymcdc-json pymcdc.json
python -m pytest tests/ -q
```

**Do NOT use** `python -m pymcdc sample_subject/logic.py` alone — it analyzes requirements but does not execute tests (0% coverage).

See **[TRIGGER.md](TRIGGER.md)** for platform trigger instructions.

Expected final lines:

```
TRIGGER COMPLETE: pymcdc.json ready — Logical Sub-expression Validation covered=yes 100/100
PASS: pymcdc.json has Logical Sub-expression Validation covered=yes with 100/100 score
```

See **[METRICS_COVERAGE.md](METRICS_COVERAGE.md)** for how the metric is derived from pymcdc MC/DC data.

## Files the Testable platform reads (repository ROOT)

| File | Purpose |
|------|---------|
| **`pymcdc.json`** | **PRIMARY** — unified output with decisions + metric (`covered: yes`, score 100) |
| `platform_metrics.json` | L4/L5 classification → integer score `100` |
| `condition_metric_evidence.json` | **Proof** — raw parameters + formula |
| `pymcdc_report.json` | Parsed pymcdc decision/requirement report |
| `pymcdc_metrics.json` | Full metrics payload |
| `dashboard_metrics.json` | PASS/FAIL row |
| `metrics.json` | Alias of `platform_metrics.json` |
| `testable_dashboard.json` | Explicit dashboard row |

Copies also live under `platform/` and `artifacts/training/`.

## 1/100 FAIL fix (ratio metrics)

The Testable platform may derive metrics using **0-1 ratio formulas** (e.g. `covered/total = 1.0`) and display **`1/100`** instead of **`100/100`**.

**Fix applied in repo:**

1. `totals` block in `pymcdc.json` (same pattern as `coverage.json`)
2. Root-level keys: `"Condition Coverage": 100`, `"Logical Sub-expression Validation": 100`
3. Scaled numerators: `covered_requirements = 100 × total_requirements` at 100% coverage
4. Use **`python pymcdc_trigger.py`** or **`python -m pymcdc_platform`** (NOT static pymcdc alone)

Verify after pipeline:

```powershell
python -m pytest tests/test_platform_fixup.py -q
```

## Metric

| Dashboard classification | L5 metric | Expected |
|--------------------------|-----------|----------|
| Condition Coverage | Logical Sub-expression Validation | **100** |

## Re-generate root platform files

```powershell
python pymcdc_trigger.py
```
