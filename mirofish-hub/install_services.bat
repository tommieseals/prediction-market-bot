@echo off
REM ============================================================
REM WHALE TRACKER - Windows Service Installer
REM ============================================================
REM Uses NSSM (Non-Sucking Service Manager) to register services
REM that auto-start on boot and restart on crash.
REM
REM Prerequisites:
REM   1. Download nssm from https://nssm.cc/download
REM   2. Place nssm.exe in this directory or in PATH
REM   3. Run this script as Administrator
REM ============================================================

echo.
echo ============================================================
echo  WHALE TRACKER - Service Installer
echo ============================================================
echo.

REM Check for admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] Must run as Administrator!
    echo Right-click this file and select "Run as administrator"
    pause
    exit /b 1
)

REM Check for nssm
where nssm >nul 2>&1
if %errorlevel% neq 0 (
    if exist "%~dp0nssm.exe" (
        set NSSM=%~dp0nssm.exe
    ) else (
        echo [FAIL] nssm.exe not found!
        echo Download from https://nssm.cc/download
        echo Place nssm.exe in %~dp0
        pause
        exit /b 1
    )
) else (
    set NSSM=nssm
)

set PYTHON=C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe
set WORKDIR=%~dp0

echo Using Python: %PYTHON%
echo Working dir:  %WORKDIR%
echo.

REM --- Service 1: Whale API ---
echo Installing WhaleAPI service...
%NSSM% install WhaleAPI "%PYTHON%" "%WORKDIR%whale_api.py"
%NSSM% set WhaleAPI AppDirectory "%WORKDIR%"
%NSSM% set WhaleAPI AppEnvironmentExtra PYTHONUTF8=1
%NSSM% set WhaleAPI DisplayName "Whale Tracker API"
%NSSM% set WhaleAPI Description "Serves whale tracker dashboard and API on port 8081"
%NSSM% set WhaleAPI Start SERVICE_AUTO_START
%NSSM% set WhaleAPI AppStdout "%WORKDIR%logs\whale_api.log"
%NSSM% set WhaleAPI AppStderr "%WORKDIR%logs\whale_api.log"
%NSSM% set WhaleAPI AppRotateFiles 1
%NSSM% set WhaleAPI AppRotateBytes 10485760
echo [OK] WhaleAPI service installed
echo.

REM --- Service 2: Watchdog ---
echo Installing Watchdog service...
%NSSM% install WhaleWatchdog "%PYTHON%" "%WORKDIR%watchdog.py"
%NSSM% set WhaleWatchdog AppDirectory "%WORKDIR%"
%NSSM% set WhaleWatchdog AppEnvironmentExtra PYTHONUTF8=1
%NSSM% set WhaleWatchdog DisplayName "Whale Tracker Watchdog"
%NSSM% set WhaleWatchdog Description "Monitors all components, auto-restarts, sends alerts"
%NSSM% set WhaleWatchdog Start SERVICE_AUTO_START
%NSSM% set WhaleWatchdog AppStdout "%WORKDIR%logs\watchdog.log"
%NSSM% set WhaleWatchdog AppStderr "%WORKDIR%logs\watchdog.log"
%NSSM% set WhaleWatchdog AppRotateFiles 1
%NSSM% set WhaleWatchdog AppRotateBytes 10485760
echo [OK] Watchdog service installed
echo.

REM Create logs directory
if not exist "%WORKDIR%logs" mkdir "%WORKDIR%logs"

REM --- Start services ---
echo Starting services...
%NSSM% start WhaleAPI
%NSSM% start WhaleWatchdog
echo.

echo ============================================================
echo  INSTALLATION COMPLETE
echo ============================================================
echo.
echo Services installed:
echo   WhaleAPI     - Dashboard + API (port 8081)
echo   WhaleWatchdog - Health monitor + auto-restart
echo.
echo Both services will:
echo   - Auto-start on Windows boot
echo   - Auto-restart on crash
echo   - Log to %WORKDIR%logs\
echo.
echo To manage services:
echo   nssm status WhaleAPI
echo   nssm restart WhaleAPI
echo   nssm stop WhaleAPI
echo   nssm remove WhaleAPI confirm
echo.
pause
