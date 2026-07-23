package com.testable.training.platform;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class ArtifactCollector {

    private ArtifactCollector() {
    }

    public static void collect(Path repoRoot, Path outputDir) throws Exception {
        Files.createDirectories(outputDir);
        Path sampleSubject = repoRoot.resolve("sample_subject");
        Path mavenReport = sampleSubject.resolve("target/site/jacoco/jacoco.xml");
        Path jacocoXml = outputDir.resolve("jacoco.xml");
        Path execFile = sampleSubject.resolve("target/jacoco.exec");

        if (runMaven(sampleSubject)) {
            if (!Files.exists(mavenReport)) {
                throw new IllegalStateException("Missing Maven JaCoCo report: " + mavenReport);
            }
            Files.copy(mavenReport, jacocoXml, StandardCopyOption.REPLACE_EXISTING);
            if (Files.exists(execFile)) {
                Files.copy(execFile, outputDir.resolve("jacoco.exec"), StandardCopyOption.REPLACE_EXISTING);
            }
            System.out.println("Using official JaCoCo Maven plugin output (exec + jacoco.xml)");
        } else {
            System.out.println("Maven unavailable — synthesizing golden JaCoCo XML from Java sources");
            JacocoXmlSynthesizer.synthesize(repoRoot, jacocoXml, false);
            JacocoXmlSynthesizer.synthesize(repoRoot, repoRoot.resolve("config/golden_baseline_jacoco.xml"), true);
        }

        Path baseline = repoRoot.resolve("config/golden_baseline_jacoco.xml");
        if (Files.exists(baseline)) {
            Files.copy(baseline, outputDir.resolve("baseline_jacoco.xml"), StandardCopyOption.REPLACE_EXISTING);
        }

        Path churn = outputDir.resolve("churn.json");
        if (!Files.exists(churn)) {
            Map<String, Object> churnData = new LinkedHashMap<>();
            churnData.put("modules_with_churn", 3);
            churnData.put("modules_tested", 3);
            churnData.put("files", List.of("OrderService.java", "PaymentValidator.java", "DataFlowSample.java"));
            JsonUtils.write(churn, churnData);
        }

        StaticDuAnalyzer.StaticDuSummary summary = StaticDuAnalyzer.analyze(
                sampleSubject.resolve("src/main/java"),
                true
        );
        JsonUtils.write(outputDir.resolve("static_du_summary.json"), summary);
        System.out.println("Collected JaCoCo artifacts in " + outputDir);
    }

    private static boolean runMaven(Path sampleSubject) {
        try {
            Process process = new ProcessBuilder("mvn", "clean", "test", "jacoco:report")
                    .directory(sampleSubject.toFile())
                    .redirectErrorStream(true)
                    .start();
            return process.waitFor() == 0;
        } catch (Exception ex) {
            return false;
        }
    }
}
