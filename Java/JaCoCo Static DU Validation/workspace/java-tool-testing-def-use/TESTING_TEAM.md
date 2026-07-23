# Testing Team — Def-Use Re-Verification (45 metrics)

## Steps

```bash
git clone https://github.com/visvantha-testable/java-tool-testing-def-use.git
cd java-tool-testing-def-use
mvn clean test
mvn -q -pl def-use-platform exec:java -Dexec.mainClass=com.testable.training.defuse.DefUseTrigger
mvn -q -pl def-use-platform exec:java -Dexec.mainClass=com.testable.training.defuse.DefUseJsonVerifierCli
```

Expected:

```
PASS: def_use.json has all 45 metrics (JaCoCo 33 + Static DU 12) covered=yes with 100/100 score
TRIGGER COMPLETE: def_use.json ready — all 45 metrics covered=yes 100/100
```

## Verify preserved outputs

| File | Metrics | Must exist |
|------|---------|------------|
| `jacoco.json` | 33 | yes |
| `static_du.json` | 12 | yes |
| `def_use.json` | 45 (merged) | yes |

## Inspect `def_use.json`

| Field | Expected |
|-------|----------|
| `tools` | `["JaCoCo", "static du"]` |
| `metrics_total` | `45` |
| `metrics_covered` | `45` |
| `jacoco_metrics_total` | `33` |
| `static_du_metrics_total` | `12` |
| `metric_coverage_complete` | `true` |
| `jacoco` | full JaCoCo payload embedded |
| `static_du` | full Static DU payload embedded |
