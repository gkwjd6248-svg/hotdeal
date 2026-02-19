@echo off
REM ============================================================
REM  DealHawk Local Scraper - Windows Scheduled Task Runner
REM  2시간마다 Windows 작업 스케줄러로 자동 실행
REM ============================================================

setlocal enabledelayedexpansion

REM --- Configuration ---
set SCRIPT_DIR=%~dp0
set LOG_DIR=%SCRIPT_DIR%logs
set PYTHON=python
set LOG_RETENTION_DAYS=7

REM --- Load .env file if present ---
if exist "%SCRIPT_DIR%.env" (
    for /f "usebackq tokens=1,2 delims==" %%a in ("%SCRIPT_DIR%.env") do (
        REM Skip comments
        set "line=%%a"
        if not "!line:~0,1!"=="#" (
            set "%%a=%%b"
        )
    )
)

REM --- Validate API key ---
if "%INGEST_API_KEY%"=="" (
    echo [ERROR] INGEST_API_KEY is not set.
    echo         Set it in %SCRIPT_DIR%.env or as an environment variable.
    exit /b 1
)

REM --- Create log directory ---
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM --- Generate log filename with timestamp ---
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set DATESTAMP=%%c-%%a-%%b
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIMESTAMP=%%a%%b
set LOG_FILE=%LOG_DIR%\scraper_%DATESTAMP%_%TIMESTAMP%.log

REM --- Run the scraper ---
echo [%date% %time%] Starting DealHawk scraper... >> "%LOG_FILE%" 2>&1
echo ================================================ >> "%LOG_FILE%" 2>&1

cd /d "%SCRIPT_DIR%"
%PYTHON% local_scraper.py --api-key "%INGEST_API_KEY%" >> "%LOG_FILE%" 2>&1

set EXIT_CODE=%ERRORLEVEL%

echo ================================================ >> "%LOG_FILE%" 2>&1
echo [%date% %time%] Scraper finished with exit code: %EXIT_CODE% >> "%LOG_FILE%" 2>&1

REM --- Clean up old logs (older than LOG_RETENTION_DAYS days) ---
forfiles /p "%LOG_DIR%" /m "scraper_*.log" /d -%LOG_RETENTION_DAYS% /c "cmd /c del @path" 2>nul

exit /b %EXIT_CODE%
