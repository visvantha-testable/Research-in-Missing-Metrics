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
        Path summaryPath = repoRoot.resolve("artifacts/training/static_du_summary.json");
        if (!Files.exists(summaryPath)) {
            errors.add("missing artifacts/training/static_du_summary.json");
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
        } else if (Files.exists(summaryPath)) {
            scores = StaticDuMetricsEngine.compute(
                    StaticDuAnalyzer.DuplicationSummary.fromMap(JsonUtils.readMap(summaryPath))
            ).normalizedScores();
        } else {
            errors.add("cannot compute scores without static_du_summary.json");
            scores = Map.of();
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

        System.out.println("All " + MetricDefinition.ALL.length + " Static DU metrics are covered with 100/100 scores.");
        return 0;
    }
}
