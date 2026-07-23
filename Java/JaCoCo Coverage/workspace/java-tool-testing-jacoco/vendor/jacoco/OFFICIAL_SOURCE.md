# Official JaCoCo Source Reference

This training repository integrates the **official JaCoCo library** from:

**https://github.com/jacoco/jacoco**

| Item | Value |
|------|-------|
| Official repo | [jacoco/jacoco](https://github.com/jacoco/jacoco) |
| Release used | **0.8.15** |
| Maven core | `org.jacoco:org.jacoco.core` |
| Maven plugin | `org.jacoco:jacoco-maven-plugin` |
| Documentation | https://www.jacoco.org/jacoco |

## How this repo uses official JaCoCo

1. **`sample_subject/`** — official `jacoco-maven-plugin` (prepare-agent, report, check)
2. **`OfficialJacocoAnalyzer.java`** — uses official Core API (`ExecFileLoader`, `Analyzer`, `CoverageBuilder`) based on:
   - `org.jacoco.examples.ReportGenerator`
   - `org.jacoco.examples.CoreTutorial`
3. **`jacoco.exec` + compiled classes** — primary coverage source (official runtime data)
4. **`jacoco.xml`** — Maven report output / synthesis fallback

## Not a fork

This repo is a **Testable training wrapper** around official JaCoCo. It does not replace or redistribute the full jacoco/jacoco source tree. It consumes official JaCoCo from Maven Central.
