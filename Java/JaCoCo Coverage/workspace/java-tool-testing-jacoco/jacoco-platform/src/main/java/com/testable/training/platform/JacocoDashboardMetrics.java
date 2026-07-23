package com.testable.training.platform;

import java.util.LinkedHashMap;
import java.util.Map;

public final class JacocoDashboardMetrics {
    public double linePercent;
    public double branchPercent;
    public double instructionPercent;
    public double pathCoveragePercent;
    public double coverageDeltaPercent;
    public double allDefsPercent;
    public double allUsesPercent;
    public double cUsePercent;
    public double pUsePercent;
    public double duPathPercent;
    public int ghostLines;
    public int partialBranchLines;
    public int definitionsTotal;
    public int usesTotal;
    public int duPairsTotal;
    public int modulesWithChurn;
    public int modulesTested;
    public final Map<String, Double> scores = new LinkedHashMap<>();

    public static JacocoDashboardMetrics compute(
            JacocoCounters current,
            JacocoCounters baseline,
            StaticDuAnalyzer.StaticDuSummary du,
            int churnModules,
            int churnTested
    ) {
        JacocoDashboardMetrics metrics = new JacocoDashboardMetrics();
        metrics.linePercent = round(current.linePercent());
        metrics.branchPercent = round(current.branchPercent());
        metrics.instructionPercent = round(current.instructionPercent());
        metrics.pathCoveragePercent = metrics.branchPercent;
        metrics.coverageDeltaPercent = round(metrics.linePercent - baseline.linePercent());
        metrics.allDefsPercent = round(du.allDefsPercent());
        metrics.allUsesPercent = round(du.allUsesPercent());
        metrics.cUsePercent = round(du.cUseTotal() == 0 ? 100.0 : du.cUseCovered() * 100.0 / du.cUseTotal());
        metrics.pUsePercent = round(du.pUseTotal() == 0 ? 100.0 : du.pUseCovered() * 100.0 / du.pUseTotal());
        metrics.duPathPercent = round(du.duPathPercent());
        metrics.ghostLines = current.ghostLines;
        metrics.partialBranchLines = current.partialBranchLines;
        metrics.definitionsTotal = du.definitionsTotal();
        metrics.usesTotal = du.usesTotal();
        metrics.duPairsTotal = du.duPairsTotal();
        metrics.modulesWithChurn = churnModules;
        metrics.modulesTested = churnTested;

        double deltaScore = scoreFromPercent(metrics.coverageDeltaPercent >= 0 ? 100.0 : 100.0 + metrics.coverageDeltaPercent);
        double unreachableScore = scoreFromPercent(current.ghostLines == 0 ? 100.0 : Math.max(0.0, 100.0 - current.ghostLines * 10.0));
        double partialPathScore = scoreFromPercent(current.partialBranchLines == 0 ? 100.0 : Math.max(0.0, 100.0 - current.partialBranchLines * 5.0));
        double churnScore = scoreFromPercent(churnTested >= churnModules ? 100.0 : churnTested * 100.0 / Math.max(churnModules, 1));

        put(metrics, "path_execution_tracking_score", metrics.branchPercent);
        put(metrics, "complete_coverage_path_verification_score", metrics.pathCoveragePercent);
        put(metrics, "partial_path_coverage_detection_score", partialPathScore);
        put(metrics, "nested_condition_path_testing_score", metrics.branchPercent);
        put(metrics, "loop_path_detection_score", metrics.branchPercent);
        put(metrics, "unreachable_path_detection_score", unreachableScore);
        put(metrics, "exception_path_handling_score", metrics.branchPercent);
        put(metrics, "multi_function_path_tracking_score", metrics.linePercent);
        put(metrics, "cicd_integration_test_score", scoreFromPercent(metrics.linePercent >= 80 ? 100.0 : metrics.linePercent));
        put(metrics, "path_coverage_percent_score", metrics.pathCoveragePercent);
        put(metrics, "regression_testing_monitoring_score", deltaScore);
        put(metrics, "test_suite_effectiveness_tracking_score", metrics.branchPercent);
        put(metrics, "cicd_quality_gate_enforcement_score", deltaScore);
        put(metrics, "change_impact_analysis_score", deltaScore);
        put(metrics, "new_code_testing_validation_score", metrics.linePercent);
        put(metrics, "quality_improvement_measurement_score", deltaScore);
        put(metrics, "variable_definition_detection_score", metrics.allDefsPercent);
        put(metrics, "definition_use_mapping_score", metrics.duPathPercent);
        put(metrics, "coverage_measurement_score", metrics.duPathPercent);
        put(metrics, "uncovered_definition_detection_score", scoreFromPercent(du.uncoveredDefinitions() == 0 ? 100.0 : Math.max(0.0, 100.0 - du.uncoveredDefinitions() * 10.0)));
        put(metrics, "edge_case_handling_score", metrics.branchPercent);
        put(metrics, "reporting_validation_score", scoreFromPercent(current.sessionId == null || current.sessionId.isBlank() ? 90.0 : 100.0));
        put(metrics, "computational_use_detection_score", metrics.cUsePercent);
        put(metrics, "predicate_use_detection_score", metrics.pUsePercent);
        put(metrics, "definition_use_pair_identification_score", metrics.duPathPercent);
        put(metrics, "all_uses_coverage_verification_score", metrics.allUsesPercent);
        put(metrics, "partial_uses_coverage_detection_score", scoreFromPercent(du.partialUses() == 0 ? 100.0 : Math.max(0.0, 100.0 - du.partialUses() * 5.0)));
        put(metrics, "multiple_definitions_handling_score", scoreFromPercent(du.multipleDefinitionSites() <= 2 ? 100.0 : 95.0));
        put(metrics, "cross_function_use_detection_score", metrics.linePercent);
        put(metrics, "unreachable_use_detection_score", scoreFromPercent(du.ghostUses() == 0 ? 100.0 : Math.max(0.0, 100.0 - du.ghostUses() * 10.0)));
        put(metrics, "coverage_reporting_validation_score", metrics.allUsesPercent);
        put(metrics, "variable_use_detection_score", metrics.allUsesPercent);
        put(metrics, "regression_testing_focus_score", churnScore);
        return metrics;
    }

    public Map<String, Double> normalizedScores() {
        Map<String, Double> result = new LinkedHashMap<>();
        for (MetricDefinition def : MetricDefinition.ALL) {
            result.put(def.key(), scores.getOrDefault(def.field(), 0.0));
        }
        return result;
    }

    public Map<String, Object> rawParameters() {
        Map<String, Object> raw = new LinkedHashMap<>();
        raw.put("line_percent", linePercent);
        raw.put("branch_percent", branchPercent);
        raw.put("instruction_percent", instructionPercent);
        raw.put("path_coverage_percent", pathCoveragePercent);
        raw.put("coverage_delta_percent", coverageDeltaPercent);
        raw.put("all_defs_percent", allDefsPercent);
        raw.put("all_uses_percent", allUsesPercent);
        raw.put("c_use_percent", cUsePercent);
        raw.put("p_use_percent", pUsePercent);
        raw.put("du_path_percent", duPathPercent);
        raw.put("definitions_total", definitionsTotal);
        raw.put("uses_total", usesTotal);
        raw.put("du_pairs_total", duPairsTotal);
        raw.put("ghost_lines", ghostLines);
        raw.put("partial_branch_lines", partialBranchLines);
        raw.put("modules_with_churn", modulesWithChurn);
        raw.put("modules_tested", modulesTested);
        return raw;
    }

    private static void put(JacocoDashboardMetrics metrics, String field, double value) {
        metrics.scores.put(field, scoreFromPercent(value));
    }

    private static double scoreFromPercent(double value) {
        return Math.max(0.0, Math.min(100.0, round(value)));
    }

    private static double round(double value) {
        return Math.round(value * 100.0) / 100.0;
    }
}
