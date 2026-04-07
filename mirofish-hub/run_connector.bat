@echo off
cd /d C:\Users\USER\clawd\mirofish-hub
set PYTHONUTF8=1
python consensus_swarm_connector.py --scan >> logs\connector_%date:~-4,4%%date:~-10,2%%date:~-7,2%.log 2>&1
