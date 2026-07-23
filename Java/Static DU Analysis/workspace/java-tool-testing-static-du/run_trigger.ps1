$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
mvn -q -pl static-du-platform exec:java -Dexec.mainClass=com.testable.training.platform.StaticDuTrigger @args
