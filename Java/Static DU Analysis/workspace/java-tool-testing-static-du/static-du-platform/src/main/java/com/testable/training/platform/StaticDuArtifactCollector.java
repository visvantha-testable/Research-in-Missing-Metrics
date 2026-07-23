package com.testable.training.platform;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;

public final class StaticDuArtifactCollector {

    private StaticDuArtifactCollector() {
    }

    public static void collect(Path repoRoot, Path outputDir) throws Exception {
        Files.createDirectories(outputDir);
        Path sourceRoot = repoRoot.resolve("sample_subject/src/main/java");
        Path testRoot = repoRoot.resolve("sample_subject/src/test/java");

        boolean allTestsPresent = verifyTestMapping(sourceRoot, testRoot);
        StaticDuAnalyzer.StaticDuSummary summary = StaticDuAnalyzer.analyze(sourceRoot, allTestsPresent);

        JsonUtils.write(outputDir.resolve("static_du_summary.json"), summary.toMap());
        JsonUtils.write(outputDir.resolve("du_path_correlation.json"), buildCorrelation(summary));

        Map<String, Object> meta = new LinkedHashMap<>();
        meta.put("tool", "Static DU");
        meta.put("source_root", sourceRoot.toString());
        meta.put("test_root", testRoot.toString());
        meta.put("all_tests_present", allTestsPresent);
        meta.put("analysis_mode", "static_definition_use");
        JsonUtils.write(outputDir.resolve("static_du_meta.json"), meta);

        System.out.println("Collected Static DU artifacts into " + outputDir);
        System.out.println("  definitions_total=" + summary.definitionsTotal());
        System.out.println("  definitions_covered=" + summary.definitionsCovered());
        System.out.println("  du_pairs_total=" + summary.duPairsTotal());
        System.out.println("  du_pairs_covered=" + summary.duPairsCovered());
        System.out.println("  all_defs_percent=" + summary.allDefsPercent());
        System.out.println("  all_uses_percent=" + summary.allUsesPercent());
    }

    private static boolean verifyTestMapping(Path sourceRoot, Path testRoot) throws Exception {
        Set<String> sources = listJavaFiles(sourceRoot);
        Set<String> tests = listJavaFiles(testRoot);
        for (String source : sources) {
            String expected = source.replace(".java", "Test.java");
            if (!tests.contains(expected)) {
                return false;
            }
        }
        return !sources.isEmpty();
    }

    private static Set<String> listJavaFiles(Path root) throws Exception {
        if (!Files.exists(root)) {
            return Set.of();
        }
        try (Stream<Path> stream = Files.walk(root)) {
            return stream.filter(p -> p.toString().endsWith(".java"))
                    .map(p -> p.getFileName().toString())
                    .collect(Collectors.toSet());
        }
    }

    private static Map<String, Object> buildCorrelation(StaticDuAnalyzer.StaticDuSummary summary) {
        Map<String, Object> correlation = new LinkedHashMap<>();
        correlation.put("du_pairs_total", summary.duPairsTotal());
        correlation.put("du_pairs_covered", summary.duPairsCovered());
        correlation.put("data_path_correlation_percent", summary.dataPathCorrelationPercent());
        correlation.put("du_paths", summary.duPaths());
        return correlation;
    }
}
