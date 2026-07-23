package com.testable.training.platform;

import java.nio.file.Path;
import java.nio.file.Paths;

public final class StaticDuJsonVerifierCli {

    public static void main(String[] args) throws Exception {
        Path repoRoot = locateRepoRoot();
        int status = StaticDuJsonVerifier.verify(repoRoot.resolve("static_du.json"));
        if (status != 0) {
            System.exit(status);
        }
    }

    private static Path locateRepoRoot() {
        Path current = Paths.get("").toAbsolutePath();
        while (current != null) {
            if (current.resolve("sample_subject").toFile().exists()
                    && current.resolve("static-du-platform").toFile().exists()) {
                return current;
            }
            current = current.getParent();
        }
        throw new IllegalStateException("Could not locate repository root");
    }
}
