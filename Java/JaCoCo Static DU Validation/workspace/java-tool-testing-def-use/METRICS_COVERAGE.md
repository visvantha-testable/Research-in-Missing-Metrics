# Metrics Coverage — Def-Use Merged Repo

## JaCoCo (33 metrics) — see config/metric_coverage_jacoco.json

Control Flow, Coverage Delta, All Definition Coverage, All Uses Coverage, Code Churn.

## Static DU (12 metrics) — see config/metric_coverage_static_du.json

IDs 20–31: Duplicated lines (%), blocks, files, counts, density.

## Unified total: 45 metrics — all at 100/100

Merged in `def_use.json` without losing individual tool outputs.

## Taxonomy audit (32 Excel classification rows)

See **TAXONOMY_COVERAGE.md** and:

- `config/taxonomy_truth_table.csv` — Native vs Platform_Derived per metric
- `config/metric_coverage_action_plan.csv` — alternative tools and required data
- `config/taxonomy_trigger_manifest.json` — trigger steps and pipeline routing
- `config/repo_routing.csv` — repo per metric family

**Trigger:** `mvn -q -pl def-use-platform exec:java -Dexec.mainClass=com.testable.training.defuse.DefUseTrigger`
