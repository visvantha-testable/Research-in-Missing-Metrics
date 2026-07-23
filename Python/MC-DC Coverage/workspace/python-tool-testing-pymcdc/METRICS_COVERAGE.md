# pymcdc — Logical Sub-expression Validation (1/1)

This document proves the **Logical Sub-expression Validation** dashboard metric is covered, derived, and scored **100/100** in this training repo.

## Important: static pymcdc does NOT emit execution coverage

Static analysis only lists MC/DC requirements:

```
python -m pymcdc sample_subject/logic.py
```

**Scores out of 100** are produced only after unittest execution:

```
sample_subject/logic.py  ──► pymcdc static analysis (.mdc log)
sample_subject/test_logic.py ──► pymcdc --unittest (records covered requirements)
        └──► pymcdc_metrics.py ──► platform_metrics.json (score 100)
```

## Metric coverage matrix

| # | L3 Strategy | L4 Classification | L5 Metric | pymcdc native? | Required artifact | Score formula |
|---|-------------|-------------------|-----------|----------------|-------------------|---------------|
| 1 | Cyclomatic Complexity | Condition Coverage | Logical Sub-expression Validation | Yes | `artifacts/training/logic.py.mdc` | `100 * covered_requirements / total_requirements` |

Machine-readable mapping: **`config/metric_coverage.json`**

## Raw parameters

| Parameter | Training value | Meaning |
|-----------|----------------|---------|
| `decision_count` | 3 | Compound logical decisions in `logic.py` |
| `total_requirements` | 11 | MC/DC requirement rows |
| `covered_requirements` | 11 | Requirements satisfied by unittest execution |
| `coverage_percent` | 100 | Percent covered |
| `subexpression_true_evaluations` | (derived) | True evaluations per sub-expression |
| `subexpression_false_evaluations` | (derived) | False evaluations per sub-expression |
| `short_circuit_irrelevant_slots` | (derived) | `----` cells from Python short-circuiting |

## Training subject decisions

| Function | Decision | Conditions |
|----------|----------|------------|
| `evaluate_access` | `user_active and has_permission and session_valid` | 3 AND |
| `evaluate_alert` | `level_high or threshold_exceeded` | 2 OR |
| `evaluate_mixed` | `(flag_a and flag_b) or flag_c` | mixed AND/OR |

## Platform files (repository ROOT)

| File | Purpose |
|------|---------|
| `pymcdc.json` | PRIMARY unified output |
| `platform_metrics.json` | Integer score 100 |
| `condition_metric_evidence.json` | Raw parameters + formula proof |
| `pymcdc_report.json` | Parsed decision tables |

## Verification

```powershell
python pymcdc_trigger.py
python scripts/verify_pymcdc_json.py
python validate_metric_coverage.py --metrics-json pymcdc_metrics.json
```

Expected: **11/11 requirements covered (100%)**
