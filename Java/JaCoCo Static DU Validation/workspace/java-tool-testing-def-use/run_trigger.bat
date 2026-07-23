@echo off
cd /d "%~dp0"
mvn -q -pl def-use-platform exec:java -Dexec.mainClass=com.testable.training.defuse.DefUseTrigger %*
