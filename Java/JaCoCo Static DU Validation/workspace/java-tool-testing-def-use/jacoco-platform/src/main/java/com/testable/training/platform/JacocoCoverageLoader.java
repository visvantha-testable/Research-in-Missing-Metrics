package com.testable.training.platform;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Resolves JaCoCo coverage counters. Primary source is the official Maven
 * {@code jacoco.xml} report; {@code jacoco.exec} is retained as supplemental
 * evidence from the official JaCoCo runtime.
 */
public final class JacocoCoverageLoader {

    private JacocoCoverageLoader() {
    }

    public static JacocoCounters load(Path jacocoXml, Path repoRoot) throws Exception {
        if (Files.exists(jacocoXml)) {
            return JacocoXmlParser.parse(jacocoXml);
        }
        Path execFile = repoRoot.resolve("sample_subject/target/jacoco.exec");
        Path classesDir = repoRoot.resolve("sample_subject/target/classes");
        if (Files.exists(execFile) && Files.isDirectory(classesDir)) {
            return OfficialJacocoAnalyzer.fromExec(execFile, classesDir);
        }
        throw new IOException("Missing JaCoCo artifacts: " + jacocoXml);
    }
}
