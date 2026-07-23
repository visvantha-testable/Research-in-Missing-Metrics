package com.testable.training.platform;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Stream;

/**
 * Static DU — static code duplication analyzer (lines / blocks / files / density).
 * Produces the 12 dashboard duplication metrics.
 */
public final class StaticDuAnalyzer {

    private static final int MIN_BLOCK_LINES = 6;

    private StaticDuAnalyzer() {
    }

    public record DuplicationSummary(
            int totalLines,
            int duplicatedLines,
            double duplicatedLinesPercent,
            int duplicatedBlocks,
            int duplicatedFiles,
            int duplicatedBlocksCount,
            int duplicatedFilesCount,
            int duplicatedLinesCount,
            double duplicationDensity,
            double duplicationDensityPercent,
            int numberOfDuplicatedBlocks,
            int numberOfDuplicatedFiles,
            int numberOfDuplicatedLines,
            List<String> filesAnalyzed,
            List<Map<String, Object>> duplicateBlocks
    ) {
        public Map<String, Object> toMap() {
            Map<String, Object> map = new LinkedHashMap<>();
            map.put("total_lines", totalLines);
            map.put("duplicated_lines", duplicatedLines);
            map.put("duplicated_lines_percent", round2(duplicatedLinesPercent));
            map.put("duplicated_blocks", duplicatedBlocks);
            map.put("duplicated_files", duplicatedFiles);
            map.put("duplicated_blocks_count", duplicatedBlocksCount);
            map.put("duplicated_files_count", duplicatedFilesCount);
            map.put("duplicated_lines_count", duplicatedLinesCount);
            map.put("duplication_density", round2(duplicationDensity));
            map.put("duplication_density_percent", round2(duplicationDensityPercent));
            map.put("number_of_duplicated_blocks", numberOfDuplicatedBlocks);
            map.put("number_of_duplicated_files", numberOfDuplicatedFiles);
            map.put("number_of_duplicated_lines", numberOfDuplicatedLines);
            map.put("files_analyzed", filesAnalyzed);
            map.put("duplicate_blocks", duplicateBlocks);
            map.put("tool", "static du");
            return map;
        }

        @SuppressWarnings("unchecked")
        public static DuplicationSummary fromMap(Map<String, Object> map) {
            List<String> files = map.containsKey("files_analyzed")
                    ? (List<String>) map.get("files_analyzed")
                    : List.of();
            List<Map<String, Object>> blocks = map.containsKey("duplicate_blocks")
                    ? (List<Map<String, Object>>) map.get("duplicate_blocks")
                    : List.of();
            return new DuplicationSummary(
                    intVal(map, "total_lines"),
                    intVal(map, "duplicated_lines"),
                    dblVal(map, "duplicated_lines_percent"),
                    intVal(map, "duplicated_blocks"),
                    intVal(map, "duplicated_files"),
                    intVal(map, "duplicated_blocks_count"),
                    intVal(map, "duplicated_files_count"),
                    intVal(map, "duplicated_lines_count"),
                    dblVal(map, "duplication_density"),
                    dblVal(map, "duplication_density_percent"),
                    intVal(map, "number_of_duplicated_blocks"),
                    intVal(map, "number_of_duplicated_files"),
                    intVal(map, "number_of_duplicated_lines"),
                    files,
                    blocks
            );
        }

        private static int intVal(Map<String, Object> map, String key) {
            return ((Number) map.getOrDefault(key, 0)).intValue();
        }

        private static double dblVal(Map<String, Object> map, String key) {
            return ((Number) map.getOrDefault(key, 0.0)).doubleValue();
        }

        private static double round2(double value) {
            return Math.round(value * 100.0) / 100.0;
        }
    }

    public static DuplicationSummary analyze(Path sourceRoot) throws Exception {
        List<Path> javaFiles = listJavaFiles(sourceRoot);
        List<String> fileNames = new ArrayList<>();
        Map<String, List<String>> fileLines = new LinkedHashMap<>();
        Map<String, String> fileHashes = new LinkedHashMap<>();
        int totalLines = 0;

        for (Path file : javaFiles) {
            String name = file.getFileName().toString();
            fileNames.add(name);
            List<String> lines = Files.readAllLines(file, StandardCharsets.UTF_8);
            List<String> normalized = normalize(lines);
            fileLines.put(name, normalized);
            fileHashes.put(name, sha256(String.join("\n", normalized)));
            totalLines += countCodeLines(normalized);
        }

        // Identical-file duplication
        Map<String, List<String>> hashToFiles = new LinkedHashMap<>();
        for (Map.Entry<String, String> entry : fileHashes.entrySet()) {
            hashToFiles.computeIfAbsent(entry.getValue(), k -> new ArrayList<>()).add(entry.getKey());
        }
        Set<String> duplicatedFileSet = new LinkedHashSet<>();
        for (List<String> group : hashToFiles.values()) {
            if (group.size() > 1) {
                duplicatedFileSet.addAll(group);
            }
        }

        // Block duplication across files
        Map<String, List<BlockHit>> blockIndex = new LinkedHashMap<>();
        for (Map.Entry<String, List<String>> entry : fileLines.entrySet()) {
            String file = entry.getKey();
            List<String> lines = entry.getValue();
            for (int i = 0; i <= lines.size() - MIN_BLOCK_LINES; i++) {
                List<String> window = lines.subList(i, i + MIN_BLOCK_LINES);
                if (window.stream().allMatch(String::isBlank)) {
                    continue;
                }
                String key = String.join("\n", window);
                blockIndex.computeIfAbsent(key, k -> new ArrayList<>())
                        .add(new BlockHit(file, i + 1, MIN_BLOCK_LINES));
            }
        }

        List<Map<String, Object>> duplicateBlocks = new ArrayList<>();
        Set<String> duplicatedLineKeys = new LinkedHashSet<>();
        int duplicatedBlocks = 0;

        for (Map.Entry<String, List<BlockHit>> entry : blockIndex.entrySet()) {
            List<BlockHit> hits = entry.getValue();
            Set<String> filesInBlock = new LinkedHashSet<>();
            for (BlockHit hit : hits) {
                filesInBlock.add(hit.file);
            }
            boolean crossFile = filesInBlock.size() > 1;
            boolean sameFileMulti = hits.size() > 1 && filesInBlock.size() == 1;
            if (!crossFile && !sameFileMulti) {
                continue;
            }
            duplicatedBlocks++;
            Map<String, Object> block = new LinkedHashMap<>();
            block.put("lines", MIN_BLOCK_LINES);
            block.put("occurrences", hits.size());
            block.put("files", new ArrayList<>(filesInBlock));
            duplicateBlocks.add(block);
            for (BlockHit hit : hits) {
                for (int line = hit.startLine; line < hit.startLine + hit.length; line++) {
                    duplicatedLineKeys.add(hit.file + ":" + line);
                }
            }
        }

        int duplicatedLines = duplicatedLineKeys.size();
        int duplicatedFiles = duplicatedFileSet.size();
        double density = totalLines == 0 ? 0.0 : (duplicatedLines * 100.0) / totalLines;

        return new DuplicationSummary(
                totalLines,
                duplicatedLines,
                density,
                duplicatedBlocks,
                duplicatedFiles,
                duplicatedBlocks,
                duplicatedFiles,
                duplicatedLines,
                density / 100.0,
                density,
                duplicatedBlocks,
                duplicatedFiles,
                duplicatedLines,
                fileNames,
                duplicateBlocks
        );
    }

    private static List<Path> listJavaFiles(Path sourceRoot) throws Exception {
        if (!Files.exists(sourceRoot)) {
            return List.of();
        }
        try (Stream<Path> stream = Files.walk(sourceRoot)) {
            return stream
                    .filter(p -> p.toString().endsWith(".java"))
                    .filter(p -> !p.toString().replace('\\', '/').contains("/test/"))
                    .sorted()
                    .toList();
        }
    }

    private static List<String> normalize(List<String> lines) {
        List<String> out = new ArrayList<>();
        for (String line : lines) {
            String stripped = line.strip();
            if (stripped.isEmpty() || stripped.startsWith("//") || stripped.startsWith("*") || stripped.startsWith("/*")) {
                out.add("");
                continue;
            }
            out.add(stripped.replaceAll("\\s+", " "));
        }
        return out;
    }

    private static int countCodeLines(List<String> normalized) {
        int count = 0;
        for (String line : normalized) {
            if (!line.isBlank()) {
                count++;
            }
        }
        return count;
    }

    private static String sha256(String content) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] hash = digest.digest(content.getBytes(StandardCharsets.UTF_8));
        return HexFormat.of().formatHex(hash);
    }

    private record BlockHit(String file, int startLine, int length) {
    }
}
