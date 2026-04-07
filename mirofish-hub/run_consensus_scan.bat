@echo off
REM Changed from --fast to --scan --top 10 to actually run MiroFish sims
REM Fixed 2026-03-25 - was causing low validation rate (1/60)
cd /d C:\Users\USER\clawd\mirofish-hub
set PYTHONUTF8=1
"C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe" consensus_swarm_connector.py --scan --top 10 >> logs\connector_%date:~-4,4%%date:~-10,2%%date:~-7,2%.log 2>&1
