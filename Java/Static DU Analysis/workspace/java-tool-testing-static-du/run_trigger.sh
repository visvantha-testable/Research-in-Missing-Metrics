#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mvn -q -pl static-du-platform exec:java -Dexec.mainClass=com.testable.training.platform.StaticDuTrigger "$@"
