package com.testable.training.platform;

import java.nio.file.Path;
import java.nio.file.Paths;

public final class JacocoJsonVerifierCli {
    public static void main(String[] args) throws Exception {
        Path repoRoot = Paths.get("").toAbsolutePath();
        while (repoRoot != null && !repoRoot.resolve("jacoco.json").toFile().exists()) {
            repoRoot = repoRoot.getParent();
        }
        if (repoRoot == null) {
            throw new IllegalStateException("Could not locate jacoco.json");
        }
        System.exit(JacocoJsonVerifier.verify(repoRoot.resolve("jacoco.json")));
    }
}
