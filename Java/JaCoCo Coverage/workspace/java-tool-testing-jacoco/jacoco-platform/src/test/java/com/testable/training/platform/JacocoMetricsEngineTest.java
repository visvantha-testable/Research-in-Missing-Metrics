package com.testable.training.platform;

import org.junit.jupiter.api.Test;

import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class JacocoMetricsEngineTest {

    @Test
    void metricDefinitionsCountIs33() {
        assertEquals(33, MetricDefinition.ALL.length);
    }

    @Test
    void goldenJacocoXmlScores100() throws Exception {
        Path repoRoot = Path.of("").toAbsolutePath();
        while (repoRoot != null && !repoRoot.resolve("sample_subject").toFile().exists()) {
            repoRoot = repoRoot.getParent();
        }
        if (repoRoot == null) {
            return;
        }

        Path training = repoRoot.resolve("artifacts/training");
        if (!training.resolve("jacoco.xml").toFile().exists()) {
            ArtifactCollector.collect(repoRoot, training);
        }

        JacocoCounters current = JacocoXmlParser.parse(training.resolve("jacoco.xml"));
        JacocoCounters baseline = JacocoXmlParser.parse(training.resolve("baseline_jacoco.xml"));
        StaticDuAnalyzer.StaticDuSummary du = StaticDuAnalyzer.analyze(
                repoRoot.resolve("sample_subject/src/main/java"),
                current.lineMissed == 0
        );
        JacocoDashboardMetrics metrics = JacocoDashboardMetrics.compute(current, baseline, du, 3, 3);
        assertTrue(metrics.normalizedScores().values().stream().allMatch(v -> v >= 100.0));
    }
}
