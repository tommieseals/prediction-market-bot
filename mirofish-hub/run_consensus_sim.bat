@echo off
REM Run consensus swarm with MiroFish simulations
REM This processes top 15 picks and runs actual simulations
REM Runtime: ~30-45 min depending on GPU load

cd /d C:\Users\USER\clawd\mirofish-hub
set PYTHONUTF8=1
echo [%date% %time%] Starting consensus sim run >> logs\consensus_sim.log
"C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe" consensus_swarm_connector.py --scan --top 15 >> logs\connector_%date:~-4,4%%date:~-10,2%%date:~-7,2%.log 2>&1
echo [%date% %time%] Finished consensus sim run >> logs\consensus_sim.log
