@echo off
cd /d C:\Users\USER\clawd\mirofish-hub
set PYTHONUTF8=1
python agents/validate_picks.py --top 3 >> validation.log 2>&1
