package com.testable.training.platform;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public final class JacocoJsonVerifier {

    private JacocoJsonVerifier() {
    }

    public static int verify(Path jacocoJson) throws Exception {
        Map<String, Object> payload = JsonUtils.readMap(jacocoJson);
        List<String> errors = new ArrayList<>();
        int expected = MetricDefinition.ALL.length;

        if (!Boolean.TRUE.equals(payload.get("output_complete"))) {
            errors.add("output_complete is not true");
        }
        if (!Boolean.TRUE.equals(payload.get("metric_coverage_complete"))) {
            errors.add("metric_coverage_complete is not true");
        }
        if (toInt(payload.get("metrics_covered")) != expected) {
            errors.add("metrics_covered is not " + expected);
        }
        if (toInt(payload.get("metrics_total")) != expected) {
            errors.add("metrics_total is not " + expected);
        }

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> metrics = (List<Map<String, Object>>) payload.get("metrics");
        if (metrics == null || metrics.size() != expected) {
            errors.add("expected " + expected + " metric rows");
        } else {
            for (Map<String, Object> row : metrics) {
                String name = String.valueOf(row.get("l5_metric"));
                if (!"yes".equals(row.get("covered"))) {
                    errors.add(name + ": covered is not yes");
                }
                if (toInt(row.get("score")) < 100) {
                    errors.add(name + ": score below 100");
                }
                if (!"PASS".equals(row.get("result"))) {
                    errors.add(name + ": result is not PASS");
                }
                if (!Boolean.TRUE.equals(row.get("raw_sources_present"))) {
                    errors.add(name + ": raw_sources_present is false");
                }
                if (row.get("raw_parameters") == null) {
                    errors.add(name + ": raw_parameters missing");
                }
                if (toInt(row.get("coverage_percent")) < 100) {
                    errors.add(name + ": coverage_percent below 100");
                }
                if (toInt(row.get("platform_ratio")) < 100) {
                    errors.add(name + ": platform_ratio below 100");
                }
            }
        }

        @SuppressWarnings("unchecked")
        Map<String, Object> supplemental = (Map<String, Object>) payload.get("supplemental_raw_data");
        if (supplemental == null || !supplemental.containsKey("jacoco_xml")) {
            errors.add("missing supplemental_raw_data.jacoco_xml");
        }

        if (!errors.isEmpty()) {
            System.err.println("FAIL: jacoco.json incomplete:");
            errors.forEach(err -> System.err.println("  - " + err));
            return 1;
        }

        System.out.println("PASS: jacoco.json has all " + expected + " JaCoCo metrics covered=yes with 100/100 score");
        return 0;
    }

    private static int toInt(Object value) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        return 0;
    }
}
