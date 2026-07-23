package com.testable.training.defuse;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

public final class DefUseJsonVerifierCli {

    public static void main(String[] args) throws Exception {
        Path repoRoot = locateRepoRoot();
        int status = DefUseJsonVerifier.verify(repoRoot.resolve("def_use.json"));
        if (status != 0) {
            System.exit(status);
        }
    }

    private static Path locateRepoRoot() {
        Path current = Paths.get("").toAbsolutePath();
        while (current != null) {
            if (Files.exists(current.resolve("def-use-platform"))
                    && Files.exists(current.resolve("jacoco-platform"))
                    && Files.exists(current.resolve("static-du-platform"))) {
                return current;
            }
            current = current.getParent();
        }
        throw new IllegalStateException("Could not locate repository root");
    }
}
