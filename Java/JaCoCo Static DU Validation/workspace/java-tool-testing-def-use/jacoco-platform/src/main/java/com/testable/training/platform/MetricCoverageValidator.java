package com.testable.training.platform;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public final class MetricCoverageValidator {

    private MetricCoverageValidator() {
    }

    public static int validate(Path repoRoot, Path metricsJson) throws Exception {
        List<String> errors = new ArrayList<>();
        Path jacocoXml = repoRoot.resolve("artifacts/training/jacoco.xml");
        if (!Files.exists(jacocoXml)) {
            errors.add("missing artifacts/training/jacoco.xml");
        }

        Map<String, Double> scores;
        if (metricsJson != null && Files.exists(metricsJson)) {
            @SuppressWarnings("unchecked")
            Map<String, Object> payload = JsonUtils.readMap(metricsJson);
            @SuppressWarnings("unchecked")
            Map<String, Object> normalized = (Map<String, Object>) payload.get("normalized_scores");
            scores = new java.util.LinkedHashMap<>();
            if (normalized != null) {
                normalized.forEach((k, v) -> scores.put(k, ((Number) v).doubleValue()));
            }
        } else {
            JacocoCounters current = JacocoCoverageLoader.load(jacocoXml, repoRoot);
            JacocoCounters baseline = JacocoXmlParser.parse(repoRoot.resolve("config/golden_baseline_jacoco.xml"));
            StaticDuAnalyzer.StaticDuSummary du = StaticDuAnalyzer.analyze(
                    repoRoot.resolve("sample_subject/src/main/java"),
                    true
            );
            scores = JacocoDashboardMetrics.compute(current, baseline, du, 3, 3).normalizedScores();
        }

        for (MetricDefinition def : MetricDefinition.ALL) {
            Double score = scores.get(def.key());
            if (score == null) {
                errors.add(def.key() + ": missing normalized score");
            } else if (score < 100.0) {
                errors.add(def.key() + ": score " + score + " is below 100/100");
            }
        }

        if (!errors.isEmpty()) {
            System.err.println("Metric coverage validation failed:");
            errors.forEach(err -> System.err.println("  - " + err));
            return 1;
        }

        System.out.println("All " + MetricDefinition.ALL.length + " JaCoCo metrics are covered with 100/100 scores.");
        return 0;
    }
}
