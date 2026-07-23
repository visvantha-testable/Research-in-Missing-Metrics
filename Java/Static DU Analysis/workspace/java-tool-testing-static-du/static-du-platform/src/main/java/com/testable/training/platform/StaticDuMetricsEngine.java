package com.testable.training.platform;

import java.util.LinkedHashMap;
import java.util.Map;

public final class StaticDuMetricsEngine {

    private StaticDuMetricsEngine() {
    }

    public static StaticDuDashboardMetrics compute(StaticDuAnalyzer.StaticDuSummary du) {
        double allDefs = round(du.allDefsPercent());
        double allUses = round(du.allUsesPercent());
        double duPath = round(du.duPathPercent());
        double dataPath = round(du.dataPathCorrelationPercent());
        double deadData = round(du.uncoveredDefinitions() == 0 ? 100.0
                : Math.max(0.0, 100.0 - du.uncoveredDefinitions() * 10.0));

        Map<String, Double> scores = new LinkedHashMap<>();
        scores.put(MetricDefinition.VARIABLE_DEFINITION.key(), allDefs);
        scores.put(MetricDefinition.DEFINITION_USE_MAPPING.key(), dataPath);
        scores.put(MetricDefinition.COVERAGE_MEASUREMENT.key(), duPath);
        scores.put(MetricDefinition.UNCOVERED_DEFINITION.key(), deadData);
        scores.put(MetricDefinition.VARIABLE_USE.key(), allUses);

        Map<String, Object> raw = new LinkedHashMap<>();
        raw.put("all_defs_percent", allDefs);
        raw.put("all_uses_percent", allUses);
        raw.put("du_path_percent", duPath);
        raw.put("data_path_correlation_percent", dataPath);
        raw.put("definitions_total", du.definitionsTotal());
        raw.put("definitions_covered", du.definitionsCovered());
        raw.put("uses_total", du.usesTotal());
        raw.put("uses_covered", du.usesCovered());
        raw.put("du_pairs_total", du.duPairsTotal());
        raw.put("du_pairs_covered", du.duPairsCovered());
        raw.put("uncovered_definitions", du.uncoveredDefinitions());
        raw.put("partial_uses", du.partialUses());
        raw.put("ghost_uses", du.ghostUses());
        raw.put("cross_function_uses", du.crossFunctionUses());
        raw.put("all_defs_coverage_score", allDefs);
        raw.put("data_path_correlation_score", dataPath);
        raw.put("du_path_validation_score", duPath);
        raw.put("dead_data_identification_score", deadData);
        raw.put("all_uses_coverage_score", allUses);

        return new StaticDuDashboardMetrics(scores, raw);
    }

    private static double round(double value) {
        return Math.round(value * 100.0) / 100.0;
    }

    public record StaticDuDashboardMetrics(Map<String, Double> scores, Map<String, Object> rawParameters) {
        public Map<String, Double> normalizedScores() {
            return scores;
        }
    }
}
