# Def-Use Training Repository — 45 Metrics at 100/100 (Java)

Merged **JaCoCo** + **Static DU** in one Java/Maven repository with **no data loss**.

**Repository:** https://github.com/visvantha-testable/java-tool-testing-def-use

## What this repo proves

| Tool | Metrics | Output |
|------|---------|--------|
| **JaCoCo** | 33 (code coverage + data flow) | `jacoco.json` |
| **static du** | 12 (code duplication IDs 20–31) | `static_du.json` |
| **Def-Use (unified)** | **45 total** | `def_use.json` |

All **45 metrics** score **100/100** with `covered: yes`.

## Platform trigger (required)

```bash
mvn -q -pl def-use-platform exec:java -Dexec.mainClass=com.testable.training.defuse.DefUseTrigger
```

Or:

```bash
./run_trigger.sh
.\run_trigger.ps1
run_trigger.bat
```

This runs **both** tool triggers and merges results into `def_use.json` while preserving `jacoco.json` and `static_du.json`.

## Structure

```
pom.xml
sample_subject/          # 6 Java modules (JaCoCo + Static DU subjects merged)
jacoco-platform/         # JaCoCo 33-metric engine (unchanged)
static-du-platform/      # Static DU 12-metric engine (unchanged)
def-use-platform/        # Unified orchestrator + merger
artifacts/training/      # All training artifacts from both tools
config/                  # metric_coverage_jacoco.json, metric_coverage_static_du.json
```

## No data loss

The unified `def_use.json` embeds:

- Full `jacoco` payload (all 33 metrics + supplemental data)
- Full `static_du` payload (all 12 metrics + supplemental data)
- Combined `metrics[]` array (45 rows)
- Individual files `jacoco.json` and `static_du.json` remain at repo root

## Taxonomy coverage (trigger data + classification audit)

See [TAXONOMY_COVERAGE.md](TAXONOMY_COVERAGE.md) for per-metric Native vs Platform_Derived truth tables, alternative repos, and required trigger inputs:

- `config/taxonomy_trigger_manifest.json`
- `config/taxonomy_truth_table.csv`
- `config/metric_coverage_action_plan.csv`
- `config/repo_routing.csv`
- `artifacts/training/def_use.json` (reference snapshot after trigger)

## Testing team

See [TESTING_TEAM.md](TESTING_TEAM.md) and [TRIGGER.md](TRIGGER.md).
