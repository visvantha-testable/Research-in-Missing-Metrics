#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mvn -q -pl def-use-platform exec:java -Dexec.mainClass=com.testable.training.defuse.DefUseTrigger "$@"
