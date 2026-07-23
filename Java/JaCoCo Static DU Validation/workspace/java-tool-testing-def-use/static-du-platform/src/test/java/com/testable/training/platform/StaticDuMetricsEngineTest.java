package com.testable.training.platform;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class StaticDuMetricsEngineTest {

    @Test
    void perfectScoreWhenZeroDuplication() {
        StaticDuAnalyzer.DuplicationSummary summary = new StaticDuAnalyzer.DuplicationSummary(
                120, 0, 0.0, 0, 0, 0, 0, 0, 0.0, 0.0, 0, 0, 0,
                java.util.List.of("InventoryService.java", "PricingEngine.java", "ShipmentTracker.java"),
                java.util.List.of()
        );
        StaticDuMetricsEngine.StaticDuDashboardMetrics metrics = StaticDuMetricsEngine.compute(summary);
        assertEquals(12, metrics.normalizedScores().size());
        metrics.normalizedScores().values().forEach(score -> assertEquals(100.0, score));
    }

    @Test
    void densityPenaltyReducesScore() {
        assertEquals(90.0, StaticDuMetricsEngine.scoreFromDensity(10.0));
        assertEquals(100.0, StaticDuMetricsEngine.scoreFromCount(0));
        assertEquals(95.0, StaticDuMetricsEngine.scoreFromCount(1));
    }
}
