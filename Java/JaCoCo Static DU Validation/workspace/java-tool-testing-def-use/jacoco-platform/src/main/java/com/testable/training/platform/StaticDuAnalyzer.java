package com.testable.training.platform;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
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
            int multipleDefinitionSites
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

        try (Stream<Path> paths = Files.walk(sourceRoot)) {
            List<Path> javaFiles = paths
                    .filter(p -> p.toString().endsWith(".java"))
                    .filter(p -> !p.toString().replace('\\', '/').contains("/test/"))
                    .sorted()
                    .toList();

            for (Path file : javaFiles) {
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
                            if (varDefs.containsKey(token.group(1))) {
                                cUseTotal++;
                                usesTotal++;
                                duPairsTotal++;
                                if (fullyCovered) {
                                    cUseCovered++;
                                    usesCovered++;
                                    duPairsCovered++;
                                }
                            }
                        }
                    }
                    if (stripped.contains("return")) {
                        Matcher token = TOKEN.matcher(stripped);
                        while (token.find()) {
                            if (varDefs.containsKey(token.group(1))) {
                                cUseTotal++;
                                usesTotal++;
                                duPairsTotal++;
                                if (fullyCovered) {
                                    cUseCovered++;
                                    usesCovered++;
                                    duPairsCovered++;
                                }
                            }
                        }
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
                multipleDefinitionSites
        );
    }
}
