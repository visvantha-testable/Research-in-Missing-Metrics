#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mvn -q -pl jacoco-platform exec:java -Dexec.mainClass=com.testable.training.platform.JacocoTrigger "$@"
