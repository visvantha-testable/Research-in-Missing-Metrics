package com.testable.training.defuse;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public final class DefUseJsonVerifier {

    private DefUseJsonVerifier() {
    }

    public static int verify(Path defUseJson) throws Exception {
        Map<String, Object> payload = JsonUtils.readMap(defUseJson);
        List<String> errors = new ArrayList<>();

        if (!Boolean.TRUE.equals(payload.get("output_complete"))) {
            errors.add("output_complete is not true");
        }
        if (!Boolean.TRUE.equals(payload.get("metric_coverage_complete"))) {
            errors.add("metric_coverage_complete is not true");
        }
        if (intVal(payload.get("metrics_total")) != DefUseMerger.TOTAL_METRICS) {
            errors.add("metrics_total is not " + DefUseMerger.TOTAL_METRICS);
        }
        if (intVal(payload.get("metrics_covered")) != DefUseMerger.TOTAL_METRICS) {
            errors.add("metrics_covered is not " + DefUseMerger.TOTAL_METRICS);
        }
        if (payload.get("jacoco") == null) {
            errors.add("missing embedded jacoco payload");
        }
        if (payload.get("static_du") == null) {
            errors.add("missing embedded static_du payload");
        }

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> metrics = (List<Map<String, Object>>) payload.get("metrics");
        if (metrics == null || metrics.size() != DefUseMerger.TOTAL_METRICS) {
            errors.add("expected " + DefUseMerger.TOTAL_METRICS + " metric rows");
        } else {
            for (Map<String, Object> row : metrics) {
                String name = String.valueOf(row.get("l5_metric"));
                if (!"yes".equals(row.get("covered"))) {
                    errors.add(name + ": covered is not yes");
                }
                if (intVal(row.get("score")) < 100) {
                    errors.add(name + ": score below 100");
                }
            }
        }

        if (!errors.isEmpty()) {
            System.err.println("FAIL: def_use.json incomplete:");
            errors.forEach(err -> System.err.println("  - " + err));
            return 1;
        }

        System.out.println("PASS: def_use.json has all " + DefUseMerger.TOTAL_METRICS
                + " metrics (JaCoCo 33 + Static DU 12) covered=yes with 100/100 score");
        return 0;
    }

    private static int intVal(Object value) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        return 0;
    }
}
