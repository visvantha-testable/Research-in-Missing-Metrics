$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
mvn -q -pl def-use-platform exec:java -Dexec.mainClass=com.testable.training.defuse.DefUseTrigger @args
