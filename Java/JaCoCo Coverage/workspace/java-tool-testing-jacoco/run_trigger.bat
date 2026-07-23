@echo off
setlocal
cd /d "%~dp0"
call mvn -q -pl jacoco-platform exec:java -Dexec.mainClass=com.testable.training.platform.JacocoTrigger %*
exit /b %ERRORLEVEL%
