@echo off
echo ============================================================
echo   WHALE TRACKER - DEPLOY FIXES + REFRESH
echo   One-click pipeline: Backfill - Sweep - Consensus - Verify
echo ============================================================
echo.

set PYTHONUTF8=1
cd /d C:\Users\USER\clawd\mirofish-hub

:: Step 1: Backup database
echo [1/6] Backing up database...
if not exist "data\backups" mkdir data\backups
copy /Y data\whale_hunter.db "data\backups\whale_hunter_%date:~-4,4%%date:~-7,2%%date:~-10,2%.db" >nul 2>&1
echo       Done.
echo.

:: Step 2: Backfill missing end_dates
echo [2/6] Backfilling missing end_dates from Polymarket API...
echo       (This may take 10-30 minutes for first run, seconds after that)
python backfill_end_dates.py --stats
echo.

:: Step 3: Kill any existing API server and restart
echo [3/6] Starting whale API server on port 8081...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8081.*LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)
start /B python whale_api.py
timeout /t 3 /nobreak >nul
curl -s http://localhost:8081/health
echo.
echo.

:: Step 4: Run consensus connector (fast mode)
echo [4/6] Running consensus connector (fast mode, top 15 picks)...
python consensus_swarm_connector.py --fast --top 15 --no-alerts
echo.

:: Step 5: Check consensus results
echo [5/6] Checking consensus pick results...
python consensus_results_tracker.py --summary 2>nul
echo.

:: Step 6: Print verification stats
echo [6/6] Verification stats:
echo.
python -c "import sqlite3; conn = sqlite3.connect('data/whale_hunter.db'); print('  Positions total:    ', conn.execute('SELECT COUNT(*) FROM whale_positions').fetchone()[0]); print('  With end_date:      ', conn.execute(\"SELECT COUNT(*) FROM whale_positions WHERE end_date IS NOT NULL AND end_date != ''\").fetchone()[0]); print('  Without end_date:   ', conn.execute(\"SELECT COUNT(*) FROM whale_positions WHERE end_date IS NULL OR end_date = ''\").fetchone()[0]); print('  Expired:            ', conn.execute(\"SELECT COUNT(*) FROM whale_positions WHERE outcome='expired'\").fetchone()[0]); print('  Pending:            ', conn.execute(\"SELECT COUNT(*) FROM whale_positions WHERE outcome='pending'\").fetchone()[0]); print('  Consensus picks:    ', conn.execute('SELECT COUNT(*) FROM consensus_picks').fetchone()[0]); print('  Won picks:          ', conn.execute(\"SELECT COUNT(*) FROM consensus_picks WHERE outcome='won'\").fetchone()[0]); print('  Lost picks:         ', conn.execute(\"SELECT COUNT(*) FROM consensus_picks WHERE outcome='lost'\").fetchone()[0])"
echo.
echo ============================================================
echo   DEPLOYMENT COMPLETE
echo   Dashboard: http://100.115.12.91:8081/
echo   Consensus: http://100.115.12.91:8081/whale-consensus.html
echo ============================================================
pause
