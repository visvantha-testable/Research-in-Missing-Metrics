package com.testable.training.platform;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class PlatformFixup {

    private PlatformFixup() {
    }

    public static Map<String, Object> apply(Map<String, Object> unified, JacocoDashboardMetrics metrics) {
        Map<String, Double> scores = metrics.normalizedScores();
        Map<String, Object> totals = metrics.rawParameters();
        totals.put("metrics_total", MetricDefinition.ALL.length);
        totals.put("metrics_covered", (int) scores.values().stream().filter(v -> v >= 100.0).count());
        totals.put("metric_coverage_complete", scores.values().stream().allMatch(v -> v >= 100.0));

        unified.put("totals", totals);
        unified.put("platform_totals", totals);
        for (Map.Entry<String, Double> entry : scores.entrySet()) {
            unified.put(entry.getKey(), (int) Math.round(entry.getValue()));
        }

        @SuppressWarnings("unchecked")
        Map<String, Object> platformMetrics = (Map<String, Object>) unified.computeIfAbsent("platform_metrics", k -> new LinkedHashMap<>());
        for (Map.Entry<String, Double> entry : scores.entrySet()) {
            platformMetrics.put(entry.getKey(), (int) Math.round(entry.getValue()));
        }
        platformMetrics.putAll(totals);
        unified.put("platform_metrics", platformMetrics);
        unified.put("platform_scores", scores);
        return unified;
    }

    public static List<String> verify(Map<String, Object> unified) {
        List<String> errors = new ArrayList<>();
        @SuppressWarnings("unchecked")
        Map<String, Object> totals = (Map<String, Object>) unified.get("totals");
        if (totals == null) {
            errors.add("missing totals block");
            return errors;
        }
        if (toDouble(totals.get("line_percent")) < 100.0) {
            errors.add("totals.line_percent below 100");
        }
        if (toDouble(totals.get("branch_percent")) < 100.0) {
            errors.add("totals.branch_percent below 100");
        }
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> rows = (List<Map<String, Object>>) unified.get("metrics");
        if (rows != null) {
            for (Map<String, Object> row : rows) {
                if (!"yes".equals(row.get("covered"))) {
                    errors.add(row.get("l5_metric") + ": covered is not yes");
                }
                if (toDouble(row.get("platform_ratio")) < 100.0) {
                    errors.add(row.get("l5_metric") + ": platform_ratio below 100");
                }
            }
        }
        if (!Boolean.TRUE.equals(unified.get("metric_coverage_complete"))) {
            errors.add("metric_coverage_complete is false");
        }
        return errors;
    }

    private static double toDouble(Object value) {
        if (value instanceof Number number) {
            return number.doubleValue();
        }
        return 0.0;
    }
}
