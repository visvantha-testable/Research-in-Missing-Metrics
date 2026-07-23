# Platform Trigger — Def-Use (JaCoCo + Static DU)

## Primary command

```bash
mvn -q -pl def-use-platform exec:java -Dexec.mainClass=com.testable.training.defuse.DefUseTrigger
```

## Pipeline

1. Runs **JaCoCo** trigger → `jacoco.json` (33 metrics)
2. Runs **Static DU** trigger → `static_du.json` (12 metrics)
3. Merges both → `def_use.json` (45 metrics, no data loss)

## Outputs

| File | Purpose |
|------|---------|
| `def_use.json` | Primary unified output (45 metrics) |
| `jacoco.json` | Preserved JaCoCo output (33 metrics) |
| `static_du.json` | Preserved Static DU output (12 metrics) |

## Expected result

```
TRIGGER COMPLETE: def_use.json ready — all 45 metrics covered=yes 100/100
```
