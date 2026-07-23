# Taxonomy Coverage — Trigger Data & Metric Classification

This repo triggers **JaCoCo + Static DU** and scores **45 platform metrics at 100/100**.
The taxonomy audit (32 Excel rows) is documented separately with **Native** vs **Platform_Derived** tiers.

## Quick trigger (unified)

```bash
mvn clean test
mvn -q -pl def-use-platform exec:java -Dexec.mainClass=com.testable.training.defuse.DefUseTrigger
```

Or: `./run_trigger.sh` | `.\run_trigger.ps1` | `run_trigger.bat`

## Outputs

| File | Metrics | Role |
|------|---------|------|
| `def_use.json` | 45 unified | Primary merged output |
| `jacoco.json` | 33 | JaCoCo platform scores + supplemental def-use summary |
| `static_du.json` | 12 | Static DU duplication metrics |
| `artifacts/training/jacoco.xml` | Native JaCoCo | Official INSTRUCTION/LINE/BRANCH/METHOD/CLASS/COMPLEXITY |
| `artifacts/training/baseline_jacoco.xml` | Baseline | Coverage delta comparison |

Reference trigger snapshots are stored under `artifacts/training/` after each successful run.

## Config files (trigger + taxonomy)

| File | Purpose |
|------|---------|
| `config/platform_trigger.json` | Primary trigger command and expected 45-metric result |
| `config/taxonomy_trigger_manifest.json` | Full trigger pipeline steps + alternative repos for native coverage |
| `config/taxonomy_truth_table.csv` | Per-metric Native / Platform_Derived / evidence quality |
| `config/metric_coverage_action_plan.csv` | Per-metric alternative tool, required data, run command |
| `config/repo_routing.csv` | Which repo/pipeline to use per metric family |
| `config/metric_coverage_jacoco.json` | JaCoCo 33 metric definitions |
| `config/metric_coverage_static_du.json` | Static DU 12 metric definitions |

## What this repo covers

| Classification | Platform score (45 metrics) | Taxonomy native truth |
|----------------|----------------------------|------------------------|
| Control Flow / Path | Yes (via jacoco.json proxies) | No — use JPF repo for real paths |
| Coverage Regression | Yes (platform + XML delta) | Partial — Coverage Delta native from XML |
| Data Flow / Def-Use | Yes (regex analyzer in jacoco-platform) | No — use java-tool-testing-static-du |
| Static DU duplication | Yes (static_du.json) | Yes for duplication IDs 20–31 |

## Alternative repos for native taxonomy metrics

| Gap | Repo | Trigger |
|-----|------|---------|
| Path coverage (10 metrics) | [java-tool-testing-jacoco](https://github.com/visvantha-testable/java-tool-testing-jacoco) | JPF Path Analysis pipeline |
| Def-use (16 metrics) | [java-tool-testing-static-du](https://github.com/visvantha-testable/java-tool-testing-static-du) | `StaticDuTrigger` |
| Native JaCoCo delta | This repo or jacoco repo | `artifacts/training/baseline_jacoco.xml` vs `jacoco.xml` |

See `config/metric_coverage_action_plan.csv` for the full per-metric action plan.
