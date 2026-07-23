@echo off
cd /d "%~dp0"
mvn -q -pl static-du-platform exec:java -Dexec.mainClass=com.testable.training.platform.StaticDuTrigger %*
