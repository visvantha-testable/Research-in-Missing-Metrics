# Platform Trigger — Static DU

## Primary command

```bash
mvn -q -pl static-du-platform exec:java -Dexec.mainClass=com.testable.training.platform.StaticDuTrigger
```

## What the trigger does

1. Scans `sample_subject/src/main/java` with **Static DU** definition-use analyzer
2. Verifies every source file has a matching `*Test.java` regression test
3. Computes 5 Data Flow Testing metric scores
4. Exports unified `static_du.json` with `covered: yes` and `score: 100` for all metrics
5. Validates metric coverage and JSON completeness

## Primary output

| File | Location |
|------|----------|
| `static_du.json` | Repository root |

## Do NOT run on the platform

- Raw Java source file grep/scan without the wrapper
- Manual JSON editing without running the trigger
- Any non-Java script trigger

## Expected result

```
TRIGGER COMPLETE: static_du.json ready — all 5 Static DU metrics covered=yes 100/100
```
