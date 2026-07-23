$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
mvn -q -pl jacoco-platform exec:java "-Dexec.mainClass=com.testable.training.platform.JacocoTrigger" @args
exit $LASTEXITCODE
