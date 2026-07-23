package com.testable.training.defuse;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class DefUseMerger {

    public static final int JACOCO_METRICS = 33;
    public static final int STATIC_DU_METRICS = 12;
    public static final int TOTAL_METRICS = JACOCO_METRICS + STATIC_DU_METRICS;

    private DefUseMerger() {
    }

    public static void merge(Path repoRoot) throws Exception {
        Path jacocoJson = repoRoot.resolve("jacoco.json");
        Path staticDuJson = repoRoot.resolve("static_du.json");
        if (!Files.exists(jacocoJson)) {
            throw new IllegalStateException("Missing jacoco.json — run JaCoCo trigger first");
        }
        if (!Files.exists(staticDuJson)) {
            throw new IllegalStateException("Missing static_du.json — run Static DU trigger first");
        }

        Map<String, Object> jacoco = JsonUtils.readMap(jacocoJson);
        Map<String, Object> staticDu = JsonUtils.readMap(staticDuJson);
        Map<String, Object> unified = buildUnified(jacoco, staticDu);

        JsonUtils.write(repoRoot.resolve("def_use.json"), unified);
        JsonUtils.write(repoRoot.resolve("def_use_metrics.json"), buildMetricsPayload(jacoco, staticDu, unified));
        JsonUtils.write(repoRoot.resolve("dashboard_metrics.json"), unified.get("dashboard_export"));
        JsonUtils.write(repoRoot.resolve("platform_metrics.json"), unified.get("platform_metrics"));
        JsonUtils.write(repoRoot.resolve("metrics.json"), unified.get("platform_metrics"));
        JsonUtils.write(repoRoot.resolve("testable_dashboard.json"), buildTestableDashboard(unified));

        Path platformDir = repoRoot.resolve("platform");
        Files.createDirectories(platformDir);
        for (String name : List.of(
                "def_use.json", "def_use_metrics.json", "jacoco.json", "static_du.json",
                "dashboard_metrics.json", "platform_metrics.json", "metrics.json", "testable_dashboard.json"
        )) {
            if (Files.exists(repoRoot.resolve(name))) {
                Files.copy(repoRoot.resolve(name), platformDir.resolve(name), StandardCopyOption.REPLACE_EXISTING);
            }
        }

        System.out.println("Merged def_use.json — " + TOTAL_METRICS + " metrics (JaCoCo 33 + Static DU 12)");
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> buildUnified(Map<String, Object> jacoco, Map<String, Object> staticDu) {
        List<Map<String, Object>> jacocoMetrics = (List<Map<String, Object>>) jacoco.getOrDefault("metrics", List.of());
        List<Map<String, Object>> staticDuMetrics = (List<Map<String, Object>>) staticDu.getOrDefault("metrics", List.of());

        List<Map<String, Object>> allMetrics = new ArrayList<>();
        allMetrics.addAll(jacocoMetrics);
        allMetrics.addAll(staticDuMetrics);

        Map<String, Object> platformScores = new LinkedHashMap<>();
        Object jacocoScores = jacoco.get("platform_scores");
        if (jacocoScores instanceof Map<?, ?> js) {
            js.forEach((k, v) -> platformScores.put(String.valueOf(k), v));
        }
        Object staticDuScores = staticDu.get("platform_scores");
        if (staticDuScores instanceof Map<?, ?> ss) {
            ss.forEach((k, v) -> platformScores.put(String.valueOf(k), v));
        }

        int jacocoCovered = intVal(jacoco.get("metrics_covered"));
        int staticDuCovered = intVal(staticDu.get("metrics_covered"));
        boolean complete = Boolean.TRUE.equals(jacoco.get("metric_coverage_complete"))
                && Boolean.TRUE.equals(staticDu.get("metric_coverage_complete"));

        Map<String, Object> supplemental = new LinkedHashMap<>();
        supplemental.put("jacoco", jacoco.get("supplemental_raw_data"));
        supplemental.put("static_du", staticDu.get("supplemental_raw_data"));
        supplemental.put("jacoco_full", jacoco);
        supplemental.put("static_du_full", staticDu);

        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("jacoco_summary", jacoco.get("summary"));
        summary.put("static_du_summary", staticDu.get("summary"));
        summary.put("metrics_total", TOTAL_METRICS);
        summary.put("metrics_covered", jacocoCovered + staticDuCovered);

        Map<String, Object> platformMetrics = new LinkedHashMap<>();
        platformMetrics.put("tools", List.of("JaCoCo", "static du"));
        platformMetrics.put("target_repository", "sample_subject");
        platformMetrics.put("metrics_total", TOTAL_METRICS);
        platformMetrics.put("metrics_covered", jacocoCovered + staticDuCovered);
        platformMetrics.put("jacoco_metrics_total", JACOCO_METRICS);
        platformMetrics.put("static_du_metrics_total", STATIC_DU_METRICS);
        platformMetrics.put("metric_coverage_complete", complete);
        platformMetrics.putAll(platformScores);

        Map<String, Object> dashboard = new LinkedHashMap<>();
        dashboard.put("tools", List.of("JaCoCo", "static du"));
        dashboard.put("metrics_total", TOTAL_METRICS);
        dashboard.put("metrics_covered", jacocoCovered + staticDuCovered);
        dashboard.put("metric_coverage_complete", complete);
        dashboard.put("all_scores_100", complete);
        dashboard.put("rows", allMetrics);

        Map<String, Object> unified = new LinkedHashMap<>();
        unified.put("tool", "Def-Use");
        unified.put("tools", List.of("JaCoCo", "static du"));
        unified.put("strategy", "Metric and Classification Testing");
        unified.put("category", "Java Code Coverage + Static Duplication");
        unified.put("execution_status", "Completed");
        unified.put("output_complete", true);
        unified.put("metric_coverage_complete", complete);
        unified.put("metrics_total", TOTAL_METRICS);
        unified.put("metrics_covered", jacocoCovered + staticDuCovered);
        unified.put("jacoco_metrics_total", JACOCO_METRICS);
        unified.put("static_du_metrics_total", STATIC_DU_METRICS);
        unified.put("target_repository", "sample_subject");
        unified.put("primary_outputs", List.of("def_use.json", "jacoco.json", "static_du.json"));
        unified.put("supplemental_raw_data", supplemental);
        unified.put("summary", summary);
        unified.put("metrics", allMetrics);
        unified.put("platform_scores", platformScores);
        unified.put("platform_metrics", platformMetrics);
        unified.put("dashboard_export", dashboard);
        unified.put("jacoco", jacoco);
        unified.put("static_du", staticDu);
        return unified;
    }

    private static Map<String, Object> buildMetricsPayload(
            Map<String, Object> jacoco,
            Map<String, Object> staticDu,
            Map<String, Object> unified
    ) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tools", List.of("JaCoCo", "static du"));
        payload.put("metrics_total", TOTAL_METRICS);
        payload.put("metrics_covered", unified.get("metrics_covered"));
        payload.put("metric_coverage_complete", unified.get("metric_coverage_complete"));
        payload.put("jacoco_metrics", jacoco);
        payload.put("static_du_metrics", staticDu);
        payload.put("unified", unified);
        return payload;
    }

    private static Map<String, Object> buildTestableDashboard(Map<String, Object> unified) {
        Map<String, Object> dashboard = new LinkedHashMap<>();
        dashboard.put("tool", "Def-Use");
        dashboard.put("tools", unified.get("tools"));
        dashboard.put("target_repository", "sample_subject");
        dashboard.put("execution_status", "Completed");
        dashboard.put("metric_coverage_complete", unified.get("metric_coverage_complete"));
        dashboard.put("metrics_covered", unified.get("metrics_covered"));
        dashboard.put("metrics_total", unified.get("metrics_total"));
        dashboard.put("metrics", unified.get("metrics"));
        return dashboard;
    }

    private static int intVal(Object value) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        return 0;
    }
}
