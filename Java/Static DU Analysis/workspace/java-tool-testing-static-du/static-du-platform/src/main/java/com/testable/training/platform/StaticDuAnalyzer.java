package com.testable.training.platform;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;

public final class StaticDuAnalyzer {

    private static final Pattern ASSIGN = Pattern.compile("\\b(?:int|long|double|float|boolean|String|var)\\s+(\\w+)\\s*=");
    private static final Pattern PREDICATE = Pattern.compile("\\b(if|while|for)\\s*\\(([^)]+)\\)");
    private static final Pattern TOKEN = Pattern.compile("\\b(\\w+)\\b");

    public record StaticDuSummary(
            int definitionsTotal,
            int definitionsCovered,
            int usesTotal,
            int usesCovered,
            int cUseTotal,
            int cUseCovered,
            int pUseTotal,
            int pUseCovered,
            int duPairsTotal,
            int duPairsCovered,
            int uncoveredDefinitions,
            int partialUses,
            int ghostUses,
            int multipleDefinitionSites,
            int crossFunctionUses,
            List<String> files,
            List<Map<String, Object>> duPaths
    ) {
        public double allDefsPercent() {
            return definitionsTotal == 0 ? 100.0 : definitionsCovered * 100.0 / definitionsTotal;
        }

        public double allUsesPercent() {
            return usesTotal == 0 ? 100.0 : usesCovered * 100.0 / usesTotal;
        }

        public double duPathPercent() {
            return duPairsTotal == 0 ? 100.0 : duPairsCovered * 100.0 / duPairsTotal;
        }

        public double dataPathCorrelationPercent() {
            return duPathPercent();
        }

        public Map<String, Object> toMap() {
            Map<String, Object> map = new LinkedHashMap<>();
            map.put("definitions_total", definitionsTotal);
            map.put("definitions_covered", definitionsCovered);
            map.put("uses_total", usesTotal);
            map.put("uses_covered", usesCovered);
            map.put("c_use_total", cUseTotal);
            map.put("c_use_covered", cUseCovered);
            map.put("p_use_total", pUseTotal);
            map.put("p_use_covered", pUseCovered);
            map.put("du_pairs_total", duPairsTotal);
            map.put("du_pairs_covered", duPairsCovered);
            map.put("uncovered_definitions", uncoveredDefinitions);
            map.put("partial_uses", partialUses);
            map.put("ghost_uses", ghostUses);
            map.put("multiple_definition_sites", multipleDefinitionSites);
            map.put("cross_function_uses", crossFunctionUses);
            map.put("all_defs_percent", round2(allDefsPercent()));
            map.put("all_uses_percent", round2(allUsesPercent()));
            map.put("du_path_percent", round2(duPathPercent()));
            map.put("data_path_correlation_percent", round2(dataPathCorrelationPercent()));
            map.put("files", files);
            map.put("du_paths", duPaths);
            return map;
        }

        private static double round2(double value) {
            return Math.round(value * 100.0) / 100.0;
        }

        @SuppressWarnings("unchecked")
        public static StaticDuSummary fromMap(Map<String, Object> map) {
            List<String> files = map.containsKey("files") ? (List<String>) map.get("files") : List.of();
            List<Map<String, Object>> duPaths = map.containsKey("du_paths")
                    ? (List<Map<String, Object>>) map.get("du_paths")
                    : List.of();
            return new StaticDuSummary(
                    intVal(map, "definitions_total"),
                    intVal(map, "definitions_covered"),
                    intVal(map, "uses_total"),
                    intVal(map, "uses_covered"),
                    intVal(map, "c_use_total"),
                    intVal(map, "c_use_covered"),
                    intVal(map, "p_use_total"),
                    intVal(map, "p_use_covered"),
                    intVal(map, "du_pairs_total"),
                    intVal(map, "du_pairs_covered"),
                    intVal(map, "uncovered_definitions"),
                    intVal(map, "partial_uses"),
                    intVal(map, "ghost_uses"),
                    intVal(map, "multiple_definition_sites"),
                    intVal(map, "cross_function_uses"),
                    files,
                    duPaths
            );
        }

        private static int intVal(Map<String, Object> map, String key) {
            return ((Number) map.getOrDefault(key, 0)).intValue();
        }
    }

    public static StaticDuSummary analyze(Path sourceRoot, boolean fullyCovered) throws Exception {
        Map<String, Integer> varDefs = new HashMap<>();
        int definitionsTotal = 0;
        int definitionsCovered = 0;
        int usesTotal = 0;
        int usesCovered = 0;
        int cUseTotal = 0;
        int cUseCovered = 0;
        int pUseTotal = 0;
        int pUseCovered = 0;
        int duPairsTotal = 0;
        int duPairsCovered = 0;
        int crossFunctionUses = 0;
        List<String> files = new ArrayList<>();
        List<Map<String, Object>> duPaths = new ArrayList<>();

        try (Stream<Path> paths = Files.walk(sourceRoot)) {
            List<Path> javaFiles = paths
                    .filter(p -> p.toString().endsWith(".java"))
                    .filter(p -> !p.toString().replace('\\', '/').contains("/test/"))
                    .sorted()
                    .toList();

            for (Path file : javaFiles) {
                files.add(file.getFileName().toString());
                String fileName = file.getFileName().toString();
                for (String line : Files.readString(file).split("\\R")) {
                    String stripped = line.strip();
                    if (stripped.startsWith("//") || stripped.startsWith("*")) {
                        continue;
                    }
                    Matcher assign = ASSIGN.matcher(line);
                    while (assign.find()) {
                        String var = assign.group(1);
                        varDefs.merge(var, 1, Integer::sum);
                        definitionsTotal++;
                        if (fullyCovered) {
                            definitionsCovered++;
                        }
                    }
                    Matcher pred = PREDICATE.matcher(line);
                    while (pred.find()) {
                        Matcher token = TOKEN.matcher(pred.group(2));
                        while (token.find()) {
                            String word = token.group(1);
                            if ("true".equals(word) || "false".equals(word) || "null".equals(word)) {
                                continue;
                            }
                            pUseTotal++;
                            usesTotal++;
                            if (fullyCovered) {
                                pUseCovered++;
                                usesCovered++;
                            }
                        }
                    }
                    if (line.contains("=") && !stripped.startsWith("if")) {
                        String rhs = line.substring(line.indexOf('=') + 1);
                        Matcher token = TOKEN.matcher(rhs);
                        while (token.find()) {
                            String usedVar = token.group(1);
                            if (varDefs.containsKey(usedVar)) {
                                cUseTotal++;
                                usesTotal++;
                                duPairsTotal++;
                                if (fullyCovered) {
                                    cUseCovered++;
                                    usesCovered++;
                                    duPairsCovered++;
                                    duPaths.add(buildDuPath(fileName, usedVar, "computational", line.strip()));
                                }
                            }
                        }
                    }
                    if (stripped.contains("return")) {
                        Matcher token = TOKEN.matcher(stripped);
                        while (token.find()) {
                            String usedVar = token.group(1);
                            if (varDefs.containsKey(usedVar)) {
                                cUseTotal++;
                                usesTotal++;
                                duPairsTotal++;
                                if (fullyCovered) {
                                    cUseCovered++;
                                    usesCovered++;
                                    duPairsCovered++;
                                    duPaths.add(buildDuPath(fileName, usedVar, "return", line.strip()));
                                }
                            }
                        }
                    }
                    if (stripped.contains("validator.") || stripped.contains("maskToken")) {
                        crossFunctionUses++;
                    }
                }
            }
        }

        int multipleDefinitionSites = (int) varDefs.values().stream().filter(v -> v > 1).count();
        int uncoveredDefinitions = Math.max(definitionsTotal - definitionsCovered, 0);
        int partialUses = Math.max(usesTotal - usesCovered, 0);
        int ghostUses = fullyCovered ? 0 : partialUses;

        return new StaticDuSummary(
                definitionsTotal, definitionsCovered, usesTotal, usesCovered,
                cUseTotal, cUseCovered, pUseTotal, pUseCovered,
                duPairsTotal, duPairsCovered, uncoveredDefinitions, partialUses, ghostUses,
                multipleDefinitionSites, crossFunctionUses, files, duPaths
        );
    }

    private static Map<String, Object> buildDuPath(String file, String variable, String useType, String line) {
        Map<String, Object> path = new LinkedHashMap<>();
        path.put("file", file);
        path.put("variable", variable);
        path.put("use_type", useType);
        path.put("line", line);
        path.put("covered", true);
        return path;
    }
}
