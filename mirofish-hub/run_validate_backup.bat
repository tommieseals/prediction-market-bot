@echo off
cd /d C:\Users\USER\clawd\mirofish-hub
set PYTHONUTF8=1
python agents/validate_picks.py --top 2 >> validation_backup.log 2>&1
