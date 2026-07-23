#!/usr/bin/env bash
set -euo pipefail
dotnet run --project src/NuGetAuditPlatform -- trigger "$@"
