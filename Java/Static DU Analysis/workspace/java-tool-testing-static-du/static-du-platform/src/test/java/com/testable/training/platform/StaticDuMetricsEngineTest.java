package com.testable.training.platform;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class StaticDuMetricsEngineTest {

    @Test
    void perfectScoreWhenAllDuPairsCovered() {
        StaticDuAnalyzer.StaticDuSummary summary = new StaticDuAnalyzer.StaticDuSummary(
                10, 10, 35, 35, 7, 7, 28, 28, 7, 7,
                0, 0, 0, 0, 2,
                java.util.List.of("DataFlowSample.java", "OrderService.java", "PaymentValidator.java"),
                java.util.List.of()
        );
        StaticDuMetricsEngine.StaticDuDashboardMetrics metrics = StaticDuMetricsEngine.compute(summary);
        assertEquals(100.0, metrics.normalizedScores().get("Variable Definition Detection"));
        assertEquals(100.0, metrics.normalizedScores().get("Definition-Use Mapping"));
        assertEquals(100.0, metrics.normalizedScores().get("Coverage Measurement"));
        assertEquals(100.0, metrics.normalizedScores().get("Uncovered Definition Detection"));
        assertEquals(100.0, metrics.normalizedScores().get("Variable Use Detection"));
    }
}
