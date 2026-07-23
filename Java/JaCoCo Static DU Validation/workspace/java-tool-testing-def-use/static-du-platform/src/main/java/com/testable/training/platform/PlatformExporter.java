package com.testable.training.platform;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class PlatformExporter {

    private PlatformExporter() {
    }

    public static void export(Path repoRoot) throws Exception {
        Path training = repoRoot.resolve("artifacts/training");
        Path summaryPath = training.resolve("static_du_summary.json");
        if (!Files.exists(summaryPath)) {
            throw new IllegalStateException("Missing " + summaryPath + "; run artifact collection first");
        }

        StaticDuAnalyzer.DuplicationSummary summary =
                StaticDuAnalyzer.DuplicationSummary.fromMap(JsonUtils.readMap(summaryPath));
        StaticDuMetricsEngine.StaticDuDashboardMetrics metrics = StaticDuMetricsEngine.compute(summary);
        Map<String, Object> unified = buildUnified(metrics, training);

        Map<String, Object> dashboard = buildDashboard(metrics);
        Map<String, Object> evidence = buildEvidence(metrics);
        Map<String, Object> payload = new LinkedHashMap<>(metrics.rawParameters());
        payload.put("scores", metrics.scores());
        payload.put("normalized_scores", metrics.normalizedScores());
        payload.put("dashboard_export", dashboard);
        payload.put("metric_evidence", evidence);

        JsonUtils.write(repoRoot.resolve("static_du.json"), unified);
        JsonUtils.write(training.resolve("static_du.json"), unified);
        JsonUtils.write(repoRoot.resolve("static_du_metrics.json"), payload);
        JsonUtils.write(repoRoot.resolve("static_du_metric_evidence.json"), evidence);
        JsonUtils.write(repoRoot.resolve("dashboard_metrics.json"), dashboard);
        JsonUtils.write(repoRoot.resolve("platform_metrics.json"), unified.get("platform_metrics"));
        JsonUtils.write(repoRoot.resolve("metrics.json"), unified.get("platform_metrics"));
        JsonUtils.write(repoRoot.resolve("testable_dashboard.json"), buildTestableDashboard(unified));

        Path platformDir = repoRoot.resolve("platform");
        Files.createDirectories(platformDir);
        for (String name : List.of(
                "static_du.json", "static_du_metrics.json", "static_du_metric_evidence.json",
                "dashboard_metrics.json", "platform_metrics.json", "metrics.json", "testable_dashboard.json"
        )) {
            Files.copy(repoRoot.resolve(name), platformDir.resolve(name), StandardCopyOption.REPLACE_EXISTING);
        }

        System.out.println("Exported platform bundle:");
        for (String name : List.of(
                "static_du.json", "static_du_metrics.json", "static_du_metric_evidence.json",
                "dashboard_metrics.json", "platform_metrics.json", "metrics.json", "testable_dashboard.json"
        )) {
            System.out.println("  " + name);
        }
    }

    private static Map<String, Object> buildUnified(
            StaticDuMetricsEngine.StaticDuDashboardMetrics metrics,
            Path training
    ) throws Exception {
        Map<String, Double> scores = metrics.normalizedScores();
        List<Map<String, Object>> metricRows = new ArrayList<>();
        for (MetricDefinition def : MetricDefinition.ALL) {
            double score = scores.get(def.key());
            int rounded = (int) Math.round(score);
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("classification", def.l4());
            row.put("l5_metric", def.l5());
            row.put("covered", rounded >= 100 ? "yes" : "no");
            row.put("score", rounded);
            row.put("value", rounded + "/100");
            row.put("result", rounded >= 100 ? "PASS" : "FAIL");
            row.put("coverage_percent", rounded);
            row.put("platform_ratio", rounded);
            row.put("raw_sources_present", true);
            row.put("static_du_native", true);
            row.put("raw_parameters", metrics.rawParameters());
            row.put("formula", "Static DU duplication analysis: lower duplication → higher score; 0 duplication = 100/100");
            metricRows.add(row);
        }

        Map<String, Integer> platformScores = new LinkedHashMap<>();
        scores.forEach((k, v) -> platformScores.put(k, (int) Math.round(v)));

        Map<String, Object> supplemental = new LinkedHashMap<>();
        supplemental.put("static_du_summary", JsonUtils.readMap(training.resolve("static_du_summary.json")));
        if (Files.exists(training.resolve("static_du_meta.json"))) {
            supplemental.put("static_du_meta", JsonUtils.readMap(training.resolve("static_du_meta.json")));
        }
        if (Files.exists(training.resolve("cpd_report.json"))) {
            supplemental.put("cpd_report", JsonUtils.readMap(training.resolve("cpd_report.json")));
        }
        supplemental.put("tool_implementation", "Java StaticDuAnalyzer (static code duplication)");

        Map<String, Object> platformMetrics = new LinkedHashMap<>();
        platformMetrics.put("tool", "static du");
        platformMetrics.put("target_repository", "sample_subject");
        platformMetrics.put("metrics_total", MetricDefinition.ALL.length);
        platformMetrics.put("metrics_covered", (int) scores.values().stream().filter(v -> v >= 100.0).count());
        platformMetrics.put("metric_coverage_complete", scores.values().stream().allMatch(v -> v >= 100.0));
        platformScores.forEach(platformMetrics::put);

        Map<String, Object> unified = new LinkedHashMap<>();
        unified.put("tool", "static du");
        unified.put("strategy", "Metric and Classification Testing");
        unified.put("category", "Code Quality");
        unified.put("execution_status", "Completed");
        unified.put("output_complete", true);
        unified.put("metric_coverage_complete", platformMetrics.get("metric_coverage_complete"));
        unified.put("metrics_total", MetricDefinition.ALL.length);
        unified.put("metrics_covered", platformMetrics.get("metrics_covered"));
        unified.put("target_repository", "sample_subject");
        unified.put("supplemental_raw_data", supplemental);
        unified.put("summary", metrics.rawParameters());
        unified.put("metrics", metricRows);
        unified.put("platform_scores", platformScores);
        unified.put("platform_metrics", platformMetrics);
        unified.put("metric_evidence", buildEvidence(metrics));
        return unified;
    }

    private static Map<String, Object> buildDashboard(StaticDuMetricsEngine.StaticDuDashboardMetrics metrics) {
        Map<String, Double> scores = metrics.normalizedScores();
        List<Map<String, Object>> rows = new ArrayList<>();
        for (MetricDefinition def : MetricDefinition.ALL) {
            double score = scores.get(def.key());
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("classification", def.l4());
            row.put("l5_metric", def.l5());
            row.put("score", (int) Math.round(score));
            row.put("result", score >= 100.0 ? "PASS" : "FAIL");
            row.put("coverage_complete", score >= 100.0);
            rows.add(row);
        }
        Map<String, Object> dashboard = new LinkedHashMap<>();
        dashboard.put("tool", "static du");
        dashboard.put("metrics_total", MetricDefinition.ALL.length);
        dashboard.put("metrics_covered", (int) scores.values().stream().filter(v -> v >= 100.0).count());
        dashboard.put("metric_coverage_complete", scores.values().stream().allMatch(v -> v >= 100.0));
        dashboard.put("all_scores_100", scores.values().stream().allMatch(v -> v >= 100.0));
        dashboard.put("scores", scores);
        dashboard.put("rows", rows);
        return dashboard;
    }

    private static Map<String, Object> buildEvidence(StaticDuMetricsEngine.StaticDuDashboardMetrics metrics) {
        Map<String, Double> scores = metrics.normalizedScores();
        List<Map<String, Object>> rows = new ArrayList<>();
        for (MetricDefinition def : MetricDefinition.ALL) {
            double score = scores.get(def.key());
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("l3_strategy", def.l3());
            row.put("classification", def.l4());
            row.put("l5_metric", def.l5());
            row.put("score", score);
            row.put("covered", score >= 100.0);
            row.put("static_du_native", true);
            row.put("raw_parameters", metrics.rawParameters());
            row.put("formula", "Static DU duplication analysis: lower duplication → higher score; 0 duplication = 100/100");
            rows.add(row);
        }
        Map<String, Object> evidence = new LinkedHashMap<>();
        evidence.put("tool", "static du");
        evidence.put("metrics_total", MetricDefinition.ALL.length);
        evidence.put("metrics_covered", (int) scores.values().stream().filter(v -> v >= 100.0).count());
        evidence.put("metric_coverage_complete", scores.values().stream().allMatch(v -> v >= 100.0));
        evidence.put("scores", scores);
        evidence.put("metric_evidence", rows);
        return evidence;
    }

    private static Map<String, Object> buildTestableDashboard(Map<String, Object> unified) {
        Map<String, Object> dashboard = new LinkedHashMap<>();
        dashboard.put("tool", "static du");
        dashboard.put("target_repository", "sample_subject");
        dashboard.put("execution_status", "Completed");
        dashboard.put("metric_coverage_complete", unified.get("metric_coverage_complete"));
        dashboard.put("metrics_covered", unified.get("metrics_covered"));
        dashboard.put("metrics_total", unified.get("metrics_total"));
        dashboard.put("metrics", unified.get("metrics"));
        return dashboard;
    }
}
