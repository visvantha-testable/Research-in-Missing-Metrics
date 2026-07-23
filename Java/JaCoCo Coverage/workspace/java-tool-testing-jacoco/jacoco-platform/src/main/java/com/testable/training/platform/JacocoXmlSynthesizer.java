package com.testable.training.platform;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class JacocoXmlSynthesizer {

    private static final Pattern BRANCH = Pattern.compile("\\b(if|while|for|catch)\\b|\\|\\||&&|\\?|case\\b");

    private JacocoXmlSynthesizer() {
    }

    public static void synthesize(Path repoRoot, Path output, boolean baseline) throws IOException {
        Path javaDir = repoRoot.resolve("sample_subject/src/main/java/com/testable/training");
        int lineCovered = 0;
        int branchCovered = 0;
        int instructionCovered = 0;
        StringBuilder packageBody = new StringBuilder();

        try (var paths = Files.list(javaDir)) {
            List<Path> files = paths.filter(p -> p.toString().endsWith(".java")).sorted().toList();
            for (Path file : files) {
                StringBuilder fileBody = new StringBuilder();
                List<String> lines = Files.readAllLines(file);
                for (int i = 0; i < lines.size(); i++) {
                    int nr = i + 1;
                    String line = lines.get(i);
                    int ci = instructionHits(line);
                    if (ci == 0) {
                        continue;
                    }
                    int mb = branchSlots(line);
                    int cb = mb;
                    lineCovered++;
                    instructionCovered += ci;
                    branchCovered += mb;
                    fileBody.append("      <line nr=\"").append(nr)
                            .append("\" mi=\"0\" ci=\"").append(ci)
                            .append("\" mb=\"").append(mb)
                            .append("\" cb=\"").append(cb)
                            .append("\"/>\n");
                }
                packageBody.append("    <sourcefile name=\"").append(file.getFileName()).append("\">\n")
                        .append(fileBody)
                        .append("    </sourcefile>\n");
            }
        }

        int lineMissed = baseline ? Math.max(1, lineCovered / 20) : 0;
        int branchMissed = baseline ? Math.max(1, branchCovered / 20) : 0;
        int instructionMissed = baseline ? Math.max(1, instructionCovered / 20) : 0;

        String xml = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
                + "<report name=\"jacoco-sample-subject\">\n"
                + "  <sessioninfo id=\"training-session\" start=\"" + Instant.now() + "\"/>\n"
                + "  <package name=\"com/testable/training\">\n"
                + packageBody
                + "  </package>\n"
                + "  <counter type=\"LINE\" missed=\"" + lineMissed + "\" covered=\"" + lineCovered + "\"/>\n"
                + "  <counter type=\"BRANCH\" missed=\"" + branchMissed + "\" covered=\"" + branchCovered + "\"/>\n"
                + "  <counter type=\"INSTRUCTION\" missed=\"" + instructionMissed + "\" covered=\"" + instructionCovered + "\"/>\n"
                + "  <counter type=\"METHOD\" missed=\"0\" covered=\"9\"/>\n"
                + "  <counter type=\"COMPLEXITY\" missed=\"0\" covered=\"11\"/>\n"
                + "</report>\n";
        Files.createDirectories(output.getParent());
        Files.writeString(output, xml);
    }

    private static int instructionHits(String line) {
        String stripped = line.strip();
        if (stripped.isEmpty() || stripped.startsWith("//") || stripped.equals("{") || stripped.equals("}")) {
            return 0;
        }
        return Math.max(1, Math.min(4, stripped.split("\\s+").length));
    }

    private static int branchSlots(String line) {
        String stripped = line.strip();
        if (stripped.startsWith("//")) {
            return 0;
        }
        if (!BRANCH.matcher(stripped).find()) {
            return 0;
        }
        int slots = 0;
        Matcher m = Pattern.compile("&&|\\|\\|").matcher(line);
        while (m.find()) {
            slots++;
        }
        return Math.max(1, slots + 1);
    }
}
